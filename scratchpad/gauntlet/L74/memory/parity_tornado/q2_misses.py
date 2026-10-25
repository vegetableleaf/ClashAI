"""Q2 misses: for each distinct live Tornado-to-king wake the SIM missed (replay starting on our Tornado cast), the Tornado
victims' pull live vs SIM (end-point error) and our king / princess damage live vs SIM -> is the miss a PULL difference
(the victim ends elsewhere) or a downstream fight / targeting difference? Read-only.
  python q2_misses.py CENSUS.json MATCHES_DIR"""
import glob
import json
import os
import sys

from q23_replay import load

j3w, _ = load(sys.argv[1], sys.argv[2:])
fights = {}
for f in glob.glob(sys.argv[2] + '/*.json'):
    for fi in json.load(open(f)).get('fights') or []:
        if fi.get('own') and fi['anchor']['name'] == 'Tornado':
            k = (os.path.basename(f)[:-5], fi['t0'])
            if (fi.get('jm') or {}).get('j2') or k not in fights:   # the spell fight (j2) and the king window share t0
                fights[k] = fi
ev = {}
for r in j3w:
    if r['anchor'] == 'Tornado':
        k = (r['m'], r['live'])
        if k not in ev or r['t0'] > ev[k]['t0']:
            ev[k] = r
for r in sorted(ev.values(), key=lambda r: (r['agree'], r['m'])):
    fi = fights.get((r['m'], r['t0']))
    s = fi['anchor']['side']
    tw = fi.get('towers', {})
    j2 = [v for v in (fi.get('jm') or {}).get('j2') or [] if v['victim'].startswith('opp ')]
    vs = '; '.join(f"{v['victim'][4:]} pull {v.get('pull_live')}/{v.get('pull_sim')} err {v.get('err')}" for v in j2) or '(no victim in reach at the cast)'
    print(f"{'AGREE' if r['agree'] else 'MISS '} {r['m']} t0 {r['t0']} live trig {r['live']} SIM {r['sim']} acts {r['acts']} | "
          f"king dmg live/SIM {tw.get(f'T{s}K', {}).get('live')}/{tw.get(f'T{s}K', {}).get('sim')} | {vs}")
