import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import config
from core import sensors as S, detector as D

def test_measure_sim():
    config.FINAL_WINDOW_S = 1.5
    hub = S.SensorHub(simulate=True, scenario="ngorok")
    ticks = []
    r = S.measure(hub.make("temp"), 4, lambda t, v, ok, aux: ticks.append(t), lambda: False)
    assert r.valid and 39.5 < r.value < 41.5, r
    assert ticks and max(ticks) < 4
    r = S.measure(hub.make("hr"), 0.5, lambda *a: None, lambda: False)   # terlalu singkat -> gagal
    assert not r.valid

def test_measure_spo2_sim():
    config.FINAL_WINDOW_S = 1.5
    hub = S.SensorHub(simulate=True, scenario="ngorok")
    r = S.measure(hub.make("hr"), 4, lambda *a: None, lambda: False)
    assert r.valid and r.aux is not None and 84 < r.aux < 90, r

def test_measure_cancel():
    hub = S.SensorHub(simulate=True)
    r = S.measure(hub.make("hr"), 5, lambda *a: None, lambda: True)
    assert not r.valid and r.message == "Dibatalkan"

def test_sound_index():
    fs = config.AUDIO_RATE; t = np.arange(fs * 2) / fs
    rng = np.random.default_rng(0)
    calm = 0.05 * np.sin(2*np.pi*120*t) + 0.005 * rng.standard_normal(len(t))      # dominan rendah
    snore = 0.05 * np.sin(2*np.pi*450*t) + 0.005 * rng.standard_normal(len(t))     # dominan 450 Hz
    _, r1, d1 = S.sound_features(calm, fs); _, r2, d2 = S.sound_features(snore, fs)
    i1, i2 = S.ratio_to_index(r1), S.ratio_to_index(r2)
    print("calm", r1, d1, i1, "| snore", r2, d2, i2)
    assert i1 < 20 and i2 > 90 and abs(d2 - 450) < 10

def test_bpm():
    m = S.MAX30102(); fs = m.FS; t = np.arange(fs * 8) / fs
    for bpm in (60, 75, 110):
        sig = 60000 + 800 * np.sin(2*np.pi*bpm/60*t) + 60 * np.random.default_rng(1).standard_normal(len(t))
        m.ir = list(sig); m.red = list(sig * 0.9); v, ok = m._estimate()[:2]
        print(bpm, "->", v, ok); assert ok and abs(v - bpm) < 4
    m.ir = [1000.0] * (fs * 8)
    m.red = [1000.0] * (fs * 8)
    assert m._estimate()[1] is False                    # tidak menempel

def test_spo2_estimate():
    """Sintesis PPG merah/IR dengan R tertentu -> SpO2 sesuai kurva (rasio-dari-rasio)."""
    m = S.MAX30102(); fs = m.FS; t = np.arange(fs * 8) / fs; rng = np.random.default_rng(2)
    a, b, c = config.SPO2_POLY
    for R in (0.5, 0.8, 1.2):
        pulse = np.sin(2*np.pi*1.2*t)
        ir = 60000 + 1200 * pulse + 40 * rng.standard_normal(len(t))
        red = 50000 + 1200 * R * (50000/60000) * pulse + 40 * rng.standard_normal(len(t))
        m.ir, m.red = list(ir), list(red)
        bpm, ok, spo2 = m._estimate()
        want = a*R*R + b*R + c
        print("R", R, "->", spo2, "(target", round(want, 1), ")", bpm)
        assert ok and abs(spo2 - want) < 1.5 and abs(bpm - 72) < 3
    m.red = [100.0] * (fs * 8)                   # kanal merah hampir nol -> SpO2 tidak valid
    assert m._estimate()[1] is False

def test_decode():
    nc = 6; pred = np.zeros((4 + nc, 8400), dtype=np.float32)
    # frame 1280x720 -> r=0.5, letterbox pad y=(640-360)/2=140
    pred[:4, 10] = [320, 320, 100, 80]; pred[4 + 2, 10] = 0.9      # Mulut PMK
    pred[:4, 11] = [322, 322, 100, 80]; pred[4 + 2, 11] = 0.7      # duplikat -> NMS
    pred[:4, 50] = [100, 200, 40, 40];  pred[4 + 1, 50] = 0.1      # di bawah ambang
    det = D.NcnnDetector.decode(object.__new__(D.NcnnDetector), pred, 0.5, 0, 140, (720, 1280))
    assert len(det) == 1 and det[0].cls == 2 and det[0].disease == "PMK"
    x1, y1, x2, y2 = det[0].box
    assert (x1, x2) == (540, 740) and (y1, y2) == (280, 440), det[0].box
    assert D.summarize(det)[0] == "pmk" and D.summarize([])[0] == "none"

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
