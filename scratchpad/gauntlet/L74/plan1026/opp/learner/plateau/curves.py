"""PLATEAU diagnosis: per-update training curves for every opponent-calibration arm, binned.
Inputs: logs/RUN.jsonl (train_log) + m/RUN/w16_matches_uNNNN.json (per-match outcome). Read-only. Output: stdout table.
Per bin: win vs CLXIII / vs init, share of CLXIII groups that are MIXED (= carry gradient under match_loo), share of
total |A| mass from CLXIII groups, KL card/cell to init, entropy card/cell, clip frac, grad norm, hazard mad."""
import json, sys, glob, os, collections
import numpy as np

H = os.environ.get("PLATEAU_DATA", r"C:/Users/benpe/ClashBot/.foreman/scratch/plateau")   # logs/ + m/ (fetched read-only, PLATEAU.md)
BIN = int(sys.argv[1]) if len(sys.argv) > 1 else 20


def loo(R):
    R = np.array(R, float)
    n = len(R)
    return np.clip(R - (R.sum() - R) / (n - 1), -2, 2)


def run(name):
    ups = [json.loads(l) for l in open(f"{H}/logs/{name}.jsonl")]
    ups = {r["update"]: r for r in ups if r.get("type") == "update"}
    out = []
    bad = 0
    for u, r in sorted(ups.items()):
        f = f"{H}/m/{name}/w16_matches_u{u:04d}.json"
        if not os.path.exists(f):
            continue
        g = collections.defaultdict(list)
        for s in json.load(open(f)):
            key, res, _ = s.split()
            grp, rep, side = key.split("_")[-1].split(":")
            g[int(grp)].append((int(side), res))
        mu = r["matchups"]
        row = dict(u=u)
        acc = collections.defaultdict(lambda: [0, 0, 0, 0.0])   # n matches, wins, mixed groups, |A| mass
        ng = collections.Counter()
        for gi, ms in g.items():
            m = mu[gi]
            if any(s != m["side"] for s, _ in ms):
                bad += 1
            k = "bot" if m["opp"].startswith("exploiter") else m["opp"]
            R = [1 if x == "win" else -1 if x == "loss" else 0 for _, x in ms]
            a = acc[k]
            a[0] += len(R); a[1] += sum(x == 1 for x in R); a[2] += int(len(set(R)) > 1)
            a[3] += float(np.abs(loo(R)).sum()); ng[k] += 1
        tot = sum(a[3] for a in acc.values()) or 1
        for k in ("bot", "init"):
            a = acc[k]
            row[f"wr_{k}"] = a[1] / max(a[0], 1)
            row[f"mix_{k}"] = a[2] / max(ng[k], 1)
            row[f"Ash_{k}"] = a[3] / tot
            row[f"n_{k}"] = a[0]
        row.update(klc=r["kl_card"], klx=r["kl_cell"], ec=r["entropy"]["card"], ex=r["entropy"]["cell"],
                   ec0=r["entropy_init"]["card"], ex0=r["entropy_init"]["cell"], clip=r["clip_frac"],
                   gn=r["grad_norm_mean"], rows=r["rows"], ppm=r["plays_per_min"],
                   mad=(r.get("th_drift") or {}).get("hazard", {}).get("mad", float("nan")), beta=r["beta_used"])
        out.append(row)
    return out, bad


KEYS = ["wr_bot", "wr_init", "mix_bot", "mix_init", "Ash_bot", "klc", "klx", "ec", "ex", "clip", "gn", "mad", "ppm", "rows"]
if __name__ == "__main__":
    names = sorted(os.path.basename(p)[:-6] for p in glob.glob(f"{H}/logs/oplc_*.jsonl"))
    for n in names:
        rows, bad = run(n)
        if not rows:
            continue
        print(f"\n## {n}  beta {rows[0]['beta']}  updates {len(rows)}  side-mismatch groups {bad}  "
              f"entropy_init card {rows[0]['ec0']:.3f} cell {rows[0]['ex0']:.3f}")
        print("bin      " + " ".join(f"{k:>8}" for k in KEYS))
        for b in range(0, rows[-1]["u"] + 1, BIN):
            seg = [r for r in rows if b <= r["u"] < b + BIN]
            if not seg:
                continue
            # pooled win rates (weight by n), others plain means
            v = []
            for k in KEYS:
                if k.startswith("wr_"):
                    kk = k[3:]
                    v.append(sum(r[k] * r[f"n_{kk}"] for r in seg) / max(sum(r[f"n_{kk}"] for r in seg), 1))
                else:
                    v.append(float(np.nanmean([r[k] for r in seg])))
            nb = sum(r["n_bot"] for r in seg)
            print(f"u{b:03d}-{b+BIN-1:03d} " + " ".join(f"{x:8.3f}" if abs(x) < 100 else f"{x:8.0f}" for x in v)
                  + f"  (n_bot {nb})")
