"""Lock-threshold sensitivity: share of reach X-Bows whose princess damage (30 s) >= thr, live vs SIM, all and on-time-answered.
python dmg_b.py live NAME ..."""
import json, sys
D = {n: json.load(open(f'out/siege_b_{n}.json'))['xbows'] for n in sys.argv[1:]}
TH = (0.0001, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50)
for sub, f in (('all', lambda r: True), ('ontime_unit', lambda r: r['cls'] == 'answer_ontime' and r['kind'] != 'spell'),
               ('none', lambda r: r['cls'] == 'none')):
    print(f'## {sub}: share with damage >= thr ' + ' '.join(f'{t:g}' for t in TH))
    for n, rs in D.items():
        s = [r for r in rs if f(r)]
        print(f'  {n:8s} n {len(s):5d} ' + ' '.join(f'{sum(r["dmg"] >= t for r in s) / len(s):.3f}' for t in TH) +
              f' | locked flag {sum(r["locked"] for r in s) / len(s):.3f}')
