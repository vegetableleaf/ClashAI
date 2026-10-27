"""F1b: the hand cycle on crforge vs RoyaleSim fin16 for the same deal and the same plays.

Per census match: both engines get the setup's deal (ShuffleMode.NONE); every 60 ticks side s plays hand slot k (a
seeded draw) at its own back corner; after each accepted play both are stepped 60 ticks (crforge runs it 20 ticks
after the act; both refill by then) and (hand, next) of both sides are compared.
usage: ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I hand_cycle.py --n 30
"""
import argparse
import json
import os
import random
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", "/workspace/f1/cb", "/workspace/f1"]
import accept_f1 as A  # noqa: E402
from pipeline import royale_heroiw as heroiw  # noqa: E402
from pipeline.crforge_core import CrforgeCore  # noqa: E402
from royalegym.protocol import DeployCommand, DeployStatus  # noqa: E402
from royalegym.rust_engine import RustEngine  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=30)
a = ap.parse_args()
pairs, out = A.census(), []
for i in range(a.n):
    cf, rs = CrforgeCore(), RustEngine(**heroiw.engine_options())
    pair = pairs[(3 * i) % len(pairs)]
    setup = A.setup(cf, pair)
    try:
        rs.reset(i, setup)
    except ValueError:                                           # a form fin16 does not load
        continue
    cf.reset(i, setup)
    rs.step([], 90)
    cf.step([], 90)
    rng, plays, same = random.Random(i), 0, 0
    first_diff = None
    while plays < 30 and not cf.state().game_over and not rs.state().game_over:
        side, slot = rng.randrange(2), rng.randrange(4)
        cmd = DeployCommand(side, slot, 18 * rng.choice((1500, 16500)), 18 * (1500 if side == 0 else 30500))
        r_cf, = cf.step([cmd], 0)
        r_rs, = rs.step([cmd], 0)
        cf.step([], 60)
        rs.step([], 60)
        if r_cf.status != DeployStatus.OK or r_rs.status != DeployStatus.OK:
            if (r_cf.status == DeployStatus.OK) != (r_rs.status == DeployStatus.OK):
                break                                            # one engine refused (elixir / placement): stop here
            continue
        plays += 1
        hc = [(p.hand, p.next_card) for p in cf.state().players]
        hr = [(p.hand, p.next_card) for p in rs.state().players]
        same += hc == hr
        if hc != hr and first_diff is None:
            first_diff = dict(play=plays, cf=hc, rs=hr)
    out.append(dict(i=i, plays=plays, hands_equal=same, first_diff=first_diff))
print(json.dumps(dict(matches=len(out), plays=sum(r["plays"] for r in out), equal=sum(r["hands_equal"] for r in out),
                      diffs=[r for r in out if r["first_diff"]][:3])))
