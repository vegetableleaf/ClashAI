"""L66m: per-mode summary of the continuation diagnostic (teacher rows with --include-pro)."""
import json, sys, glob, statistics as st
GX, GY = 36, 64
bench = {(r["tag"], r["tick"]): r for r in json.load(open(sys.argv[1]))["rows"]}
for mode in sys.argv[2:]:
    rows = [json.loads(l) for f in sorted(glob.glob(f"scratchpad/gauntlet/L66/cont/{mode}_s*.jsonl")) for l in open(f) if l.strip()]
    rows = [r for r in rows if "pro_rank" in r]
    d, rk, top, gap, win = [], [], [], [], []
    for r in rows:
        b = bench[(r["tag"], r["tick"])]
        dx = (r["px"] / GX - b["x"]) * (GX / 2); dy = (r["py"] / GY - b["y"]) * (GY / 2)
        d.append((dx * dx + dy * dy) ** 0.5)
        rk.append(r["pro_rank"]); top.append(r["pro_rank"] <= max(1, r["n_scored"] // 4))
        gap.append(r["best_score"] - r["pro_score"]); win.append(r["pro_rank"] == 1)
    n = len(rows)
    print(json.dumps({"mode": mode, "n": n, "dist_mean": round(st.mean(d), 2), "dist_median": round(st.median(d), 2),
                      "pro_rank_median": st.median(rk), "pro_top_quartile": round(sum(top) / n, 3),
                      "pro_is_best": round(sum(win) / n, 3), "gap_median": round(st.median(gap), 1),
                      "pro_score_median": round(st.median(r["pro_score"] for r in rows), 1),
                      "best_score_median": round(st.median(r["best_score"] for r in rows), 1)}))
