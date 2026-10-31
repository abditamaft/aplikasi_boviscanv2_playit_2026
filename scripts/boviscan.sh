#!/usr/bin/env bash
# Peluncur BoviScan di Raspberry Pi
cd "$(dirname "$0")/.." || exit 1
source .venv/bin/activate
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"   # ganti ke 'wayland' bila xcb bermasalah
exec python main.py --fullscreen "$@"
