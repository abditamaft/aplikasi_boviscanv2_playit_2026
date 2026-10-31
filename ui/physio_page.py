from __future__ import annotations
import threading

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFrame)

import config
from core import fuzzy, history
from core.sensors import measure
from ui import styles
from ui.widgets import StepCard, RiskBar

STEPS = [
    ("temp", "Suhu Tubuh (Inframerah)", "Arahkan sensor IR MLX90614 ke mata atau pangkal telinga sapi, jarak ±2–5 cm, lalu tekan Mulai.", "°C"),
    ("hr", "Detak Jantung & SpO₂", "Tempelkan sensor MAX30102 ke pangkal ekor (kulit dicukur/tanpa pigmen), tahan diam. Detak dan SpO₂ dibaca bersamaan.", "bpm"),
    ("sound", "Suara Napas", "Dekatkan mikrofon ke lubang hidung / leher sapi tanpa menyentuh. Tahan stabil selama pengukuran.", ""),
]
CAT_COLOR = {"Sehat": styles.GREEN, "Terindikasi": styles.AMBER, "Ngorok": styles.RED}


class MeasureWorker(QThread):
    tick = Signal(float, object, bool, object)
    done = Signal(object)

    def __init__(self, sensor, duration):
        super().__init__()
        self.sensor, self.duration = sensor, duration
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            res = measure(self.sensor, self.duration,
                          lambda t, v, ok, aux: self.tick.emit(t, v, ok, aux), self._stop.is_set)
        except Exception as e:  # noqa: BLE001  (I2C/audio tidak ada, dll.)
            from core.sensors import MeasureResult
            res = MeasureResult(None, False, 0, f"Sensor error: {e}")
        self.done.emit(res)


