"""On-time answer placement relative to the X-Bow (lane-mirrored: dx > 0 = toward the centre), per card, live vs SIM;
+ follow-up commitment: opponent elixir played in the X-Bow's lane within 10 s.  python place_b.py live NAME CARD ..."""
import json, sys, statistics as st
L, S = (json.load(open(f'out/siege_b_{n}.json'))['xbows'] for n in sys.argv[1:3])
for c in sys.argv[3:]:
    for nm, rs in (('live', L), (sys.argv[2], S)):
        on = [r for r in rs if r['cls'] == 'answer_ontime' and r['card'] == c]
        if len(on) < 10: continue
        dx = [(r['ax'] - r['xx']) * (1 if r['xx'] < 9 else -1) for r in on]
        dy = [r['ay'] - r['xy'] for r in on]
        q = lambda v: '/'.join(f'{x:.1f}' for x in st.quantiles(v, n=4))
        lk = lambda f: (lambda s: f"{sum(r['locked'] for r in s)/len(s):.2f} n{len(s)}" if s else '-')([r for r, a, b in zip(on, dx, dy) if f(a, b)])
        print(f'{c:14s} {nm:7s} n {len(on):4d} lock {sum(r["locked"] for r in on)/len(on):.2f} | dx q {q(dx)} dy q {q(dy)} | '
              f'dy<2 (at/behind X-Bow, toward us) lock {lk(lambda a, b: b < 2)} ; dy>=2 lock {lk(lambda a, b: b >= 2)}')
for nm, rs in (('live', L), (sys.argv[2], S)):
    n2 = [r['n_plays_10s'] for r in rs if r['cls'] == 'answer_ontime']
    print(nm, 'on-time answered X-Bows: mean opponent plays in 10 s', round(st.mean(n2), 2), '| lock by plays-in-10s:',
          {k: (round(sum(r['locked'] for r in rs if r['cls'] == 'answer_ontime' and min(r['n_plays_10s'], 4) == k) / max(1, sum(1 for r in rs if r['cls'] == 'answer_ontime' and min(r['n_plays_10s'], 4) == k)), 2),
               sum(1 for r in rs if r['cls'] == 'answer_ontime' and min(r['n_plays_10s'], 4) == k)) for k in (1, 2, 3, 4)})
