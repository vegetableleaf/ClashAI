"""Verify the root cause: repaint the LIVE frames with OUR towers at the sim's board-true rows
(princess row 76 cols 12/51 hw2, king row 87 col 32 hw3) instead of the frame-space rows 57-61/66-72.
If the gate recovers to ~the 'RGB := sim' ceiling (0.70-0.73), the anchor bug is the seam."""
import numpy as np, torch, sys
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
torch.set_num_threads(2)
L = np.load(sys.argv[1]); CK = sys.argv[2]; S = np.load(sys.argv[3])
from rollout_search import load_net
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
env = SimMatchEnv(Config.load(), seed=1); net = load_net(CK, env, torch.device("cpu"))
costs = torch.tensor([float(s.elixir) for s in env.specs])
def pp(obs, D, bs=64):
    out = []; n = len(D["t"])
    for a in range(0, n, bs):
        sl = slice(a, min(n, a + bs))
        o = torch.from_numpy(obs[sl]).float().permute(0, 3, 1, 2) / 255.0
        v = lambda x: torch.from_numpy(np.asarray(x[sl], np.float32))
        with torch.no_grad(): cq, ceq, gq, _, _ = net(o, v(D["hand"]), v(D["next"]), v(D["elixir_vec"]), v(D["threat"]))
        pl = (v(D["hand"]) > 0.5) & (costs.view(1, -1) <= v(D["elixir_vec"]) * 10 + 1e-6)
        p = torch.sigmoid(gq[:, 1] - gq[:, 0]).numpy(); p[~pl.any(1).numpy()] = np.nan; out.append(p)
    return np.concatenate(out)
e = L["elixir_vec"][:, 0] * 10; hi = (e >= 9)
def rep(name, obs):
    p = pp(obs, L); m = hi & ~np.isnan(p)
    print(f"{name:60s} p_play(all) {np.nanmean(p):.3f}  elixir>=9: mean {np.nanmean(p[m]):.3f} share>0.25 {(p[m] > 0.25).mean():.3f}")
    return p
base = L["obs"].copy(); rep("live as recorded", base)
YOU = np.array([230, 90, 60], np.uint8); GRASS = np.array([25, 80, 25], np.uint8)
oh, ow = base.shape[1], base.shape[2]
# frame-space (buggy) anchors -> pixel boxes; board-true (sim) anchors -> pixel boxes
def box(ax, ay, hw): cx, cy = int(ax * ow), int(ay * oh); return slice(max(0, cy-hw), cy+hw+1), slice(max(0, cx-hw), cx+hw+1)
bug = [box(0.245, 0.615, 2), box(0.745, 0.615, 2), box(0.495, 0.72, 3)]
fix = [box(0.1944, 0.7969, 2), box(0.8056, 0.7969, 2), box(0.5, 0.9062, 3)]
print("bug boxes (rows, cols):", [((b[0].start, b[0].stop), (b[1].start, b[1].stop)) for b in bug])
print("fix boxes (rows, cols):", [((b[0].start, b[0].stop), (b[1].start, b[1].stop)) for b in fix])
# check the bug boxes really hold the tower colour in the live frames
for i, (rs, cs) in enumerate(bug):
    frac = (base[:, rs, cs, :3] == YOU).all(-1).mean(); print(f"  live frames: tower colour fill in bug box {i}: {frac:.3f}")
alive = L["threat"][:, 46:49] > 0.0   # mine L/R/king HP fractions (>0 = alive)
print("  alive (threat 46-48) mean per tower:", alive.mean(0).round(3))
o = base.copy()
for rs, cs in bug: o[:, rs, cs, :3] = GRASS
rep("live, our towers ERASED (rows 57-61/66-72 -> grass)", o)
o2 = o.copy()
for i, (rs, cs) in enumerate(fix): o2[:, rs, cs, :3] = YOU
rep("live, our towers at SIM rows (all drawn)", o2)
o3 = o.copy()
for i, (rs, cs) in enumerate(fix):
    sel = alive[:, i]; o3[sel][:, rs, cs, :3] = YOU  # (fancy index copy -- do it explicitly)
    idx = np.where(sel)[0]; o3[idx[:, None, None], rs, cs, :3] = YOU
rep("live, our towers at SIM rows (alive-gated by threat 46-48)", o3)
# reference: the RGB := sim ceiling from the same rng as before
rng = np.random.default_rng(0); es = S["elixir_vec"][:, 0] * 10; pool = np.where(es >= 7)[0]; pick = rng.choice(pool, size=len(base))
o4 = base.copy(); o4[..., :3] = S["obs"][pick][..., :3]; rep("reference: RGB := random sim RGB", o4)
# does the sim ever have red at rows 57-61? (our units near the river)
SR = S["obs"][pool]; red = (SR[..., 0] > 180) & (SR[..., 2] < 120)
print("sim: fraction of frames with any red pixel in rows 55-73:", red[:, 55:74].any(axis=(1, 2)).mean().round(3), " rows 74-91:", red[:, 74:92].any(axis=(1, 2)).mean().round(3))
