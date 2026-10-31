"""Driver & simulasi sensor BoviScan.

Setiap sensor punya antarmuka sama:
    start() -> mulai membaca      stop() -> berhenti & lepas sumber daya
    poll()  -> None            : belum ada estimasi baru
               (nilai, valid)  : estimasi baru; valid=False bila sensor tidak menempel/tidak mengarah
               (nilai, valid, aux) : sama + nilai kedua (SpO2 dari MAX30102)
measure() menjalankan sensor selama N detik lalu menghasilkan nilai akhir
(median sampel VALID pada FINAL_WINDOW_S detik terakhir).
"""
from __future__ import annotations
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

import config

# ============================================================== hasil pengukuran
@dataclass
class MeasureResult:
    value: Optional[float]
    valid: bool
    n_valid: int
    message: str = ""
    extra: dict = field(default_factory=dict)
    aux: Optional[float] = None      # nilai kedua dari sensor yg sama (SpO2 dari MAX30102)


def measure(sensor, duration: float, tick: Callable[[float, Optional[float], bool, Optional[float]], None],
            should_stop: Callable[[], bool]) -> MeasureResult:
    """Baca `sensor` selama `duration` detik. tick(elapsed, nilai_live, valid) dipanggil tiap iterasi."""
    samples: list[tuple[float, float]] = []
    aux_samples: list[tuple[float, float]] = []
    sensor.start()
    t0 = time.monotonic()
    try:
        while True:
            elapsed = time.monotonic() - t0
            if should_stop():
                return MeasureResult(None, False, 0, "Dibatalkan")
            if elapsed >= duration:
                break
            r = sensor.poll()
            if r is not None:
                v, ok, *rest = r
                aux = rest[0] if rest else None
                if ok:
                    samples.append((elapsed, v))
                    if aux is not None:
                        aux_samples.append((elapsed, aux))
                tick(elapsed, v, ok, aux)
            else:
                tick(elapsed, None, True, None)
            time.sleep(sensor.interval)
    finally:
        sensor.stop()
    tail = [v for t, v in samples if t >= duration - config.FINAL_WINDOW_S]
    if len(tail) < sensor.min_valid:
        return MeasureResult(None, False, len(tail), sensor.fail_message)
    aux_tail = [v for t, v in aux_samples if t >= duration - config.FINAL_WINDOW_S]
    if aux_samples and not aux_tail:       # ada SpO2 selama pengukuran tetapi tidak valid di jendela akhir
        return MeasureResult(None, False, len(tail), sensor.fail_message)
    aux_val = float(statistics.median(aux_tail)) if aux_tail else None
    return MeasureResult(float(statistics.median(tail)), True, len(tail), "OK", aux=aux_val,
                         extra={"all": [v for _, v in samples]})


# ============================================================== I2C helper
def _open_bus():
    from smbus2 import SMBus
    return SMBus(config.I2C_BUS)


# ============================================================== MLX90614
class MLX90614:
    name = "MLX90614"
    interval = 0.2
    min_valid = config.MIN_VALID_SAMPLES
    fail_message = "Sinyal suhu tidak valid. Arahkan sensor IR ke titik bidik (mata/pangkal telinga) dan coba lagi."

    def __init__(self):
        self.bus = None

    def start(self):
        self.bus = _open_bus()

    def stop(self):
        if self.bus:
            self.bus.close()
            self.bus = None

    def _read(self, reg):
        for _ in range(3):
            try:
                raw = self.bus.read_word_data(config.MLX_ADDR, reg)
                return raw * 0.02 - 273.15
            except OSError:
                time.sleep(0.01)
        raise OSError("MLX90614 tidak merespons")

    def poll(self):
        try:
            t = self._read(0x07)          # T_object1
        except OSError:
            return (0.0, False)
        lo, hi = config.IR_VALID_RANGE
        return (round(t, 2), lo <= t <= hi)


