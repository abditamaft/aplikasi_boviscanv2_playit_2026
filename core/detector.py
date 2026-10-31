"""Detektor YOLO11n format NCNN (hasil export Ultralytics).

Model: input "in0" (1x3x640x640, RGB, 0-1), output "out0" shape (4+nc, 8400):
4 baris pertama = cx,cy,w,h (piksel 640), sisanya = skor kelas (sudah sigmoid).
"""
from __future__ import annotations
from dataclasses import dataclass
import time

import cv2
import numpy as np

import config


@dataclass
class Detection:
    cls: int
    conf: float
    box: tuple  # x1,y1,x2,y2 di koordinat frame asli

    @property
    def name(self): return config.CLASS_NAMES[self.cls]
    @property
    def is_disease(self): return config.CLASS_IS_DISEASE[self.cls]
    @property
    def disease(self): return config.CLASS_DISEASE[self.cls]


class NcnnDetector:
    def __init__(self, model_dir=config.MODEL_DIR):
        import ncnn
        self.ncnn = ncnn
        self.net = ncnn.Net()
        self.net.opt.num_threads = config.NCNN_THREADS
        self.net.opt.use_vulkan_compute = False
        self.net.load_param(str(model_dir / "model.ncnn.param"))
        self.net.load_model(str(model_dir / "model.ncnn.bin"))
        self.size = config.IMG_SIZE
        self.nc = len(config.CLASS_NAMES)

    def _letterbox(self, img):
        h, w = img.shape[:2]
        r = self.size / max(h, w)
        nw, nh = int(round(w * r)), int(round(h * r))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.size, self.size, 3), 114, dtype=np.uint8)
        px, py = (self.size - nw) // 2, (self.size - nh) // 2
        canvas[py:py + nh, px:px + nw] = resized
        return canvas, r, px, py

    def detect(self, frame_bgr) -> list[Detection]:
        ncnn = self.ncnn
        img, r, px, py = self._letterbox(frame_bgr)
        rgb = np.ascontiguousarray(img[:, :, ::-1])
        mat = ncnn.Mat.from_pixels(rgb, ncnn.Mat.PixelType.PIXEL_RGB, self.size, self.size)
        mat.substract_mean_normalize([0, 0, 0], [1 / 255.0] * 3)
        with self.net.create_extractor() as ex:
            ex.input("in0", mat)
            _, out = ex.extract("out0")
            pred = np.array(out)            # (4+nc, 8400)
        if pred.shape[0] != 4 + self.nc:
            pred = pred.reshape(4 + self.nc, -1)
        return self.decode(pred, r, px, py, frame_bgr.shape[:2])

    def decode(self, pred, r, px, py, shape) -> list[Detection]:
        """pred: (4+nc, 8400) keluaran mentah model; r/px/py: parameter letterbox."""
        pred = pred.T                       # (8400, 4+nc)
        scores = pred[:, 4:]
        cls = scores.argmax(1)
        conf = scores[np.arange(len(scores)), cls]
        keep = conf >= config.CONF_THRESHOLD
        if not keep.any():
            return []
        p, cls, conf = pred[keep], cls[keep], conf[keep]
        cx, cy, w, h = p[:, 0], p[:, 1], p[:, 2], p[:, 3]
        boxes = np.stack([(cx - w / 2 - px) / r, (cy - h / 2 - py) / r, w / r, h / r], 1)
        idx = cv2.dnn.NMSBoxes(boxes.tolist(), conf.tolist(), config.CONF_THRESHOLD, config.NMS_IOU)
        H, W = shape
        out_list = []
        for i in np.array(idx).flatten():
            bx, by, bw_, bh_ = boxes[i]
            out_list.append(Detection(int(cls[i]), float(conf[i]),
                                      (int(max(0, bx)), int(max(0, by)),
                                       int(min(W - 1, bx + bw_)), int(min(H - 1, by + bh_)))))
        return out_list


def draw(frame, dets: list[Detection]):
    for d in dets:
        color = (60, 60, 235) if d.is_disease else (80, 200, 90)   # BGR
        x1, y1, x2, y2 = d.box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        label = f"{d.name} {d.conf:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (x1, max(0, y1 - th - 10)), (x1 + tw + 8, y1), color, -1)
        cv2.putText(frame, label, (x1 + 4, max(th, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 2, cv2.LINE_AA)
    return frame


def summarize(dets: list[Detection]) -> tuple[str, str]:
    """Return (kode, teks) status untuk bar bawah: 'pmk' | 'lsd' | 'both' | 'ok' | 'none'."""
    if not dets:
        return "none", "Arahkan kamera ke sapi"
    diseases = {d.disease for d in dets if d.is_disease}
    if diseases == {"PMK", "LSD"}:
        return "both", "TERDETEKSI LESI PMK & LSD"
    if "PMK" in diseases:
        return "pmk", "TERDETEKSI LESI PMK"
    if "LSD" in diseases:
        return "lsd", "TERDETEKSI LESI LSD"
    return "ok", "Area terdeteksi tampak sehat"
