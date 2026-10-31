"""Simpan riwayat pemeriksaan fisiologis ke CSV."""
import csv
from datetime import datetime
import config

FIELDS = ["waktu", "suhu_ir_mentah", "suhu_tubuh_terkoreksi", "detak_bpm", "spo2", "indeks_suara",
          "suhu_ruang", "kelembapan", "skor_risiko", "kategori"]


def save(raw_ir, temp, hr, spo2, sound, amb, rh, result) -> str:
    config.DATA_DIR.mkdir(exist_ok=True)
    if config.HISTORY_CSV.exists() and config.HISTORY_CSV.read_text(encoding='utf-8').split('\n', 1)[0].split(',') != FIELDS:
        config.HISTORY_CSV.rename(config.HISTORY_CSV.with_suffix('.lama.csv'))   # format kolom berubah
    new = not config.HISTORY_CSV.exists()
    with open(config.HISTORY_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(FIELDS)
        w.writerow([datetime.now().isoformat(timespec="seconds"), f"{raw_ir:.2f}", f"{temp:.2f}",
                    f"{hr:.1f}", f"{spo2:.1f}", f"{sound:.1f}", f"{amb:.2f}", f"{rh:.1f}",
                    f"{result.score:.1f}", result.category])
    return str(config.HISTORY_CSV)
