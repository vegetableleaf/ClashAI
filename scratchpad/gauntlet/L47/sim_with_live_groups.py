"""Reverse-direction channel-group swap (HANDOFF 5cs open item): take SIM states (elixir>=7) and drop in the LIVE
image one channel group at a time -- RGB 0-2 / semantic 3-8 / predictive 9-11.  Which group carries the
0.483 -> 0.317 drop seen when the whole live image is dropped in (L46, s6)?  argv: live.npz ckpt sim.npz"""
import numpy as np, torch, sys
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src"); torch.set_num_threads(2)
L = np.load(sys.argv[1]); S = np.load(sys.argv[3])
from rollout_search import load_net
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
env = SimMatchEnv(Config.load(), seed=1); net = load_net(sys.argv[2], env, torch.device("cpu"))
costs = torch.tensor([float(s.elixir) for s in env.specs])
def pp(obs, hand, nxt, elx, thr, bs=64):
    out = []; n = len(obs)
    for a in range(0, n, bs):
        sl = slice(a, min(n, a + bs)); v = lambda x: torch.from_numpy(np.asarray(x[sl], np.float32))
        with torch.no_grad(): cq, ceq, gq, _, _ = net(torch.from_numpy(obs[sl]).float().permute(0, 3, 1, 2) / 255.0, v(hand), v(nxt), v(elx), v(thr))
        pl = (v(hand) > 0.5) & (costs.view(1, -1) <= v(elx) * 10 + 1e-6)
        p = torch.sigmoid(gq[:, 1] - gq[:, 0]).numpy(); p[~pl.any(1).numpy()] = np.nan; out.append(p)
    return np.concatenate(out)
hi = np.nonzero(L["elixir_vec"][:, 0] * 10 >= 9)[0]
simhi = np.nonzero(S["elixir_vec"][:, 0] * 10 >= 7)[0]
print(f"live {sys.argv[1].split('/')[-1]}: rows {len(L['t'])}, elixir>=9 rows {len(hi)};  sim {sys.argv[3].split(chr(92))[-1]}: elixir>=7 rows {len(simhi)}")
GROUPS = [("RGB 0-2", 0, 3), ("semantic 3-8", 3, 9), ("predictive 9-11", 9, 12), ("canvas 3-11", 3, 12)]
for seed in (0, 1, 2):
    rng = np.random.default_rng(seed)
    sidx = rng.choice(simhi, min(400, len(simhi)), replace=False); lidx = rng.choice(hi, len(sidx))
    base = dict(obs=S["obs"][sidx], hand=S["hand"][sidx], nxt=S["next"][sidx], elx=S["elixir_vec"][sidx], thr=S["threat"][sidx])
    def rep(name, obs):
        a = dict(base); a["obs"] = obs; p = pp(**a)
        print(f"  seed {seed} {name:40s} p_play mean {np.nanmean(p):.3f} share>0.25 {np.nanmean(p > 0.25):.3f}")
    rep("sim as recorded", base["obs"])
    rep("sim with whole live obs", L["obs"][lidx])
    for nm, a, b in GROUPS:
        o = base["obs"].copy(); o[..., a:b] = L["obs"][lidx][..., a:b]; rep(f"sim, {nm} := live", o)
    for nm, a, b in GROUPS:
        o = base["obs"].copy(); o[..., a:b] = 0; rep(f"sim, {nm} zeroed", o)
    # the complement: live obs everywhere EXCEPT the group (keeps sim's group)
    for nm, a, b in GROUPS[:3]:
        o = L["obs"][lidx].copy(); o[..., a:b] = base["obs"][..., a:b]; rep(f"live obs, but {nm} := sim", o)
