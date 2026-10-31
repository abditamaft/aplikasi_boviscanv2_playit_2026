# BoviScan — Aplikasi Raspberry Pi 5 (Python + PySide6)

Dua halaman:
1. **Kamera (halaman awal, langsung menyala saat boot)** — YOLO11n NCNN mendeteksi Kuku/Mulut PMK, Lesi LSD, dan area sehat. Tombol kecil **Fisiologis ›** di pojok kanan atas.
2. **Fisiologis** — SHT31 tampil realtime; lalu 3 sensor diukur **bergantian 10 detik** (suhu IR → detak jantung → suara napas), masing-masing dimulai dengan tombol **Mulai Deteksi**. Setelah ketiganya selesai, hasil diolah **fuzzy Mamdani** → *Sapi Sehat / Terindikasi Ngorok / Terkena Ngorok*. Tombol **Kamera** kembali ke halaman 1.

## 1. File dari `hasil_model1.zip` yang dipakai
Hanya 3 file dari `pmk_lsd_v1/weights/best_ncnn_model/` (sudah disalin ke `models/pmk_lsd/`):
`model.ncnn.param`, `model.ncnn.bin`, `metadata.yaml`.
Tidak perlu: `best.pt`, `last.pt`, `model_ncnn.py`, `__pycache__`, gambar kurva/confusion matrix (simpan untuk laporan).

## 2. Struktur folder
```
boviscan/
├── main.py                 # titik masuk (python main.py)
├── config.py               # SEMUA parameter kalibrasi ada di sini
├── core/  detector.py (NCNN) · camera.py · sensors.py · fuzzy.py · history.py
├── ui/    main_window.py · camera_page.py · physio_page.py · widgets.py · styles.py
├── models/pmk_lsd/         # model NCNN
├── scripts/                # install_pi.sh · boviscan.sh · run_windows.bat
├── tests/                  # test_fuzzy.py · test_core.py
└── data/riwayat_pemeriksaan.csv   # dibuat otomatis saat menekan "Simpan Riwayat"
```

## 3. Tes di laptop Windows
```
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py                 # kamera laptop + menu fisiologis (hanya tampilan desain)
python main.py --sim           # alur fisiologis penuh dengan data sensor PALSU
python main.py --sim --scenario ngorok     # sehat | terindikasi | ngorok
python main.py --windowed --page physio    # langsung buka halaman fisiologis
```
Di laptop tanpa `--sim`, sensor fisik tidak jalan: tombol **Mulai Deteksi** hanya menampilkan pesan, jadi menu bisa dilihat tanpa sensor. Kamera ganti lewat `CAMERA_INDEX` di `config.py`. F11 = fullscreen.

## 4. Pasang di Raspberry Pi 5 (Raspberry Pi OS Bookworm 64-bit)
Ini aplikasi Python (bukan APK). Salin foldernya, lalu pasang sekali:
```
# dari laptop:
scp -r boviscan pi@raspberrypi.local:~/
# di Raspi:
cd ~/boviscan && bash scripts/install_pi.sh && sudo reboot
```
Script memasang paket apt (picamera2, numpy, scipy, opencv, portaudio), membuat `.venv`, mengaktifkan I2C/I2S di `/boot/firmware/config.txt` (`i2c_arm=on`, `i2s=on`, `googlevoicehat-soundcard`), dan membuat **autostart** sehingga setelah Raspi menyala aplikasi langsung fullscreen di halaman kamera.
Cek setelah reboot: `i2cdetect -y 1` → harus tampak **0x44 (SHT31), 0x57 (MAX30102), 0x5a (MLX90614)**; `arecord -l` → kartu suara I2S muncul.
Jalankan manual: `bash scripts/boviscan.sh`. Jika layar kosong di Wayland: `QT_QPA_PLATFORM=wayland bash scripts/boviscan.sh`.
Pin mikrofon INMP441 sesuai wiring proposal: SCK→GPIO18, WS→GPIO19, SD→GPIO20, L/R→GND.

## 5. Cara kerja pengukuran (jawaban "sensor tetap membaca atau berhenti?")
- Sensor **tetap membaca terus selama 10 detik langkahnya**, karena sensor tidak tahu kapan sudah menempel; dokter hewan menempelkan sensor setelah menekan Mulai.
- Nilai akhir **bukan satu pembacaan terakhir**, melainkan **median sampel VALID pada 3 detik terakhir** (`FINAL_WINDOW_S`). Dengan begitu 3–5 detik awal (sensor belum menempel/belum stabil) tidak mencemari hasil, dan satu lonjakan tidak merusak nilai.
- Sampel dianggap valid hanya bila: suhu IR 30–43 °C; MAX30102 sinyal IR cukup (menempel) dan interval denyut konsisten; mikrofon di atas ambang kebisingan. Bila sampel valid < batas minimum, langkah **gagal** dan dapat diulang — tidak dipaksa masuk fuzzy.
- Setelah selesai, nilainya **dikunci dan sensor itu dimatikan**; langkah berikutnya baru aktif. SHT31 terus realtime dan nilainya diambil saat fuzzy dihitung.

