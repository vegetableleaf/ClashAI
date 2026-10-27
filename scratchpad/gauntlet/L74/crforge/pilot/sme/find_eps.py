"""List episode onsets of a run whose detail mentions a name/kind: python3 find_eps.py RUNDIR SUBSTRING [N]"""
import json, os, sys
n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
for l in open(os.path.join(sys.argv[1], 'results.jsonl')):
    r = json.loads(l)
    for e in r.get('episodes', []):
        d = e['detail'] or []
        if any(sys.argv[2] in str(x[2]) or x[0].startswith(sys.argv[2]) for x in d):
            print(r['match'], e['start'], e['end'], e['healed'], json.dumps(d)[:600])
            n -= 1
            break
    if n <= 0:
        break
