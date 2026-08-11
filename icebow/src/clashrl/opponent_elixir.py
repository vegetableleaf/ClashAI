"""Opponent elixir inference from observable card-play events.

Live play cannot read the enemy elixir bar directly. This tracker follows the deterministic
relationship

    enemy_elixir ~= my_elixir + my_spend - enemy_spend

where my_elixir is read from OCR, my_spend is known from our own plays, and enemy_spend is inferred
from newly observed enemy card appearances.

The event detector is intentionally simple and robust: enemy detections are matched to short-lived
tracks by (base card, proximity) so one long-lived unit is not charged repeatedly, and clustered on
spawn so swarm cards are charged once per play rather than once per body.
"""
from __future__ import annotations

from typing import Iterable, List


class OpponentElixirEstimator:
    def __init__(self, db, match_radius: float = 0.07, cluster_radius: float = 0.10,
                 forget_s: float = 6.0):
        self.db = db
        self.match_radius = float(match_radius)
        self.cluster_radius = float(cluster_radius)
        self.forget_s = float(forget_s)
        self.reset()

    def reset(self, my_elixir: float = 5.0, now: float | None = None) -> None:
        self._my_spent = 0.0
        self._opp_spent = 0.0
        self._tracks: list[dict] = []      # {base, x, y, t}
        self._est = float(max(0.0, min(10.0, my_elixir)))
        self._last_t = float(now) if now is not None else None

    def record_my_play(self, base: str) -> None:
        c = float(self.db.elixir(base) or 0.0)
        if c > 0.0:
            self._my_spent += c

    def _seen_tracks(self, now: float) -> None:
        self._tracks = [tr for tr in self._tracks if now - tr["t"] <= self.forget_s]

    def _find_track(self, base: str, x: float, y: float):
        best = None
        best_d2 = self.match_radius * self.match_radius
        for tr in self._tracks:
            if tr["base"] != base:
                continue
            dx = x - tr["x"]
            dy = y - tr["y"]
            d2 = dx * dx + dy * dy
            if d2 <= best_d2:
                best, best_d2 = tr, d2
        return best

    def _cluster_new(self, fresh: List[tuple[str, float, float]]) -> List[tuple[str, float, float]]:
        """Cluster new detections by base + proximity so swarms cost one card play, not N bodies."""
        out = []
        rem = list(fresh)
        r2 = self.cluster_radius * self.cluster_radius
        while rem:
            base, x, y = rem.pop()
            xs, ys, n = x, y, 1
            keep = []
            for b2, x2, y2 in rem:
                if b2 != base:
                    keep.append((b2, x2, y2))
                    continue
                dx = x2 - x
                dy = y2 - y
                if dx * dx + dy * dy <= r2:
                    xs += x2
                    ys += y2
                    n += 1
                else:
                    keep.append((b2, x2, y2))
            rem = keep
            out.append((base, xs / n, ys / n))
        return out

    def update(self, my_elixir: float, enemy_dets: Iterable, now: float) -> float:
        """Return normalized estimated enemy elixir in [0, 1].

        enemy_dets should contain detections with `.base`, `.cx`, `.gy`, and `.team` where team is
        already resolved to "enemy"/"mine".
        """
        now = float(now)
        self._seen_tracks(now)

        fresh = []
        for d in enemy_dets:
            if getattr(d, "team", None) != "enemy":
                continue
            base = str(getattr(d, "base", "") or "")
            if not base:
                continue
            x = float(getattr(d, "cx", 0.5))
            y = float(getattr(d, "gy", 0.5))
            tr = self._find_track(base, x, y)
            if tr is not None:
                tr["x"], tr["y"], tr["t"] = x, y, now
            else:
                fresh.append((base, x, y))

        for base, x, y in self._cluster_new(fresh):
            self._tracks.append({"base": base, "x": x, "y": y, "t": now})
            c = float(self.db.elixir(base) or 0.0)
            if c > 0.0:
                self._opp_spent += c

        est = float(my_elixir) + self._my_spent - self._opp_spent
        self._est = max(0.0, min(10.0, est))
        self._last_t = now
        return self._est / 10.0