# ============================================================== SHT31
class SHT31:
    name = "SHT31"

    def __init__(self):
        self.bus = None

    def open(self):
        self.bus = _open_bus()

    def close(self):
        if self.bus:
            self.bus.close()
            self.bus = None

    def read(self) -> Optional[tuple[float, float]]:
        from smbus2 import i2c_msg
        try:
            self.bus.i2c_rdwr(i2c_msg.write(config.SHT_ADDR, [0x24, 0x00]))   # single shot, high rep.
            time.sleep(0.02)
            rd = i2c_msg.read(config.SHT_ADDR, 6)
            self.bus.i2c_rdwr(rd)
            b = list(rd)
        except OSError:
            return None
        t = -45 + 175 * ((b[0] << 8) | b[1]) / 65535.0
        h = 100 * ((b[3] << 8) | b[4]) / 65535.0
        return round(t, 2), round(h, 1)


# ============================================================== MAX30102
class MAX30102:
    name = "MAX30102"
    interval = 0.1
    min_valid = 2
    fail_message = "Detak jantung tidak terbaca. Tempelkan sensor ke kulit tipis (pangkal ekor / bagian dalam telinga) dan coba lagi."
    FS = 100  # Hz

    def __init__(self):
        self.bus = None
        self.ir: list[float] = []
        self.red: list[float] = []
        self._last_calc = 0.0

    def _w(self, reg, val):
        self.bus.write_byte_data(config.MAX_ADDR, reg, val)

    def start(self):
        self.bus = _open_bus()
        self._w(0x09, 0x40)           # reset
        time.sleep(0.1)
        self._w(0x08, 0x1F)           # no averaging, rollover, almost-full 15
        self._w(0x09, 0x03)           # mode SpO2 (red + IR)
        self._w(0x0A, 0x27)           # ADC 4096nA, 100 sps, pulse 411us
        self._w(0x0C, 0x3F)           # LED merah
        self._w(0x0D, 0x3F)           # LED IR
        self._w(0x04, 0); self._w(0x05, 0); self._w(0x06, 0)   # kosongkan FIFO
        self.ir, self.red = [], []
        self._last_calc = time.monotonic()

    def stop(self):
        if self.bus:
            try:
                self._w(0x09, 0x80)   # shutdown
            except OSError:
                pass
            self.bus.close()
            self.bus = None

    def _drain(self):
        wr = self.bus.read_byte_data(config.MAX_ADDR, 0x04)
        rd = self.bus.read_byte_data(config.MAX_ADDR, 0x06)
        n = (wr - rd) & 0x1F
        while n > 0:
            k = min(n, 5)
            d = self.bus.read_i2c_block_data(config.MAX_ADDR, 0x07, 6 * k)
            for i in range(k):
                red = ((d[6*i] << 16) | (d[6*i+1] << 8) | d[6*i+2]) & 0x3FFFF
                ir = ((d[6*i+3] << 16) | (d[6*i+4] << 8) | d[6*i+5]) & 0x3FFFF
                self.red.append(float(red)); self.ir.append(float(ir))
            n -= k
        self.ir = self.ir[-self.FS * 12:]
        self.red = self.red[-self.FS * 12:]

    def poll(self):
        try:
            self._drain()
        except OSError:
            return None
        now = time.monotonic()
        if now - self._last_calc < 0.5:
            return None
        self._last_calc = now
        return self._estimate()

    def _estimate(self):
        from scipy.signal import find_peaks, butter, filtfilt
        n = self.FS * 6
        if len(self.ir) < self.FS * 3:
            return None
        x = np.array(self.ir[-n:])
        if x.mean() < config.MAX_MIN_IR_SIGNAL:       # tidak menempel
            return (0.0, False)
        raw_ir = x
        raw_red = np.array(self.red[-n:])
        bb, aa = butter(2, [0.5, 4.0], btype="band", fs=self.FS)   # 30-240 bpm
        h = self.FS // 2                                           # buang artefak tepi filter
        x = filtfilt(bb, aa, raw_ir - raw_ir.mean())[h:-h]
        xr = filtfilt(bb, aa, raw_red - raw_red.mean())[h:-h]
        x = -x if abs(x.min()) > abs(x.max()) else x
        peaks, _ = find_peaks(x, distance=int(self.FS * 0.3), prominence=x.std() * 0.5)
        if len(peaks) < 4:
            return (0.0, False)
        iv = np.diff(peaks) / self.FS
        iv = iv[(iv > 0.27) & (iv < 2.0)]
        if len(iv) < 3 or np.std(iv) / np.mean(iv) > 0.25:
            return (0.0, False)
        bpm = 60.0 / float(np.median(iv))
        lo, hi = config.HR_VALID_RANGE
        hr_ok = lo <= bpm <= hi
        spo2 = self._spo2(raw_ir, raw_red, x, xr)
        return (round(bpm, 1), hr_ok and spo2 is not None, spo2)

    @staticmethod
    def _spo2(raw_ir, raw_red, ac_ir, ac_red):
        """SpO2 dengan rasio-dari-rasio R = (AC_red/DC_red)/(AC_ir/DC_ir). None bila sinyal tidak layak."""
        dc_ir, dc_red = raw_ir.mean(), raw_red.mean()
        if dc_ir < config.MAX_MIN_IR_SIGNAL or dc_red < config.MAX_MIN_RED_SIGNAL:
            return None
        pi = np.std(ac_ir) / dc_ir * 100                   # indeks perfusi (%)
        if pi < config.SPO2_MIN_PERFUSION_INDEX:
            return None
        R = (np.std(ac_red) / dc_red) / (np.std(ac_ir) / dc_ir)
        if not (0.3 <= R <= 3.4):
            return None
        a, b, c = config.SPO2_POLY
        spo2 = a * R * R + b * R + c + config.SPO2_OFFSET
        return round(float(np.clip(spo2, 50.0, 100.0)), 1)


