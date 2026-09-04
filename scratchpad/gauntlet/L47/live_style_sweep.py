"""Is the gate PALETTE-SENSITIVE?  The live canonical render uses the fixed palette (grass 25,80,25 / river
120,90,30 / you 230,90,60 / enemy 60,60,230); training frames are DomainRand-restyled per match (bg +-55,
team +-25, gain 0.7-1.25, bias +-25, noise <=6).  Re-style the LIVE frames exactly as DomainRand would, N styles,
and read the spread of share>0.25 at elixir>=9.  argv: live.npz ckpt [n_styles]"""
import numpy as np, torch, sys
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src"); torch.set_num_threads(2)
L = np.load(sys.argv[1]); N = int(sys.argv[3]) if len(sys.argv) > 3 else 24
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
hi = L["elixir_vec"][:, 0] * 10 >= 9
PAL = {"grass": (25, 80, 25), "river": (120, 90, 30), "you": (230, 90, 60), "enemy": (60, 60, 230)}
base = L["obs"].copy(); rgb = base[..., :3]
masks = {k: (rgb == np.array(v, np.uint8)).all(-1) for k, v in PAL.items()}
cover = sum(m.sum() for m in masks.values()) / rgb[..., 0].size; print(f"palette covers {cover:.4f} of live RGB pixels")
def restyle(rng, bg_j=55, team_j=25, gain=(0.7, 1.25), bias=(-25, 25), noise=6.0, canonical=False):
    o = base.copy()
    if canonical: return o, "canonical"
    jit = lambda c, a: tuple(int(min(255, max(0, x + rng.uniform(-a, a)))) for x in c)
    cols = {"grass": jit(PAL["grass"], bg_j), "river": jit(PAL["river"], bg_j), "you": jit(PAL["you"], team_j), "enemy": jit(PAL["enemy"], team_j)}
    img = o[..., :3].astype(np.float32)
    for k, m in masks.items(): img[m] = cols[k]
    g = rng.uniform(*gain); b = rng.uniform(*bias); nz = rng.uniform(0, noise)
    img = img * g + b + rng.uniform(-nz, nz, img.shape)
    o[..., :3] = np.clip(img, 0, 255).astype(np.uint8)
    return o, f"grass{cols['grass']} gain{g:.2f} bias{b:+.0f} noise{nz:.1f}"
def rep(name, o):
    p = pp(o, L["hand"], L["next"], L["elixir_vec"], L["threat"]); s = float(np.nanmean(p[hi] > 0.25))
    print(f"  {name:50s} p_play(all) {np.nanmean(p):.3f}  e>=9 mean {np.nanmean(p[hi]):.3f} share>0.25 {s:.3f}"); return s
print("live canonical:"); c = rep("canonical (as recorded)", base)
rng = np.random.default_rng(0); shares = []
print(f"{N} DomainRand styles:")
for i in range(N):
    o, nm = restyle(rng); shares.append(rep(nm, o))
shares = np.array(shares)
print(f"styles: share>0.25 min {shares.min():.3f} p25 {np.percentile(shares,25):.3f} median {np.median(shares):.3f} p75 {np.percentile(shares,75):.3f} max {shares.max():.3f}; canonical {c:.3f} = percentile {100*(shares < c).mean():.0f}")
print("single-factor sweeps (palette fixed canonical):")
for g in (0.7, 0.85, 1.0, 1.1, 1.25):
    o = base.copy(); o[..., :3] = np.clip(o[..., :3].astype(np.float32) * g, 0, 255).astype(np.uint8); rep(f"gain {g}", o)
for b in (-25, -12, 12, 25):
    o = base.copy(); o[..., :3] = np.clip(o[..., :3].astype(np.float32) + b, 0, 255).astype(np.uint8); rep(f"bias {b:+d}", o)
for nz in (3.0, 6.0):
    o = base.copy(); o[..., :3] = np.clip(o[..., :3].astype(np.float32) + rng.uniform(-nz, nz, o[..., :3].shape), 0, 255).astype(np.uint8); rep(f"noise {nz}", o)
