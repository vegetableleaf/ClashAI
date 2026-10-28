"""Merge oppcheck's per-actor JSONs -> one summary (per opponent id).  usage: python summ.py OUTDIR > SUM.json"""
import json
import sys
from pathlib import Path

S, G = {}, {"actors": 0, "batches": 0, "errors": {}, "learner_decisions": 0, "learner_matches": 0}
for f in sorted(Path(sys.argv[1]).glob("*.json")):
    d = json.loads(f.read_text())
    G["actors"] += 1
    for k in ("batches", "learner_decisions", "learner_matches"):
        G[k] += d[k]
    for k, v in d["errors"].items():
        G["errors"][k] = G["errors"].get(k, 0) + v
    for i, o in d["opponents"].items():
        t = S.setdefault(i, {})
        for k, v in o.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                t[k] = max(t.get(k, 0.0), v) if k.endswith("max_abs_diff") else t.get(k, 0) + v
            elif isinstance(v, dict):
                dd = t.setdefault(k, {})
                for a, b in v.items():
                    dd[a] = dd.get(a, 0) + b
            elif isinstance(v, list):
                t[k] = (t.get(k, []) + v)[:8] if k == "first_diffs" else t.get(k, []) + v
for i, t in S.items():
    pm = t.pop("per_match_decisions", [])
    t["decisions_per_match"] = round(sum(pm) / len(pm), 1) if pm else None
    t["ok"] = (t["matches"] == t["cfg_equal"] == t["rng_init_equal"] and t["compared"] == t["actions_equal"] ==
               t["rng_after_equal"] and t["sched"] == t["sched_equal"] and t["compared"] == t["decisions"])
G["learner_decisions_per_match"] = round(G["learner_decisions"] / G["learner_matches"], 1) if G["learner_matches"] else None
tot = sum(t["decisions"] for t in S.values())
for t in S.values():
    t["share_of_opp_rows"] = round(t["decisions"] / tot, 4) if tot else None
G["all_ok"] = bool(S) and all(t["ok"] for t in S.values()) and not G["errors"]
print(json.dumps({"summary": G, "opponents": S}, indent=1))
