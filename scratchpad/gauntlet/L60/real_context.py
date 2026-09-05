"""L60 Measurement 1 -- does REAL (non-sim) context beat the board-blind per-card cell prior?

Features come ONLY from the replay records (meta.csv columns copied from the corpus / engine record, and
data/royaleapi/crawl2/plays_ext.csv), never from the sim state:
  time   = meta seconds (corpus tick*0.05)            -> buckets 0-60 / 60-120 / 120-180 / 180+
  elixir = meta eng_elixir_before (engine record; present 5753/6922) -> buckets <4 / 4-6 / 6-8 / 8+ ; missing -> "na"
  oppcard = opponent's last NON-ability play (card slug) with tick < focus tick and focus_sec - opp_sec <= 6 ; else "none"
  opptile = that play's tile in the FOCUS player's own frame (mirrored like the drive: side 1 -> nx = 1 - x/18000,
            ny = y/32000; side 0 -> nx = x/18000, ny = 1 - y/32000), bucketed 4 rows (ny*4) x 3 lanes (nx*3) ; else "none"
Scoring = knn_vs_bc.score on the pro card's MASKED 432-cell map, same 1,004 val rows.
Conditional histogram of (card, key): score(cell) = n_key(cell) + alpha * p_card(cell) + 1e-3 * (n_key @ Gauss)(cell)
  where p_card = Laplace-1 normalised card prior; if the (card,key) bucket has < min_n train rows -> back off to the
  plain card prior (hard counts + 1e-3 gauss tie-break = control_prior "hard", 13.65/40.04).
NB combination: log-score = log p(cell|card) + sum_f [log p(cell|card,f) - log p(cell|card)], p(.|card,f) interpolated
  with alpha pseudo-counts toward p(.|card) (buckets with < min_n rows contribute nothing).
Selection of "the best combination" is done by 5-fold by-replay CV on TRAIN, then the selected one is reported on val.
kNN: same-card neighbours, Euclidean on the real-record vector, k = 15 (5, 50 for reference), hard vote + gauss tie-break.
Usage (cwd icebow): PYTHONPATH=src PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L60/real_context.py
"""
from __future__ import annotations

import csv
import itertools
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import knn_vs_bc as K  # noqa: E402  (unmodified; imported)

DATA, MODELS = K.DATA, K.MODELS
CRAWL = K.ICEBOW / "data" / "royaleapi" / "crawl2"
GW, GH, NC = K.GW, K.GH, K.GW * K.GH
MIN_N = 5
WINDOW = 6.0


# ----------------------------------------------------------------------------------------------- features
def time_bucket(s):
    return "t0" if s < 60 else "t1" if s < 120 else "t2" if s < 180 else "t3"


def elixir_bucket(e):
    if e == "" or e is None:
        return "na"
    e = float(e)
    return "e0" if e < 4 else "e1" if e < 6 else "e2" if e < 8 else "e3"


def build_features():
    rows = list(csv.DictReader(open(DATA / "meta.csv", newline="")))
    tags = {r["tag"] for r in rows}
    plays = defaultdict(list)
    with (CRAWL / "plays_ext.csv").open(encoding="utf-8", newline="") as h:
        for p in csv.DictReader(h):
            if p["replay_tag"] in tags and p["attr_ability"] == "0":
                plays[p["replay_tag"]].append((int(p["tick"]), float(p["seconds"]), {"red": 0, "blue": 1}[p["attr_s"]],
                                              p["attr_card"].strip(), int(p["x_units"]), int(p["y_units"])))
    for t in plays:
        plays[t].sort()
    feats = []
    for r in rows:
        tag, side, tick, sec = r["tag"], int(r["side"]), int(r["tick"]), float(r["seconds"])
        opp = None                                  # last opponent (non-ability) play strictly before our tick, if within 6 s
        for (pt, ps, s, card, x, y) in reversed(plays[tag]):
            if pt >= tick or s == side:
                continue
            if sec - ps <= WINDOW:
                opp = (card, x, y, sec - ps)
            break
        if opp is not None:
            card, x, y, dt = opp
            nx, ny = (1 - x / 18000.0, y / 32000.0) if side == 1 else (x / 18000.0, 1 - y / 32000.0)
            row_b, lane_b = min(int(ny * 4), 3), min(int(nx * 3), 2)
            opptile = f"r{row_b}l{lane_b}"
        else:
            card, nx, ny, dt, opptile = "none", 0.5, 0.5, WINDOW, "none"
        el = r["eng_elixir_before"]
        feats.append({"time": time_bucket(sec), "elixir": elixir_bucket(el), "oppcard": card, "opptile": opptile,
                      "sec": sec, "el": (float(el) if el != "" else np.nan), "nx": nx, "ny": ny, "dt": dt})
    return feats


