"""Teacher A candidate measured on the L43 ceiling instrument: the DOCTRINE (drill_env.doctrine_policy = doctrine_cards
+ doctrine_cells, HOLD when nothing is nominated) playing WHOLE ladder matches, same seeds / pool / DR-off as
L43 ceiling.sh (policy alone 41.7%, search teacher 77.1% on gatec2_m10k).  argv: --matches --seed0 --out --ckpt
(ckpt only for the base leg: --leg policy|doctrine)"""
import sys, os, json, time, argparse
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
import numpy as np, torch, random
ap = argparse.ArgumentParser(); ap.add_argument("--matches", type=int, default=48); ap.add_argument("--seed0", type=int, default=5000000)
ap.add_argument("--out", required=True); ap.add_argument("--leg", default="doctrine"); ap.add_argument("--ckpt", default=None)
args = ap.parse_args()
import rollout_search as rs
from rollout_search import play_match, Searcher, load_net
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
from clashrl.sim.drill_env import doctrine_policy
torch.set_num_threads(1); torch.manual_seed(0); np.random.seed(0); random.seed(0)
cfg = Config.load(); env = SimMatchEnv(cfg, seed=12345); env.domain_rand.enabled = False; env.domain_rand.resample(); env.opponent_provider = None
if not hasattr(env, "scenario"): env.scenario = None
class Doctrine:
    def __init__(self): self.rich_dec = 0; self.rich_play = 0; self.quiet6_dec = 0; self.quiet6_bow = 0
    def act(self, i):
        a = doctrine_policy(None, env); e = float(env.eng.elixir[0])
        if e >= 9: self.rich_dec += 1; self.rich_play += a[0] == 1
        return tuple(int(x) for x in a), False
if args.leg == "doctrine":
    s = Doctrine()
else:
    net = load_net(args.ckpt, env, torch.device("cpu"))
    s = Searcher(env, net, torch.device("cpu"), 1e-6, 0, 4, 1.0, float(cfg.get("sim", "ppo_gate_threshold", default=0.25)))
recs = []; w0 = time.perf_counter()
for m in range(args.matches):
    recs.append(play_match(env, s, args.seed0 + m))
    if (m + 1) % 8 == 0:
        print(f"  [{args.leg}] {m+1}/{args.matches} wr={100*np.mean([r['outcome']=='win' for r in recs]):.1f}% {(time.perf_counter()-w0)/(m+1):.2f} s/match", flush=True)
wr = 100 * np.mean([r["outcome"] == "win" for r in recs]); td = np.mean([r["tower_delta"] for r in recs])
plays = sum(r["plays"] for r in recs); steps = sum(r["steps"] for r in recs); ge6 = sum(r["ge6"] for r in recs)
cd = np.mean([r["crown_delta"] for r in recs])
print(f"[{args.leg}] wr={wr:.1f}%  towerdelta={td:+.3f} crowndelta={cd:+.2f} plays/match={plays/len(recs):.1f} play share {plays/steps:.3f} elixir>=6 share {ge6/steps:.3f}"
      + (f" rich(>=9) decisions {s.rich_dec} play share {s.rich_play/max(1,s.rich_dec):.3f}" if args.leg == "doctrine" else ""))
json.dump({"leg": args.leg, "wr": wr, "tower_delta": float(td), "records": recs}, open(args.out, "w"))
