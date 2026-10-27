"""Identity check (SPEED.md d): two harness results.jsonl, matched by (tag, k, side), row for row.
    python compare.py REF/results.jsonl CAND/results.jsonl
Prints: matches, rows, obs-identical / action-identical matches, action-identical rows, max |delta| per log-prob."""
import json
import sys


def load(p):
    return {(r["tag"], r["k"], r["side"]): r for r in map(json.loads, open(p))}


def main(a, b):
    A, B = load(a), load(b)
    keys = sorted(set(A) & set(B))
    n_obs = n_act = rows = rows_same = 0
    dmax: dict = {}
    first_diff = []
    exposed = diverged = 0                       # per-decision divergence hazard: rows up to the first differing one
    for k in keys:
        x, y = A[k], B[k]
        n_obs += x["sha_obs"] == y["sha_obs"]
        n_act += x["sha_act"] == y["sha_act"]
        n = min(x["n_rows"], y["n_rows"])
        rows += max(x["n_rows"], y["n_rows"])
        fd = next((i for i in range(n) if any(x["act"][f][i] != y["act"][f][i] for f in x["act"])), None)
        exposed += n if fd is None else fd + 1
        diverged += fd is not None
        for i in range(n):
            same = all(x["act"][f][i] == y["act"][f][i] for f in x["act"])
            rows_same += same
            if not same and len(first_diff) < 5:
                first_diff.append((k, i, {f: (x["act"][f][i], y["act"][f][i]) for f in x["act"]
                                          if x["act"][f][i] != y["act"][f][i]}))
        if x["sha_act"] == y["sha_act"]:
            for f in x["lp"]:
                d = max((abs(u - v) for u, v in zip(x["lp"][f], y["lp"][f])), default=0.0)
                dmax[f] = max(dmax.get(f, 0.0), d)
    out = {"matches_ref": len(A), "matches_cand": len(B), "matched": len(keys), "obs_identical": n_obs,
           "actions_identical": n_act, "rows": rows, "rows_action_identical": rows_same,
           "max_abs_dlp_on_identical": dmax,
           "first_divergence_per_decision": round(diverged / exposed, 6) if exposed else None,
           "matches_diverged": diverged, "first_diffs": first_diff,
           "outcomes_identical": sum(A[k]["outcome"] == B[k]["outcome"] for k in keys)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
