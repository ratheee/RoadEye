"""RoadEye web server: streams annotated video and exposes a small JSON API."""

import argparse
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.utils import secure_filename

import config
from detector import RoadEyeDetector, detection_to_dict

ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class VideoProcessor:
    """Reads frames in a background thread, runs detection, keeps the latest
    annotated JPEG and status for the web clients."""

    def __init__(self, detector, source=config.DEFAULT_SOURCE):
        self.detector = detector
        self.lock = threading.Lock()
        self.cap = None
        self.source = None
        self.running = True
        self.paused = False
        self.jpeg = self._placeholder("Starting...")
        self.status = {"detections": [], "alert": "safe", "fps": 0.0,
                       "source": None, "error": None}
        self.set_source(source)
        threading.Thread(target=self._loop, daemon=True).start()

    @staticmethod
    def _placeholder(text):
        img = np.zeros((480, 854, 3), np.uint8)
        img[:] = (30, 24, 20)
        cv2.putText(img, text, (40, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (200, 200, 200), 2, cv2.LINE_AA)
        return cv2.imencode(".jpg", img)[1].tobytes()

    def set_source(self, source):
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        # CAP_DSHOW opens Windows webcams much faster than the default backend.
        if isinstance(source, int) and os.name == "nt":
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(source)
        with self.lock:
            if self.cap is not None:
                self.cap.release()
            self.cap = cap
            self.source = source
            ok = cap.isOpened()
            self.status["source"] = str(source)
            self.status["error"] = None if ok else f"Cannot open source: {source}"
            if not ok:
                self.jpeg = self._placeholder(f"Cannot open source: {source}")
        return ok

    def _loop(self):
        last = time.time()
        fps = 0.0
        while self.running:
            if self.paused:
                time.sleep(0.05)
                continue
            with self.lock:
                cap, source = self.cap, self.source
            if cap is None or not cap.isOpened():
                time.sleep(0.2)
                continue

            ok, frame = cap.read()
            if not ok:
                if isinstance(source, str):  # video file finished -> loop it
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                else:
                    time.sleep(0.05)
                continue

            # Keep processing time reasonable for large videos.
            if frame.shape[1] > 1280:
                scale = 1280 / frame.shape[1]
                frame = cv2.resize(frame, None, fx=scale, fy=scale)

            detections = self.detector.detect(frame)
            self.detector.annotate(frame, detections)

            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - last, 1e-6))
            last = now
            cv2.putText(frame, f"{fps:.1f} FPS", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

            levels = {d.level for d in detections}
            alert = "danger" if "danger" in levels else "warning" if "warning" in levels else "safe"
            jpeg = cv2.imencode(".jpg", frame,
                                [cv2.IMWRITE_JPEG_QUALITY, config.STREAM_JPEG_QUALITY])[1].tobytes()
            with self.lock:
                if cap is self.cap:  # ignore frames from a source we just replaced
                    self.jpeg = jpeg
                    self.status.update(
                        detections=[detection_to_dict(d) for d in detections],
                        alert=alert,
                        fps=round(fps, 1),
                    )

    def frames(self):
        while True:
            with self.lock:
                jpeg = self.jpeg
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            time.sleep(1 / 30)

    def get_status(self):
        with self.lock:
            s = dict(self.status)
        s["paused"] = self.paused
        s["settings"] = self.detector.settings()
        return s


def create_app(source):
    app = Flask(__name__)
    upload_dir = Path(config.UPLOAD_DIR)
    upload_dir.mkdir(exist_ok=True)

    print("Loading YOLOv9 model (downloads on first run)...")
    processor = VideoProcessor(RoadEyeDetector(), source)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/video_feed")
    def video_feed():
        return Response(processor.frames(),
                        mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/api/status")
    def status():
        return jsonify(processor.get_status())

    @app.route("/api/settings", methods=["POST"])
    def settings():
        data = request.get_json(force=True, silent=True) or {}
        processor.detector.update_settings(**{
            k: v for k, v in data.items()
            if k in ("confidence", "danger_m", "warning_m", "zone_width")
        })
        return jsonify(processor.detector.settings())

    @app.route("/api/source", methods=["POST"])
    def set_source():
        data = request.get_json(force=True, silent=True) or {}
        src = data.get("source", 0)
        ok = processor.set_source(src)
        return jsonify({"ok": ok, "source": str(src)}), (200 if ok else 400)

    @app.route("/api/upload", methods=["POST"])
    def upload():
        f = request.files.get("video")
        if not f or not f.filename:
            return jsonify({"ok": False, "error": "No file"}), 400
        name = secure_filename(f.filename)
        if Path(name).suffix.lower() not in ALLOWED_EXT:
            return jsonify({"ok": False, "error": "Unsupported file type"}), 400
        path = upload_dir / name
        f.save(path)
        ok = processor.set_source(str(path))
        return jsonify({"ok": ok, "source": name}), (200 if ok else 400)

    @app.route("/api/pause", methods=["POST"])
    def pause():
        processor.paused = not processor.paused
        return jsonify({"paused": processor.paused})

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RoadEye detection server")
    parser.add_argument("--source", default=str(config.DEFAULT_SOURCE),
                        help="webcam index (0, 1, ...) or path to a video file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    app = create_app(args.source)
    print(f"Open http://{args.host}:{args.port} in your browser")
    app.run(host=args.host, port=args.port, threaded=True, debug=False)
