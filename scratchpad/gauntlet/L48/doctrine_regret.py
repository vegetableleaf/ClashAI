"""L48: the SEARCH as an oracle over the DOCTRINE's decisions. The doctrine plays the match; at every
decision the searcher scores its own candidates (policy top-K x cells + WAIT) PLUS the doctrine's
action with the same 12 s rollouts, and we log the regret = best - doctrine. Aggregated by
(doctrine action kind, search best kind, board) -> the doctrine's gaps, ranked by summed regret.
argv: matches override_module out.json"""
import sys, json, collections, importlib
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
import numpy as np, torch
torch.set_num_threads(1)
from rollout_search import play_match, Searcher, load_net
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
from clashrl.sim import drill_env, doctrine
n = int(sys.argv[1]); ov = sys.argv[2]; out = sys.argv[3]
if ov != "none": importlib.import_module(ov).install()
cfg = Config.load(); env = SimMatchEnv(cfg, seed=12345); env.domain_rand.enabled = False; env.domain_rand.resample(); env.opponent_provider = None; env.scenario = None
K = list(env.deck_keys)
net = load_net(r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L47\_rs_c2rbest.pt", env, torch.device("cpu"))
S = Searcher(env, net, torch.device("cpu"), 12.0, 1, 4, 1.0, float(cfg.get("sim", "ppo_gate_threshold", default=0.25)), cells=3)
S._jit_active = False; S._jit_plan = None
rows = []
def kind(a):
    return "HOLD" if a[0] == 0 else K[a[1]]
class D:
    def act(self, i):
        a = tuple(int(x) for x in drill_env.doctrine_policy(None, env))
        pol, (cq_m, ceq, gq_m, playable) = S.greedy_action()
        cands = S.candidates(cq_m, ceq, playable)
        if a not in cands: cands.append(a)
        S._rs_ctr += 1; S._rs_seed = 1_000_003 * S._rs_ctr + 7; S._clamped_now = 0
        scores = [S._rollout(c) for c in cands]
        b = int(np.argmax(scores)); best = cands[b]
        sd = scores[cands.index(a)]
        committed = tuple(sorted(set(u.spec.base for u in doctrine._enemies(env) if u.y > 0.42 and u.spec.kind != "spell")))
        rows.append({"t": round(float(env.eng.t), 1), "e": round(float(env.eng.elixir[0]), 1), "doc": kind(a), "best": kind(best),
                     "regret": round(float(scores[b] - sd), 4), "board": committed, "hand": [K[c] for c in env._hand_ids()]})
        return a, False
s = D(); w = 0
for m in range(n):
    r = play_match(env, s, 5000000 + m); w += r["outcome"] == "win"; print(f"  match {m+1}/{n} wins {w}", flush=True)
json.dump(rows, open(out, "w"))
R = np.array([r["regret"] for r in rows]); print(f"decisions {len(rows)}  mean regret {R.mean():.4f}  regret>0.05 share {(R>0.05).mean():.3f}  total {R.sum():.2f}")
agg = collections.defaultdict(float); cnt = collections.Counter()
for r in rows:
    k = (r["doc"], r["best"]); agg[k] += r["regret"]; cnt[k] += 1
print("regret by (doctrine did -> search best): summed regret, n, mean")
for k, v in sorted(agg.items(), key=lambda kv: -kv[1])[:16]: print(f"  {k[0]:>11s} -> {k[1]:<11s} {v:7.2f}  n={cnt[k]:4d}  mean={v/cnt[k]:.3f}")
agg2 = collections.defaultdict(float); cnt2 = collections.Counter()
for r in rows:
    if r["regret"] > 0.05: k = r["board"][:3]; agg2[k] += r["regret"]; cnt2[k] += 1
print("high-regret decisions by board (top 12):")
for k, v in sorted(agg2.items(), key=lambda kv: -kv[1])[:12]: print(f"  {v:6.2f} n={cnt2[k]:3d} {k}")