## 6. Ambang batas & rujukan
| Variabel | Himpunan fuzzy (nilai tengah) | Rujukan |
|---|---|---|
| Suhu tubuh | Normal ≤ 39.0 (penuh) → 0 di 39.7 · Demam puncak 40.0 (39.3–40.7) · Sangat tinggi ≥ 40.9 | Rata-rata sapi sehat 39.3 ± 0.32 °C dan ambang demam 39.5 / 39.7 / 40 °C (Colazo, WCDS 2018); kisaran normal 101.5–103 °F ≈ 38.6–39.4 °C; SE akut demam 40–41.1 °C, mati 8–24 jam setelah gejala (MSD Veterinary Manual) |
| Detak jantung | Normal 48–84 bpm · Tinggi puncak 102 · Sangat tinggi ≥ 125 | Normal sapi 48–84 bpm. Titik 102 dan 125 adalah **pilihan desain** (ambang >100 bpm di literatur yang saya temukan berasal dari pedet, bukan sapi dewasa) |
| SpO₂ | Normal ≥ 95 % (penuh) → 0 di 93 · Rendah puncak 91 (87–95) · Berat ≤ 85 % (0 di 90) | Normal 95–99 %, hipoksemia < 90 % (Burton's Veterinary); sapi perah sehat 98.4–98.9 % dengan sensor MAX (MAXREFDES117) (Agroengineering/JAE); posisi terbaik pangkal ekor, < 85 % = perjalanan penyakit ireversibel (Coghe, AABP 1998); oksimeter cenderung menaksir terlalu tinggi saat SaO₂ rendah, bias +2.1 % pada pedet (Uystepruyst 2000) |
| Suara napas | Indeks 0–100: Normal ≤ 20 · Ringan puncak 45 · Kuat ≥ 70 | **Tidak ada ambang Hz baku untuk "ngorok" sapi.** Acuan terdekat (anak kerbau): normal 71–371 Hz (rata-rata 221), wheezing 322–535 Hz, crackle 129–652 Hz → indeks = rasio energi pita **300–700 Hz** terhadap 60–1000 Hz, dipetakan linear 0.20→0 dan 0.55→100 |
| Suhu ruang | Nyaman ≤ 30 · Panas ≥ 34 | Dipakai (a) koreksi suhu IR `IR_AMBIENT_COEF`, (b) aturan "cekaman panas" yang menurunkan risiko bila demam ringan tanpa gejala lain |

Keluaran: skor 0–100 (centroid) → Sehat (≤ ~35) · Terindikasi (~35–65) · Ngorok (≥ ~65). Basis aturan 81 kombinasi (3 suhu × 3 detak × 3 suara × 3 SpO₂, dibangkitkan otomatis dari 27 aturan dasar: SpO₂ rendah menaikkan keluaran 1 tingkat, SpO₂ berat 2 tingkat; bila hanya SpO₂ yang turun hasilnya dibatasi 'Terindikasi' karena rawan artefak) + 1 aturan ambient, ada di `core/fuzzy.py` (`RULES`) dan mudah diedit bersama dokter hewan.

## 7. Yang WAJIB dikalibrasi sebelum diklaim akurat
Semua di `config.py`:
- `IR_OFFSET_C` — bidik titik tetap (mata/pangkal telinga) pada 20–30 sapi, bandingkan dengan termometer rektal; offset = rata-rata (rektal − IR). IR permukaan selalu lebih rendah dari rektal. `IR_AMBIENT_COEF` bisa diisi lewat regresi terhadap suhu SHT31.
- `SOUND_RATIO_NORMAL / ABNORMAL` — rekam sapi sehat dan sapi bernapas berat, ambil rasio pita 300–700 Hz; set ambang dari data itu (nilai default hanya tebakan awal).
- `SPO2_OFFSET` / `SPO2_POLY` — kurva SpO₂ default dibuat untuk manusia. Bandingkan dengan oksimeter veteriner pada pangkal ekor, lalu isi offset (atau fit ulang kurva).
- Validasi MAX30102 pada kulit sapi (rambut/pigmen) dengan oksimeter veteriner; sensor ini dirancang untuk jari manusia.

## 8. Catatan kejujuran
- Hasil training: P 0.668 / R 0.617 / mAP50 0.640 (epoch terbaik 88). Target proposal recall ≥ 85% & precision ≥ 80% **belum tercapai**; kelas PMK (kuku/mulut) dan LSD punya F1 ~0.45–0.55. `CONF_THRESHOLD=0.30` dipilih dekat puncak kurva F1 (0.256).
- Aplikasi **skrining, bukan diagnosis**; teks ini juga tampil di halaman hasil.
- Belum ada: kirim MQTT ke Android dan asisten LLM (ada di proposal, di luar permintaan ini).
