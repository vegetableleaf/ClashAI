"""Off byte-identity across code versions: the same arm's match records (outcome, crowns, tower HP, end tick, plays,
decisions, behaviour) from two runs.  python off_identity.py <run A dir> <run B dir> <arm>"""
import json, os, sys

A, B, arm = sys.argv[1:4]
KEYS = ('outcome', 'crowns_for', 'crowns_against', 'tower_hp_for', 'tower_hp_against', 'end_tick', 'plays_attempted',
        'plays_accepted', 'opp_plays_accepted', 'decisions', 'behaviour')


def load(O):
    out = {}
    for s in ('evo', 'lad'):
        p = f'{O}/v3_{arm}_{s}/matches.jsonl'
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                out[(s, r['tag'])] = tuple(json.dumps(r.get(k), sort_keys=True) for k in KEYS)
    return out


a, b = load(A), load(B)
common = sorted(set(a) & set(b))
diff = [k for k in common if a[k] != b[k]]
print(f'{arm}: {len(common)} common matches (A {len(a)}, B {len(b)}); records identical {len(common) - len(diff)}; '
      f'differ {len(diff)} {diff[:10]}')
