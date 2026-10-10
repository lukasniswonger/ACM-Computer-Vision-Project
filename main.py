"""
Detect everyday carry items (card, keys, key fob, keychain medals) in a video and turn them into sound.

Per frame: read -> detect (every Nth frame) -> track -> enter/exit events -> log, crop, OSC to SuperCollider -> draw
"""
import argparse
import csv
import os
import time
from collections import defaultdict

import cv2

from detector import Detector
from sonify import Sonifier
from tracker import Tracker

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW = "Object Sonifier"

# One BGR color per class id
COLORS = [(80, 200, 80), (0, 200, 255), (255, 160, 0), (200, 80, 255), (255, 255, 0), (60, 60, 255), (0, 140, 255)]


def parse_args():
    p = argparse.ArgumentParser(description="Detect objects in a video and sonify them with SuperCollider.")
    p.add_argument("--video", default=os.path.join(HERE, "videos", "demo.mov"), help="input video file")
    p.add_argument("--model", default=os.path.join(HERE, "model", "best.onnx"))
    p.add_argument("--classes", default=os.path.join(HERE, "model", "classes.txt"))
    p.add_argument("--conf", type=float, default=0.5, help="confidence threshold (default 0.5)")
    p.add_argument("--detect-every", type=int, default=2, help="run the model on every Nth frame (default 2)")
    p.add_argument("--output", default=os.path.join(HERE, "output"), help="folder for the event log, crops and video")
    p.add_argument("--save-video", action="store_true", help="also write the annotated video to the output folder")
    p.add_argument("--no-display", action="store_true", help="don't open a window (useful with --save-video)")
    p.add_argument("--no-audio", action="store_true", help="don't send OSC messages to SuperCollider")
    p.add_argument("--osc-host", default="127.0.0.1")
    p.add_argument("--osc-port", type=int, default=57120, help="port sclang listens on (default 57120)")
    return p.parse_args()


def color_for(class_id):
    return COLORS[class_id % len(COLORS)]


def draw_label(frame, text, x, y, color, scale=1.1):
    """Text on a filled background, kept inside the top edge of the frame."""
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    y = max(y, th + baseline + 4)
    cv2.rectangle(frame, (x, y - th - baseline - 4), (x + tw + 6, y), color, -1)
    cv2.putText(frame, text, (x + 3, y - baseline - 2), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 2, cv2.LINE_AA)


def draw_tracks(frame, tracks):
    for t in tracks:
        left, top, w, h = t.box
        color = color_for(t.class_id)
        # Thin box = not seen in the latest detection run, holding its last position
        cv2.rectangle(frame, (left, top), (left + w, top + h), color, 4 if t.misses == 0 else 1)
        draw_label(frame, f"{t.class_name} #{t.track_id} {t.confidence:.2f}", left, top - 2, color)


def draw_hud(frame, tracks, recent_events, video_time, fps):
    """Panel in the top-left corner: what's on screen right now and the latest events."""
    counts = defaultdict(int)
    for t in tracks:
        counts[t.class_name] += 1

    lines = [(f"t = {video_time:5.1f}s   {fps:4.1f} fps", (255, 255, 255))]
    if counts:
        lines.append((f"On screen: {sum(counts.values())}", (255, 255, 255)))
        lines += [(f"  {name} x{n}", (200, 200, 200)) for name, n in sorted(counts.items())]
    else:
        lines.append(("No objects detected", (120, 120, 255)))
    if recent_events:
        lines.append(("Events:", (255, 255, 255)))
        lines += [(e, (200, 200, 200)) for e in recent_events]

    line_h, pad = 44, 14
    panel_w, panel_h = 560, pad * 2 + line_h * len(lines)
    frame[:panel_h, :panel_w] //= 3  # darken the corner so text stays readable
    for i, (text, color) in enumerate(lines):
        y = pad + line_h * (i + 1) - 10
        cv2.putText(frame, text, (pad, y), cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 2, cv2.LINE_AA)


def open_video_writer(output_dir, fps, frame_size):
    """H.264 .mp4 if this OpenCV build supports it, otherwise Motion-JPEG .avi."""
    for filename, codec in [("annotated.mp4", "avc1"), ("annotated.avi", "MJPG")]:
        writer = cv2.VideoWriter(os.path.join(output_dir, filename), cv2.VideoWriter_fourcc(*codec), fps, frame_size)
        if writer.isOpened():
            return writer
    print("Warning: no supported video codec found, the annotated video will not be saved")
    return None


