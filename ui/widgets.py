from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QLinearGradient
from PySide6.QtWidgets import (QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton)

from ui import styles


class CountdownRing(QWidget):
    """Cincin hitung mundur: progres BERKURANG dari penuh ke kosong; centang saat selesai."""

    def __init__(self, total=10, parent=None):
        super().__init__(parent)
        self.total, self.remaining, self.mode = total, total, "idle"  # idle|running|done|failed
        self.setFixedSize(96, 96)

    def set_state(self, mode, remaining=None):
        self.mode = mode
        if remaining is not None:
            self.remaining = max(0.0, remaining)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(8, 8, self.width() - 16, self.height() - 16)
        pen = QPen(QColor("#26314d"), 9); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen); p.drawEllipse(r)
        if self.mode == "running":
            pen.setColor(QColor(styles.BLUE)); p.setPen(pen)
            p.drawArc(r, 90 * 16, int(-360 * 16 * self.remaining / self.total))
            p.setPen(QColor(styles.TEXT)); p.setFont(QFont("DejaVu Sans", 22, QFont.Bold))
            p.drawText(self.rect(), Qt.AlignCenter, str(int(self.remaining + 0.999)))
        elif self.mode == "done":
            pen.setColor(QColor(styles.GREEN)); p.setPen(pen); p.drawEllipse(r)
            p.setFont(QFont("DejaVu Sans", 34, QFont.Bold))
            p.drawText(self.rect(), Qt.AlignCenter, "✓")
        elif self.mode == "failed":
            pen.setColor(QColor(styles.RED)); p.setPen(pen); p.drawEllipse(r)
            p.setFont(QFont("DejaVu Sans", 34, QFont.Bold))
            p.drawText(self.rect(), Qt.AlignCenter, "!")
        else:
            p.setPen(QColor(styles.MUTED)); p.setFont(QFont("DejaVu Sans", 18, QFont.Bold))
            p.drawText(self.rect(), Qt.AlignCenter, f"{int(self.total)}s")


class StepCard(QFrame):
    start_clicked = Signal()

    def __init__(self, number, title, instruction, unit, total, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.unit = unit
        self.ring = CountdownRing(total)
        self.title = QLabel(f"{number}. {title}"); self.title.setObjectName("title")
        self.hint = QLabel(instruction); self.hint.setObjectName("hint"); self.hint.setWordWrap(True)
        self.value = QLabel("—"); self.value.setObjectName("value")
        self.btn = QPushButton("Mulai Deteksi"); self.btn.setMinimumWidth(170)
        self.btn.clicked.connect(self.start_clicked)
        mid = QVBoxLayout(); mid.setSpacing(2)
        mid.addWidget(self.title); mid.addWidget(self.hint); mid.addWidget(self.value)
        lay = QHBoxLayout(self); lay.setContentsMargins(14, 8, 14, 8); lay.setSpacing(14)
        lay.addWidget(self.ring); lay.addLayout(mid, 1); lay.addWidget(self.btn)
        self.set_state("locked")

    def set_state(self, state, text=None, remaining=None):
        """state: locked | ready | running | done | failed"""
        self.setProperty("state", state)
        self.style().unpolish(self); self.style().polish(self)
        ring = {"locked": "idle", "ready": "idle", "running": "running", "done": "done", "failed": "failed"}[state]
        self.ring.set_state(ring, remaining)
        self.btn.setEnabled(state in ("ready", "done", "failed"))
        self.btn.setObjectName("ghost" if state in ("done", "failed") else "")
        self.btn.style().unpolish(self.btn); self.btn.style().polish(self.btn)
        self.btn.setText({"locked": "Menunggu", "ready": "Mulai Deteksi", "running": "Mengukur…",
                          "done": "Ulangi", "failed": "Coba Lagi"}[state])
        if text is not None:
            self.value.setText(text)


class RiskBar(QWidget):
    """Bar risiko 0-100 dengan zona hijau/kuning/merah dan penanda skor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.score = 0.0
        self.setMinimumHeight(54)

    def set_score(self, s):
        self.score = s; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bar = QRectF(0, 18, w, 18)
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0.0, QColor(styles.GREEN)); g.setColorAt(0.42, QColor(styles.GREEN))
        g.setColorAt(0.5, QColor(styles.AMBER)); g.setColorAt(0.68, QColor(styles.AMBER))
        g.setColorAt(0.78, QColor(styles.RED)); g.setColorAt(1.0, QColor(styles.RED))
        p.setBrush(g); p.setPen(Qt.NoPen); p.drawRoundedRect(bar, 9, 9)
        x = w * self.score / 100
        p.setBrush(QColor("white")); p.drawRoundedRect(QRectF(x - 4, 10, 8, 34), 4, 4)
        p.setPen(QColor(styles.MUTED)); p.setFont(QFont("DejaVu Sans", 9))
        p.drawText(0, h - 2, "0%"); p.drawText(w - 36, h - 2, "100%")