# ============================================================== INMP441 (mikrofon)
def sound_features(x: np.ndarray, fs: int) -> tuple[float, float, float]:
    """Return (rms_dbfs, rasio_energi_300_700, frekuensi_dominan_Hz)."""
    from scipy.signal import welch
    x = x - x.mean()
    rms = float(np.sqrt(np.mean(x ** 2)) + 1e-12)
    dbfs = 20 * math.log10(rms)
    f, p = welch(x, fs=fs, nperseg=min(8192, len(x)))
    tot = p[(f >= config.SOUND_TOTAL_BAND[0]) & (f <= config.SOUND_TOTAL_BAND[1])]
    band = p[(f >= config.SOUND_BAND[0]) & (f <= config.SOUND_BAND[1])]
    ratio = float(band.sum() / (tot.sum() + 1e-18))
    m = (f >= config.SOUND_TOTAL_BAND[0]) & (f <= config.SOUND_TOTAL_BAND[1])
    dom = float(f[m][np.argmax(p[m])])
    return dbfs, ratio, dom


def ratio_to_index(ratio: float) -> float:
    r0, r1 = config.SOUND_RATIO_NORMAL, config.SOUND_RATIO_ABNORMAL
    return float(np.clip((ratio - r0) / (r1 - r0), 0, 1) * 100)


