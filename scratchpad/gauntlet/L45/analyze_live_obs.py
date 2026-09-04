"""Offline read of a live obs dump (HANDOFF 5cr): recompute the PPO gate on every recorded live state with the
same net + same rule the sim twin used, and classify each executed play by ORIGIN (PPO greedy pick / wheel or
search override / cell rewrite). Then compare threat-vector slots live vs sim (sim npz from sim_obs_dump.py)."""
import argparse, os, sys
import numpy as np, torch
ROOT = r"C:\Users\benpe\ClashBot\icebow"; os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad")
from rollout_search import load_net, _NEG  # noqa: E402
from clashrl.config import Config  # noqa: E402
from clashrl.sim.env import SimMatchEnv  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--live", required=True); ap.add_argument("--ckpt", required=True)
ap.add_argument("--sim", default=None); ap.add_argument("--tau", type=float, default=0.25)
a = ap.parse_args()
L = np.load(a.live)
cfg = Config.load(); env = SimMatchEnv(cfg, seed=1); dev = torch.device("cpu"); net = load_net(a.ckpt, env, dev)
costs = torch.tensor([float(s.elixir) for s in env.specs]); names = [s.key for s in env.specs]
n = len(L["t"]); print("live decisions", n, "matches", sorted(set(L["match"].tolist())))
obs = L["obs"]; print("obs shape", obs.shape, "dtype", obs.dtype, "mean", float(obs.mean()))
pp = np.zeros(n); ppo_pick = []
for i in range(n):
    o = torch.from_numpy(obs[i]).float()
    o = o.permute(2, 0, 1).unsqueeze(0) / 255.0
    v = lambda x: torch.from_numpy(np.asarray(x, np.float32)).unsqueeze(0)
    with torch.no_grad():
        cq, ceq, gq, _, _ = net(o, v(L["hand"][i]), v(L["next"][i]), v(L["elixir_vec"][i]), v(L["threat"][i]))
    playable = (v(L["hand"][i]) > 0.5) & (costs.view(1, -1) <= v(L["elixir_vec"][i]) * 10.0 + 1e-6)
    pp[i] = float(torch.sigmoid(gq[0, 1] - gq[0, 0])) if bool(playable.any()) else 0.0
    ppo_pick.append(int(cq.masked_fill(~playable, _NEG).argmax()) if bool(playable.any()) else -1)
ch = L["chosen"]; ex = L["exec"]
played = ex[:, 0] == 1; chosen_play = ch[:, 0] == 1
print(f"p_play: mean {pp.mean():.3f} p50 {np.median(pp):.3f} p90 {np.percentile(pp,90):.3f} p99 {np.percentile(pp,99):.3f} max {pp.max():.3f}")
print(f"gate would play @tau{a.tau}: {(pp > a.tau).sum()}  @0.5: {(pp > 0.5).sum()}  of {n}")
print(f"chosen play {chosen_play.sum()}  executed play {played.sum()}  (chosen WAIT but executed play = override: {(played & ~chosen_play).sum()})")
if played.any():
    same_card = (ex[played, 1] == np.array(ppo_pick)[played]); print(f"executed card == PPO greedy card: {same_card.sum()}/{played.sum()}")
    cell_rw = (ch[played & chosen_play, 2] != ex[played & chosen_play, 2]).sum(); print(f"cell rewritten by env on PPO plays: {cell_rw}/{(played & chosen_play).sum()}")
    from collections import Counter
    print("executed cards:", Counter(names[c] for c in ex[played, 1]).most_common())
    print("gate p at executed plays:", np.round(np.sort(pp[played])[::-1][:20], 3))
el = L["elixir"]; print(f"elixir at decision: mean {el.mean():.2f}  >=9.5 share {(el >= 9.5).mean():.3f}  plays at >=9.5: {(played & (el >= 9.5)).sum()}")
dt = np.diff(L["t"]); print(f"decision cadence: median {np.median(dt):.3f}s p90 {np.percentile(dt,90):.3f}s") if n > 1 else None
T = L["threat"]; print("threat live: slots nonzero share", np.round((np.abs(T) > 1e-6).mean(0), 2).tolist())
print("threat live: mean", np.round(T.mean(0), 3).tolist())
if a.sim:
    S = np.load(a.sim); TS = S["threat"]
    print("threat sim : nonzero share", np.round((np.abs(TS) > 1e-6).mean(0), 2).tolist())
    print("threat sim : mean", np.round(TS.mean(0), 3).tolist())
    print(f"sim p_play mean {S['p_play'].mean():.3f} p99 {np.percentile(S['p_play'],99):.3f}; sim obs mean {float(S['obs'].mean()):.1f} live obs mean {float(obs.mean()):.1f}")
    print("hand live mean", np.round(L["hand"].mean(0), 2).tolist()); print("hand sim  mean", np.round(S["hand"].mean(0), 2).tolist())
    print("elixir_vec live mean", float(L["elixir_vec"].mean()), "sim", float(S["elixir_vec"].mean()))
