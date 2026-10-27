"""F1b: crforge's elixir regen per tick, by phase, vs opp_elixir_count.REGEN_SCHEDULE and royale_env.REGEN_SCHEDULE.

Census matches on CrforgeCore, both seats playing a random hand card at their own back corner every 10 ticks when
they can (keeps elixir under the cap). A tick's regen = elixir_milli(t+1) - elixir_milli(t) on ticks where it rose and
the side is below 9,500 milli and no play of the side ran in it (a run takes elixir). Mean by phase [from, to).
usage: ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I regen_probe.py --n 40 --out out/regen.json
"""
import argparse
import json
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", "/workspace/f1/cb", "/workspace/f1"]
import accept_f1 as A  # noqa: E402
from pipeline.crforge_core import CrforgeCore  # noqa: E402
from pipeline.opp_elixir_count import REGEN_SCHEDULE as REAL  # noqa: E402
from royalegym.protocol import DeployCommand  # noqa: E402

PHASES = ((0, 2400), (2400, 3600), (3600, 4800), (4800, 6200))
ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=40)
ap.add_argument("--out", required=True)
a = ap.parse_args()
pairs = A.census()
acc = {p: [0, 0] for p in PHASES}        # sum milli, ticks
ends = []
for i in range(a.n):
    c = CrforgeCore()
    c.reset(500 + i, A.setup(c, pairs[i % len(pairs)]))
    rng = random.Random(i)
    prev = c.state()
    while not prev.game_over:
        t = prev.tick
        cmds = []
        if t % 10 == 0:
            for side in (0, 1):
                y = 1500 if side == 0 else 30500
                cmds.append(DeployCommand(side, rng.randrange(4), 18 * rng.choice((1500, 16500)), 18 * y))
        c.step(cmds, 1)
        st = c.state()
        for s in (0, 1):
            d = st.players[s].elixir_milli - prev.players[s].elixir_milli
            if d > 0 and prev.players[s].elixir_milli < 9500 and st.players[s].pending_cost == prev.players[s].pending_cost:
                for p in PHASES:
                    if p[0] <= t < p[1]:
                        acc[p][0] += d
                        acc[p][1] += 1
        prev = st
    ends.append(prev.tick)
rows = [dict(phase=list(p), ticks=n, elixir_per_tick=round(s / n / 1000, 5) if n else None) for p, (s, n) in acc.items()]
out = dict(matches=a.n, end_ticks=sorted(ends), crforge=rows, opp_elixir_count=REAL)
Path(a.out).write_text(json.dumps(out, indent=1))
print(json.dumps(out))
