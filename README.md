# RoadEye
Real-Time Vehicle and Pedestrian Detection with Collision Alerts

## Overview
This project is a driver assistance system that processes live video to detect vehicles and pedestrians on the road, estimates how far each one is from the camera, and warns the driver when an object enters an unsafe range. It aims to reduce accidents caused by delayed driver reaction.

## Key Features
- Real-time detection of vehicles and pedestrians using YOLOv9
- Distance estimation for each detected object from a single camera
- Visual and audio alerts when an object crosses a safety threshold
- Web interface showing the live feed with bounding boxes and distances
- Support for webcam input and pre-recorded video files

## Tech Stack
- Language: Python
- Detection model: YOLOv9 (pretrained, PyTorch)
- Video processing: OpenCV
- Backend: Flask
- Frontend: HTML, CSS, JavaScript

## Getting Started
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

python app.py                    # webcam 0
python app.py --source road.mp4  # or a video file
```
Open http://127.0.0.1:5000. The YOLOv9 weights (`yolov9c.pt`, ~50 MB) download automatically on first run.

From the web page you can switch webcams, upload a video, pause, mute alerts, and tune the
danger/warning distances, confidence, and alert-zone width live.

### Calibrating distance (optional, recommended)
By default the focal length is derived from an assumed 60° field of view. For accurate distances,
stand a person at a known distance from the camera and run:
```bash
python calibrate.py --distance 3.0 --label person --height 1.75
```
Press SPACE a few times to take samples, then Q, and copy the printed `FOCAL_LENGTH_PX` into `config.py`.

## How It Works
1. The system captures frames from a camera or video file.
2. Each frame is passed to the YOLOv9 model, which returns the detected objects with bounding boxes and confidence scores.
3. The distance of each object is estimated from its bounding box size and the camera's focal length:
   `distance = real_height × focal_length_px / box_height_px`.
4. If an object inside the central alert zone (the vehicle's path) is closer than the warning or danger threshold, an alert is triggered.
5. The annotated frame is streamed to the web interface in real time (MJPEG), while the page polls `/api/status` for detections and alert state.

## Project Structure
| File | Purpose |
|------|---------|
| `app.py` | Flask server, background video-processing thread, REST API |
| `detector.py` | YOLOv9 inference, distance estimation, alert levels, frame annotation |
| `config.py` | Model, classes, object heights, thresholds, camera settings |
| `calibrate.py` | Measures the camera focal length for accurate distances |
| `templates/index.html`, `static/` | Web dashboard (live feed, alerts, beeps, settings) |

## API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/video_feed` | MJPEG stream of annotated frames |
| GET | `/api/status` | Detections, alert level, FPS, settings |
| POST | `/api/settings` | `{danger_m, warning_m, confidence, zone_width}` |
| POST | `/api/source` | `{source: 0}` webcam index or file path |
| POST | `/api/upload` | multipart `video` file |
| POST | `/api/pause` | Toggle pause |

## My Contribution
- Built the video processing pipeline and integrated the YOLOv9 model
- Implemented the distance estimation and alert logic
- Developed the backend API and the web interface
- Tested the system on multiple road videos and tuned the thresholds

## Future Scope
- Lane detection and traffic sign recognition
- Object tracking to predict the movement of pedestrians
- Deployment on edge devices such as Raspberry Pi or Jetson Nano
