"""Small centroid tracker that turns per-frame detections into objects that enter and leave the scene."""
import math
from dataclasses import dataclass


@dataclass
class Track:
    track_id: int
    class_id: int
    class_name: str
    box: tuple
    confidence: float
    first_frame: int
    last_frame: int
    hits: int = 1
    misses: int = 0
    confirmed: bool = False

    @property
    def center(self):
        left, top, w, h = self.box
        return left + w / 2, top + h / 2


@dataclass
class Event:
    kind: str  # "enter" or "exit"
    track: Track
    frame_index: int


class Tracker:
    """
    Matches each detection to the nearest existing track of the same class.

    A track only counts as a real object once it has been matched `confirm_hits` times,
    which filters out one-frame false positives. It is removed after `max_misses`
    detection runs in a row without a match, which rides out short dropouts.
    """

    def __init__(self, confirm_hits=4, max_misses=8, max_distance=0.15):
        self.confirm_hits = confirm_hits
        self.max_misses = max_misses
        self.max_distance = max_distance  # as a fraction of the frame diagonal
        self.tracks = []
        self.next_id = 1

    def update(self, detections, frame_index, frame_size):
        """Update tracks with this frame's detections and return the enter/exit events it caused."""
        frame_w, frame_h = frame_size
        max_dist = self.max_distance * math.hypot(frame_w, frame_h)
        events = []

        # Greedy matching: closest same-class (track, detection) pairs first
        pairs = []
        for t in self.tracks:
            for d_index, d in enumerate(detections):
                if t.class_id == d.class_id:
                    dist = math.dist(t.center, d.center)
                    if dist <= max_dist:
                        pairs.append((dist, t, d_index))
        pairs.sort(key=lambda p: p[0])

        matched_tracks, matched_detections = set(), set()
        for _, t, d_index in pairs:
            if t.track_id in matched_tracks or d_index in matched_detections:
                continue
            matched_tracks.add(t.track_id)
            matched_detections.add(d_index)
            d = detections[d_index]
            t.box, t.confidence = d.box, d.confidence
            t.last_frame = frame_index
            t.hits += 1
            t.misses = 0
            if not t.confirmed and t.hits >= self.confirm_hits:
                t.confirmed = True
                events.append(Event("enter", t, frame_index))

        # Unmatched tracks: count a miss, drop them once they've been gone too long
        survivors = []
        for t in self.tracks:
            if t.track_id not in matched_tracks:
                t.misses += 1
                if t.misses > self.max_misses:
                    if t.confirmed:
                        events.append(Event("exit", t, frame_index))
                    continue
            survivors.append(t)
        self.tracks = survivors

        # Unmatched detections start new (unconfirmed) tracks
        for d_index, d in enumerate(detections):
            if d_index not in matched_detections:
                self.tracks.append(
                    Track(self.next_id, d.class_id, d.class_name, d.box, d.confidence, frame_index, frame_index)
                )
                self.next_id += 1

        return events

    def flush(self, frame_index):
        """End of input: close every confirmed track so it gets an exit event."""
        events = [Event("exit", t, frame_index) for t in self.tracks if t.confirmed]
        self.tracks = []
        return events

    @property
    def confirmed_tracks(self):
        return [t for t in self.tracks if t.confirmed]
