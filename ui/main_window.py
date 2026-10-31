import os
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox, QApplication

import config
from ui.camera_page import CameraPage
from ui.physio_page import PhysioPage


class MainWindow(QMainWindow):
    def __init__(self, hub, fullscreen=False, start_page="camera"):
        super().__init__()
        self.setWindowTitle("BoviScan")
        self.resize(1024, 600)
        self.cam = CameraPage(hub)
        self.phy = PhysioPage(hub)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.cam)
        self.stack.addWidget(self.phy)
        self.setCentralWidget(self.stack)
        self.cam.open_physio.connect(self.show_physio)
        self.phy.open_camera.connect(self.show_camera)
        self.phy.request_exit.connect(self._exit_dialog)
        if fullscreen:
            self.showFullScreen()
        (self.show_physio if start_page == "physio" else self.show_camera)()

    def show_camera(self):
        self.phy.deactivate()
        self.stack.setCurrentWidget(self.cam)
        self.cam.activate()

    def show_physio(self):
        self.cam.deactivate()          # bebaskan CPU & kamera selama pengukuran sensor
        self.stack.setCurrentWidget(self.phy)
        self.phy.activate()

    def _exit_dialog(self):
        box = QMessageBox(self)
        box.setWindowTitle("Keluar")
        box.setText("Pilih tindakan:")
        quit_btn = box.addButton("Tutup aplikasi", QMessageBox.AcceptRole)
        off_btn = box.addButton("Matikan Raspberry Pi", QMessageBox.DestructiveRole) if config.IS_RASPI else None
        box.addButton("Batal", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is quit_btn:
            QApplication.quit()
        elif off_btn is not None and box.clickedButton() is off_btn:
            subprocess.Popen(["systemctl", "poweroff"])

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif e.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        self.cam.deactivate()
        self.phy.deactivate()
        super().closeEvent(e)
