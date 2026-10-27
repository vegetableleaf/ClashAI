"""Ability commands in [onset-80, onset+5] of each match's first episode: python3 dossier_abil.py RUNDIR MATCH ..."""
import json, os, sys
run = sys.argv[1]
for m in sys.argv[2:]:
    r = json.load(open(os.path.join(run, m, 'result.json')))
    plan = json.load(open(os.path.join(run, m, 'plan.json')))
    t0 = r['episodes'][0]['start']
    ab = [(i, c['side'], c['run'], c.get('unit'), c['_src'].get('source'), (c['_src']['lo'], c['_src']['hi']))
          for i, c in enumerate(plan['cmds']) if c['kind'] in ('ability', 'skip') and t0 - 80 <= c['run'] <= t0 + 5]
    units = {('cmd%d_0' % i): c.get('card') for i, c in enumerate(plan['cmds'])}
    print(m, 'onset', t0, [(a[:3] + (units.get(a[3]),) + a[4:]) for a in ab])
