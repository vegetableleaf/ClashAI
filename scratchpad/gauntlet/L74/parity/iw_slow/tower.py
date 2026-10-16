"""Tower victim summary from probe output: red princess tower's buffs and its hit interval on the blue shooter.
Usage: python tower.py probe_out.json"""
import json
import sys

R = json.load(open(sys.argv[1]))['runs']
for name in [n for n in R if n.startswith('tower_')]:
    fr = [f for f in R[name] if 'rows' in f]
    def tower(f):
        return next((r for r in f['rows'] if r['team'] == 'Red' and r['kind'] == 'PrincessTower'
                     and r['pos']['x'] < 162000), None)
    def shooter(f):
        return next((r for r in f['rows'] if r['team'] == 'Blue' and r['kind'] == 'Troop'), None)
    bt = [(f['tick'], tuple(b['id'] for b in tower(f)['buffs'])) for f in fr if tower(f)]
    drops = [f1['tick'] for f0, f1 in zip(fr, fr[1:]) if shooter(f0) and shooter(f1) and shooter(f1)['hp'] < shooter(f0)['hp']]
    first = next((t for t, ids in bt if ids), None)
    print(name, 'tower first buffed tick', first, 'buff ids', sorted({i for _, ids in bt for i in ids}),
          'shooter hp-drop ticks', drops, 'intervals', [b - a for a, b in zip(drops, drops[1:])])
