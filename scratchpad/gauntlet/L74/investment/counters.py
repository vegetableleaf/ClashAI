"""Derive the X-Bow counter list from what actually neutralised our (live) and pros' (re-drive) BRIDGE X-Bows.
Per opponent card c:  engaged = c played within 7 tiles of the X-Bow during its life, or a c body within 7 tiles of it.
  lock rate / mean reach damage when c engaged vs the source's bridge X-Bows where c did not engage
  deck level: lock rate of bridge X-Bows in matches where c was revealed at all vs not.
    python counters.py  -> counters.out, counters.json (the list analyze.py uses)"""
import json
import pickle
from collections import defaultdict

R = pickle.load(open('rows.pkl', 'rb'))
B = [r for r in R['xbow'] if r['type'] == 'bridge' and 'life_s' in r and not r['censored']]
rev = {m['key']: set(m['revealed']) for m in R['match']}


def stats(rs):
    n = len(rs)
    return (n, sum(r['lock'] for r in rs) / n if n else float('nan'), sum(r['dmg_reach'] for r in rs) / n if n else float('nan'),
            sum(r['life_s'] < 10 for r in rs) / n if n else float('nan'))


out, res = [], {}
for src in ('live', 'pro'):
    rs = [r for r in B if r['src'] == src]
    base = stats(rs)
    out.append(f'== {src}: bridge X-Bows (uncensored) n={base[0]} lock {base[1]:.3f} dmg {base[2]:.3f} died<10s {base[3]:.3f}')
    eng, deck = defaultdict(list), defaultdict(list)
    for r in rs:
        for c in set(r['answer']) | set(r['near']):
            eng[c].append(r)
        for c in rev[r['key']]:
            deck[c].append(r)
    for c in eng:
        e, ne = stats(eng[c]), stats([r for r in rs if r not in eng[c]]) if False else None
        d = stats(deck.get(c, []))
        nd = stats([r for r in rs if c not in rev[r['key']]])
        res.setdefault(c, {})[src] = dict(n_eng=e[0], lock_eng=e[1], dmg_eng=e[2], fast_eng=e[3], n_deck=d[0], lock_deck=d[1],
                                          dmg_deck=d[2], lock_nodeck=nd[1], dmg_nodeck=nd[2], base_lock=base[1], base_dmg=base[2])
rows = []
for c, v in res.items():
    L, P = v.get('live'), v.get('pro')
    if not (L and P) or L['n_deck'] < 20 or P['n_deck'] < 20:
        continue
    rows.append((c, L, P))
# rank by the deck-level lock drop, averaged over the two sources (each relative to its own no-deck rate)
rows.sort(key=lambda t: (t[1]['lock_deck'] - t[1]['lock_nodeck']) + (t[2]['lock_deck'] - t[2]['lock_nodeck']))
out.append('\ncard | LIVE n_deck lock(deck) vs lock(no deck) d_dmg | n_eng lock(eng) dmg(eng) died<10s(eng) || PRO same')
for c, L, P in rows:
    out.append(f"{c:18s} | {L['n_deck']:4d} {L['lock_deck']:.2f} vs {L['lock_nodeck']:.2f} {L['dmg_deck'] - L['dmg_nodeck']:+.3f} | "
               f"{L['n_eng']:4d} {L['lock_eng']:.2f} {L['dmg_eng']:.3f} {L['fast_eng']:.2f} || "
               f"{P['n_deck']:4d} {P['lock_deck']:.2f} vs {P['lock_nodeck']:.2f} {P['dmg_deck'] - P['dmg_nodeck']:+.3f} | "
               f"{P['n_eng']:4d} {P['lock_eng']:.2f} {P['dmg_eng']:.3f} {P['fast_eng']:.2f}")
open('counters.out', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out[:80]))
json.dump({c: v for c, v in res.items()}, open('counters_raw.json', 'w'), indent=0)
