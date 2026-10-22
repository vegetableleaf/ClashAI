"""Aggregate hits.py output: same-gap hits whose size differs live vs SIM, by attacker (single live attacker) and victim;
plus crown-tower shots (the live attacker is a tower only) by era. Only gaps where BOTH runs drop (> 0) count as 'same-gap'.
  python hitagg.py HITS_JSONL [HITS_JSONL ...]"""
import json, sys
from collections import Counter, defaultdict

same, diff = Counter(), Counter()
sizes = defaultdict(Counter)
one_side = Counter()
tower = defaultdict(Counter)
for f in sys.argv[1:]:
    for line in open(f):
        x = json.loads(line)
        era = 'L16' if x['match'][10:23] >= '20261019_1402' else 'pre'
        for victim, own, atl, ats, dl, ds, n in x['rows']:
            atl = tuple(a for a in atl)
            key = (atl[0] if len(atl) == 1 else '+'.join(atl) if atl else '-', victim)
            if dl is not None and ds is not None and dl > 0 and ds > 0:
                if abs(dl - ds) <= 2:
                    same[key] += n
                else:
                    diff[key] += n
                    sizes[key][(dl, ds)] += n
                if atl == ('tower',) and not victim.startswith('T'):
                    tower[era, 'own' if not own else 'opp'][(dl, ds) if abs(dl - ds) > 2 else 'same'] += n
            else:
                one_side[key] += n
print('same-gap hits: equal', sum(same.values()), 'different size', sum(diff.values()))
print('\nattacker -> victim with the most different-size same-gap hits (equal / different / top (live, SIM) sizes):')
for key, v in diff.most_common(40):
    print(f'{key[0]} -> {key[1]}: {same[key]} / {v} | {sizes[key].most_common(4)}')
print('\ncrown-tower shots on troops (live attacker = a tower only), by era and whose tower (own = OUR tower shooting):')
for k, c in sorted(tower.items()):
    tot = sum(c.values())
    print(k, 'n', tot, 'same', c['same'], 'diff', tot - c['same'], [x for x in c.most_common(6) if x[0] != 'same'])
