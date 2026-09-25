"""T12a: engine-only self-play speed -- two cheapest-affordable scripted policies (test_royale_selfplay), CPU, 1 process.

    research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L68/selfplay/speed.py [n_matches] [every]
Deck pairs: seeded draws from loadable_decks.json's top-1000 loadable decks + icebow; one seed per match.
"""
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[3]))
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from pipeline.tests.test_royale_selfplay import ICEBOW, play_scripted  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
every = int(sys.argv[2]) if len(sys.argv) > 2 else 10
pool = [d["engine"] for d in json.load(open(HERE / "loadable_decks.json"))["decks"]] + [ICEBOW]
rng = random.Random(0)
env = RoyaleSelfPlayEnv()
outs, ticks, plays, ends = Counter(), [], [], Counter()
t0 = time.perf_counter()
for i in range(n):
    p = play_scripted(env, rng.choice(pool), rng.choice(pool), seed=i, every=every)
    outs[env.outcome(0)[0]] += 1
    ends["game_over" if env.terminated else "tail_cap"] += 1
    ticks.append(env.tick)
    plays.append(p[0] + p[1])
dt = time.perf_counter() - t0
print(json.dumps({"matches": n, "decide_every_ticks": every, "wall_s": round(dt, 2), "matches_per_s": round(n / dt, 2),
                  "sim_ticks_per_s": round(sum(ticks) / dt), "mean_end_tick": round(sum(ticks) / n),
                  "mean_plays_per_match": round(sum(plays) / n, 1), "side0_outcomes": dict(outs), "ended_by": dict(ends)}))
