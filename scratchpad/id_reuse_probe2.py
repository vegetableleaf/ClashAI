"""Does the address reuse actually LAND on a live per-unit ledger entry?

`_trade_reward` rebuilds `self._ev_enemy = {id(u): (...)}` from the live enemy units every step and
looks the PREVIOUS step's entry up by `id(u)`. A false continuation is therefore an address that is
present in two consecutive snapshots carrying DIFFERENT `deploy_seq` values: the ledger reads unit B
as if it were the same body as the dead unit A, and credits/decredits accordingly.
"""
import sys
sys.path.insert(0, r"C:\Users\benpe\ClashBot\icebow\src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv

cfg = Config.load()
env = SimMatchEnv(cfg, seed=12345)
env.domain_rand.enabled = False
env.domain_rand.resample()
env.opponent_provider = None
matches = int(sys.argv[1]) if len(sys.argv) > 1 else 30
false_en = false_own = 0
hit_matches = 0
for m in range(matches):
    env.rng.seed(5_000_000 + m); env.reset()
    prev_en, prev_own = {}, {}
    hits = 0
    for _ in range(600):
        _o, _r, done, _i = env.step((0, 0, 0))
        cur_en = {id(u): int(u.deploy_seq) for u in env.eng.units if u.team == 1 and u.hp > 0}
        cur_own = {id(u): int(u.deploy_seq) for u in env.eng.units if u.team == 0 and u.hp > 0}
        for a, s in cur_en.items():
            if a in prev_en and prev_en[a] != s:
                false_en += 1; hits += 1
        for a, s in cur_own.items():
            if a in prev_own and prev_own[a] != s:
                false_own += 1; hits += 1
        prev_en, prev_own = cur_en, cur_own
        if done:
            break
    hit_matches += hits > 0
print(f"matches={matches}  FALSE CONTINUATIONS in the step-to-step per-unit ledger keyed on id(u): "
      f"enemy {false_en}, own {false_own}   matches with >=1: {hit_matches}/{matches}")
