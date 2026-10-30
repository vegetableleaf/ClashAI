"""d3_same.py A.jsonl [B.jsonl] -- OPP-PUSH bootstrap check E1: print the game count, CLXIII wins and a digest of the sorted
(end_tick, outcome) list of a D3 matches.jsonl; with two files also say whether the lists are identical (exact engine copy).
Runs on any pod's python (stdlib only)."""
import hashlib, json, sys


def key(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    lst = sorted((r["end_tick"], r["outcome"]) for r in rows)
    return len(rows), sum(o == "win" for _, o in lst), hashlib.sha256(repr(lst).encode()).hexdigest()[:16], lst


ks = [key(p) for p in sys.argv[1:]]
for p, (n, w, h, _) in zip(sys.argv[1:], ks):
    print(f"{p}: games {n} CLXIII W {w} digest {h}")
if len(ks) == 2:
    same = ks[0][3] == ks[1][3]
    diff = sum(1 for a, b in zip(ks[0][3], ks[1][3]) if a != b)
    print("IDENTICAL" if same else f"DIFFERENT ({diff} of {len(ks[0][3])} sorted entries differ)")
