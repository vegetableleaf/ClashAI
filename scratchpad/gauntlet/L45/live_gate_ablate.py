"""Which LIVE input pushes the gate down? Recompute p_play on the live s2 states with one input group at a
time replaced (zeroed or sim-like) -- offline, same net + rule as pplay_by_state.py (HANDOFF 5cr.8)."""
import numpy as np, torch, sys
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src"); torch.set_num_threads(2)
L = np.load(sys.argv[1]); S = np.load(r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L45\sim_obs_gatec2m10k.npz")
from rollout_search import load_net
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
env = SimMatchEnv(Config.load(), seed=1); net = load_net("data/policy_gatec2_20260903_best.pt", env, torch.device("cpu"))
costs = torch.tensor([float(s.elixir) for s in env.specs])
def pp(obs, hand, nxt, elx, thr, bs=64):
    out = []; n = len(obs)
    for a in range(0, n, bs):
        sl = slice(a, min(n, a + bs)); v = lambda x: torch.from_numpy(np.asarray(x[sl], np.float32))
        with torch.no_grad(): cq, ceq, gq, _, _ = net(torch.from_numpy(obs[sl]).float().permute(0, 3, 1, 2) / 255.0, v(hand), v(nxt), v(elx), v(thr))
        pl = (v(hand) > 0.5) & (costs.view(1, -1) <= v(elx) * 10 + 1e-6)
        p = torch.sigmoid(gq[:, 1] - gq[:, 0]).numpy(); p[~pl.any(1).numpy()] = np.nan; out.append(p)
    return np.concatenate(out)
hi = L["elixir_vec"][:, 0] * 10 >= 9
rng = np.random.default_rng(0); simhi = np.nonzero(S["elixir_vec"][:, 0] * 10 >= 7)[0]
def rep(name, **kw):
    a = dict(obs=L["obs"], hand=L["hand"], nxt=L["next"], elx=L["elixir_vec"], thr=L["threat"]); a.update(kw)
    p = pp(**a); print(f"{name:42s} p_play(all) {np.nanmean(p):.3f}  elixir>=9: mean {np.nanmean(p[hi]):.3f} share>0.25 {np.nanmean(p[hi] > 0.25):.3f}")
rep("live as recorded")
T0 = L["threat"].copy(); T0[:, 6:16] = 0; rep("threat slots 6-15 zeroed (sim never fills)", thr=T0)
T1 = L["threat"].copy(); T1[:, :16] = 0; rep("threat base16 zeroed", thr=T1)
T2 = L["threat"].copy(); T2[:, 16:] = 0; rep("threat slots 16+ zeroed (detector-fed)", thr=T2)
rep("threat all zero", thr=np.zeros_like(L["threat"]))
idx = rng.choice(simhi, len(L["t"])); rep("threat := random sim state's threat", thr=S["threat"][idx])
rep("next zeroed", nxt=np.zeros_like(L["next"]))
rep("next := random sim next", nxt=S["next"][idx])
rep("obs := random sim obs (elixir>=7 states)", obs=S["obs"][idx])
rep("obs zero", obs=np.zeros_like(L["obs"]))
rep("hand := random sim hand", hand=S["hand"][idx])
rep("obs+threat+next := sim (keep live hand,elx)", obs=S["obs"][idx], thr=S["threat"][idx], nxt=S["next"][idx])
# reverse: sim states with live-typical inputs
sidx = simhi[:400]; lidx = rng.choice(np.nonzero(hi)[0], len(sidx))
def rep2(name, **kw):
    a = dict(obs=S["obs"][sidx], hand=S["hand"][sidx], nxt=S["next"][sidx], elx=S["elixir_vec"][sidx], thr=S["threat"][sidx]); a.update(kw)
    p = pp(**a); print(f"{name:42s} sim elixir>=7 states: p_play mean {np.nanmean(p):.3f} share>0.25 {np.nanmean(p > 0.25):.3f}")
rep2("sim as recorded"); rep2("sim with live threat", thr=L["threat"][lidx]); rep2("sim with live obs", obs=L["obs"][lidx]); rep2("sim with live next", nxt=L["next"][lidx])
print("--- per-group (layout: 16-25 identity, 26-33 opp-memory, 34-45 interactions, 46-51 tower) ---")
for gname, a, b in [("identity 16-25", 16, 26), ("opp-memory 26-33", 26, 34), ("interactions 34-45", 34, 46), ("tower 46-51", 46, 52)]:
    T = L["threat"].copy(); T[:, a:b] = 0; rep(f"live, {gname} zeroed", thr=T)
    T = L["threat"].copy(); T[:, a:b] = S["threat"][idx][:, a:b]; rep(f"live, {gname} := sim", thr=T)
print("--- per-slot zeroing, slots 16-51 (share>0.25 at elixir>=9) ---")
row = []
for s in range(16, 52):
    T = L["threat"].copy(); T[:, s] = 0; p = pp(L["obs"], L["hand"], L["next"], L["elixir_vec"], T); row.append((s, round(float(np.nanmean(p[hi] > 0.25)), 3), round(float(L["threat"][hi, s].mean()), 3), round(float(S["threat"][simhi, s].mean()), 3)))
print("slot, share>0.25 when zeroed, live mean(e>=9), sim mean(e>=7):"); [print("  ", r) for r in row]
print("--- single-slot fixes ---")
T = L["threat"].copy(); T[:, 31] = L["elixir_vec"][:, 0]; rep("live, slot 31 := own elixir/10 (sim semantics)", thr=T)
T = L["threat"].copy(); T[:, 31] = S["threat"][idx][:, 31]; rep("live, slot 31 := sim value", thr=T)
T = L["threat"].copy(); T[:, 30] = S["threat"][idx][:, 30]; rep("live, slot 30 := sim value (control)", thr=T)
T = L["threat"].copy(); T[:, 31] = L["elixir_vec"][:, 0]; T[:, 30] = S["threat"][idx][:, 30]; rep("live, slot 31 := own elixir + slot 30 := sim", thr=T)
# what does the sim do when slot 31 is set to the live-style opp estimate (~0)?
T = S["threat"][sidx].copy(); T[:, 31] = L["threat"][lidx][:, 31]; rep2("sim with live slot 31 only", thr=T)
