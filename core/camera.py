"""Kamera: Picamera2 di Raspberry Pi (Pi Camera Module 3), OpenCV di laptop/Windows."""
from __future__ import annotations
import os
import cv2
import config


class Camera:
    def __init__(self, index=config.CAMERA_INDEX):
        self.kind = None
        self.cap = None
        self.pc = None
        if config.IS_RASPI:
            try:
                from picamera2 import Picamera2
                self.pc = Picamera2()
                cfg = self.pc.create_preview_configuration(
                    main={"size": config.CAMERA_RESOLUTION, "format": "RGB888"})  # urutan memori = BGR
                self.pc.configure(cfg)
                self.pc.start()
                self.kind = "picamera2"
                return
            except Exception as e:  # noqa: BLE001  -> jatuh ke USB cam
                print("[camera] Picamera2 gagal, coba OpenCV:", e)
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(index, backend)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_RESOLUTION[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_RESOLUTION[1])
        if not self.cap.isOpened():
            raise RuntimeError(f"Kamera index {index} tidak bisa dibuka")
        self.kind = "opencv"

    def read(self):
        """Return frame BGR atau None."""
        if self.kind == "picamera2":
            return self.pc.capture_array()
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self):
        if self.pc:
            self.pc.stop(); self.pc.close()
        if self.cap:
            self.cap.release()
