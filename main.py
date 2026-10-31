"""BoviScan - titik masuk aplikasi.

Contoh:
    python main.py                      # laptop: kamera + desain menu fisiologis
    python main.py --sim                # laptop: alur fisiologis dengan data sensor palsu
    python main.py --sim --scenario ngorok
    python main.py --fullscreen         # Raspberry Pi (otomatis fullscreen bila di Raspi)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import config
from core.sensors import SensorHub, SCENARIOS
from ui import styles
from ui.main_window import MainWindow


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true", help="simulasikan sensor fisiologis")
    ap.add_argument("--scenario", choices=list(SCENARIOS), default="terindikasi")
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--windowed", action="store_true", help="paksa jendela biasa (dev di Raspi)")
    ap.add_argument("--page", choices=["camera", "physio"], default="camera")
    ap.add_argument("--hide-cursor", action="store_true")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    app.setStyleSheet(styles.QSS)
    if args.hide_cursor or config.IS_RASPI:
        app.setOverrideCursor(Qt.BlankCursor)

    hub = SensorHub(simulate=args.sim, scenario=args.scenario)
    full = (args.fullscreen or config.IS_RASPI) and not args.windowed
    win = MainWindow(hub, fullscreen=full, start_page=args.page)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
