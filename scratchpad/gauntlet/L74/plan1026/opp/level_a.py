"""P2-OPP1 scorecard level A (per decision) for a timing-head opponent model, against THRESHOLDS.json (sha-checked by
humanlike/scorecard.load_thresholds; refuses on a mismatch).

    python level_a.py --ckpt OPP.pt --data ROWS.npz [--memory-tables M.npz] [--split 2] [--max-tags N] --out A.json

ROWS must hold EVERY grid slot of each side (rows_to_npz --keep-wait 1): the time-rescaling needs the hazard of every slot.
  * card / cell: agreement (top-1; cell = exact lattice cell, the ceiling's own definition), NLL, ECE (top-1 confidence,
    10 bins), on play rows (card: card_ok rows).
  * timing: per-slot NLL, slot ECE (hazard vs event, 10 bins of h), and the discrete time-rescaling of the gaps between
    plays at TICK resolution (Haslinger, Pipa & Brown 2010): per tick j of a slot, lambda_j = h p_j / (1 - h sum_{i<j} p_i);
    a gap's tau = sum of -log(1 - lambda) over its ticks before the play + -log(1 - r lambda_play), r ~ U(0, 1). Under the
    true model tau ~ Exp(1) exactly; KS vs Exp(1). Gaps crossing a missing slot or still open at the end are dropped.
  * ability press: the same rescaling on ab_ok rows (all heroes pooled: per-hero n is reported, not split).
  * memory used: rows after 120 s, NLL (card + cell + timing) with the real memory vs the memory of ANOTHER match (tables
    rotated across matches); difference with a match-bootstrap 90% CI.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / "scratchpad/gauntlet/L74/opp_model/humanlike")]
from pipeline.dataset import load as load_ds          # noqa: E402
from pipeline.model_gen import load_model, slot_nll    # noqa: E402
from pipeline.model_v3 import cell_label               # noqa: E402
from pipeline.train_gen import GenRows                 # noqa: E402


def ece(p, c, bins=10):
    p, c = np.asarray(p, float), np.asarray(c, float)
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[b == k].mean() - c[b == k].mean()) * (b == k).sum() for k in range(bins) if (b == k).any()) / max(len(p), 1))


def ks_exp(x):
    g = np.sort(np.asarray(x, float))
    n = len(g)
    if not n:
        return float("nan")
    F = 1 - np.exp(-g)
    i = np.arange(n)
    return float(max(((i + 1) / n - F).max(), (F - i / n).max()))


def rescale(seq_keys, tick, h, pt, ev, etick, rng, slot=10):
    """Discrete time-rescaled gaps. seq_keys: one key per row (a side of a match); rows of a key sorted by tick."""
    lam_all = h[:, None] * pt / np.clip(1 - h[:, None] * np.concatenate([np.zeros((len(h), 1)), np.cumsum(pt, 1)[:, :-1]], 1), 1e-12, None)
    lam_all = np.clip(lam_all, 0, 1 - 1e-12)
    q = -np.log1p(-lam_all)
    out = []
    order = np.lexsort((tick, seq_keys))
    prev_key, prev_t, tau, valid = None, None, 0.0, True
    for r in order:
        k, t = seq_keys[r], tick[r]
        if k != prev_key:
            tau, valid = 0.0, True                       # a new side: its first gap = time to its first play
        elif t - prev_t != slot:
            tau, valid = 0.0, False                      # a missing slot: the running gap is dropped
        prev_key, prev_t = k, t
        if ev[r]:
            j = int(etick[r])
            tau += q[r, :j].sum() - math.log1p(-rng.random() * lam_all[r, j])
            if valid:
                out.append(tau)
            tau, valid = 0.0, True
        else:
            tau += q[r].sum()
    return np.asarray(out)


def selftest():
    """Instrument control: slots simulated from a known hazard h(x) and tick pmf -> rescaled gaps of the TRUE model are
    Exp(1) (KS small); a model with the hazard x 1.3, or a flat tick pmf, is rejected."""
    rng = np.random.default_rng(0)
    n_sides, T = 600, 360
    x = rng.normal(size=(n_sides, T))
    h = 1 / (1 + np.exp(-(0.8 * x - 2.3)))
    pmf = np.array([0.0, 0.3, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.07, 0.03])
    ev = rng.random((n_sides, T)) < h
    et = np.where(ev, rng.choice(10, size=(n_sides, T), p=pmf), 0)
    key, tick = np.repeat(np.arange(n_sides), T), np.tile(np.arange(T) * 10, n_sides)
    flat = lambda a: a.reshape(-1)
    pt = np.broadcast_to(pmf, (n_sides * T, 10))
    res = {}
    for name, hh, pp in (("true", flat(h), pt), ("hazard_x1.3", np.clip(flat(h) * 1.3, 0, 0.99), pt),
                         ("flat_tick", flat(h), np.full((n_sides * T, 10), 0.1))):
        g = rescale(key, tick, hh, pp, flat(ev), flat(et), np.random.default_rng(1))
        res[name] = {"gaps": int(len(g)), "ks": ks_exp(g), "mean": float(g.mean())}
    ok = res["true"]["ks"] < 0.02 and res["hazard_x1.3"]["ks"] > 0.05 and res["flat_tick"]["ks"] > res["true"]["ks"]
    print(json.dumps(dict(res, SELFTEST="OK" if ok else "FAIL"), indent=1))
    return 0 if ok else 1


@torch.no_grad()
def main(argv=None) -> int:
    if (argv or sys.argv[1:])[:1] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--memory-tables", type=Path, default=None)
    ap.add_argument("--split", type=int, default=2)
    ap.add_argument("--max-tags", type=int, default=0)
    ap.add_argument("--bs", type=int, default=1024)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    import scorecard as SC
    th, th_sha = SC.load_thresholds()
    A = th["A"]
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, st = load_model(a.ckpt, dev)
    model.eval()
    from pipeline.train_gen import load_dir
    arrs, meta = load_dir(a.data) if a.data.is_dir() else load_ds(a.data)
    if (meta.get("row_builder") or {}).get("keep_wait") != 1:
        raise SystemExit("level A needs every slot: build the rows with rows_to_npz --keep-wait 1")
    if meta["card_vocab"] != st["card_vocab"]:
        raise SystemExit("data / checkpoint card_vocab differ")
    idx = np.where(arrs["split"] == a.split)[0]
    if a.max_tags:
        keep = np.unique(arrs["rep"][idx])[: a.max_tags]
        idx = idx[np.isin(arrs["rep"][idx], keep)]
    rows = GenRows(arrs, idx, dev)
    mem = st.get("memory")
    if mem:
        from pipeline.dataset_gen import checkpoint_gid, load_memory_tables
        packed, row_tab, _ = load_memory_tables(a.memory_tables)
        rows.memory, rows.memory_version, rows.memory_gid = (packed, row_tab, arrs["tick"]), mem, checkpoint_gid(st["card_vocab"])
    rng = np.random.default_rng(0)
    R = {k: [] for k in ("i", "h", "pt", "card_p", "card_top", "card_ok", "cell_p", "cell_top", "cell_ok", "nll", "abh", "abpt")}

    def run(ids):
        out = []
        for s0 in range(0, len(ids), a.bs):
            b = rows.batch(ids[s0:s0 + a.bs])
            o = model(b, card=b["card"], form=b["form"])
            play = (b["gate"] > 0.5)
            lab = cell_label(b["xy"].clamp(0, 1), "lattice")
            cl = Fn.log_softmax(o["cell"].float(), -1)
            ck = Fn.log_softmax(o["card"].float(), -1)
            slot_ok = b["card_ok"] > 0
            card_lp = torch.where(play & slot_ok & (b["slot"] >= 0), ck.gather(1, b["slot"].clamp(min=0)[:, None])[:, 0], torch.zeros_like(cl[:, 0]))
            cell_lp = torch.where(play, cl.gather(1, lab.clamp(min=0)[:, None])[:, 0], torch.zeros_like(cl[:, 0]))
            s = b["slot_ok"] > 0
            tnll = torch.where(s, slot_nll(o["hazard"].float(), o["tick"].float(), b["slot_ev"], b["slot_tick"]), torch.zeros_like(cell_lp))
            out.append(dict(card_lp=card_lp, cell_lp=cell_lp, tnll=tnll, o=o, b=b, play=play, lab=lab, cl=cl, ck=ck))
        return out

    ids = np.asarray(idx)
    for chunk in run(ids):
        o, b, play = chunk["o"], chunk["b"], chunk["play"]
        R["h"].append(torch.sigmoid(o["hazard"].float()).cpu().numpy())
        R["pt"].append(torch.softmax(o["tick"].float(), -1).cpu().numpy())
        R["abh"].append(torch.sigmoid(o["ab_hazard"].float()).cpu().numpy() if "ab_hazard" in o else np.zeros(len(play)))
        R["abpt"].append(torch.softmax(o["ab_tick"].float(), -1).cpu().numpy() if "ab_tick" in o else np.zeros((len(play), 10)))
        ck, cl = chunk["ck"].exp(), chunk["cl"].exp()
        R["card_p"].append(ck.max(-1).values.cpu().numpy()); R["card_top"].append((ck.argmax(-1) == b["slot"]).cpu().numpy())
        R["card_ok"].append((play & (b["card_ok"] > 0) & (b["slot"] >= 0)).cpu().numpy())
        R["cell_p"].append(cl.max(-1).values.cpu().numpy()); R["cell_top"].append((cl.argmax(-1) == chunk["lab"]).cpu().numpy())
        R["cell_ok"].append(play.cpu().numpy())
        R["nll"].append(torch.stack([-chunk["card_lp"], -chunk["cell_lp"], chunk["tnll"]], 1).cpu().numpy())
    R = {k: np.concatenate(v) for k, v in R.items() if v}
    sub = {k: np.asarray(arrs[k])[ids] for k in ("tick", "side", "rep", "slot_ok", "slot_ev", "slot_tick", "ab_ok", "ab_ev", "ab_tick", "y_gate")}
    key = sub["rep"].astype(np.int64) * 2 + sub["side"].astype(np.int64)
    co, eo = R["card_ok"], R["cell_ok"]
    res = {"ckpt": str(a.ckpt), "data": str(a.data), "split": a.split, "rows": int(len(ids)), "thresholds_sha256": th_sha,
           "card": {"n": int(co.sum()), "agreement": float(R["card_top"][co].mean()), "nll": float(R["nll"][co, 0].mean()),
                    "ece_pp": 100 * ece(R["card_p"][co], R["card_top"][co])},
           "cell": {"n": int(eo.sum()), "agreement": float(R["cell_top"][eo].mean()), "nll": float(R["nll"][eo, 1].mean()),
                    "ece_pp": 100 * ece(R["cell_p"][eo], R["cell_top"][eo])}}
    s = sub["slot_ok"] > 0
    gaps = rescale(key[s], sub["tick"][s], R["h"][s], R["pt"][s], sub["slot_ev"][s] > 0, sub["slot_tick"][s], rng)
    res["timing"] = {"slots": int(s.sum()), "events": int((sub["slot_ev"][s] > 0).sum()), "nll_per_slot": float(R["nll"][s, 2].mean()),
                     "hazard_mean": float(R["h"][s].mean()), "event_rate": float((sub["slot_ev"][s] > 0).mean()),
                     "ece_slot_pp": 100 * ece(R["h"][s], sub["slot_ev"][s] > 0), "gaps": int(len(gaps)), "ks_rescaled": ks_exp(gaps),
                     "rescaled_mean": float(gaps.mean()) if len(gaps) else None}
    ab = sub["ab_ok"] > 0
    if ab.any():
        ag = rescale(key[ab], sub["tick"][ab], R["abh"][ab], R["abpt"][ab], sub["ab_ev"][ab] > 0, sub["ab_tick"][ab], rng)
        res["ability"] = {"slots": int(ab.sum()), "presses": int((sub["ab_ev"][ab] > 0).sum()), "gaps": int(len(ag)),
                          "ks_rescaled": ks_exp(ag), "ece_slot_pp": 100 * ece(R["abh"][ab], sub["ab_ev"][ab] > 0)}
    if mem:                                   # memory used: late rows, real vs another match's tables
        late = np.where(sub["tick"] > 2400)[0]
        if len(late):
            tabs = np.asarray(row_tab).copy()
            reps = np.unique(sub["rep"])
            rot = {r: reps[(i + 1) % len(reps)] for i, r in enumerate(reps)}   # each match gets the next match's table
            first_tab = {}
            for i in ids:
                first_tab.setdefault((int(arrs["rep"][i]), int(arrs["side"][i])), tabs[i])
            for i in ids:
                tabs[i] = first_tab.get((int(rot[int(arrs["rep"][i])]), int(arrs["side"][i])), -1)
            rows.memory = (packed, tabs, arrs["tick"])
            shuf = np.concatenate([np.stack([-c["card_lp"], -c["cell_lp"], c["tnll"]], 1).cpu().numpy() for c in run(ids[late])])
            real = R["nll"][late]
            d = (shuf - real).sum(1)                                   # > 0 = the real memory predicts better
            per = {}
            for r_, v in zip(sub["rep"][late], d):
                per.setdefault(int(r_), []).append(v)
            m = np.array([np.mean(v) for v in per.values()])
            boots = [rng.choice(m, len(m)).mean() for _ in range(2000)]
            res["memory_used"] = {"late_rows": int(len(late)), "matches": int(len(m)), "nll_gain_real_vs_other_match": float(d.mean()),
                                  "match_mean_gain_ci90": [float(np.percentile(boots, 5)), float(np.percentile(boots, 95))],
                                  "seed_gap": None, "note": "THRESHOLDS asks gain > seed gap; one seed trained -> seed gap not measured"}
    res["pass"] = {"card_agreement": res["card"]["agreement"] >= A["agreement_card_min"],
                   "cell_agreement": res["cell"]["agreement"] >= A["agreement_cell_min"],
                   "ece_card": res["card"]["n"] >= A["ece_min_decisions"] and res["card"]["ece_pp"] <= A["ece_card_pp_max"],
                   "ece_top_cell": res["cell"]["n"] >= A["ece_min_decisions"] and res["cell"]["ece_pp"] <= A["ece_top_cell_pp_max"],
                   "ece_timing_slot": res["timing"]["ece_slot_pp"] <= A["ece_timing_slot_pp_max"],
                   "timing_ks": res["timing"]["gaps"] >= A["timing_min_gaps_per_archetype"] and res["timing"]["ks_rescaled"] <= A["timing_rescaled_gap_ks_max"],
                   "ability_ks": ("ability" in res and res["ability"]["gaps"] >= A["ability_press_min_n_per_hero"]
                                  and res["ability"]["ks_rescaled"] <= A["ability_press_ks_max"]),
                   "memory_used": None}
    res["notes"] = ["timing KS pooled over archetypes (THRESHOLDS asks >= 5000 gaps PER archetype: not split here)",
                    "ability KS pooled over heroes (per-hero n not split)", "nll_vs_per_deck_finetune: not run (no per-deck fine-tunes)"]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
