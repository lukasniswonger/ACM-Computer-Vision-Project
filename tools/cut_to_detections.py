"""
Make a copy of a video that keeps only the parts where at least one object is detected.

    python tools/cut_to_detections.py videos/demo.mov videos/demo_detected.mp4

Uses the same detector and tracker as main.py: a stretch is kept from the first to the last frame
an object was seen, for every object the tracker confirms (one-off false positives don't count).
Audio isn't copied, since OpenCV only reads and writes video.
"""
import argparse
import os
import sys

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from detector import Detector  # noqa: E402
from tracker import Tracker  # noqa: E402


def find_segments(video_path, detector, detect_every):
    """First pass: run detection and return merged (start_frame, end_frame) ranges with an object on screen."""
    video = cv2.VideoCapture(video_path)
    frame_size = (int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    tracker = Tracker()
    ranges = []
    frame_index = 0
    while True:
        ret, frame = video.read()
        if not ret:
            break
        if frame_index % detect_every == 0:
            events = tracker.update(detector.detect(frame), frame_index, frame_size)
            ranges += [(e.track.first_frame, e.track.last_frame) for e in events if e.kind == "exit"]
        frame_index += 1
    ranges += [(e.track.first_frame, e.track.last_frame) for e in tracker.flush(frame_index)]
    video.release()

    # Merge overlapping or touching ranges
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged, frame_index


def main():
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("video")
    p.add_argument("output", help="output .mp4 path")
    p.add_argument("--model", default=os.path.join(ROOT, "model", "best.onnx"))
    p.add_argument("--classes", default=os.path.join(ROOT, "model", "classes.txt"))
    p.add_argument("--conf", type=float, default=0.5)
    p.add_argument("--detect-every", type=int, default=2)
    args = p.parse_args()

    video = cv2.VideoCapture(args.video)
    if not video.isOpened():
        raise SystemExit(f"Could not open video: {args.video}")
    fps = video.get(cv2.CAP_PROP_FPS) or 30.0
    frame_size = (int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    video.release()

    detector = Detector(args.model, args.classes, conf_threshold=args.conf)
    segments, total_frames = find_segments(args.video, detector, args.detect_every)
    if not segments:
        print("No objects were detected, so there is nothing to keep. No video written.")
        return

    # Second pass: copy only the frames inside a segment
    writer = cv2.VideoWriter(args.output, cv2.VideoWriter_fourcc(*"avc1"), fps, frame_size)
    if not writer.isOpened():
        raise SystemExit(f"Could not open an H.264 writer for {args.output}")
    video = cv2.VideoCapture(args.video)
    kept = 0
    frame_index = 0
    seg = 0
    while seg < len(segments):
        ret, frame = video.read()
        if not ret:
            break
        start, end = segments[seg]
        if start <= frame_index <= end:
            writer.write(frame)
            kept += 1
        if frame_index >= end:
            seg += 1
        frame_index += 1
    video.release()
    writer.release()

    print("Kept segments:")
    for start, end in segments:
        print(f"  {start / fps:6.2f}s - {(end + 1) / fps:6.2f}s  ({(end - start + 1) / fps:.2f}s)")
    print(f"Kept {kept / fps:.1f}s of {total_frames / fps:.1f}s -> {args.output}")


if __name__ == "__main__":
    main()
