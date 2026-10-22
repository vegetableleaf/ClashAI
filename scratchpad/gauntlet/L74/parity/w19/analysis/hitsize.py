import json, sys
from collections import Counter, defaultdict
c = Counter(); ex = defaultdict(Counter); eq = Counter()
for f in sys.argv[1:]:
    for line in open(f):
        x = json.loads(line)
        for victim, own, atl, ats, dl, ds, n in x['rows']:
            if dl is None or ds is None or dl <= 30 or ds <= 30:
                continue
            k = ('+'.join(atl) or '-', victim, 'own victim' if own else 'opp victim')
            if abs(dl - ds) > max(5, .05 * max(dl, ds)):
                c[k] += n; ex[k][(dl, ds)] += n
            else:
                eq[k] += n
print('attacker -> victim | true size differences (both > 30 hp) | equal | top (live, SIM)')
for k, v in c.most_common(30):
    print(k, v, eq[k], ex[k].most_common(4))
print('total diff', sum(c.values()), 'equal', sum(eq.values()))
