"""pair_rows.py A_MATCHES B_MATCHES -- per paired game (seed, tag, side, opp deck): outcome / plays / end tick of A and B,
and how many games are identical on (outcome, plays_accepted, end_tick, tower_hp_diff). Read-only diagnostics."""
import json
import sys


def load(p):
    out = {}
    for line in open(p):
        r = json.loads(line)
        out[(r['seed'], r['tag'], r['learner_side'], tuple(r['opp_deck']))] = r
    return out


a, b = load(sys.argv[1]), load(sys.argv[2])
ks = sorted(set(a) & set(b))
F = ('outcome', 'plays_accepted', 'end_tick', 'tower_hp_diff')
same = 0
for k in ks:
    va, vb = [tuple(x.get(f) for f in F) for x in (a[k], b[k])]
    same += va == vb
    print(k[0], k[1], k[2], va, vb, '' if va == vb else 'DIFF')
print(f'paired {len(ks)} (A {len(a)}, B {len(b)}); identical on {F}: {same}')
