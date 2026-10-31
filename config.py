"""Konfigurasi terpusat BoviScan.

Semua angka yang perlu dikalibrasi (offset suhu, ambang suara, dll.) ada di sini,
jadi tidak perlu menyentuh kode lain saat kalibrasi bersama dokter hewan.
"""
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models" / "pmk_lsd"
DATA_DIR = BASE_DIR / "data"
HISTORY_CSV = DATA_DIR / "riwayat_pemeriksaan.csv"

IS_RASPI = platform.system() == "Linux" and platform.machine() in ("aarch64", "armv7l")

# ------------------------------------------------------------------ Computer Vision
CLASS_NAMES = [  # urutan = metadata.yaml model
    "Kuku PMK", "Kuku Sehat", "Mulut PMK", "Mulut Sehat", "Lesi LSD (lumpy skin)", "Kulit Normal",
]
# True = kelas penyakit (kotak merah), False = sehat (kotak hijau)
CLASS_IS_DISEASE = [True, False, True, False, True, False]
CLASS_DISEASE = ["PMK", None, "PMK", None, "LSD", None]

IMG_SIZE = 640
CONF_THRESHOLD = 0.30   # F1 terbaik pada kurva F1 model = 0.256; 0.30 mengurangi false positive
NMS_IOU = 0.45
NCNN_THREADS = 4        # Raspberry Pi 5 = 4 core
CAMERA_INDEX = 0        # webcam laptop / USB cam
CAMERA_RESOLUTION = (1280, 720)
INFER_EVERY_N_FRAMES = 1  # naikkan ke 2 bila FPS kurang

# ------------------------------------------------------------------ Pengukuran fisiologis
MEASURE_SECONDS = 10      # durasi tiap sensor
FINAL_WINDOW_S = 3.0      # nilai akhir = median sampel VALID pada N detik terakhir
MIN_VALID_SAMPLES = 3

# --- Suhu inframerah (MLX90614, I2C 0x5A)
MLX_ADDR = 0x5A
IR_VALID_RANGE = (30.0, 43.0)   # di luar ini = sensor tidak mengarah ke tubuh sapi
IR_OFFSET_C = 0.0               # KALIBRASI: selisih (suhu rektal - suhu IR) pada titik bidik tetap
IR_AMBIENT_COEF = 0.0           # KALIBRASI: koreksi per °C selisih suhu ruang dari 25 °C (SHT31)
IR_AMBIENT_REF = 25.0

# --- Detak jantung (MAX30102, I2C 0x57)
MAX_ADDR = 0x57
HR_VALID_RANGE = (30, 220)
MAX_MIN_IR_SIGNAL = 20000       # IR di bawah ini = sensor tidak menempel pada kulit
MAX_MIN_RED_SIGNAL = 10000      # kanal merah minimal (untuk SpO2)

# --- SpO2 (dari MAX30102 yang sama, di langkah 2)
SPO2_POLY = (-45.060, 30.354, 94.845)   # SpO2 = a*R^2 + b*R + c  (kurva referensi Maxim, untuk manusia)
SPO2_OFFSET = 0.0                       # KALIBRASI: (SpO2 oksimeter veteriner - SpO2 sensor ini), tail-base
SPO2_MIN_PERFUSION_INDEX = 0.05         # % ; di bawah ini sinyal AC terlalu lemah -> SpO2 tidak dipercaya

# --- Suara napas (INMP441, I2S)
AUDIO_RATE = 48000              # googlevoicehat/INMP441 stabil di 48 kHz
AUDIO_CHANNELS = 2             # I2S stereo, L/R mic ke GND = kanal kiri (index 0)
AUDIO_DEVICE = None             # None = default ALSA; atau nama/ID dari `python -m sounddevice`
AUDIO_MIN_RMS_DBFS = -55.0      # di bawah ini dianggap tidak ada suara
SOUND_BAND = (300.0, 700.0)     # pita "abnormal" (wheeze/stertor) - lihat README
SOUND_TOTAL_BAND = (60.0, 1000.0)
SOUND_RATIO_NORMAL = 0.20       # KALIBRASI: rasio energi sapi sehat
SOUND_RATIO_ABNORMAL = 0.55     # KALIBRASI: rasio energi suara ngorok kuat

# --- SHT31 (I2C 0x44)
SHT_ADDR = 0x44
I2C_BUS = 1
