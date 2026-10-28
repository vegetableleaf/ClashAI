# usage: grades_cmp.py BASE_DIR NEW_DIR -- per-replay comparison of two D1-C fault runs on the keys both carry
import glob, json, os, sys
same = diff = 0
for p in sorted(glob.glob(os.path.join(sys.argv[1], "*.jsonl"))):
    a = {r["tag"]: r for r in map(json.loads, open(p))}
    b = {r["tag"]: r for r in map(json.loads, open(os.path.join(sys.argv[2], os.path.basename(p))))}
    assert a.keys() == b.keys(), p
    for t in a:
        k = a[t].keys() & b[t].keys()
        if all(a[t][x] == b[t][x] for x in k):
            same += 1
        else:
            diff += 1
            print("DIFF", t, {x: (a[t][x], b[t][x]) for x in k if a[t][x] != b[t][x]})
print("replays identical on common keys", same, "differing", diff)
