"""
Turn a makesense.ai YOLO export plus the extracted frames into a YOLOv8 dataset zip for training/fine_tune_yolo.ipynb.

    python tools/build_dataset.py frames/ labels_export/ dataset.zip

Only frames that have a label file are included.
"""
import argparse
import json
import os
import shutil
import tempfile
from collections import Counter

# Class order must match the label order used in makesense.ai
NAMES = ["Card", "Tow-", "cotwo", "Saint Christopher", "Mary", "Fob", "Key"]

# Hand-picked so every class appears in both splits, taken as contiguous chunks
# to limit near-duplicate frames leaking between train and valid
VALID_FRAMES = [28, 29, 30, 31, 32, 33, 34, 272, 545, 632, 775, 796]


def main():
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("frames_dir")
    p.add_argument("labels_dir", help="unzipped makesense.ai export (one .txt per labeled frame)")
    p.add_argument("zip_out", help="output zip path")
    args = p.parse_args()

    valid = {f"frame_{n:04d}" for n in VALID_FRAMES}
    counts = {"train": Counter(), "valid": Counter()}

    with tempfile.TemporaryDirectory() as tmp:
        ds = os.path.join(tmp, "dataset")
        for split in ["train", "valid"]:
            os.makedirs(f"{ds}/{split}/images")
            os.makedirs(f"{ds}/{split}/labels")

        for fname in sorted(os.listdir(args.labels_dir)):
            if not fname.endswith(".txt"):
                continue
            stem = fname[:-4]
            image = os.path.join(args.frames_dir, stem + ".jpg")
            if not os.path.exists(image):
                print(f"skipping {fname}: no matching frame")
                continue
            split = "valid" if stem in valid else "train"
            with open(os.path.join(args.labels_dir, fname)) as f:
                lines = [l.strip() for l in f if l.strip()]
            for l in lines:
                counts[split][NAMES[int(l.split()[0])]] += 1
            shutil.copy(image, f"{ds}/{split}/images/")
            with open(f"{ds}/{split}/labels/{fname}", "w") as f:
                f.write("\n".join(lines) + "\n")

        with open(f"{ds}/data.yaml", "w") as f:
            f.write("train: train/images\nval: valid/images\n")
            f.write(f"nc: {len(NAMES)}\nnames: {json.dumps(NAMES)}\n")

        zip_base = args.zip_out[:-4] if args.zip_out.endswith(".zip") else args.zip_out
        shutil.make_archive(zip_base, "zip", tmp, "dataset")

    print(f"{'class':20}{'train':>6}{'valid':>6}")
    for name in NAMES:
        print(f"{name:20}{counts['train'][name]:>6}{counts['valid'][name]:>6}")


if __name__ == "__main__":
    main()
