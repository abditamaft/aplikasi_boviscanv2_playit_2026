"""Logika fuzzy Mamdani untuk skrining risiko ngorok (SE) pada sapi.

Input  : suhu tubuh (°C, hasil IR terkoreksi), detak jantung (bpm), SpO2 (%),
         indeks suara napas abnormal (0-100), suhu ruang (°C).
Output : skor risiko 0-100 -> Sehat / Terindikasi ngorok / Ngorok.

Murni numpy, tanpa scikit-fuzzy, supaya ringan di Raspberry Pi.
Dasar ambang (lihat README untuk rujukan):
  * Suhu normal sapi 38.0-39.3 °C; demam >= 39.5 °C; akut SE 40-41 °C (MSD Vet Manual).
  * Detak jantung normal sapi dewasa 48-84 bpm.
  * SpO2 normal 95-99 %, hipoksemia < 90 %, < 85 % = perjalanan penyakit ireversibel (Coghe 1998).
  * Suara: band 300-700 Hz = wheeze/crackle (normal 71-371 Hz, wheeze 322-535 Hz pada kerbau).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

# ------------------------------------------------------------ fungsi keanggotaan
def trap(x, a, b, c, d):
    """Trapesium (a,b,c,d). Bahu kiri jika a==b, bahu kanan jika c==d."""
    x = np.asarray(x, dtype=float)
    left = np.ones_like(x) if b == a else np.clip((x - a) / (b - a), 0, 1)
    right = np.ones_like(x) if d == c else np.clip((d - x) / (d - c), 0, 1)
    return np.minimum(left, right)

def tri(x, a, b, c):
    return trap(x, a, b, b, c)

# ------------------------------------------------------------ himpunan fuzzy
TEMP_SETS = {      # suhu tubuh (°C)
    "Normal":       lambda x: trap(x, 0, 0, 39.0, 39.7),
    "Demam":        lambda x: tri(x, 39.3, 40.0, 40.7),
    "SangatTinggi": lambda x: trap(x, 40.3, 40.9, 50, 50),
}
HR_SETS = {        # detak jantung (bpm)
    "Normal":       lambda x: trap(x, 0, 0, 84, 92),
    "Tinggi":       lambda x: tri(x, 84, 102, 120),
    "SangatTinggi": lambda x: trap(x, 108, 125, 300, 300),
}
SOUND_SETS = {     # indeks suara abnormal 0-100
    "Normal":       lambda x: trap(x, 0, 0, 20, 40),
    "Ringan":       lambda x: tri(x, 25, 45, 65),
    "Kuat":         lambda x: trap(x, 50, 70, 100, 100),
}
SPO2_SETS = {      # saturasi oksigen (%) - nilai RENDAH = buruk
    "Normal":       lambda x: trap(x, 93, 95, 100, 100),
    "Rendah":       lambda x: tri(x, 87, 91, 95),         # hipoksemia ringan-sedang
    "Berat":        lambda x: trap(x, 0, 0, 85, 90),      # hipoksemia berat
}
AMB_SETS = {       # suhu ruang (°C)
    "Nyaman":       lambda x: trap(x, 0, 0, 30, 33),
    "Panas":        lambda x: trap(x, 30, 34, 60, 60),
}
OUT_X = np.linspace(0, 100, 501)
OUT_SETS = {
    "Sehat":        lambda x: trap(x, 0, 0, 25, 45),
    "Terindikasi":  lambda x: tri(x, 30, 50, 70),
    "Ngorok":       lambda x: trap(x, 55, 75, 100, 100),
}
LABELS = {
    "Sehat": "SAPI SEHAT",
    "Terindikasi": "SAPI TERINDIKASI NGOROK",
    "Ngorok": "SAPI TERKENA PENYAKIT NGOROK (RISIKO TINGGI)",
}

# ------------------------------------------------------------ basis aturan (27 + 1 aturan ambient)
# (suhu, detak, suara) -> (keluaran, bobot aturan)
_S, _T, _N = "Sehat", "Terindikasi", "Ngorok"
RULES: dict[tuple[str, str, str], tuple[str, float]] = {
    ("Normal", "Normal", "Normal"): (_S, 1.0),
    ("Normal", "Normal", "Ringan"): (_T, 0.7),
    ("Normal", "Normal", "Kuat"):   (_T, 0.9),
    ("Normal", "Tinggi", "Normal"): (_S, 0.7),    # takikardia saja = stres penanganan
    ("Normal", "Tinggi", "Ringan"): (_T, 0.8),
    ("Normal", "Tinggi", "Kuat"):   (_T, 1.0),
    ("Normal", "SangatTinggi", "Normal"): (_T, 0.6),
    ("Normal", "SangatTinggi", "Ringan"): (_T, 0.9),
    ("Normal", "SangatTinggi", "Kuat"):   (_N, 0.7),
    ("Demam", "Normal", "Normal"):  (_T, 0.8),
    ("Demam", "Normal", "Ringan"):  (_T, 1.0),
    ("Demam", "Normal", "Kuat"):    (_N, 0.8),
    ("Demam", "Tinggi", "Normal"):  (_T, 1.0),
    ("Demam", "Tinggi", "Ringan"):  (_N, 0.8),
    ("Demam", "Tinggi", "Kuat"):    (_N, 1.0),
    ("Demam", "SangatTinggi", "Normal"): (_N, 0.7),
    ("Demam", "SangatTinggi", "Ringan"): (_N, 1.0),
    ("Demam", "SangatTinggi", "Kuat"):   (_N, 1.0),
    ("SangatTinggi", "Normal", "Normal"): (_T, 0.9),
    ("SangatTinggi", "Normal", "Ringan"): (_N, 0.8),
    ("SangatTinggi", "Normal", "Kuat"):   (_N, 1.0),
    ("SangatTinggi", "Tinggi", "Normal"): (_T, 1.0),
    ("SangatTinggi", "Tinggi", "Ringan"): (_N, 1.0),
    ("SangatTinggi", "Tinggi", "Kuat"):   (_N, 1.0),
    ("SangatTinggi", "SangatTinggi", "Normal"): (_N, 0.8),
    ("SangatTinggi", "SangatTinggi", "Ringan"): (_N, 1.0),
    ("SangatTinggi", "SangatTinggi", "Kuat"):   (_N, 1.0),
}

# SpO2 memperluas 27 aturan menjadi 81: SpO2 rendah menaikkan tingkat keluaran 1 tingkat, SpO2 berat 2 tingkat
# (maks. Ngorok). Bobot diturunkan karena SpO2 sensor optik pada kulit sapi rawan artefak.
_LEVELS = [_S, _T, _N]
_ESC = {"Normal": (0, 1.0), "Rendah": (1, 0.85), "Berat": (2, 0.9)}
for (_t, _h, _s), (_out, _w) in list(RULES.items()):
    del RULES[(_t, _h, _s)]
    for _o2, (_up, _f) in _ESC.items():
        _lvl = _LEVELS.index(_out)
        if _lvl == 0 and _o2 != "Normal":       # semua lain normal, hanya SpO2 turun -> curigai artefak, cukup 'Terindikasi'
            RULES[(_t, _h, _s, _o2)] = (_T, 0.5 if _o2 == "Rendah" else 0.7)
        else:
            RULES[(_t, _h, _s, _o2)] = (_LEVELS[min(2, _lvl + _up)], _w * _f)
HEAT_RULE_WEIGHT = 0.4  # ruang panas + demam ringan + HR & suara normal -> mungkin cekaman panas


@dataclass
class FuzzyResult:
    inputs: dict
    memberships: dict          # derajat keanggotaan tiap variabel
    fired: list = field(default_factory=list)   # [(deskripsi aturan, kekuatan, keluaran)]
    score: float = 0.0         # 0-100 (centroid)
    out_degrees: dict = field(default_factory=dict)
    category: str = "Sehat"
    label: str = ""

    @property
    def risk_percent(self) -> float:
        return self.score


def _mu(sets: dict, x: float) -> dict:
    return {k: float(f(np.array([x]))[0]) for k, f in sets.items()}


def evaluate(temp_c: float, hr_bpm: float, sound_index: float, ambient_c: float, spo2: float = 98.0) -> FuzzyResult:
    mt, mh = _mu(TEMP_SETS, temp_c), _mu(HR_SETS, hr_bpm)
    mo = _mu(SPO2_SETS, spo2)
    ms, ma = _mu(SOUND_SETS, sound_index), _mu(AMB_SETS, ambient_c)
    res = FuzzyResult(
        inputs=dict(suhu=temp_c, detak=hr_bpm, suara=sound_index, spo2=spo2, ruang=ambient_c),
        memberships=dict(suhu=mt, detak=mh, suara=ms, spo2=mo, ruang=ma),
    )
    agg = np.zeros_like(OUT_X)
    out_mu = {k: f(OUT_X) for k, f in OUT_SETS.items()}

    def fire(strength, out, weight, desc):
        s = strength * weight
        if s <= 1e-6:
            return
        res.fired.append((desc, s, out))
        np.maximum(agg, np.minimum(out_mu[out], s), out=agg)

    for (t, h, s, o), (out, w) in RULES.items():
        fire(min(mt[t], mh[h], ms[s], mo[o]), out, w, f"Suhu {t} & Detak {h} & Suara {s} & SpO2 {o}")
    fire(min(ma["Panas"], mt["Demam"], mh["Normal"], ms["Normal"], mo["Normal"]), "Sehat", HEAT_RULE_WEIGHT,
         "Ruang Panas & Demam ringan & Detak/Suara normal (cekaman panas)")

    if agg.sum() <= 1e-9:
        res.score = 50.0
    else:
        res.score = float((OUT_X * agg).sum() / agg.sum())  # centroid
    res.out_degrees = {k: float(f(np.array([res.score]))[0]) for k, f in OUT_SETS.items()}
    res.category = max(res.out_degrees, key=res.out_degrees.get)
    res.label = LABELS[res.category]
    res.fired.sort(key=lambda r: -r[1])
    return res


def correct_body_temp(ir_c: float, ambient_c: float, offset: float, ambient_coef: float, ref: float = 25.0) -> float:
    """Estimasi suhu inti dari suhu IR permukaan, dikoreksi offset kalibrasi & suhu ruang (SHT31)."""
    return ir_c + offset + ambient_coef * (ref - ambient_c)
