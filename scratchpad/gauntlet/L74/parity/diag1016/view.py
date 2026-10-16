"""Print one fight: tower hp live vs sim per frame, and body diffs. usage: view.py STEM T0 [every]"""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import capture
stem, T0 = sys.argv[1], int(sys.argv[2]); every = int(sys.argv[3]) if len(sys.argv) > 3 else 1
res, ctx = capture(stem, lambda f, a: f['t0'] == T0)
cat = ctx['catalog']
for f, a, rows, setup, r in res:
    print('ANCHOR', a, 'flags', r.get('flags'))
    print('EVENTS', [(ctx['events'][j]['tick'], ctx['events'][j]['side'], ctx['events'][j]['name'], ctx['events'][j]['source']) for j in f['events']])
    print('own side', ctx['m']['side'])
    for i, (t, live, sim) in enumerate(rows):
        if i % every: continue
        lt = {b['id']: b['hp'] for b in live if b['tower']}; st = {b['id']: b['hp'] for b in sim if b['tower']}
        tw = ' '.join(f"{k}:{lt[k]}/{st.get(k)}" for k in sorted(lt) if lt[k] != st.get(k) or i == 0)
        L = sorted((cat[b['card_id']]['display_name'][:10] if b['card_id'] in cat else str(b['card_id']), b['side'], round(b['x']), round(b['y']), b['hp']) for b in live if not b['tower'])
        S = sorted((b['name'][:10], b['side'], round(b['x']), round(b['y']), b['hp']) for b in sim if not b['tower'])
        print(f"t{t} TW {tw}")
        print('   L', L)
        print('   S', S)