def main():
    args = parse_args()

    video = cv2.VideoCapture(args.video)
    if not video.isOpened():
        raise SystemExit(f"Could not open video: {args.video}")
    fps = video.get(cv2.CAP_PROP_FPS) or 30.0
    frame_size = (int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    detector = Detector(args.model, args.classes, conf_threshold=args.conf)
    tracker = Tracker()
    sonifier = None if args.no_audio else Sonifier(args.osc_host, args.osc_port)

    crops_dir = os.path.join(args.output, "crops")
    os.makedirs(crops_dir, exist_ok=True)
    log_file = open(os.path.join(args.output, "events.csv"), "w", newline="")
    log = csv.writer(log_file)
    log.writerow(["time_s", "frame", "event", "track_id", "class", "confidence", "x", "y", "w", "h", "seconds_on_screen"])

    writer = None
    if args.save_video:
        writer = open_video_writer(args.output, fps, frame_size)

    if not args.no_display:
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, 960, int(960 * frame_size[1] / frame_size[0]))

    totals = defaultdict(lambda: [0, 0.0])  # class name -> [appearances, seconds on screen]
    recent = []

    def handle(events, frame):
        for e in events:
            t = e.track
            left, top, w, h = t.box
            time_s = e.frame_index / fps
            if e.kind == "enter":
                seconds = ""
                totals[t.class_name][0] += 1
                crop_name = f"{t.track_id:03d}_{t.class_name.replace(' ', '_').strip('-')}.jpg"
                cv2.imwrite(os.path.join(crops_dir, crop_name), frame[top:top + h, left:left + w])
                if sonifier:
                    sonifier.enter(t, frame_size)
            else:
                # Exits fire a few detection runs after the object was last seen (see Tracker.max_misses)
                seconds = round((t.last_frame - t.first_frame + 1) / fps, 2)
                totals[t.class_name][1] += seconds
                if sonifier:
                    sonifier.exit(t, seconds)

            log.writerow([round(time_s, 2), e.frame_index, e.kind, t.track_id, t.class_name,
                          round(t.confidence, 3), left, top, w, h, seconds])
            sign = "+" if e.kind == "enter" else "-"
            recent.append(f"{time_s:5.1f}s {sign} {t.class_name} #{t.track_id}")
            del recent[:-4]
            print(f"[{time_s:6.2f}s] {e.kind:5} {t.class_name} #{t.track_id}"
                  + (f" ({seconds}s on screen)" if seconds else ""))

    frame_index = 0
    display_fps = 0.0
    try:
        while True:
            start = time.perf_counter()
            ret, frame = video.read()
            if not ret:
                break

            if frame_index % args.detect_every == 0:
                detections = detector.detect(frame)
                handle(tracker.update(detections, frame_index, frame_size), frame)
                if sonifier:
                    sonifier.update(tracker.confirmed_tracks, frame_size)

            # HUD first so object labels stay visible when they overlap it
            draw_hud(frame, tracker.confirmed_tracks, recent, frame_index / fps, display_fps)
            draw_tracks(frame, tracker.confirmed_tracks)
            if writer:
                writer.write(frame)

            if not args.no_display:
                cv2.imshow(WINDOW, frame)
                # Play no faster than the video's real speed
                elapsed_ms = (time.perf_counter() - start) * 1000
                key = cv2.waitKey(max(1, int(1000 / fps - elapsed_ms))) & 0xFF
                if key in (ord("q"), 27) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break

            display_fps = 0.9 * display_fps + 0.1 / (time.perf_counter() - start)
            frame_index += 1
    finally:
        handle(tracker.flush(frame_index), None)
        if sonifier:
            sonifier.clear()
        video.release()
        if writer:
            writer.release()
        log_file.close()
        cv2.destroyAllWindows()

    print_summary(totals, frame_index / fps, args.output)


def print_summary(totals, duration, output_dir):
    lines = [f"Summary of {duration:.1f}s of video"]
    if not totals:
        lines.append("No objects were detected.")
    else:
        lines.append(f"{'class':20}{'appearances':>12}{'seconds on screen':>20}")
        for name, (count, seconds) in sorted(totals.items()):
            lines.append(f"{name:20}{count:>12}{seconds:>20.1f}")
    text = "\n".join(lines)
    print("\n" + text)
    with open(os.path.join(output_dir, "summary.txt"), "w") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
