"""
Save frames from a video as JPEGs for labeling.

    python tools/extract_frames.py videos/demo.mov frames/ --every 1
"""
import argparse
import os

import cv2


def main():
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("video")
    p.add_argument("out_dir")
    p.add_argument("--every", type=int, default=1, help="keep every Nth frame (default 1 = all)")
    args = p.parse_args()

    video = cv2.VideoCapture(args.video)
    if not video.isOpened():
        raise SystemExit(f"Could not open video: {args.video}")
    os.makedirs(args.out_dir, exist_ok=True)

    frame_index = saved = 0
    while True:
        ret, frame = video.read()
        if not ret:
            break
        if frame_index % args.every == 0:
            cv2.imwrite(os.path.join(args.out_dir, f"frame_{frame_index:04d}.jpg"), frame)
            saved += 1
        frame_index += 1
    video.release()
    print(f"Saved {saved} of {frame_index} frames to {args.out_dir}")


if __name__ == "__main__":
    main()
