"""YOLOv8 object detector running a fine-tuned ONNX model through OpenCV's DNN module."""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    box: tuple  # (left, top, width, height) in frame pixels

    @property
    def center(self):
        left, top, w, h = self.box
        return left + w / 2, top + h / 2


class Detector:
    def __init__(self, model_path, classes_path, input_size=640, conf_threshold=0.5, nms_threshold=0.45):
        self.net = cv2.dnn.readNetFromONNX(model_path)
        with open(classes_path) as f:
            self.class_names = [line.strip() for line in f if line.strip()]
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold

    def detect(self, frame):
        """Return a list of Detections for one BGR frame (empty list if nothing is found)."""
        frame_h, frame_w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (self.input_size, self.input_size), swapRB=True, crop=False)
        self.net.setInput(blob)

        # (1, 4 + num_classes, 8400) -> (8400, 4 + num_classes): one row per candidate box
        predictions = self.net.forward()[0].T

        # YOLOv8 has no objectness score: the best class score is the confidence
        scores = predictions[:, 4:]
        class_ids = scores.argmax(axis=1)
        confidences = scores.max(axis=1)

        keep = confidences >= self.conf_threshold
        if not keep.any():
            return []
        predictions, class_ids, confidences = predictions[keep], class_ids[keep], confidences[keep]

        # Center boxes in input-size space -> top-left boxes in frame pixels
        x_scale = frame_w / self.input_size
        y_scale = frame_h / self.input_size
        cx, cy, w, h = predictions[:, :4].T
        boxes = np.stack([(cx - w / 2) * x_scale, (cy - h / 2) * y_scale, w * x_scale, h * y_scale], axis=1)
        boxes = boxes.round().astype(int)

        # Per-class NMS, so a Key overlapping a Fob doesn't suppress it
        indices = cv2.dnn.NMSBoxesBatched(
            boxes.tolist(), confidences.tolist(), class_ids.tolist(), self.conf_threshold, self.nms_threshold
        )

        detections = []
        for i in np.array(indices).flatten():
            left, top, bw, bh = boxes[i]
            # Clip to the frame so crops and drawing never go out of bounds
            left, top = max(0, left), max(0, top)
            bw, bh = min(bw, frame_w - left), min(bh, frame_h - top)
            if bw <= 0 or bh <= 0:
                continue
            class_id = int(class_ids[i])
            detections.append(
                Detection(class_id, self.class_names[class_id], float(confidences[i]), (int(left), int(top), int(bw), int(bh)))
            )
        return detections
