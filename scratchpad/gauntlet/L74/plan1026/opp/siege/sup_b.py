"""Support around the answer: our (CLXIII) plays and the opponent's elixir in the 10 s after a reach X-Bow, by class.
python sup_b.py live NAME ..."""
import json, sys, statistics as st
for n in sys.argv[1:]:
    rs = json.load(open(f'out/siege_b_{n}.json'))['xbows']
    for sub, f in (('all', lambda r: True), ('ontime', lambda r: r['cls'] == 'answer_ontime')):
        s = [r for r in rs if f(r)]
        own = [r['own_plays_10s'] for r in s]
        lk = {k: [r['locked'] for r in s if min(r['own_plays_10s'], 3) == k] for k in range(4)}
        print(f"{n:8s} {sub:7s} n {len(s):5d} our plays in 10 s mean {st.mean(own):.2f} | opp elixir in 10 s mean {st.mean(r['opp_spent_10s'] for r in s):.2f} | "
              f"lock by our plays 0/1/2/3+: " + ' '.join(f"{sum(v)/len(v):.2f}(n{len(v)})" if v else '-' for v in lk.values()))
