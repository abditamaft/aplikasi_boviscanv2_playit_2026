import time

import cv2
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QPushButton

import config
from ui import styles

STATUS_COLORS = {"none": "#334155", "ok": "#15803d", "pmk": "#b91c1c", "lsd": "#b91c1c", "both": "#991b1b"}


class CVWorker(QThread):
    frame_ready = Signal(QImage)
    status = Signal(str, str, float)   # kode, teks, fps
    message = Signal(str)

    def __init__(self, detector_factory):
        super().__init__()
        self._factory = detector_factory
        self._run = True

    def stop(self):
        self._run = False
        self.wait(5000)

    def run(self):
        from core.camera import Camera
        from core import detector as D
        try:
            self.message.emit("Memuat model…")
            det = self._factory()
            self.message.emit("Membuka kamera…")
            cam = Camera()
        except Exception as e:  # noqa: BLE001
            self.message.emit(f"Gagal: {e}")
            return
        self.message.emit("")
        fps, n, t_fps, dets = 0.0, 0, time.time(), []
        try:
            while self._run:
                frame = cam.read()
                if frame is None:
                    self.msleep(30)
                    continue
                n += 1
                if n % config.INFER_EVERY_N_FRAMES == 0:
                    dets = det.detect(frame)
                D.draw(frame, dets)
                code, text = D.summarize(dets)
                el = time.time() - t_fps
                if el >= 1.0:
                    fps, t_fps, n = n / el, time.time(), 0
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, _ = rgb.shape
                img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
                self.frame_ready.emit(img)
                self.status.emit(code, text, fps)
        finally:
            cam.release()


class CameraPage(QWidget):
    open_physio = Signal()

    def __init__(self, hub=None):
        super().__init__()
        self.setObjectName("root")
        self.worker = None
        self.video = QLabel(self); self.video.setAlignment(Qt.AlignCenter)
        self.video.setStyleSheet("background:#000;")
        self.info = QLabel("", self); self.info.setAlignment(Qt.AlignCenter)
        self.info.setStyleSheet("font-size:20px; color:#cbd5f0; background:transparent;")
        self.chip = QLabel("BoviScan • Computer Vision", self)
        self.chip.setStyleSheet("background:rgba(11,18,32,190); border-radius:10px; padding:5px 12px; font-size:13px;")
        self.menu_btn = QPushButton("Fisiologis  ›", self); self.menu_btn.setObjectName("overlay")
        self.menu_btn.clicked.connect(self.open_physio)
        self.bar = QLabel("Arahkan kamera ke sapi", self); self.bar.setAlignment(Qt.AlignCenter)
        self.fps = QLabel("", self)
        self.fps.setStyleSheet("background:rgba(11,18,32,190); border-radius:8px; padding:2px 8px; font-size:12px;")
        self._set_bar("none", "Arahkan kamera ke sapi")

    # ---- siklus hidup
    def activate(self):
        if self.worker:
            return
        from core.detector import NcnnDetector
        self.worker = CVWorker(NcnnDetector)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.status.connect(self._on_status)
        self.worker.message.connect(self._on_msg)
        self.worker.start()

    def deactivate(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.video.clear()

    # ---- slot
    def _on_frame(self, img):
        pm = QPixmap.fromImage(img).scaled(self.video.size(), Qt.KeepAspectRatioByExpanding,
                                            Qt.SmoothTransformation)
        self.video.setPixmap(pm)

    def _on_status(self, code, text, fps):
        self._set_bar(code, text)
        self.fps.setText(f"{fps:.1f} FPS"); self.fps.adjustSize()
        self._layout()

    def _on_msg(self, m):
        self.info.setText(m); self.info.setVisible(bool(m))

    def _set_bar(self, code, text):
        self.bar.setText(text)
        self.bar.setStyleSheet(f"background:{STATUS_COLORS.get(code, '#334155')}; color:white; "
                               "font-size:22px; font-weight:700; border-radius:0px;")

    # ---- tata letak overlay
    def resizeEvent(self, e):
        self._layout()

    def _layout(self):
        w, h = self.width(), self.height()
        self.video.setGeometry(0, 0, w, h)
        self.info.setGeometry(0, h // 2 - 30, w, 60)
        self.chip.adjustSize(); self.chip.move(10, 10)
        self.menu_btn.adjustSize(); self.menu_btn.move(w - self.menu_btn.width() - 10, 10)
        self.bar.setGeometry(0, h - 56, w, 56)
        self.fps.move(10, h - 56 - self.fps.height() - 6)
        for wdg in (self.info, self.chip, self.menu_btn, self.bar, self.fps):
            wdg.raise_()
