"""A2c-M census: casts of a spell seen through the buff it leaves (phase-2 unit buffs in the raw live log) vs the
extracted plays of that card. A buff instance is new when first seen on a body generation or when its remaining goes
up; made = first sighting - (duration - remaining) / 50. Instances with the same made tick and source side are one cast.
Reads only unit buffs (never the opponent elixir estimate).
python3 buff_census.py INPUTS.jsonl LOGDIR BUFF CARD"""
import collections, json, os, sys

inp, logdir, BUFF, CARD = sys.argv[1:5]


ALIVE = {}  # (path, tick) -> {side: set of unit names}


def casts(path):
    last, out, hp0 = {}, collections.defaultdict(list), {}
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:30]:
            continue
        d = json.loads(line)
        t = d['tick']
        al = collections.defaultdict(set)
        for u in (d.get('phase2') or {}).get('units', []):
            al[u['side']].add(u['name'])
        ALIVE[t] = al
        hp = {e[7]: e[4] for e in d.get('ents', [])}
        for u in (d.get('phase2') or {}).get('units', []):
            for b in u['buffs']:
                if b['name'] != BUFF:
                    continue
                k = (u['generation'], b['address'])
                rem, dur = b['remaining_ms_raw'], b['duration_ms_raw']
                if k not in last or rem > last[k]:
                    made = t - (dur - rem) // 50
                    out[(made, b.get('source_side_cached'))].append((u['side'], u['generation'], u['name'], t, rem, hp0.get(u['address'], 0) - hp.get(u['address'], 0)))
                last[k] = rem
        hp0 = hp
    return out


tot = collections.Counter()
for line in open(inp):
    r = json.loads(line)
    p = os.path.join(logdir, r['match'] + '.jsonl')
    if not os.path.exists(p):
        tot['no_log'] += 1
        continue
    plays = [q for q in r['plays'] if q['card'] == CARD and q['kind'] == 'play']
    used = set()
    for (made, s), hits in sorted(casts(p).items()):
        m = [i for i, q in enumerate(plays) if q['side'] == s and i not in used and abs(q['tick'] - made) <= 6]
        if m:
            i = min(m, key=lambda i: abs(plays[i]['tick'] - made))
            used.add(i)
            tot['matched d=%+d' % (made - plays[i]['tick'])] += 1
            print('MATCHED', r['match'], 'made', made, 'side', s, [h[2:] for h in hits])
        else:
            tot['unmatched'] += 1
            near = min((t for t in ALIVE if t >= made), default=None)
            src = sorted(n for n in ALIVE.get(near, {}).get(s, ()) if 'Tower' not in n) if near is not None else []
            print('UNMATCHED', r['match'], 'flagged' if r['flags'] else 'clean', 'made', made, 'side', s, hits[:3], 'SRC', src)
    for i, q in enumerate(plays):
        if i not in used:
            tot['play without buff'] += 1
            print('NOBUFF', r['match'], q['side'], q['tick'], q['source'], q.get('x'), q.get('y'))
print(dict(sorted(tot.items())))
