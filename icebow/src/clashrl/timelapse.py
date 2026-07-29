"""Fixed-length training timelapse.

Collects gameplay frames while ``train-rl`` runs and writes an mp4 that is ALWAYS the
same length -- ``seconds`` long at ``fps`` (default 30 s at 30 fps = exactly 900 frames) --
no matter how long training lasts. However many frames are captured, they are resampled to
exactly ``seconds * fps`` frames on save, so a 5-minute run and a 5-hour run both produce a
30-second timelapse.

To keep memory bounded over a long run, frames are stored JPEG-compressed and thinned
(drop every other one) whenever the buffer grows past twice the target, which also keeps the
kept frames spread evenly across the whole session.
"""
from __future__ import annotations

from pathlib import Path

import cv2


class TimelapseRecorder:
    def __init__(self, path, seconds: float = 30.0, fps: int = 30,
                 width: int = 640, quality: int = 70):
        self.path = Path(path)
        self.fps = max(1, int(fps))
        self.seconds = float(seconds)
        self.target = max(1, int(round(self.seconds * self.fps)))   # frames in the final video
        self.width = int(width)
        self.quality = int(quality)
        self._buf: list = []        # JPEG-encoded frames, spread evenly over the run
        self._interval = 1          # keep 1 of every `_interval` candidate frames
        self._seen = 0              # candidate frames offered

    def add(self, frame) -> None:
        """Offer one gameplay frame (called once per training step)."""
        if frame is None:
            return
        self._seen += 1
        if self._seen % self._interval != 0:        # thinning: skip most candidates
            return
        h, w = frame.shape[:2]
        if w != self.width and w > 0:
            frame = cv2.resize(frame, (self.width, max(1, round(h * self.width / w))),
                               interpolation=cv2.INTER_AREA)
        ok, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        if not ok:
            return
        self._buf.append(enc)
        if len(self._buf) >= self.target * 2:        # bound memory + keep even time coverage
            self._buf = self._buf[::2]
            self._interval *= 2

    def save(self):
        """Write EXACTLY ``target`` frames (subsampled if more were captured, duplicated if
        fewer) at ``fps`` -> an mp4 that is always ``seconds`` long. Returns the path, or
        None if nothing was captured / the writer couldn't open."""
        if not self._buf:
            return None
        n = len(self._buf)
        if self.target == 1:
            idx = [0]
        else:                                        # even resample onto exactly `target` slots
            idx = [min(n - 1, int(round(i * (n - 1) / (self.target - 1)))) for i in range(self.target)]
        first = cv2.imdecode(self._buf[0], cv2.IMREAD_COLOR)
        if first is None:
            return None
        h, w = first.shape[:2]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        vw = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (w, h))
        if not vw.isOpened():
            return None
        for j in idx:
            f = cv2.imdecode(self._buf[j], cv2.IMREAD_COLOR)
            if f is not None:
                vw.write(f)
        vw.release()
        return self.path

    @property
    def seen(self) -> int:
        return self._seen
