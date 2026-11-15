"""Detection, distance estimation and alert logic."""

import math
from dataclasses import dataclass, asdict

import cv2
import numpy as np
from ultralytics import YOLO

import config

# BGR colours
GREEN = (80, 200, 80)
ORANGE = (0, 165, 255)
RED = (40, 40, 230)
WHITE = (255, 255, 255)


@dataclass
class Detection:
    label: str
    confidence: float
    box: tuple  # x1, y1, x2, y2
    distance_m: float
    level: str  # "safe" | "warning" | "danger"
    in_zone: bool


class DistanceEstimator:
    """Pinhole-camera distance: D = (real_height * focal_px) / pixel_height."""

    def __init__(self, focal_length_px=None, hfov_deg=config.ASSUMED_HFOV_DEG):
        self.focal_length_px = focal_length_px
        self.hfov_deg = hfov_deg

    def focal_for(self, frame_width):
        if self.focal_length_px:
            return self.focal_length_px
        return (frame_width / 2) / math.tan(math.radians(self.hfov_deg / 2))

    def estimate(self, label, box_height_px, frame_width):
        if box_height_px <= 0:
            return float("inf")
        real_h = config.REAL_HEIGHTS_M.get(label, 1.5)
        return real_h * self.focal_for(frame_width) / box_height_px


class RoadEyeDetector:
    def __init__(self, model_path=config.MODEL_PATH):
        self.model = YOLO(model_path)
        self.estimator = DistanceEstimator(config.FOCAL_LENGTH_PX)
        self.confidence = config.CONFIDENCE
        self.danger_m = config.DANGER_DISTANCE_M
        self.warning_m = config.WARNING_DISTANCE_M
        self.zone_width = config.ALERT_ZONE_WIDTH

    def update_settings(self, **kw):
        if "confidence" in kw:
            self.confidence = float(np.clip(kw["confidence"], 0.05, 0.95))
        if "danger_m" in kw:
            self.danger_m = max(0.5, float(kw["danger_m"]))
        if "warning_m" in kw:
            self.warning_m = max(self.danger_m, float(kw["warning_m"]))
        if "zone_width" in kw:
            self.zone_width = float(np.clip(kw["zone_width"], 0.1, 1.0))

    def settings(self):
        return {
            "confidence": self.confidence,
            "danger_m": self.danger_m,
            "warning_m": self.warning_m,
            "zone_width": self.zone_width,
        }

    def _level(self, distance, in_zone):
        if not in_zone:
            return "safe"
        if distance <= self.danger_m:
            return "danger"
        if distance <= self.warning_m:
            return "warning"
        return "safe"

    def detect(self, frame):
        """Run YOLO on a BGR frame and return a list of Detection."""
        h, w = frame.shape[:2]
        zone_l = w * (1 - self.zone_width) / 2
        zone_r = w - zone_l

        result = self.model.predict(
            frame,
            conf=self.confidence,
            imgsz=config.IMG_SIZE,
            classes=list(config.TARGET_CLASSES.keys()),
            verbose=False,
        )[0]

        detections = []
        for box in result.boxes:
            cls_id = int(box.cls[0])
            label = config.TARGET_CLASSES.get(cls_id)
            if label is None:
                continue
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            cx = (x1 + x2) / 2
            in_zone = zone_l <= cx <= zone_r
            dist = self.estimator.estimate(label, y2 - y1, w)
            detections.append(Detection(
                label=label,
                confidence=float(box.conf[0]),
                box=(x1, y1, x2, y2),
                distance_m=dist,
                level=self._level(dist, in_zone),
                in_zone=in_zone,
            ))
        detections.sort(key=lambda d: d.distance_m)
        return detections

    def annotate(self, frame, detections):
        """Draw alert zone, boxes and distances onto the frame (in place)."""
        h, w = frame.shape[:2]
        zone_l = int(w * (1 - self.zone_width) / 2)
        zone_r = w - zone_l

        overlay = frame.copy()
        cv2.rectangle(overlay, (zone_l, 0), (zone_r, h), (255, 200, 0), -1)
        cv2.addWeighted(overlay, 0.06, frame, 0.94, 0, frame)
        cv2.line(frame, (zone_l, 0), (zone_l, h), (255, 200, 0), 1)
        cv2.line(frame, (zone_r, 0), (zone_r, h), (255, 200, 0), 1)

        colour = {"safe": GREEN, "warning": ORANGE, "danger": RED}
        for d in detections:
            x1, y1, x2, y2 = d.box
            c = colour[d.level]
            thick = 3 if d.level == "danger" else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), c, thick)
            text = f"{d.label} {d.distance_m:.1f}m"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            ty = max(y1, th + 8)
            cv2.rectangle(frame, (x1, ty - th - 8), (x1 + tw + 8, ty), c, -1)
            cv2.putText(frame, text, (x1 + 4, ty - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 2, cv2.LINE_AA)

        if any(d.level == "danger" for d in detections):
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), RED, 8)
        return frame


def detection_to_dict(d: Detection):
    out = asdict(d)
    out["distance_m"] = round(d.distance_m, 2)
    out["confidence"] = round(d.confidence, 3)
    return out
