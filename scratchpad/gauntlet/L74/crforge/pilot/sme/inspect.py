"""Side-by-side recorded vs simulated objects for a tick range: python3 inspect.py REC.jsonl SIM.jsonl LO HI [kinds]"""
import json, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from sme import load_frames, canon_rec, canon_sim, diff
rec = load_frames(sys.argv[1], key='f')
sim = {}
for l in open(sys.argv[2]):
    o = json.loads(l); sim[o['t']] = o
lo, hi = int(sys.argv[3]), int(sys.argv[4])
kinds = sys.argv[5] if len(sys.argv) > 5 else 'TUPAS'
for t in range(lo, hi + 1):
    if t not in rec or t not in sim: continue
    d = diff(canon_rec(rec[t]), canon_sim(sim[t]))
    print('t', t, 'ndiff', len(d))
    for x in d:
        if x[0][0] in kinds: print('   ', x)
    if 'N' in kinds:  # names of sim objects in the diff area
        for e in sim[t]['E']:
            if e[1] in 'PCA' and e[2] not in ('KingTower','PrincessTower'): print('    sim', e[:9])
        for p in rec[t]['projectiles']: print('    recP', p['side'], p['x'], p['y'], p['card_id'], p['target_x'], p['target_y'])
