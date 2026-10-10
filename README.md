# Object Sonifier

Detects the things in my pocket (a roadside-assistance card, its phone number, my car key, key fob, and two keychain medals) in a recorded video, tracks them as they come and go, and **turns them into sound with SuperCollider**: each object type gets its own note, a bell rings when it appears, and a drone follows it around the stereo field while it stays on screen.

![Card, key and phone number detected](samples/screenshots/01_card_key_and_number.jpg)

| Fob and Mary medal | Nothing detected |
|---|---|
| ![](samples/screenshots/02_fob_and_mary.jpg) | ![](samples/screenshots/03_no_objects.jpg) |

Full annotated run: [samples/demo_annotated.mp4](samples/demo_annotated.mp4)

## What it detects

A YOLOv8n model fine-tuned on frames from my own video, with 7 classes:

| Class | What it is |
|---|---|
| `Card` | roadside-assistance card |
| `Tow-` | the tow/road service phone number printed on the card |
| `cotwo` | button on the key fob |
| `Saint Christopher` | Saint Christopher keychain medal |
| `Mary` | Mary keychain medal |
| `Fob` | car alarm key fob |
| `Key` | car key |

None of these exist in standard pretrained datasets (COCO has no keys, cards or fobs), so a pretrained model alone couldn't do this.

## Model and why

- **YOLOv8n (nano), fine-tuned** with Ultralytics on Google Colab's free GPU ([training/fine_tune_yolo.ipynb](training/fine_tune_yolo.ipynb)). Fine-tuning from COCO weights learns new classes from very little data. Here, 68 labeled frames.
- **Nano** because inference runs on a 2019 Intel MacBook Pro CPU. Larger models would be too slow for playback.
- **Exported to ONNX and run with OpenCV's `cv2.dnn`**, so running the project needs only OpenCV and NumPy, not PyTorch. (PyTorch no longer ships builds for Intel Macs on Python 3.13.)

