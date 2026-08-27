"""Does CPython recycle a dead Unit's address into a LIVE one, inside a single match?

conflicts.md I10-FOLLOWUP fixed exactly this for the five SPELL sites by keying on
`Unit.deploy_seq`. `env.py` still keys four OTHER per-unit ledgers on `id(u)`:
  * `_ev_enemy` / `_ev_own`  (line ~1938) -- the elixir-TRADE event ledger
  * `_nado_watch[...]['pulled']` (line ~2401) -- the tornado delayed-execution credit
  * `_bow_ledger` (line ~2667) -- X-Bow overcommit / lock / dps
This asks whether the precondition for the bug (address reuse) actually occurs, and how often.
"""
import pathlib
import sys

sys.path.insert(0, r"C:\Users\benpe\ClashBot\icebow\src")
from clashrl.config import Config          # noqa: E402
from clashrl.sim.env import SimMatchEnv    # noqa: E402

cfg = Config.load()
env = SimMatchEnv(cfg, seed=12345)
env.domain_rand.enabled = False
env.domain_rand.resample()
env.opponent_provider = None

matches = int(sys.argv[1]) if len(sys.argv) > 1 else 30
tot_units = tot_dead = tot_collide = 0
match_hits = 0
for m in range(matches):
    env.rng.seed(5_000_000 + m)
    env.reset()
    seen = {}          # id -> deploy_seq of the unit that last held this address
    dead_ids = {}      # id -> deploy_seq of a unit known dead
    collide = 0
    for _ in range(600):
        for u in env.eng.units:
            a, s = id(u), int(getattr(u, "deploy_seq", -1))
            if a in dead_ids and dead_ids[a] != s:
                collide += 1
                dead_ids.pop(a)
            seen[a] = s
        _o, _r, done, _i = env.step((0, 0, 0))
        alive = {id(u) for u in env.eng.units}
        for a, s in list(seen.items()):
            if a not in alive:
                dead_ids[a] = s
                seen.pop(a)
        if done:
            break
    tot_collide += collide
    tot_dead += len(dead_ids)
    match_hits += collide > 0
print(f"matches={matches}  address reuse events (a DEAD unit's id() taken over by a LIVE one "
      f"with a different deploy_seq): {tot_collide}   matches with >=1: {match_hits}/{matches}")
