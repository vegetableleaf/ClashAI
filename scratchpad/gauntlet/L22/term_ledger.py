"""L22: which reward terms carry what the policy earns? Greedy, search-free (ab_reward_report's loop), full term ledger."""
import sys, json, collections; sys.path.insert(0, "src")
import torch, numpy as np
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS
ckpt, matches, seed, mode = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[5]
rng = np.random.RandomState(seed)
cfg = Config.load("data/bench/gate05_run.yaml")
env = SimMatchEnv(cfg); env.rng.seed(seed); env.reset()
net = RS.load_net(ckpt, env, torch.device("cpu"))
sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
done = steps = plays = 0; elix = []; cost = collections.Counter(); play_elix = []
while done < matches:
    if mode == "greedy":
        act, _ = sr.act(0)
    else:  # SAMPLED: gate ~ Bernoulli(P(play)), card ~ softmax over affordable, cell = head argmax (the probe's instrument, minus centre-cell)
        cq_m, ceq, gq_m, playable = sr._forward()
        pp = float(torch.softmax(gq_m, 0)[1]) if bool(playable.any()) else 0.0
        if rng.rand() < pp:
            pc = torch.softmax(cq_m, 0).numpy(); ci = int(rng.choice(len(pc), p=pc / pc.sum()))
            act = (1, ci, sr._cell_for(ceq, ci))
        else:
            act = (0, 0, 0)
    elix.append(float(env.eng.elixir[0])); steps += 1
    if act[0] == 1:
        plays += 1; play_elix.append(float(env.eng.elixir[0]))
    _o, _r, d, info = env.step(act)
    if d: done += 1; env.reset()
led = env.rw_stats.run_summary(); n = max(1, led["matches"])
e = np.asarray(elix)
print(f"{ckpt} mode={mode} matches={n} steps={steps} plays={plays} ({100*plays/steps:.1f}% of steps) elixir mean {e.mean():.2f} >=6 {100*(e>=6).mean():.1f}%")
rows = []
for name, t in led["terms"].items():
    rows.append((abs(t["total"]) / n, name, t))
tot_abs = sum(r[0] for r in rows) or 1.0
print(f"{'term':24s} {'per-match':>10s} {'|share|':>8s} {'fires/match':>12s} keys={list(rows[0][2].keys()) if rows else ''}")
for a, name, t in sorted(rows, reverse=True):
    fires = t.get("n", t.get("count", t.get("fires", "-")))
    print(f"{name:24s} {t['total']/n:+10.3f} {100*a/tot_abs:7.1f}% {str(fires if isinstance(fires,str) else fires/n):>12s}")
json.dump({"ckpt": ckpt, "mode": mode, "matches": n, "steps": steps, "plays": plays, "elixir_mean": float(e.mean()), "ge6": float((e>=6).mean()),
           "terms": {k: v for k, v in led["terms"].items()}}, open(sys.argv[4], "w"), default=float)
