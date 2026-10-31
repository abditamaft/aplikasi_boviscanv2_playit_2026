import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.fuzzy import evaluate, correct_body_temp

CASES = [
    # suhu, detak, suara, ruang -> kategori yang diharapkan
    (38.6, 66, 8, 27, 98, "Sehat"),
    (38.9, 80, 15, 26, 97, "Sehat"),
    (39.8, 90, 20, 27, 97, "Terindikasi"),
    (38.7, 70, 75, 27, 97, "Terindikasi"),
    (38.7, 70, 8, 27, 88, "Terindikasi"),    # hanya SpO2 turun -> curigai artefak, bukan langsung Ngorok
    (40.2, 100, 50, 27, 93, "Ngorok"),
    (40.8, 115, 80, 27, 88, "Ngorok"),
    (41.0, 130, 90, 28, 82, "Ngorok"),
]

def test_cases():
    for t, h, s, a, o, exp in CASES:
        r = evaluate(t, h, s, a, o)
        print(f"T={t} HR={h} S={s} SpO2={o} Ruang={a} -> {r.category} ({r.score:.1f})")
        assert r.category == exp, (t, h, s, a, o, r.category, r.score)

def test_monotonic_in_temp():
    prev = -1
    for t in [38.5, 39.3, 39.8, 40.3, 40.9]:
        sc = evaluate(t, 90, 45, 27).score
        assert sc >= prev - 1e-6
        prev = sc

def test_spo2_lowers_health():
    base = evaluate(39.2, 80, 15, 27, 98).score
    assert evaluate(39.2, 80, 15, 27, 92).score > base
    assert evaluate(39.2, 80, 15, 27, 84).score >= evaluate(39.2, 80, 15, 27, 92).score
    assert len([1 for _ in __import__("core.fuzzy", fromlist=["RULES"]).RULES]) == 81

def test_full_coverage():
    import itertools, numpy as np
    for t, h, s, o in itertools.product(np.arange(35, 43, 0.5), range(40, 200, 10), range(0, 101, 10), range(70, 101, 3)):
        r = evaluate(float(t), float(h), float(s), 27, float(o))
        assert r.fired, (t, h, s)

def test_correction():
    assert abs(correct_body_temp(38.0, 25, 0.5, 0.0) - 38.5) < 1e-9

if __name__ == "__main__":
    test_cases(); test_monotonic_in_temp(); test_spo2_lowers_health(); test_full_coverage(); test_correction()
    print("OK")
