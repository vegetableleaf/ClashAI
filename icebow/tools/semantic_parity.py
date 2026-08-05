"""Verify the claim clashrl/semantic.py is built on: the SIM raster and the LIVE raster are the same
tensor when they describe the same board.

"Identical by construction" is a design claim, and design claims rot. This script pins it down: it
builds a sim engine state, derives the detections a PERFECT detector would have produced from that same
state, renders both paths, and asserts the two arrays are bit-identical. If someone later changes a
footprint rule, a channel order, or a coordinate convention on one side only, this fails.

Run from icebow/:
    .venv/Scripts/python.exe tools/semantic_parity.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from clashrl import semantic
from clashrl.cards import CardDB
from clashrl.config import Config
from clashrl.sim.engine import SimEngine, build_spec


class FakeDet:
    """The Detection surface `LiveRaster` reads: base card, ground position, team tag."""

    def __init__(self, base, cx, gy, team):
        self.base, self.cx, self.gy, self.team = base, cx, gy, team


def main() -> int:
    cfg = Config.load(str(pathlib.Path(__file__).resolve().parent.parent / "config" / "config.yaml"))
    cfg.data.setdefault("observation", {})["obs_mode"] = "semantic"
    db = CardDB(cfg)
    import random

    rng = random.Random(11)
    eng = SimEngine(cfg, db, rng)
    eng.reset()

    # A board with both teams' troops and buildings, at asymmetric positions so any coordinate or
    # team-channel mix-up shows up as a difference rather than cancelling out.
    board = [(0, "knight", 0.30, 0.60), (0, "x_bow", 0.48, 0.58), (0, "skeletons", 0.62, 0.55),
             (1, "hog_rider", 0.28, 0.42), (1, "musketeer", 0.70, 0.30), (1, "tesla", 0.55, 0.25)]
    for team, base, x, y in board:
        spec = build_spec(db, base, 11)
        eng.elixir[team] = 10.0             # deploy() charges elixir; top it up so every unit lands
        if not eng.deploy(team, spec, x, y):
            print(f"FAIL: could not deploy {base} for team {team}")
            return 1
    # Damage a tower so the tower channels carry a NON-trivial HP fraction (a full-HP-only test would
    # pass even if one side ignored HP entirely).
    eng.towers[1][0].hp = eng.towers[1][0].max_hp * 0.37
    eng.towers[0][1].hp = eng.towers[0][1].max_hp * 0.72

    ow, oh = cfg.get("observation", "arena_size", default=[64, 96])
    oh, ow = int(oh), int(ow)

    # SIM path, with the detector-realism filter OFF so we compare the rasterizers, not the rng.
    sim = semantic.SimRaster(cfg, db, rng)
    sim.realism = False
    sim_obs = sim.render(eng, oh, ow, team=0)

    # LIVE path, fed the detections a perfect detector would have reported for that same board.
    live = semantic.LiveRaster(cfg, db)
    dets = [FakeDet(getattr(u.spec, "base", None), u.x, u.y, "mine" if u.team == 0 else "enemy")
            for u in eng.units if u.hp > 0 and getattr(u.spec, "base", None)]
    my_full = eng.towers[0][0].max_hp
    en_full = eng.towers[1][0].max_hp
    live_obs = live.render(
        dets,
        [t.hp for t in eng.towers[0]], my_full, [t.alive for t in eng.towers[0]],
        [t.hp for t in eng.towers[1]], en_full, [t.alive for t in eng.towers[1]],
        oh, ow)

    ok = True
    if sim_obs.shape != live_obs.shape:
        print(f"FAIL shape: sim {sim_obs.shape} vs live {live_obs.shape}")
        return 1
    for c, name in enumerate(semantic.CHANNELS):
        a, b = sim_obs[:, :, c], live_obs[:, :, c]
        same = np.array_equal(a, b)
        ok &= same
        print(f"  {'ok  ' if same else 'FAIL'} ch{c} {name:<16} "
              f"sim nz={int((a > 0).sum()):5d} live nz={int((b > 0).sum()):5d} "
              f"max|diff|={int(np.abs(a.astype(int) - b.astype(int)).max())}")
    nonempty = sum(int((sim_obs[:, :, c] > 0).any()) for c in range(semantic.N_CHANNELS))
    if nonempty < semantic.N_CHANNELS:
        print(f"FAIL: only {nonempty}/{semantic.N_CHANNELS} channels carry signal -- the test board must "
              "exercise every channel or parity is vacuous for the empty ones")
        ok = False
    print("PARITY OK -- sim and live rasters are bit-identical" if ok else "PARITY FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
