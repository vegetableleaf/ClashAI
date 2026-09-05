"""L59 geo LEDGER probe (place_probe driver verbatim, config = the arm yaml so env.geometry is ON):
per-key geo_* fires/sums over 6 envs x 400 steps, plus per-card scored/paid/mean credit.
Usage: geo_ledger_probe.py <ckpt> [seed] [yaml]  (yaml default data/bench/armG_run.yaml)

ORIGINAL DOCSTRING: L55 placement probe: where does a checkpoint put each card IN THE SIM, greedy card + greedy cell
(the live path's rule, play.py 582/634), gate sampled for state coverage. Same env setup as
tools/gate_prior_probe.py (6 envs, seeds 4242+i, 400 steps). Prints per-card top cells."""
import sys, json, collections
from pathlib import Path
import numpy as np, torch, torch.nn as nn
_ROOT = Path("C:/Users/benpe/ClashBot/icebow")
sys.path.insert(0, str(_ROOT / "src"))
from clashrl.config import Config
from clashrl.model import PolicyNet
from clashrl.sim.env import SimMatchEnv

YAML = None
def run(ckpt, seed=0, envs=6, steps=400, greedy_card=True):
    np.random.seed(seed); torch.manual_seed(seed)
    cfg = Config.load(_ROOT / (YAML if YAML else "data/bench/armG_run.yaml"))
    cfg.data.setdefault("action", {})["grid"] = [18, 24]
    state = torch.load(ckpt, map_location="cpu", weights_only=False)
    pool = [SimMatchEnv(cfg, seed=4242 + i) for i in range(envs)]
    e0 = pool[0]
    for e in pool:
        if getattr(e, "domain_rand", None) is not None:
            e.domain_rand.enabled = False; e.domain_rand.resample()
    in_ch = int(state.get("in_ch") or 12); thr_dim = int(state.get("threat_dim") or e0.threat_dim)
    class PPONet(nn.Module):
        def __init__(s):
            super().__init__()
            s.policy = PolicyNet(in_ch, e0.n_cards, e0.n_cells, threat_dim=thr_dim)
            s.gate = nn.Linear(s.policy.embed_dim, 2)
        def forward(s, x, hand, nxt, elx, thr):
            z, cards, cells = s.policy.forward_parts(x, hand, nxt, elx, thr)
            return cards, cells, s.gate(z)
    net = PPONet(); net.policy.load_state_dict(state["model"])
    if "gate" in state: net.gate.load_state_dict(state["gate"])
    net.eval()
    def obs_t(o):
        x = np.asarray(o)
        if x.shape[2] > in_ch: x = x[:, :, :in_ch]
        elif x.shape[2] < in_ch:
            x = np.concatenate([x, np.zeros((x.shape[0], x.shape[1], in_ch - x.shape[2]), dtype=x.dtype)], axis=2)
        return torch.from_numpy(x).float().permute(2, 0, 1) / 255.0
    def thr_t(v):
        t = np.asarray(v, np.float32)
        return torch.from_numpy(t[:thr_dim] if t.shape[0] > thr_dim else np.pad(t, (0, thr_dim - t.shape[0])))
    names = [str(getattr(sp, "key", i)) for i, sp in enumerate(e0.specs)]
    cells = collections.defaultdict(collections.Counter)   # card -> cell counter (greedy cell)
    first = collections.Counter()                           # (card, cell) of the first play of each match
    cellarg_all = collections.Counter()                     # greedy cell regardless of play (every step)
    geo_rows = []
    obs = [e.reset() for e in pool]; fresh = [True] * envs
    with torch.no_grad():
        for _ in range(steps):
            xb = torch.stack([obs_t(o) for o in obs])
            hb = torch.stack([torch.from_numpy(np.asarray(e.hand_vec, np.float32)) for e in pool])
            nb = torch.stack([torch.from_numpy(np.asarray(e.next_vec, np.float32)) for e in pool])
            eb = torch.stack([torch.from_numpy(np.asarray(e.elixir_vec, np.float32)) for e in pool])
            tb = torch.stack([thr_t(e.threat_vec) for e in pool])
            cq, ceq, gq = net(xb, hb, nb, eb, tb)
            pg = torch.softmax(gq, dim=1)[:, 1].numpy(); pc = torch.softmax(cq, dim=1).numpy()
            ceqn = ceq.numpy()            # (B, n_cards, n_cells) per-card placement maps
            own = np.zeros(e0.n_cells, bool); own[12*18:] = True   # own half = rows 12-23 (live cells 235/374/423)
            for i, e in enumerate(pool):
                elx = float(e.eng.elixir[0])
                hand = [c for c in e._hand_ids() if 0 <= c < len(e.specs) and elx >= e.specs[c].elixir]
                pick = None
                if hand:
                    if greedy_card: pick = int(max(hand, key=lambda c: pc[i][c]))
                    else:
                        w = np.asarray([pc[i][c] for c in hand], dtype=np.float64); w = w / w.sum()
                        pick = int(np.random.choice(hand, p=w))
                play = bool(hand) and bool(np.random.random() < pg[i])
                if pick is not None:
                    m = ceqn[i, pick].copy(); m[~own] = -1e9; cellmax = int(m.argmax())
                    cellarg_all[(names[pick], cellmax)] += 1
                if play and pick is not None:
                    cell = cellmax; cells[names[pick]][cell] += 1
                    if fresh[i]: first[(names[pick], cell)] += 1; fresh[i] = False
                    act = (1, pick, cell)
                else: act = (0, 0, 0)
                nobs, _r, done, _i = e.step(act)
                gc = getattr(e, "_geo_cache", None)
                if act[0] and gc is not None and gc[0][0] == act[1]:
                    t = gc[1]; nm = names[act[1]]
                    geo_rows.append((nm, e.specs[act[1]].kind, float(t.get("credit", 0.0)), float(t.get("p1_pull_band", 0.0)), float(t.get("p3_intercept", 0.0)), float(t.get("p6_siege", 0.0)), float(t.get("p5_timing", 0.0)), float(t.get("gate", 1.0))))
                if done: obs[i] = e.reset(); fresh[i] = True
                else: obs[i] = nobs
    out = {"ckpt": str(ckpt), "seed": seed, "greedy_card": greedy_card,
           "cells": {k: v.most_common(6) for k, v in cells.items()},
           "n": {k: sum(v.values()) for k, v in cells.items()},
           "distinct": {k: len(v) for k, v in cells.items()},
           "first": first.most_common(8), "cellarg_all": cellarg_all.most_common(8)}
    ledger = collections.defaultdict(lambda: [0, 0.0])
    for e in pool:
        for k, t in e.rw_stats.run_summary()["terms"].items():
            if k.startswith("geo_"): ledger[k][0] += t["fires"]; ledger[k][1] += t["total"]
    out["ledger"] = {k: v for k, v in sorted(ledger.items())}
    out["geo_rows"] = geo_rows
    return out