# ----------------------------------------------------------------------------------------------- conditional histograms
class CondHist:
    def __init__(self, card_tr, cell_tr, keys_tr, dev, alpha, min_n=MIN_N):
        self.dev, self.alpha, self.min_n = dev, alpha, min_n
        self.K = K.gauss_kernel(1.0).to(dev)
        n_cards = 10
        self.hist = torch.zeros(n_cards, NC, device=dev)
        self.hist.index_put_((card_tr, cell_tr), torch.ones(len(card_tr), device=dev), accumulate=True)
        self.prior_score = self.hist + 1e-3 * (self.hist @ self.K)             # control_prior "hard"
        self.p_card = (self.hist + 1.0) / (self.hist + 1.0).sum(1, keepdim=True)  # Laplace-1 normalised
        self.buckets = {}
        card_np = card_tr.cpu().numpy()
        for c in range(n_cards):
            for key in set(keys_tr[card_np == c]):
                m = torch.from_numpy((card_np == c) & (keys_tr == key)).to(dev)
                h = torch.zeros(NC, device=dev).index_put_((cell_tr[m],), torch.ones(int(m.sum()), device=dev), accumulate=True)
                self.buckets[(c, key)] = h
        self.n_buckets = len(self.buckets)

    def scores(self, card_va, keys_va):
        """Joint bucket with back-off."""
        out = self.prior_score[card_va].clone()
        card_np = card_va.cpu().numpy()
        n_backoff = 0
        for i in range(len(card_np)):
            h = self.buckets.get((int(card_np[i]), keys_va[i]))
            if h is None or h.sum() < self.min_n:
                n_backoff += 1
                continue
            out[i] = h + self.alpha * self.p_card[card_np[i]] + 1e-3 * (h @ self.K)
        return out, n_backoff

    def logp_bucket(self, c, key):
        h = self.buckets.get((c, key))
        if h is None or h.sum() < self.min_n:
            return None
        return torch.log((h + self.alpha * self.p_card[c]) / (h.sum() + self.alpha))


def nb_scores(hists: dict, card_va, feat_va: dict, names):
    """Naive-Bayes style combination of single-feature conditionals: log p_card + sum_f (log p_f - log p_card)."""
    dev = next(iter(hists.values())).dev
    card_np = card_va.cpu().numpy()
    base = next(iter(hists.values()))
    logp_card = torch.log(base.p_card)
    out = logp_card[card_va].clone()
    for f in names:
        H = hists[f]
        for i in range(len(card_np)):
            lp = H.logp_bucket(int(card_np[i]), feat_va[f][i])
            if lp is not None:
                out[i] += lp - logp_card[card_np[i]]
    return out


def eval_scores(sc, T, meta, idx, name):
    sc = sc.masked_fill(~T["mask"][idx], float("-inf"))
    res, _, _ = K.score(sc, T["cell"][idx], meta, idx, name)
    return res


def cv_folds(meta_tags, tr, n_folds=5, seed=0):
    tags = sorted(set(meta_tags[tr]))
    rng = np.random.RandomState(seed); rng.shuffle(tags)
    fold_of = {t: i % n_folds for i, t in enumerate(tags)}
    f = np.array([fold_of[t] for t in meta_tags[tr]])
    return [(tr[f != k], tr[f == k]) for k in range(n_folds)]


