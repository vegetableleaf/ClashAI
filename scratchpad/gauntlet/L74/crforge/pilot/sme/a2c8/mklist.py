"""onset lists of the unflagged failing matches of a run: python3 mklist.py RESULTS INPUTS FIRST_OUT ALL_OUT"""
import json, sys
flags = {json.loads(l)['match']: json.loads(l)['flags'] for l in open(sys.argv[2])}
first, allo = open(sys.argv[3], 'w'), open(sys.argv[4], 'w')
for l in open(sys.argv[1]):
    r = json.loads(l)
    if flags.get(r['match']) or 'error' in r or r['counts'].get('div', 0) == 0:
        continue
    first.write('%s %d\n' % (r['match'], r['first_div']))
    for e in r.get('episodes', []):
        allo.write('%s %d\n' % (r['match'], e['start']))
