"""hf_tally.py BASE_GRADES NEW_GRADES -- CF-MAIN: a D1-C fault run (complete or not) against a base run on the shards
both have: replays, outcomes, faults by first message (unit ids numbered out), and replays whose outcome changed."""
import collections, glob, json, os, re, sys

base, new = sys.argv[1], sys.argv[2]
n, oc_b, oc_n, msg, changed = 0, collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
for p in sorted(glob.glob(os.path.join(new, "*.jsonl"))):
    b = {r["tag"]: r for r in map(json.loads, open(os.path.join(base, os.path.basename(p))))}
    for r in map(json.loads, open(p)):
        n += 1
        oc_n[r["outcome"]] += 1
        oc_b[b[r["tag"]]["outcome"]] += 1
        if r["outcome"] != b[r["tag"]]["outcome"]:
            changed[b[r["tag"]]["outcome"] + " -> " + r["outcome"]] += 1
        for f in r.get("faults", [])[:1]:
            m = re.sub(r"\b[A-Za-z0-9]+_\d+(_\d+)*(_clone\d+)?\b", "#", f[2].split("UnsupportedOperationException: ")[-1])
            msg[m[:110]] += 1
print("shards", len(glob.glob(os.path.join(new, "*.jsonl"))), "replays", n)
print("outcomes base", dict(oc_b), "| new", dict(oc_n))
print("outcome changes", dict(changed))
for m, k in msg.most_common():
    print(f"{k:5d}  {m}")
