BG = "#0b1220"
CARD = "#16213a"
CARD_ACTIVE = "#1b2a4a"
TEXT = "#e8eefc"
MUTED = "#8a97b5"
GREEN = "#22c55e"
AMBER = "#f59e0b"
RED = "#ef4444"
BLUE = "#3b82f6"

QSS = f"""
* {{ font-family: 'Noto Sans','DejaVu Sans','Segoe UI',sans-serif; color: {TEXT}; }}
QMainWindow, QWidget#root, QStackedWidget {{ background: {BG}; }}
QLabel {{ background: transparent; }}
QFrame#card {{ background: {CARD}; border-radius: 14px; border: 2px solid transparent; }}
QFrame#card[state="running"] {{ background: {CARD_ACTIVE}; border: 2px solid {BLUE}; }}
QFrame#card[state="ready"] {{ border: 2px solid #2b3d66; }}
QFrame#card[state="done"] {{ border: 2px solid {GREEN}; }}
QFrame#card[state="failed"] {{ border: 2px solid {RED}; }}
QPushButton {{ background: {BLUE}; color: white; border: none; border-radius: 12px;
              padding: 10px 18px; font-size: 18px; font-weight: 600; min-height: 44px; }}
QPushButton:pressed {{ background: #2563eb; }}
QPushButton:disabled {{ background: #26314d; color: #5f6c8a; }}
QPushButton#ghost {{ background: #26314d; color: {TEXT}; }}
QPushButton#green {{ background: {GREEN}; color: #06210f; }}
QPushButton#danger {{ background: {RED}; }}
QPushButton#overlay {{ background: rgba(11,18,32,190); border: 1px solid rgba(255,255,255,70);
                      border-radius: 10px; padding: 4px 12px; font-size: 14px; min-height: 36px; }}
QLabel#title {{ font-size: 22px; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; font-size: 14px; }}
QLabel#value {{ font-size: 30px; font-weight: 700; }}
QLabel#hint {{ color: #cbd5f0; font-size: 15px; }}
QLabel#banner {{ background: #3a2a0a; color: #fcd34d; border-radius: 10px; padding: 6px 12px; font-size: 14px; }}
QTableWidget {{ background: {CARD}; border: none; font-size: 15px; gridline-color: #26314d; }}
QHeaderView::section {{ background: #1b2a4a; border: none; padding: 4px; font-size: 14px; }}
"""