class Microphone:
    name = "INMP441"
    interval = 0.1
    min_valid = 2
    fail_message = "Suara napas tidak terdeteksi. Dekatkan mikrofon ke hidung/leher sapi dan coba lagi."

    def __init__(self):
        self.stream = None
        self.buf = np.zeros(0, dtype=np.float32)
        self._last = 0.0
        self.last_dom = 0.0

    def start(self):
        import sounddevice as sd
        self.buf = np.zeros(0, dtype=np.float32)

        def cb(indata, frames, t, status):
            ch = indata[:, 0].astype(np.float32)
            if indata.dtype == np.int32:
                ch = ch / 2147483648.0
            elif indata.dtype == np.int16:
                ch = ch / 32768.0
            self.buf = np.concatenate([self.buf, ch])[-config.AUDIO_RATE * 4:]

        self.stream = sd.InputStream(device=config.AUDIO_DEVICE, samplerate=config.AUDIO_RATE,
                                     channels=config.AUDIO_CHANNELS, dtype="int32", callback=cb)
        self.stream.start()
        self._last = time.monotonic()

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def poll(self):
        now = time.monotonic()
        if now - self._last < 0.5:
            return None
        self._last = now
        win = self.buf[-config.AUDIO_RATE * 2:]
        if len(win) < config.AUDIO_RATE:
            return None
        dbfs, ratio, dom = sound_features(win, config.AUDIO_RATE)
        self.last_dom = dom
        if dbfs < config.AUDIO_MIN_RMS_DBFS:
            return (0.0, False)
        return (round(ratio_to_index(ratio), 1), True)


# ============================================================== SIMULASI (laptop / demo)
SCENARIOS = {  # suhu IR, detak, indeks suara, SpO2
    "sehat":       (38.6, 66, 8, 97.5),
    "terindikasi": (39.8, 92, 45, 93.5),
    "ngorok":      (40.6, 112, 82, 87.0),
}


class SimSensor:
    interval = 0.1
    min_valid = 2
    fail_message = "Simulasi gagal"

    def __init__(self, name, base, noise, period=0.4):
        self.name, self.base, self.noise, self.period = name, base, noise, period
        self._last = 0.0
        self._t0 = 0.0

    def start(self):
        self._last = self._t0 = time.monotonic()

    def stop(self):
        pass

    def poll(self):
        now = time.monotonic()
        if now - self._last < self.period:
            return None
        self._last = now
        warm = min(1.0, (now - self._t0) / 3.0)  # nilai "menyetel" ke target dalam 3 dtk
        v = self.base * warm + (self.base * 0.85) * (1 - warm) + random.gauss(0, self.noise)
        return (round(v, 2), True)


class SimHR(SimSensor):
    """Simulasi MAX30102: detak + SpO2."""

    def __init__(self, hr, spo2):
        super().__init__("MAX(sim)", hr, 1.2)
        self.spo2 = spo2

    def poll(self):
        r = super().poll()
        if r is None:
            return None
        return (r[0], True, round(min(100.0, self.spo2 + random.gauss(0, 0.4)), 1))


class SimSHT:
    name = "SHT31(sim)"

    def open(self): pass
    def close(self): pass

    def read(self):
        return (round(27.5 + random.gauss(0, 0.1), 2), round(68 + random.gauss(0, 0.5), 1))


# ============================================================== pabrik
class SensorHub:
    """Menyediakan sensor sesuai lingkungan. available=False -> mode desain saja (laptop)."""

    def __init__(self, simulate: bool = False, scenario: str = "terindikasi"):
        self.simulate = simulate
        self.scenario = scenario
        self.available = False
        self.reason = ""
        self.sht = None
        if simulate:
            self.available = True
            self.sht = SimSHT()
        elif config.IS_RASPI:
            try:
                import smbus2  # noqa: F401
                self.sht = SHT31()
                self.available = True
            except ImportError:
                self.reason = "Paket smbus2 belum terpasang"
        else:
            self.reason = "Mode laptop: sensor fisik tidak tersedia (hanya tampilan desain)"

    def make(self, kind: str):
        if self.simulate:
            t, h, s, o2 = SCENARIOS[self.scenario]
            return {"temp": SimSensor("MLX(sim)", t, 0.08),
                    "hr": SimHR(h, o2),
                    "sound": SimSensor("MIC(sim)", s, 3.0)}[kind]
        return {"temp": MLX90614, "hr": MAX30102, "sound": Microphone}[kind]()
