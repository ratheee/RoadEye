"""Compute the camera focal length (in pixels) for accurate distances.

1. Stand a person (or place a car) at a known distance from the camera.
2. Run:  python calibrate.py --distance 3.0 --label person [--height 1.75] [--source 0]
3. Press SPACE when the object is detected, Q to quit.
4. Copy the printed FOCAL_LENGTH_PX value into config.py.

Formula: focal_px = pixel_height * known_distance / real_height
"""

import argparse
import os

import cv2

import config
from detector import RoadEyeDetector


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--distance", type=float, required=True, help="known distance in metres")
    p.add_argument("--label", default="person", choices=list(config.REAL_HEIGHTS_M))
    p.add_argument("--height", type=float, help="real object height in metres")
    p.add_argument("--source", default="0")
    a = p.parse_args()

    real_h = a.height or config.REAL_HEIGHTS_M[a.label]
    src = int(a.source) if a.source.isdigit() else a.source
    cap = cv2.VideoCapture(src, cv2.CAP_DSHOW) if isinstance(src, int) and os.name == "nt" \
        else cv2.VideoCapture(src)
    det = RoadEyeDetector()
    samples = []

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        targets = [d for d in det.detect(frame) if d.label == a.label]
        best = max(targets, key=lambda d: d.box[3] - d.box[1], default=None)
        if best:
            x1, y1, x2, y2 = best.box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            focal = (y2 - y1) * a.distance / real_h
            cv2.putText(frame, f"focal={focal:.0f}px  samples={len(samples)}  [SPACE] save [Q] done",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("RoadEye calibration", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(" ") and best:
            samples.append(focal)
            print(f"sample {len(samples)}: {focal:.1f}px")
        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    if samples:
        avg = sum(samples) / len(samples)
        print(f"\nSet in config.py:  FOCAL_LENGTH_PX = {avg:.1f}")
    else:
        print("No samples captured.")


if __name__ == "__main__":
    main()
