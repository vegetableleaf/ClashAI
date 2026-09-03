"""L22: how long are the QUIET windows in the sim (no enemy TROOP younger than W s on the board), on the
sampled m10k policy's own trajectories? A 2 -> 6 bank takes 11.2 s in single elixir (19 steps of 0.6 s).
Also the same key on the pro timeline (gaps between red troop plays) for the comparison. Run from icebow/."""
import sys, csv, json, math
sys.path.insert(0, "src"); sys.path.insert(0, "tools")
import numpy as np, torch
from collections import defaultdict
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS
import gate_prior as GP

W = 6.0
ckpt, matches, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
cfg = Config.load("data/bench/gate05_run.yaml")
env = SimMatchEnv(cfg); env.rng.seed(seed); env.reset()
net = RS.load_net(ckpt, env, torch.device("cpu"))
sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
rng = np.random.RandomState(seed)
flags, ts, phase_single = [], [], []
done = 0
while done < matches:
    cq_m, ceq, gq_m, playable = sr._forward()
    pp = float(torch.softmax(gq_m, 0)[1]) if bool(playable.any()) else 0.0
    if rng.rand() < pp:
        pc = torch.softmax(cq_m, 0).numpy(); ci = int(rng.choice(len(pc), p=pc / pc.sum()))
        act = (1, ci, sr._cell_for(ceq, ci))
    else:
        act = (0, 0, 0)
    e = env.eng
    pres = any(u.team == 1 and u.hp > 0 and u.spec.kind == "troop" and u.age < W for u in e.units)
    flags.append(int(pres)); ts.append(float(e.t)); phase_single.append(float(e.t) < 120.0)
    _o, _r, d, info = env.step(act)
    if d:
        done += 1; flags.append(-1); ts.append(-1); phase_single.append(False); env.reset()

def stretches(fl):
    out, run = [], 0
    for f in fl:
        if f == 0:
            run += 1
        else:
            if run:
                out.append(run)
            run = 0
    if run:
        out.append(run)
    return out
fl = np.asarray(flags); ps = np.asarray(phase_single)
flags = [f if (ok or f < 0) else -1 for f, ok in zip(flags, phase_single)]   # single elixir only; -1 breaks stretches
fl = np.asarray(flags)
valid = fl >= 0
print(f"SIM {ckpt} sampled, {matches} matches, {int(valid.sum())} single-elixir steps: pressure on {100 * (fl[valid] == 1).mean():.0f}% of steps (W={W:.0f}s)")
st = np.asarray(stretches(flags))
print(f"  quiet stretches: n={len(st)} mean {st.mean() * 0.6:.1f}s median {np.median(st) * 0.6:.1f}s | "
      f">= 11.2s (2->6 bank): {100 * (st >= 19).mean():.0f}% of stretches, {100 * st[st >= 19].sum() / max(1, st.sum()):.0f}% of quiet steps")
print("  stretch length (s) percentiles 50/75/90/95:", [round(float(np.percentile(st, p)) * 0.6, 1) for p in (50, 75, 90, 95)])

# pro timeline, same key
src = cfg.path("data/royaleapi/crawl2/plays_ext.csv")
rows = list(csv.DictReader(open(src, encoding="utf-8"))); by = defaultdict(list)
for r in rows:
    by[r["replay_tag"]].append(r)
SPELLS = {"the_log", "zap", "arrows", "fireball", "rocket", "tornado", "poison", "lightning", "freeze", "rage",
          "earthquake", "giant_snowball", "barbarian_barrel", "goblin_barrel", "graveyard", "mirror", "clone", "void",
          "goblin_curse", "royal_delivery", "skeleton_barrel"}
BUILDINGS = {"tesla", "x_bow", "mortar", "inferno_tower", "cannon", "bomb_tower", "goblin_cage", "goblin_hut",
             "barbarian_hut", "furnace", "tombstone", "elixir_collector", "goblin_drill"}
pst, pfl = [], []
for tag, rs in by.items():
    theirs = sorted(float(r["seconds"]) for r in rs if r.get("attr_s") == "red" and r.get("attr_ability") != "1"
                    and GP._base(r["attr_card"]).replace("-", "_") not in SPELLS | BUILDINGS)
    end = min(120.0, max(float(r["seconds"]) for r in rs))       # single elixir only, like the sim rows above
    t, k, f = 0.0, 0, []
    while t < end:
        while k < len(theirs) and theirs[k] <= t:
            k += 1
        f.append(int(k > 0 and t - theirs[k - 1] < W)); t += 0.6
    pfl += f; pst += stretches(f)
pst = np.asarray(pst); pfl = np.asarray(pfl)
print(f"PRO ({len(by)} replays, single elixir, {len(pfl)} windows): pressure on {100 * pfl.mean():.0f}% of windows")
print(f"  quiet stretches: n={len(pst)} mean {pst.mean() * 0.6:.1f}s median {np.median(pst) * 0.6:.1f}s | "
      f">= 11.2s: {100 * (pst >= 19).mean():.0f}% of stretches, {100 * pst[pst >= 19].sum() / max(1, pst.sum()):.0f}% of quiet windows")
print("  stretch length (s) percentiles 50/75/90/95:", [round(float(np.percentile(pst, p)) * 0.6, 1) for p in (50, 75, 90, 95)])