# ----------------------------------------------------------------------------------------------- kNN on real features
def knn_real(T, meta, feats, tr, va, oppcards, ks=(5, 15, 50)):
    dev = T["obs"].device
    V = {c: i for i, c in enumerate(oppcards)}
    def vec(i):
        f = feats[i]
        oh = np.zeros(len(V) + 1); oh[V.get(f["oppcard"], len(V))] = 1.0   # last slot = "none"/unseen
        el_na = np.isnan(f["el"])
        return np.concatenate([[f["sec"] / 180.0, (0.0 if el_na else f["el"] / 10.0), float(el_na),
                                f["nx"], f["ny"], f["dt"] / WINDOW], oh])
    X = torch.tensor(np.stack([vec(i) for i in range(len(feats))]), dtype=torch.float32, device=dev)
    Xtr, Xva = X[tr], X[va]
    D = torch.cdist(Xva, Xtr)                                         # Euclidean [nva, ntr]
    same = T["card"][va][:, None] == T["card"][tr][None]
    D = D.masked_fill(~same, 1e9)
    Kg = K.gauss_kernel(1.0).to(dev)
    cells_tr = T["cell"][tr]
    out = []
    for k in ks:
        nb = torch.topk(-D, k, dim=1).indices
        votes = torch.zeros(len(va), NC, device=dev).scatter_add_(1, cells_tr[nb], torch.ones(len(va), k, device=dev))
        smooth = votes @ Kg
        for variant, sc in (("hard", votes + 1e-3 * smooth), ("gauss", smooth)):
            out.append(eval_scores(sc, T, meta, va, f"knn_real_k{k}_{variant}"))
    return out, X.shape[1]


