"""F635: first divergence of each match of an SME run: python3 firstdiv.py RUN_DIR [match ...]"""
import json, os, sys
for r in map(json.loads, open(os.path.join(sys.argv[1], 'results.jsonl'))):
    if len(sys.argv) > 2 and r['match'] not in sys.argv[2:]:
        continue
    if 'error' in r:
        print(r['match'], 'ERROR', str(r['error'])[:200]); continue
    e = (r.get('episodes') or [None])[0]
    print(r['match'], r['counts'], json.dumps(e)[:600] if e else '-')
