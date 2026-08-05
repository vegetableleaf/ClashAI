"""Continuous ~10 Hz perception loop: grab -> detect -> team-track in a background thread.

The act loop (env.step / play) only LOOKS at the world when it decides -- at 1 Hz the model is
blind for up to a second between decisions, and every tracker velocity is sampled at that coarse
cadence. This loop decouples sense from act: a daemon thread runs the detector continuously and
keeps the TeamTracker current, so at decision time the policy reads a snapshot that is at most one
perception period old (~100 ms at 10 Hz), and track velocities (the rocket-lead assist, the motion
team evidence) are estimated from fine-grained motion instead of act-cadence deltas.

Threading contract: the loop OWNS the detector calls and the tracker's tag() (single consumer of
the torch model). The env/play thread interacts only through the lock-guarded passthroughs
(record_play / set_towers / snapshot / enemy_tracks). The loop owns a PRIVATE WindowCapture --
mss handles are per-thread (same pattern as the monitor + preview threads).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional


class PerceptionLoop:
    def __init__(self, cfg, detector, tracker, conf: float, hz: float = 10.0,
                 preview=None, cap_factory=None):
        self._detector = detector
        self._tracker = tracker
        self._conf = float(conf)
        self.hz = min(20.0, max(1.0, float(hz)))
        self._preview = preview                     # LivePreview: fed per pass -> near-realtime boxes
        self._cap_factory = cap_factory             # test hook; default = own WindowCapture from cfg
        self._title = cfg.get("window", "title_contains", default=None)
        self._region_cfg = cfg.get("window", "region", default=None)
        self._lock = threading.Lock()
        self._dets: list = []
        self._t = 0.0                                # wall time of the latest completed pass
        self._region = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # NEW-ENEMY EVENT: set when a pass sees MORE enemy detections than any pass in the last ~1.5s
        # (a rising count = a genuinely new commitment; a unit blinking out and back in returns to a
        # RECENT level, so detector flicker at ~0.6 recall never fires it). The act loop waits on this
        # to react the moment something happens instead of sleeping out its full act period.
        self._event = threading.Event()
        self._cnt_hist: deque = deque()              # (t, enemy_det_count) history, ~3s

    # -- lifecycle ----------------------------------------------------
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="clashrl-perception", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    # -- act-loop interface (lock-guarded) ------------------------------
    def snapshot(self):
        """(tagged detections, age_seconds) of the latest perception pass."""
        with self._lock:
            return list(self._dets), (time.time() - self._t if self._t else float("inf"))

    def record_play(self, x: float, y: float, t: float, base=None) -> None:
        with self._lock:
            self._tracker.record_play(x, y, t, base=base)

    def set_towers(self, mine_alive, enemy_alive) -> None:
        with self._lock:
            self._tracker.set_towers(mine_alive, enemy_alive)

    def enemy_tracks(self, now: float):
        with self._lock:
            return self._tracker.enemy_tracks(now)

    def reset_tracker(self) -> None:
        with self._lock:
            self._tracker.reset()
            self._dets = []
        self._cnt_hist.clear()
        self._event.clear()

    # -- event-driven acting ---------------------------------------------
    def wait_event(self, period: float, min_gap: float = 0.3) -> bool:
        """Sleep like ``time.sleep(period)`` but WAKE EARLY when perception spots a new enemy
        commitment -- reaction latency collapses from one act period to ~one perception period +
        inference. ``min_gap`` is always slept first (rate limit: no decision thrash; events during
        it coalesce into one wake). Returns True when woken by an event."""
        time.sleep(max(0.0, min(min_gap, period)))
        left = period - min_gap
        if left > 0:
            fired = self._event.wait(timeout=left)
        else:
            fired = self._event.is_set()
        self._event.clear()
        return fired

    def consume_event(self) -> bool:
        """Non-blocking event check (play's poll loop): True at most once per event."""
        if self._event.is_set():
            self._event.clear()
            return True
        return False

    # -- the loop -------------------------------------------------------
    def _run(self) -> None:
        try:
            if self._cap_factory is not None:
                cap = self._cap_factory()
            else:
                from .capture import WindowCapture
                cap = WindowCapture(self._title, self._region_cfg)
        except Exception:
            self._stop.set()
            return
        period = 1.0 / self.hz
        while not self._stop.is_set():
            t0 = time.time()
            try:
                frame = cap.grab()
                if frame is None:
                    cap.refresh_region()
                    time.sleep(0.5)
                    continue
                self._region = getattr(cap, "region", None)
                dets = self._detector.detect(frame, conf=self._conf)
                now = time.time()
                with self._lock:
                    self._tracker.tag(dets, now)         # evidence fusion at perception rate
                    self._dets = dets
                    self._t = now
                # rising enemy-count edge (vs the recent window) = a NEW commitment -> wake the act loop
                n_enemy = sum(1 for d in dets if d.team == "enemy")
                recent = [c for (tt, c) in self._cnt_hist if now - tt <= 1.5]
                if n_enemy > (max(recent) if recent else 0):
                    self._event.set()
                self._cnt_hist.append((now, n_enemy))
                while self._cnt_hist and now - self._cnt_hist[0][0] > 3.0:
                    self._cnt_hist.popleft()
                if self._preview is not None:             # boxes now refresh at perception rate
                    self._preview.update(None, dets, self._region)
            except Exception:
                time.sleep(0.5)                           # transient (window minimized etc.) -> keep trying
            time.sleep(max(0.0, period - (time.time() - t0)))
