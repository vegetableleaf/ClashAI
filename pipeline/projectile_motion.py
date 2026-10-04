"""Causal, constant-closing-speed TTI estimate from public observations only.

Identity-free matching deliberately uses only a unique (card, side, target)
group in consecutive observations. Ambiguous, stationary, receding, new and
stale tracks remain unknown. No future disappearance, damage or command data
enters an estimate. Units are native board coordinates and 50-ms ticks.
"""
from collections import Counter
import math


class ProjectileMotion:
    def __init__(self, max_gap_ticks=20, catalog_fallback=False):
        self.max_gap_ticks = max_gap_ticks
        self.catalog_fallback = catalog_fallback
        self.reset()

    def reset(self):
        self.tick = None
        self.previous = {}
        self.current = {}

    @staticmethod
    def key(row):
        return tuple(row[:2]) + tuple(row[4:6])

    def update(self, observed, tick, stats=None):
        tick = int(tick)
        stats = stats if stats is not None else {}
        if self.tick is not None and tick < self.tick:
            self.reset()
        if tick != self.tick:
            self.previous = self.current
            self.tick = tick
        rows = observed['projectiles']
        counts = Counter(self.key(r) for r in rows)
        current = {}
        result = []
        for row in rows:
            key = self.key(row)
            values = tuple(row)
            if row[4] is None or row[5] is None:
                result.append(values)
                continue
            x, y, tx, ty = map(float, row[2:6])
            if not all(math.isfinite(v) for v in (x, y, tx, ty)):
                raise ValueError('Non-finite public projectile position')
            # R6: catalog distance/speed takes precedence on EVERY frame, not
            # just first sightings. Native recorded timers do not override it.
            if self.catalog_fallback:
                from .projectile_observation import catalog_tti
                ms = catalog_tti(row[0],x,y,tx,ty)
                values = (*row[:-1],ms)
                if ms is not None:
                    stats['projectiles_catalog_estimated'] = stats.get('projectiles_catalog_estimated',0)+1
            if counts[key] == 1:
                current[key] = (tick, x, y)
                old = self.previous.get(key)
                if values[-1] is None and old is not None:
                    dt = (tick-old[0])*.05
                    distance = math.hypot(tx-x, ty-y)
                    if 0 < tick-old[0] <= self.max_gap_ticks and distance > 0:
                        closing = ((x-old[1])*(tx-x)+(y-old[2])*(ty-y))/(dt*distance)
                        if closing > 1e-6:
                            ms = 1000*distance/closing
                            if math.isfinite(ms):
                                values = (*row[:-1], ms)
                                stats['projectiles_motion_estimated'] = stats.get('projectiles_motion_estimated', 0)+1
            result.append(values)
        self.current = current
        return dict(projectiles=result, effects=list(observed['effects']))
