"""Aggregate retarget.py: live target switches (old target still alive) and whether the SIM made the same switch.
  python ragg.py RETARGET_JSONL [...]"""
import json, sys
from collections import Counter, defaultdict
by = defaultdict(Counter); ctx = defaultdict(Counter)
for f in sys.argv[1:]:
    for line in open(f):
        x = json.loads(line)
        for card, own, st, fresh, dep, ans, n in x['rows']:
            k = ('own ' if own else 'opp ') + card
            by[k][ans] += n
            ctx[(st, fresh, dep)][ans] += n
tot = Counter()
for c in by.values():
    tot.update(c)
print('all switches:', dict(tot), 'SIM same share %.3f' % (tot['same'] / max(1, sum(tot.values()))))
print('\nby context (live state before: 1 walk / 2 attack, new target fresh <= 30 ticks, new target still deploying):')
for k, c in sorted(ctx.items(), key=lambda kv: -sum(kv[1].values())):
    n = sum(c.values())
    print(k, n, dict(c), 'same %.3f' % (c['same'] / n))
print('\nby attacker card (most SIM misses):')
for k, c in sorted(by.items(), key=lambda kv: -(kv[1]['stayed'] + kv[1]['other']))[:30]:
    n = sum(c.values())
    print(k, n, dict(c), 'same %.3f' % (c['same'] / n))
