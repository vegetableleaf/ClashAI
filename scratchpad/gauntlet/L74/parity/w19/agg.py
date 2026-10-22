"""Aggregate cls.py output: the failing J1 fights by first-divergence cause, by anchor card, and by (cause x card).
  python agg.py CLS_DIR [CENSUS_JSON] [--top N]
Cause of a failing fight = its first disagreeing anchor body's (or spell victim's, or tower's) first divergence among the
bodies next to it: kind (tgt / pos / hp / presence / gone / tower) x the diverging body (own / opp card, set-up or new) x
when (ticks after the fight start). 'direct' = no earlier divergence: the disagreeing death / hit is itself the first."""
import json
import sys
from collections import Counter, defaultdict

d = sys.argv[1]
census = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 25
rows, errs = [], Counter()
for line in open(f'{d}/cls.jsonl'):
    x = json.loads(line)
    if x['err']:
        errs['match:' + x['err'][:60]] += 1
    for f in x['fights']:
        if 'error' in f:
            errs['fight:' + f['error'][:60]] += 1
            continue
        rows.append(f)
share = {}
if census:
    tot = sum(census['plays'].values())
    share = {k: v / tot for k, v in census['plays'].items()}


def cause(f):
    b = f['bad'][0] if f['bad'] else None
    if b is None:
        return ('none', '-', '-', '-')
    fd = b['first']
    if fd is None:
        return (b['kind'], 'direct', '-', '-')
    when = 'setup<=10' if fd['dt'] <= 10 else 'early<=40' if fd['dt'] <= 40 else 'late'
    who = fd['body'] + (' [setup]' if fd.get('setup') else ' [anchor]' if fd.get('anchor') else ' [new]')
    kind = fd['kind']
    if kind.startswith('gone') and b['dt'] - fd['dt'] <= 4:
        kind = 'direct_death'
    return (b['kind'], kind, who, when)


print(f'classified failing fights: {len(rows)}; errors {dict(errs)}')
C = [cause(f) for f in rows]
print('\n== disagreement kind (the anchor side)')
for k, v in Counter(c[0] for c in C).most_common():
    print(f'{k:28s} {v:5d} {v/len(C):.3f}')
print('\n== first divergence kind')
for k, v in Counter(c[1] for c in C).most_common():
    print(f'{k:28s} {v:5d} {v/len(C):.3f}')
print('\n== first divergence kind x when')
for k, v in Counter((c[1], c[3]) for c in C).most_common(20):
    print(f'{str(k):45s} {v:5d} {v/len(C):.3f}')
print('\n== first diverging body (kind, body)')
for k, v in Counter((c[1], c[2]) for c in C).most_common(top):
    print(f'{str(k):70s} {v:5d} {v/len(C):.3f}')
print('\n== setup vs new vs anchor for the first divergence')
print(Counter(('setup' if '[setup]' in c[2] else 'anchor' if '[anchor]' in c[2] else 'new' if '[new]' in c[2] else c[1]) for c in C))
print('\n== by anchor card: failing fights, top causes')
by = defaultdict(list)
for f, c in zip(rows, C):
    by[f['lab']].append(c)
for lab, cs in sorted(by.items(), key=lambda kv: -len(kv[1]))[:top]:
    sh = share.get(lab)
    print(f"{lab} | fails {len(cs)} | play share {sh:.4f}" if sh is not None else f"{lab} | fails {len(cs)}", '|',
          '; '.join(f'{k[0]}/{k[1]} {v}' for k, v in Counter((c[1], c[2].split(' [')[0]) for c in cs).most_common(4)))
json.dump([dict(f, cause=c) for f, c in zip(rows, C)], open(f'{d}/cls_flat.json', 'w'))
