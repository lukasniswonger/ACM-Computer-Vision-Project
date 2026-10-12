"""Sends tracker events to SuperCollider over OSC. The receiving side is supercollider/sonify.scd."""
import math

from pythonosc.udp_client import SimpleUDPClient


class Sonifier:
    """
    OSC messages (positions are normalized to 0-1, size is sqrt(box area / frame area)):
        /detect/enter   track_id class_id class_name x y size confidence
        /detect/update  track_id x y size confidence
        /detect/exit    track_id class_id class_name seconds_on_screen
        /detect/clear

    Every message is also kept in `score` with the video time it belongs to (set `time` before
    sending), so the same sound can be rendered offline in sync with the video (see preview.py).
    """

    def __init__(self, host="127.0.0.1", port=57120, send=True):
        self.client = SimpleUDPClient(host, port) if send else None
        self.score = []  # (video_time, address, args)
        self.time = 0.0

    def _send(self, address, args):
        self.score.append((self.time, address, args))
        if self.client is None:
            return
        # UDP is fire-and-forget: if SuperCollider isn't running, the message is simply dropped
        try:
            self.client.send_message(address, args)
        except OSError:
            pass

    @staticmethod
    def _position(track, frame_size):
        frame_w, frame_h = frame_size
        cx, cy = track.center
        w, h = track.box[2], track.box[3]
        size = math.sqrt((w * h) / (frame_w * frame_h))
        return [cx / frame_w, cy / frame_h, size]

    def enter(self, track, frame_size):
        x, y, size = self._position(track, frame_size)
        self._send("/detect/enter", [track.track_id, track.class_id, track.class_name, x, y, size, track.confidence])

    def update(self, tracks, frame_size):
        for t in tracks:
            x, y, size = self._position(t, frame_size)
            self._send("/detect/update", [t.track_id, x, y, size, t.confidence])

    def exit(self, track, seconds):
        self._send("/detect/exit", [track.track_id, track.class_id, track.class_name, float(seconds)])

    def clear(self):
        self._send("/detect/clear", [])
