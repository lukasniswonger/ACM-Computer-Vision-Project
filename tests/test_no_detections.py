"""
Checks that frames with nothing in them are handled cleanly.

Run from the project root:  python tests/test_no_detections.py
"""
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from detector import Detector  # noqa: E402
from main import draw_hud, draw_tracks  # noqa: E402
from tracker import Tracker  # noqa: E402


def test_empty_frame():
    detector = Detector(os.path.join(ROOT, "model", "best.onnx"), os.path.join(ROOT, "model", "classes.txt"))
    tracker = Tracker()
    frame = np.zeros((1080, 1920, 3), np.uint8)

    detections = detector.detect(frame)
    assert detections == [], detections

    for i in range(20):
        assert tracker.update(detections, i, (1920, 1080)) == []
    assert tracker.flush(20) == []

    draw_tracks(frame, tracker.confirmed_tracks)
    draw_hud(frame, tracker.confirmed_tracks, [], 0.0, 0.0)
    print("ok: empty frame -> no detections, no events, HUD draws")


def test_blank_video_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        video_path = os.path.join(tmp, "blank.mp4")
        writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"avc1"), 30, (640, 360))
        if not writer.isOpened():
            writer = cv2.VideoWriter(video_path := os.path.join(tmp, "blank.avi"), cv2.VideoWriter_fourcc(*"MJPG"), 30, (640, 360))
        for _ in range(30):
            writer.write(np.full((360, 640, 3), 40, np.uint8))
        writer.release()

        out_dir = os.path.join(tmp, "out")
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "main.py"), "--video", video_path,
             "--output", out_dir, "--no-display", "--no-audio"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "No objects were detected." in result.stdout, result.stdout
        with open(os.path.join(out_dir, "events.csv")) as f:
            assert len(f.readlines()) == 1  # header only
    print("ok: blank video runs end to end and reports no objects")


if __name__ == "__main__":
    test_empty_frame()
    test_blank_video_end_to_end()
    print("all tests passed")
