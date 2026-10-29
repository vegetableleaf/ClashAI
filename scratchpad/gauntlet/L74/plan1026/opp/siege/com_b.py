"""Lock rate by opponent elixir committed in the 10 s after a reach X-Bow (bins), live vs SIM, + the gap re-weighted to the live
commitment mix.  python com_b.py live NAME ..."""
import json, sys
B = ((0, 3), (3, 6), (6, 9), (9, 12), (12, 99))
L = json.load(open('out/siege_b_live.json'))['xbows']
def binof(r): return next(i for i, (a, b) in enumerate(B) if a <= r['opp_spent_10s'] < b)
def tab(rs):
    out = []
    for i in range(len(B)):
        s = [r['locked'] for r in rs if binof(r) == i]
        out.append((len(s) / len(rs), sum(s) / len(s) if s else float('nan'), len(s)))
    return out
tl = tab(L)
print('bins (elixir in 10 s):', B)
print('live    ', ' '.join(f'{sh:.2f}/{lk:.2f}' for sh, lk, n in tl), f"lock {sum(r['locked'] for r in L)/len(L):.3f}")
for n in sys.argv[1:]:
    S = json.load(open(f'out/siege_b_{n}.json'))['xbows']
    ts = tab(S)
    rew = sum(tl[i][0] * ts[i][1] for i in range(len(B)))
    print(f'{n:8s}', ' '.join(f'{sh:.2f}/{lk:.2f}' for sh, lk, _ in ts), f"lock {sum(r['locked'] for r in S)/len(S):.3f} | at the live commitment mix {rew:.3f}")
