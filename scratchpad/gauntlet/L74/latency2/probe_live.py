"""SUPERVISED live probe for live_play --follow-up-taps (L74 latency2). NOT run by anything; the lead schedules it.

The infrastructure has no producer yet (the Rocket+Tornado decision logic belongs to the rocket-clump worker), so a live test
needs one: this wraps the deployed GenPilot and, at a few quiet moments, replaces "wait" with TWO cheap plays on my own half --
A now, B planned `--probe-after` game ticks later -- exactly the shape the combo will use. Everything else (flags, model, gate,
logging) is the deployed path.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/latency2/probe_live.py [--probe-every S] [--probe-after T] \
        [--probe-max N] -- <the live_play.py arguments of the test run>

A probe fires only when: the model itself has no play this decision, game tick >= 600, >= --probe-every game seconds since the
last probe, at most --probe-max per match, two different hand slots hold plain base-form cards costing <= 3 that are neither
buildings nor Mirror, and my elixir covers both costs plus 2 spare. Cells: my own half, left and right of the bridge lanes.
Read the result with analyze_probe.py. Runs the same live_play.main(), so --dry-run / --check work as usual.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIVE = REPO / "scratchpad/gauntlet/L68/live_reader"
sys.path.insert(0, str(LIVE))
sys.path.insert(0, str(REPO))

NOT_PROBED = {"cannon", "tesla", "xbow", "x-bow", "mortar", "tombstone", "furnace", "bomb tower", "inferno tower",
              "goblin cage", "goblin hut", "barbarian hut", "elixir collector", "mirror"}
CELL_A, CELL_B = (0.30, 0.62), (0.70, 0.62)          # my-frame (x, y): y 0.62 = tile 19.8, my half is y >= 0.5


def probe_plan(pilot, frame, d, state, *, after_ticks=4, every_s=45.0, max_probes=6, max_cost=3.0, spare=2.0):
    """The decision dict ``d`` the pilot just made -> the probe's replacement (A with follow_ups=[B]) or None."""
    from pipeline.live_gen_v2 import my_side_of
    from pipeline.live_mem import deck_of
    from live_play import card_cost_of
    tick = int(frame["game_tick"])
    if d.get("play") or tick < 600 or state["n"] >= max_probes or tick - state["last"] < every_s * 20:
        return None
    side = my_side_of(frame)
    me = next(p for p in frame["players"] if int(p["side"]) == side)
    _, names = deck_of(frame, side)
    forms = list(me.get("deck_form_flags") or [0] * 8)
    opts = []
    for pos, di in enumerate(me["hand_deck_indices"]):
        if di < 0 or int(forms[di]) != 0 or str(names[di]).lower() in NOT_PROBED:
            continue
        cost = card_cost_of(names[di])
        if 0 < cost <= max_cost:
            opts.append((cost, pos, di))
    if len(opts) < 2 or me["elixir_raw"] / 1e4 < sum(c for c, _, _ in sorted(opts)[:2]) + spare:
        return None
    (_, pa, da), (_, pb, db) = sorted(opts)[:2]
    a = dict(d, play=True, no_affordable=False, hand_pos=pa, deck_index=int(da), card=pilot._card(names[da]),
             form=int(forms[da]), name=names[da], xy=CELL_A, probe=True)
    fu = pilot.plan_follow_up(frame, a, names[db], CELL_B, after_ticks=after_ticks)
    if fu is None:
        return None
    a["follow_ups"] = [fu]
    state["n"] += 1
    state["last"] = tick
    return a


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe-every", type=float, default=45.0, help="game seconds between probes (default 45)")
    ap.add_argument("--probe-after", type=int, default=4, help="ticks between the two decisions (default 4)")
    ap.add_argument("--probe-max", type=int, default=6, help="probes per match (default 6)")
    ap.add_argument("--probe-spare", type=float, default=2.0, help="elixir kept after both plays (default 2)")
    args, rest = ap.parse_known_args()
    if rest and rest[0] == "--":
        rest = rest[1:]
    if "--follow-up-taps" not in rest:
        rest.append("--follow-up-taps")
    import live_play as lp
    from pipeline.live_gen_v2 import GenPilot as Real

    class ProbePilot(Real):
        def reset_match(self):
            super().reset_match()
            self._probe = dict(n=0, last=-10 ** 9)

        def decide(self, frame):
            d = super().decide(frame)
            if not hasattr(self, "_probe"):
                self._probe = dict(n=0, last=-10 ** 9)
            return probe_plan(self, frame, d, self._probe, after_ticks=args.probe_after, every_s=args.probe_every,
                              max_probes=args.probe_max, spare=args.probe_spare) or d

    lp.GenPilot = ProbePilot
    sys.argv = [str(LIVE / "live_play.py")] + rest
    return lp.main()


if __name__ == "__main__":
    raise SystemExit(main())