if __name__ == "__main__":
    ck = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    gc = (sys.argv[3] != "sample") if len(sys.argv) > 3 else True
    if len(sys.argv) > 4: YAML = sys.argv[4]
    o = run(ck, seed, greedy_card=gc)
    print("geo ledger (fires, sum) over 6 envs:", {k: (v[0], round(v[1], 3)) for k, v in o["ledger"].items()})
    by = collections.defaultdict(list)
    for r in o["geo_rows"]: by[r[0]].append(r)
    for nm, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        paid = [r for r in rs if r[2] > 0]
        print(f"  {nm:14s} scored={len(rs):3d} paid={len(paid):3d} mean_credit_paid={np.mean([r[2] for r in paid]) if paid else 0:.3f} "
              f"mean_p1={np.mean([r[3] for r in rs]):.3f} mean_p3={np.mean([r[4] for r in rs]):.3f} mean_p6={np.mean([r[5] for r in rs]):.3f} mean_p5={np.mean([r[6] for r in rs]):.3f} mean_gate={np.mean([r[7] for r in rs]):.3f}")
    print(json.dumps({"ckpt": o["ckpt"], "seed": seed, "greedy_card": gc, "first": o["first"], "cellarg_all": o["cellarg_all"]}))
    for k in sorted(o["cells"], key=lambda k: -o["n"][k]):
        print(f"{k:14s} n={o['n'][k]:3d} distinct={o['distinct'][k]:3d} top={o['cells'][k][:5]}")