class PhysioPage(QWidget):
    open_camera = Signal()
    request_exit = Signal()

    def __init__(self, hub):
        super().__init__()
        self.setObjectName("root")
        self.hub = hub
        self.values: dict[str, float | None] = {k: None for k, *_ in STEPS}
        self.raw_ir = None
        self.spo2 = None
        self.amb = None; self.rh = None
        self.worker = None
        self.active_idx = None
        self.last_result = None

        # ---------- header
        title = QLabel("Deteksi Fisiologis"); title.setObjectName("title")
        self.cam_btn = QPushButton("Kamera"); self.cam_btn.setObjectName("ghost")
        self.cam_btn.clicked.connect(self._to_camera)
        self.exit_btn = QPushButton("⏻"); self.exit_btn.setObjectName("ghost"); self.exit_btn.setFixedWidth(64)
        self.exit_btn.clicked.connect(self.request_exit)
        head = QHBoxLayout(); head.addWidget(title); head.addStretch()
        head.addWidget(self.cam_btn); head.addWidget(self.exit_btn)

        # ---------- SHT (realtime)
        self.sht_lbl = QLabel("Suhu ruang —   |   Kelembapan —"); self.sht_lbl.setObjectName("hint")
        live = QLabel("● LIVE  SHT31"); live.setStyleSheet(f"color:{styles.GREEN}; font-size:13px; font-weight:700;")
        sht = QFrame(); sht.setObjectName("card")
        sl = QHBoxLayout(sht); sl.setContentsMargins(14, 6, 14, 6)
        sl.addWidget(live); sl.addStretch(); sl.addWidget(self.sht_lbl)

        self.banner = QLabel(""); self.banner.setObjectName("banner"); self.banner.setWordWrap(True)
        self.banner.setVisible(False)

        # ---------- langkah
        self.cards: list[StepCard] = []
        steps_lay = QVBoxLayout(); steps_lay.setSpacing(8)
        for i, (key, ttl, ins, unit) in enumerate(STEPS):
            c = StepCard(i + 1, ttl, ins, unit, config.MEASURE_SECONDS)
            c.start_clicked.connect(lambda i=i: self._start(i))
            self.cards.append(c); steps_lay.addWidget(c)
        self.msg = QLabel(""); self.msg.setObjectName("muted"); self.msg.setWordWrap(True)

        measure_page = QWidget()
        ml = QVBoxLayout(measure_page); ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(8)
        ml.addWidget(sht); ml.addWidget(self.banner); ml.addLayout(steps_lay, 1); ml.addWidget(self.msg)

        self.result_page = self._build_result_page()
        self.stack = QStackedWidget(); self.stack.addWidget(measure_page); self.stack.addWidget(self.result_page)

        root = QVBoxLayout(self); root.setContentsMargins(14, 10, 14, 10); root.setSpacing(8)
        root.addLayout(head); root.addWidget(self.stack, 1)

        self.sht_timer = QTimer(self); self.sht_timer.setInterval(1000)
        self.sht_timer.timeout.connect(self._poll_sht)
        self._reset()

    # ================================================================ hasil
    def _build_result_page(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(8)
        self.res_label = QLabel(""); self.res_label.setAlignment(Qt.AlignCenter); self.res_label.setWordWrap(True)
        self.res_score = QLabel(""); self.res_score.setAlignment(Qt.AlignCenter); self.res_score.setObjectName("muted")
        self.risk = RiskBar()
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Variabel", "Nilai", "Derajat keanggotaan"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.disc = QLabel("Hasil ini skrining awal, bukan diagnosis. Konfirmasikan ke dokter hewan / uji laboratorium.")
        self.disc.setObjectName("muted"); self.disc.setWordWrap(True)
        self.save_btn = QPushButton("Simpan Riwayat"); self.save_btn.setObjectName("green")
        self.save_btn.clicked.connect(self._save)
        again = QPushButton("Periksa Ulang"); again.setObjectName("ghost"); again.clicked.connect(self._reset)
        cam = QPushButton("Kamera"); cam.setObjectName("ghost"); cam.clicked.connect(self._to_camera)
        row = QHBoxLayout(); row.addWidget(self.save_btn); row.addWidget(again); row.addWidget(cam)
        lay.addWidget(self.res_label); lay.addWidget(self.res_score); lay.addWidget(self.risk)
        lay.addWidget(self.table, 1); lay.addWidget(self.disc); lay.addLayout(row)
        return w

    def _show_result(self, r: fuzzy.FuzzyResult):
        self.last_result = r
        col = CAT_COLOR[r.category]
        self.res_label.setText(r.label)
        self.res_label.setStyleSheet(f"font-size:26px; font-weight:800; color:{col};")
        self.res_score.setText(f"Skor risiko ngorok: {r.score:.0f}%   •   "
                               + "  ".join(f"{k} {v:.2f}" for k, v in r.out_degrees.items()))
        self.risk.set_score(r.score)
        rows = [("Suhu tubuh (terkoreksi)", f"{r.inputs['suhu']:.1f} °C", r.memberships["suhu"]),
                ("Detak jantung", f"{r.inputs['detak']:.0f} bpm", r.memberships["detak"]),
                ("Saturasi oksigen SpO₂", f"{r.inputs['spo2']:.0f} %", r.memberships["spo2"]),
                ("Indeks suara abnormal", f"{r.inputs['suara']:.0f} / 100", r.memberships["suara"]),
                ("Suhu ruang (SHT31)", f"{r.inputs['ruang']:.1f} °C", r.memberships["ruang"])]
        self.table.setRowCount(len(rows))
        for i, (n, v, mu) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(n)); self.table.setItem(i, 1, QTableWidgetItem(v))
            self.table.setItem(i, 2, QTableWidgetItem("  ".join(f"{k}={x:.2f}" for k, x in mu.items() if x > 0.001)))
            self.table.setRowHeight(i, 34)
        self.save_btn.setEnabled(True); self.save_btn.setText("Simpan Riwayat")
        self.stack.setCurrentIndex(1)

    def _save(self):
        r = self.last_result
        path = history.save(self.raw_ir, r.inputs["suhu"], r.inputs["detak"], r.inputs["spo2"],
                            r.inputs["suara"], r.inputs["ruang"], self.rh or 0.0, r)
        self.save_btn.setText("Tersimpan ✓"); self.save_btn.setEnabled(False)

    # ================================================================ alur ukur
    def activate(self):
        if self.hub.available and self.hub.sht:
            try:
                self.hub.sht.open()
                self.sht_timer.start(); self._poll_sht()
            except Exception as e:  # noqa: BLE001
                self.sht_lbl.setText(f"SHT31 tidak terbaca ({e})")
        else:
            self.sht_lbl.setText("Suhu ruang —   |   Kelembapan —   (sensor tidak aktif)")
        if not self.hub.available:
            self.banner.setText("MODE LAPTOP — " + self.hub.reason + ". Jalankan dengan --sim untuk mencoba alur.")
            self.banner.setVisible(True)
        elif self.hub.simulate:
            self.banner.setText(f"MODE SIMULASI — data sensor palsu (skenario: {self.hub.scenario}).")
            self.banner.setVisible(True)

    def deactivate(self):
        self._cancel()
        self.sht_timer.stop()
        if self.hub.sht:
            try: self.hub.sht.close()
            except Exception: pass  # noqa: BLE001

    def _to_camera(self):
        self._cancel(); self.open_camera.emit()

    def _poll_sht(self):
        r = self.hub.sht.read() if self.hub.sht else None
        if r:
            self.amb, self.rh = r
            self.sht_lbl.setText(f"Suhu ruang  {r[0]:.1f} °C   |   Kelembapan  {r[1]:.0f} %")

    def _cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel(); self.worker.wait(3000)
        self.worker = None

    def _reset(self):
        self._cancel()
        self.values = {k: None for k, *_ in STEPS}
        self.raw_ir = None
        self.spo2 = None
        for i, c in enumerate(self.cards):
            c.set_state("ready" if i == 0 else "locked", "—")
        self.msg.setText("Tekan «Mulai Deteksi» pada langkah 1. Tiap sensor diukur bergantian selama "
                         f"{config.MEASURE_SECONDS} detik.")
        self.stack.setCurrentIndex(0)

    def _start(self, i):
        if self.worker and self.worker.isRunning():
            return
        if not self.hub.available:
            self.msg.setText("Sensor fisik tidak tersedia di perangkat ini (mode laptop). "
                             "Tampilan ini hanya untuk melihat desain menu.")
            return
        key = STEPS[i][0]
        for j, c in enumerate(self.cards):       # kunci kartu lain selama mengukur
            if j != i:
                c.btn.setEnabled(False)
        self.active_idx = i
        self.cards[i].set_state("running", "Mengukur…", config.MEASURE_SECONDS)
        self.msg.setText(STEPS[i][2])
        self.worker = MeasureWorker(self.hub.make(key), config.MEASURE_SECONDS)
        self.worker.tick.connect(self._on_tick)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _fmt(self, key, v, aux=None):
        if key == "hr":
            return f"{v:.0f} bpm" + (f"  •  SpO₂ {aux:.0f}%" if aux is not None else "")
        if key == "sound":
            return f"{v:.0f} / 100"
        return f"{v:.1f} " + ("°C" if key == "temp" else "bpm")

    def _on_tick(self, elapsed, value, ok, aux):
        i = self.active_idx; key = STEPS[i][0]
        txt = "Belum ada sinyal valid…" if value is None else (self._fmt(key, value, aux) if ok else "Sinyal tidak valid")
        self.cards[i].set_state("running", txt, config.MEASURE_SECONDS - elapsed)

    def _on_done(self, res):
        i = self.active_idx; key = STEPS[i][0]
        self.worker = None
        if res.valid:
            self.values[key] = res.value
            if key == "temp":
                self.raw_ir = res.value
            if key == "hr":
                self.spo2 = res.aux
            self.cards[i].set_state("done", self._fmt(key, res.value, res.aux))
            self.msg.setText(f"Langkah {i + 1} selesai ({res.n_valid} sampel valid).")
        else:
            self.values[key] = None
            self.cards[i].set_state("failed", "Gagal")
            self.msg.setText(res.message)
        # buka kunci kartu: langkah selesai tetap bisa diulang, langkah berikutnya siap jika yang ini lengkap
        for j, c in enumerate(self.cards):
            have = self.values[STEPS[j][0]] is not None
            prev_ok = j == 0 or self.values[STEPS[j - 1][0]] is not None
            if have:
                c.set_state("done", c.value.text())
            elif prev_ok:
                c.set_state("failed" if j == i and not res.valid else "ready", c.value.text() if j == i else "—")
            else:
                c.set_state("locked", "—")
        if all(v is not None for v in self.values.values()):
            QTimer.singleShot(900, self._compute)

    def _compute(self):
        amb = self.amb if self.amb is not None else 27.0   # cadangan bila SHT gagal baca
        temp = fuzzy.correct_body_temp(self.values["temp"], amb, config.IR_OFFSET_C,
                                       config.IR_AMBIENT_COEF, config.IR_AMBIENT_REF)
        spo2 = self.spo2 if self.spo2 is not None else 98.0   # cadangan bila SpO2 tak tersedia (mis. sim lama)
        r = fuzzy.evaluate(temp, self.values["hr"], self.values["sound"], amb, spo2)
        self._show_result(r)