Training data: 853 frames were extracted from the video, 68 were labeled in [makesense.ai](https://www.makesense.ai) (labels in [labels/](labels/)), and split 56 train / 12 validation by video section rather than at random, so near-identical neighboring frames don't make the validation score look better than it is.

## How it works

```
video frame ─► detector.py ─► tracker.py ─► enter / exit events ─┬─► events.csv + terminal log
 (every 2nd    YOLOv8 ONNX     match boxes                       ├─► crops/ (snapshot of each object)
  frame)       + NMS           to tracks                         ├─► sonify.py ──OSC──► SuperCollider
                                                                 └─► on-screen boxes, counts, event list
```

1. **Read** a frame with `cv2.VideoCapture`.
2. **Detect** ([detector.py](detector.py)): resize to 640×640 into a blob, run the network, and decode its `(1, 11, 8400)` output: 8400 candidate boxes, each with 4 box values and 7 class scores. The highest score is the class and confidence; candidates under 0.5 are dropped. Boxes are scaled back to frame pixels, and per-class non-max suppression (`NMSBoxesBatched`) removes duplicates. The decoding is vectorized with NumPy, which made it about 100× faster than a Python loop. The model runs on every 2nd frame (`--detect-every`), and the boxes carry over in between.
3. **Track** ([tracker.py](tracker.py)): each detection is matched to the nearest existing track of the same class. A track is **confirmed** after 4 matches, which filters out one-off false positives, and **removed** after 8 detection runs without a match, which rides out brief motion blur. Confirming produces an `enter` event; removing a confirmed track produces an `exit` event.
4. **Act on events** ([main.py](main.py)): log them, save a crop, send OSC, and draw the result.
5. **No detections** are a normal case: the detector returns an empty list, the overlay shows *"No objects detected"*, and the summary says *"No objects were detected."* if nothing ever appears (covered by [tests/test_no_detections.py](tests/test_no_detections.py)).

## Custom behavior

### 1. Sonification with SuperCollider
[sonify.py](sonify.py) sends OSC messages to [supercollider/sonify.scd](supercollider/sonify.scd):

| Message | Sent when | Sound |
|---|---|---|
| `/detect/enter id class_id name x y size conf` | an object is confirmed | a bell at that object's note, panned to where it appeared, and a drone starts |
| `/detect/update id x y size conf` | every detection run, for each tracked object | the drone follows the object: **x → stereo pan, size → volume, height on screen → filter brightness** |
| `/detect/exit id class_id name seconds` | an object leaves | a softer bell an octave lower, and its drone fades out |
| `/detect/clear` | the program ends | all drones fade out |

Each class has its own note from a C-major pentatonic scale (Card C4, Key D4, Saint Christopher E4, Mary G4, Fob G3, …), so any combination of objects is consonant, and you can tell which object entered just by listening.

### 2. Tracking with IDs
Objects keep an ID (`Key #3`) while they stay on screen. A thick box means the object was seen in the latest detection run; a thin box means it's briefly lost and being held at its last position.

### 3. Event log, crops and analytics
- `output/events.csv`: every enter/exit with time, track ID, class, confidence, box, and how long the object was on screen.
- `output/crops/`: a cropped image of each object at the moment it was confirmed.
- `output/summary.txt`: appearances and total seconds on screen per class, also printed at the end.

## Install

Tested on macOS 15 (Intel) with Python 3.13 and SuperCollider 3.14.

```bash
git clone <repo-url>
cd object-sonifier
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For sound, install [SuperCollider](https://supercollider.github.io/downloads). It isn't needed to run detection (`--no-audio`).

## Run

**1. Start the sound engine.** Either open `supercollider/sonify.scd` in the SuperCollider IDE, click anywhere inside the outer parentheses and press **Cmd+Return**, or from a terminal:

```bash
/Applications/SuperCollider.app/Contents/MacOS/sclang supercollider/sonify.scd
```

Wait for `Object Sonifier ready, listening on port 57120`. If it reports a different port (for example 57121, because another SuperCollider instance already has 57120), pass that port with `--osc-port`.

**2. Run the detector** (in another terminal, with the virtual environment active):

```bash
python main.py
```

Press `q` or Esc to stop. Other ways to run it:

```bash
python main.py --no-audio                              # detection only, no SuperCollider
python main.py --no-display --save-video --no-audio    # render output/annotated.mp4 without a window
python main.py --video path/to/other.mov --conf 0.4    # another video / threshold
python main.py --detect-every 1                        # run the model on every frame (slower, smoother)
```

**Test** the "no objects" handling:

```bash
python tests/test_no_detections.py
```

## Sample output

From `python main.py --no-display --save-video --no-audio` on [videos/demo.mov](videos/demo.mov) (all in [samples/](samples/)):

```
[  0.20s] enter Card #1
[  1.33s] enter Tow- #2
[  1.53s] enter Key #3
...
[ 25.87s] enter Mary #28
[ 27.73s] exit  Mary #28 (1.7s on screen)

Summary of 28.4s of video
class                appearances   seconds on screen
Card                           2                 4.7
Fob                            1                 1.0
Key                            1                 1.0
Mary                           3                 8.8
Tow-                           2                 2.5
```

- [samples/demo_annotated.mp4](samples/demo_annotated.mp4): the annotated video (downscaled to 960×540)
- [samples/events.csv](samples/events.csv), [samples/summary.txt](samples/summary.txt), [samples/console_output.txt](samples/console_output.txt)
- [samples/crops/](samples/crops/): snapshots taken on each `enter`

## Reproducing the training

```bash
python tools/extract_frames.py videos/demo.mov frames/
# label frames in makesense.ai, export "YOLO" format, unzip into labels/
python tools/build_dataset.py frames/ labels/ dataset.zip
```

Then open [training/fine_tune_yolo.ipynb](training/fine_tune_yolo.ipynb) in Google Colab (T4 GPU), upload `dataset.zip`, and run all cells. It trains, shows validation metrics, and downloads `best.onnx`, `best.pt` and `classes.txt` for `model/`.

## Project structure

```
main.py                    entry point: video loop, events, drawing, logging, CLI
detector.py                YOLOv8 ONNX inference + output decoding with OpenCV DNN
tracker.py                 centroid tracker producing enter/exit events
sonify.py                  OSC messages to SuperCollider
supercollider/sonify.scd   synths and OSC handlers that make the sound
model/                     best.onnx (used), best.pt (for retraining), classes.txt
videos/demo.mov            demo input
labels/                    makesense.ai YOLO labels for the 68 training frames
tools/                     frame extraction and dataset building
training/                  Colab fine-tuning notebook
tests/                     no-detection test
samples/                   example output
```

## Limitations

- **Small dataset from one video.** 68 labeled frames is enough for the card and its number, but `Key`, `Fob` and the medals are missed often (for example, the key at the end of the demo), and `cotwo` and `Saint Christopher` (4–5 training boxes each) are effectively never detected. The model is also tuned to this room, lighting and camera, so it will generalize poorly.
- **Some false positives** remain: a hand or the fob is occasionally labeled `Mary`. The tracker's 4-hit confirmation removes the short ones.
- **HDR input.** The iPhone recorded HDR (HLG) video, which OpenCV decodes without tone mapping, so frames look washed out. The model was trained on those same frames, so it's consistent, but SDR footage would need converting or retraining.
- **Stretched input.** Frames are stretched to 640×640 rather than letterboxed as in training, which distorts shapes slightly.
- **Simple tracker.** Matching is per class by distance, so two identical objects crossing paths could swap IDs, and exits are reported ~0.5 s after the object is last seen.
- **Speed.** One model pass takes ~55 ms on a 2019 Intel MacBook Pro CPU, which is why it runs on every 2nd frame (about 50 fps processed without a window; with a window, playback is capped at the video's 30 fps). With `--detect-every 1` it falls below real time.

## Improvements I'd make

- Label more frames (especially keys, fob and the two medals) from several videos and lighting conditions, with hard examples like motion blur and partial views.
- Letterbox the input to match training, and try a 416×416 export for speed.
- Replace the centroid tracker with ByteTrack or an IoU/Kalman tracker.
- Run on a live webcam, and make the sonification richer: rhythm from object speed, or chords from which objects appear together.
