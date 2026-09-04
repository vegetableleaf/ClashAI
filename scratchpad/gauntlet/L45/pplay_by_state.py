import numpy as np, torch, sys, os
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
torch.set_num_threads(2)
S = np.load(r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L45\sim_obs_gatec2m10k.npz"); L = np.load(sys.argv[1])
from rollout_search import load_net, _NEG
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
env = SimMatchEnv(Config.load(), seed=1); net = load_net("data/policy_gatec2_20260903_best.pt", env, torch.device("cpu"))
costs = torch.tensor([float(s.elixir) for s in env.specs])
def pp(D, bs=64):
    out = []; n = len(D["t"])
    for a in range(0, n, bs):
        sl = slice(a, min(n, a + bs))
        o = torch.from_numpy(D["obs"][sl]).float().permute(0, 3, 1, 2) / 255.0
        v = lambda x: torch.from_numpy(np.asarray(x[sl], np.float32))
        with torch.no_grad(): cq, ceq, gq, _, _ = net(o, v(D["hand"]), v(D["next"]), v(D["elixir_vec"]), v(D["threat"]))
        pl = (v(D["hand"]) > 0.5) & (costs.view(1, -1) <= v(D["elixir_vec"]) * 10 + 1e-6)
        p = torch.sigmoid(gq[:, 1] - gq[:, 0]).numpy(); p[~pl.any(1).numpy()] = np.nan; out.append(p)
    return np.concatenate(out)
cache = r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L45\sim_pplay.npy"
ps = np.load(cache) if os.path.exists(cache) else pp(S); np.save(cache, ps); pl_ = pp(L)
for name, D, p in [("sim", S, ps), ("live", L, pl_)]:
    e = D["elixir_vec"][:, 0] * 10
    print(name, "n", len(p), "play share", (D["exec"][:, 0] == 1).mean().round(3))
    for lo, hi in [(0, 4), (4, 7), (7, 9), (9, 11)]:
        m = (e >= lo) & (e < hi) & ~np.isnan(p); print(f"  elixir [{lo},{hi}): n {m.sum():4d}  p_play mean {np.nanmean(p[m]) if m.any() else float('nan'):.3f}  share>0.25 {(p[m] > 0.25).mean() if m.any() else float('nan'):.3f}  plays {(D['exec'][m, 0] == 1).sum()}")
t = L["t"]; mm = L["match"]
for mi in np.unique(mm):
    sel = mm == mi; tt = t[sel] - t[sel][0]; p = pl_[sel]; e = L["elixir_vec"][sel, 0] * 10
    for lo, hi in [(0, 30), (30, 90), (90, 400)]:
        m = (tt >= lo) & (tt < hi) & ~np.isnan(p); print(f"  live match {mi} t[{lo},{hi})s: n {m.sum():3d} p_play {np.nanmean(p[m]) if m.any() else float('nan'):.3f} elixir {e[m].mean() if m.any() else float('nan'):.1f} plays {(L['exec'][sel][m, 0] == 1).sum()}")
st = S["t"]
for lo, hi in [(0, 30), (30, 90), (90, 400)]:
    m = (st >= lo) & (st < hi) & ~np.isnan(ps); print(f"  sim t[{lo},{hi})s: n {m.sum():4d} p_play {np.nanmean(ps[m]):.3f} elixir {(S['elixir_vec'][m, 0] * 10).mean():.1f} play share {(S['exec'][m, 0] == 1).mean():.3f}")
