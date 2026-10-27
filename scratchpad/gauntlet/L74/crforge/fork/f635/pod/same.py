"""F635: per-match identity of two SME runs (counts and first divergence): python3 same.py RUN_A RUN_B"""
import json, os, sys
def load(r):
    return {x["match"]: x for x in map(json.loads, open(os.path.join(r, "results.jsonl")))}
a, b = load(sys.argv[1]), load(sys.argv[2])
key = lambda x: (x.get("error"), x.get("counts"), x.get("missing_in_sim"), (x.get("episodes") or [None])[0])
same = [m for m in a if m in b and key(a[m]) == key(b[m])]
diff = [m for m in a if m in b and key(a[m]) != key(b[m])]
print("matches in both %d: identical %d, different %d" % (len(same) + len(diff), len(same), len(diff)))
for m in diff:
    print(" ", m, json.dumps(key(a[m]))[:200], "->", json.dumps(key(b[m]))[:200])