# ----------------------------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    T, meta, deck, tr, va = K.load_all(dev)
    feats = build_features()
    assert len(feats) == len(meta["cell"])
    F = {f: np.array([x[f] for x in feats]) for f in ("time", "elixir", "oppcard", "opptile")}
    meta_tags = np.array([r["tag"] for r in csv.DictReader(open(DATA / "meta.csv", newline=""))])
    report = {"coverage": {}, "single": {}, "combos_cv": {}, "combos_val": {}, "nb_val": {}, "knn": []}
    # coverage of the real-record features
    for f in F:
        vals, cnt = np.unique(F[f][tr], return_counts=True)
        report["coverage"][f] = {"n_values_train": int(len(vals)),
                                 "top": {str(v): int(c) for v, c in sorted(zip(vals, cnt), key=lambda z: -z[1])[:8]}}
    report["coverage"]["opp_within_6s_train"] = float((F["oppcard"][tr] != "none").mean() * 100)
    report["coverage"]["opp_within_6s_val"] = float((F["oppcard"][va] != "none").mean() * 100)
    report["coverage"]["elixir_present_val"] = float((F["elixir"][va] != "na").mean() * 100)
    print("coverage", json.dumps(report["coverage"]))

    # control reproduced through this code path
    ctrl = CondHist(T["card"][tr], T["cell"][tr], np.array(["all"] * len(tr)), dev, alpha=1.0)
    sc, _ = ctrl.scores(T["card"][va], np.array(["all"] * len(va)))
    r = eval_scores(sc, T, meta, va, "prior_card_hist_hard(reproduced)")
    print(K.fmt(r)); report["prior"] = r

    def key_of(names, idx):
        return np.array(["|".join(F[f][i] for f in names) for i in idx])

    singles = ["time", "elixir", "oppcard", "opptile"]
    alphas = (1.0, 5.0, 20.0)
    # (a)-(d) singles on val, every alpha
    for f in singles:
        for a in alphas:
            H = CondHist(T["card"][tr], T["cell"][tr], key_of([f], tr), dev, alpha=a)
            sc, nb = H.scores(T["card"][va], key_of([f], va))
            r = eval_scores(sc, T, meta, va, f"cond_{f}_a{a:g}")
            r["n_buckets"] = H.n_buckets; r["val_backoff"] = nb
            print(K.fmt(r), "buckets", H.n_buckets, "backoff", nb)
            report["single"][f"{f}_a{a:g}"] = r
    # (e) combinations: joint buckets and NB, selected by 5-fold by-replay CV on train
    combos = [c for n in (1, 2, 3, 4) for c in itertools.combinations(singles, n)]
    folds = cv_folds(meta_tags, tr)
    cv_table = {}
    for names in combos:
        for a in alphas:
            for mode in ("joint", "nb"):
                if mode == "joint" and len(names) == 1:
                    continue        # the singles are already the joint case
                if mode == "nb" and len(names) == 1:
                    continue
                accs1, accs5 = [], []
                for ftr, fva in folds:
                    if mode == "joint":
                        H = CondHist(T["card"][ftr], T["cell"][ftr], key_of(names, ftr), dev, alpha=a)
                        sc, _ = H.scores(T["card"][fva], key_of(names, fva))
                    else:
                        hs = {f: CondHist(T["card"][ftr], T["cell"][ftr], key_of([f], ftr), dev, alpha=a) for f in names}
                        sc = nb_scores(hs, T["card"][fva], {f: key_of([f], fva) for f in names}, names)
                    r = eval_scores(sc, T, meta, fva, "cv")
                    accs1.append(r["top1"]); accs5.append(r["top5"])
                cv_table[f"{mode}:{'+'.join(names)}:a{a:g}"] = (float(np.mean(accs1)), float(np.mean(accs5)))
    # singles CV too (for a fair selection table)
    for f in singles:
        for a in alphas:
            accs1, accs5 = [], []
            for ftr, fva in folds:
                H = CondHist(T["card"][ftr], T["cell"][ftr], key_of([f], ftr), dev, alpha=a)
                sc, _ = H.scores(T["card"][fva], key_of([f], fva))
                r = eval_scores(sc, T, meta, fva, "cv"); accs1.append(r["top1"]); accs5.append(r["top5"])
            cv_table[f"joint:{f}:a{a:g}"] = (float(np.mean(accs1)), float(np.mean(accs5)))
    accs1, accs5 = [], []
    for ftr, fva in folds:
        H = CondHist(T["card"][ftr], T["cell"][ftr], np.array(["all"] * len(ftr)), dev, alpha=1.0)
        sc, _ = H.scores(T["card"][fva], np.array(["all"] * len(fva)))
        r = eval_scores(sc, T, meta, fva, "cv"); accs1.append(r["top1"]); accs5.append(r["top5"])
    cv_table["prior"] = (float(np.mean(accs1)), float(np.mean(accs5)))
    report["combos_cv"] = cv_table
    ranked = sorted(cv_table.items(), key=lambda kv: -kv[1][0])
    print("CV (train, 5-fold by replay) top-1 ranking:")
    for k_, v in ranked[:12]:
        print(f"  {k_:40s} {v[0]:.2f} / {v[1]:.2f}")
    print(f"  {'prior':40s} {cv_table['prior'][0]:.2f} / {cv_table['prior'][1]:.2f}")
    # every combination on val as well (for the record), and the CV-selected one flagged
    for key in cv_table:
        if key == "prior":
            continue
        mode, names_s, a_s = key.split(":"); names = names_s.split("+"); a = float(a_s[1:])
        if mode == "joint":
            H = CondHist(T["card"][tr], T["cell"][tr], key_of(names, tr), dev, alpha=a)
            sc, nb = H.scores(T["card"][va], key_of(names, va))
        else:
            hs = {f: CondHist(T["card"][tr], T["cell"][tr], key_of([f], tr), dev, alpha=a) for f in names}
            sc = nb_scores(hs, T["card"][va], {f: key_of([f], va) for f in names}, names); nb = None
        r = eval_scores(sc, T, meta, va, key); r["val_backoff"] = nb; r["cv"] = cv_table[key]
        report["combos_val"][key] = r
    sel = ranked[0][0]
    report["selected_by_cv"] = sel
    print("SELECTED by CV:", sel, "cv", cv_table[sel], "VAL:", K.fmt(report["combos_val"][sel]))
    # kNN over the real-record vector
    oppcards = sorted(set(F["oppcard"][tr]) - {"none"})
    kres, dim = knn_real(T, meta, feats, tr, va, oppcards)
    for r in kres:
        print(K.fmt(r))
    report["knn"] = kres; report["knn_dim"] = dim
    report["runtime_s"] = time.time() - t0
    json.dump(report, open(MODELS / "M1_real_context.json", "w"), indent=1)
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    torch.set_num_threads(2)
    main()
