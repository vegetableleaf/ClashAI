"""TROOP INTERACTION PREDICTOR -- who is moving toward whom, derived (not learned) from Clash Royale's
deterministic targeting rules: a BUILDING-TARGETER ignores troops and goes for the nearest enemy
building/tower; any other troop locks the nearest ATTACKABLE enemy unit inside its sight range (a
ground-only attacker cannot take an air target), else it marches at the nearest alive enemy tower.

Because the rule is known, no model is needed -- the same pure functions run on the SIM's ground-truth
units and on LIVE detector tracks (the sim/live dual-source pattern). The policy-facing summary is a
FIXED-WIDTH 12-dim block (`interaction_vector`): for each of your 3 towers (L princess, R princess,
king) the incoming elixir-VALUE predicted to be heading at it and an URGENCY (nearest attacker's ETA),
then the same 6 dims for YOUR units heading at the ENEMY's towers. Units engaging other units light no
tower dim (they're occupied) -- exactly the "is anything coming for my tower, how much, how soon" read.

Limitations (documented, deliberate): invisibility/cloak isn't modelled (no KB flag), stationary
buildings are skipped as movers (an X-Bow's siege pressure reaches the policy via the wincon/CNN
channels), and kiting/retarget micro is beyond a nearest-target model. Coarse but honest -- the same
approximation a human makes at a glance.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import numpy as np

from . import card_threat

INTERACTION_DIM = 12          # (value, urgency) x my 3 towers + (value, urgency) x enemy 3 towers

# speed word -> normalized units/second (matches sim/engine._SPEED)
_SPEED = {"slow": 0.023, "medium": 0.031, "fast": 0.047, "very_fast": 0.063}

Unit = Tuple[str, str, float, float]          # (team 'mine'|'enemy', base_card, x, y) normalized
Tower = Tuple[float, float, bool]             # (x, y, alive)
Target = Tuple[Optional[str], int, float]     # (kind 'unit'|'tower'|None, index, distance)


def predict_targets(units: Sequence[Unit], my_towers: Sequence[Tower],
                    enemy_towers: Sequence[Tower], db, sight_range: float = 0.12) -> List[Target]:
    """Predicted target per unit, by CR's targeting rules. ``my_towers``/``enemy_towers`` are each the
    3 (x, y, alive) towers of that side in the SAME frame as the units ('mine' units attack toward
    ``enemy_towers`` and vice versa). Spells get (None, -1, 0)."""
    out: List[Target] = []
    for i, (team, base, x, y) in enumerate(units):
        p = card_threat.profile(db, base)
        if p.spell:
            out.append((None, -1, 0.0))
            continue
        foe_team = "enemy" if team == "mine" else "mine"
        towers = enemy_towers if team == "mine" else my_towers
        best: Optional[Target] = None
        if p.building_targeting:                      # ignores troops: nearest enemy BUILDING unit...
            for j, (ft, fb, fx, fy) in enumerate(units):
                if ft != foe_team or card_threat.profile(db, fb).kind != "building":
                    continue
                d = math.hypot(x - fx, y - fy)
                if best is None or d < best[2]:
                    best = ("unit", j, d)
        else:                                         # nearest ATTACKABLE foe inside sight range
            for j, (ft, fb, fx, fy) in enumerate(units):
                if ft != foe_team:
                    continue
                fp = card_threat.profile(db, fb)
                if fp.spell or (fp.flying and not p.attacks_air):
                    continue
                d = math.hypot(x - fx, y - fy)
                if d <= sight_range and (best is None or d < best[2]):
                    best = ("unit", j, d)
        # nearest alive enemy tower = the march target
        tbest: Optional[Target] = None
        for k, (tx, ty, alive) in enumerate(towers):
            if not alive:
                continue
            d = math.hypot(x - tx, y - ty)
            if tbest is None or d < tbest[2]:
                tbest = ("tower", k, d)
        if p.building_targeting:                      # building-targeter: nearest of {building unit, tower}
            if tbest is not None and (best is None or tbest[2] < best[2]):
                best = tbest
        elif best is None:                            # no foe in sight range -> march at the tower
            best = tbest
        out.append(best if best is not None else (None, -1, 0.0))
    return out


def interaction_vector(units: Sequence[Unit], my_towers: Sequence[Tower],
                       enemy_towers: Sequence[Tower], db, sight_range: float = 0.12,
                       value_norm: float = 8.0, eta_norm: float = 10.0) -> np.ndarray:
    """The policy-facing 12-dim TOWER-PRESSURE summary. dims [0..5] = per MY tower (L, R, king):
    [incoming enemy elixir-value / value_norm (clipped 1), URGENCY = 1 - nearest_eta/eta_norm (0 =
    nothing within ~eta_norm s)]; dims [6..11] = the same for MY units heading at ENEMY towers.
    Units predicted to fight another UNIT light nothing (engaged); stationary buildings are skipped."""
    v = np.zeros(INTERACTION_DIM, np.float32)
    for (team, base, x, y), (kind, k, dist) in zip(units, predict_targets(units, my_towers,
                                                                          enemy_towers, db, sight_range)):
        if kind != "tower" or not (0 <= k < 3):
            continue
        c = db.get(base) or {}
        if card_threat.profile(db, base).kind == "building":
            continue                                   # buildings don't march (siege shows elsewhere)
        value = float(c.get("elixir") or 4) / max(1, int(c.get("count") or 1))
        eta = dist / max(1e-6, _SPEED.get(c.get("speed"), 0.031))
        off = 0 if team == "enemy" else 6              # enemy -> pressure ON MY towers; mine -> on theirs
        v[off + 2 * k] = min(1.0, v[off + 2 * k] + value / value_norm)
        v[off + 2 * k + 1] = max(v[off + 2 * k + 1], max(0.0, 1.0 - eta / eta_norm))
    return v
