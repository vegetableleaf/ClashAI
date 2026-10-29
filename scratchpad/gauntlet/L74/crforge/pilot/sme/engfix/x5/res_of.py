"""ENG-FIX5: one match's result line (counts, first div, flags) from results jsonl files. python res_of.py MATCH FILE..."""
import json, sys
for f in sys.argv[2:]:
    for l in open(f):
        x = json.loads(l)
        if x['match'].endswith(sys.argv[1]):
            print(f.split('/')[-2:], x['flags'], x['counts'], x['first_div'], x.get('sim_end'), x.get('live_end'))
