"""Central configuration for RoadEye. Values here are defaults; most can be
changed at runtime from the web interface."""

# YOLOv9 weights. Ultralytics downloads this automatically on first run.
MODEL_PATH = "yolov9c.pt"

# Minimum confidence for a detection to be kept.
CONFIDENCE = 0.40

# Inference image size (smaller = faster, less accurate).
IMG_SIZE = 640

# COCO class ids we care about -> label shown in the UI.
TARGET_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# Typical real-world heights in metres, used for monocular distance estimation.
REAL_HEIGHTS_M = {
    "person": 1.70,
    "bicycle": 1.05,
    "car": 1.50,
    "motorcycle": 1.20,
    "bus": 3.20,
    "truck": 3.00,
}

# Camera focal length in pixels. None = derive from the frame width and an
# assumed horizontal field of view (good enough for most webcams / dashcams).
# Run `python calibrate.py` for an accurate value and paste it here.
FOCAL_LENGTH_PX = None
ASSUMED_HFOV_DEG = 60.0

# Alert thresholds in metres.
DANGER_DISTANCE_M = 5.0
WARNING_DISTANCE_M = 10.0

# Only objects whose centre falls in this middle fraction of the frame width
# (the vehicle's path) can raise alerts. 1.0 = whole frame.
ALERT_ZONE_WIDTH = 0.6

# Default video source: 0 = first webcam, or a path to a video file.
DEFAULT_SOURCE = 0

# JPEG quality of the stream sent to the browser.
STREAM_JPEG_QUALITY = 80

UPLOAD_DIR = "uploads"
