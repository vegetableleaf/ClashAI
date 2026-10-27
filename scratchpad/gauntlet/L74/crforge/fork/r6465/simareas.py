"""Print the sim's area rows (kind A) and anything named like the pattern, for ticks [lo,hi] of an SmeRun o*.jsonl."""
import json, sys, re
path, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
pat = re.compile(sys.argv[4] if len(sys.argv) > 4 else 'Rage')
for line in open(path):
    d = json.loads(line)
    if lo <= d['t'] <= hi:
        print(d['t'], [e for e in d['E'] if e[1] == 'A' or pat.search(e[2])])
