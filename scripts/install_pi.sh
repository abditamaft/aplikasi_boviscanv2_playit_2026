#!/usr/bin/env bash
# Jalankan SEKALI di Raspberry Pi 5 (Raspberry Pi OS Bookworm 64-bit):  bash scripts/install_pi.sh
set -e
cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"

echo "== 1. Paket sistem =="
sudo apt update
sudo apt install -y python3-venv python3-numpy python3-scipy python3-opencv python3-picamera2 \
     libportaudio2 libasound2-dev i2c-tools libxcb-cursor0 libxkbcommon-x11-0 libegl1 fonts-noto-core fonts-dejavu-core

echo "== 2. Virtualenv (system-site-packages agar picamera2/numpy/opencv terbaca) =="
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-pi.txt

echo "== 3. Aktifkan I2C & I2S di /boot/firmware/config.txt =="
CFG=/boot/firmware/config.txt
sudo cp -n $CFG ${CFG}.bak-boviscan
add() { grep -qxF "$1" $CFG || echo "$1" | sudo tee -a $CFG >/dev/null; }
add "dtparam=i2c_arm=on"
add "dtparam=i2c_arm_baudrate=50000"      # MLX90614 lebih stabil di 50 kHz
add "dtparam=i2s=on"
add "dtoverlay=googlevoicehat-soundcard"  # INMP441 (I2S mic) -> kartu suara ALSA

echo "== 4. Autostart saat desktop menyala =="
chmod +x scripts/boviscan.sh
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/boviscan.desktop <<EOF
[Desktop Entry]
Type=Application
Name=BoviScan
Exec=$APP_DIR/scripts/boviscan.sh
X-GNOME-Autostart-enabled=true
EOF
# Bookworm memakai labwc: tambahkan juga ke autostart labwc
mkdir -p ~/.config/labwc
grep -qF boviscan.sh ~/.config/labwc/autostart 2>/dev/null || echo "$APP_DIR/scripts/boviscan.sh &" >> ~/.config/labwc/autostart

echo "== Selesai. Reboot untuk mengaktifkan I2C/I2S:  sudo reboot =="
echo "Cek sensor setelah reboot:  i2cdetect -y 1   (harus tampak 0x44, 0x57, 0x5a)  |  arecord -l"
