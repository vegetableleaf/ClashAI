"""SME-F1FIX: which listed bodies the Rune Giant's friend search skips. Per launch tick of one Rune Giant (its projectiles
first seen that frame), every body listed in the frame before that is nearer to it than its farthest target, is not a
target and was not buffed by it before: tallied by (own / enemy, card id). Visible board only. Also: own bodies the
search could have taken, listed with their tags from the tables (characters.json TagsOnSpawn-like columns not read:
the card id is what the reader gives). python -I rg_filter.py LIVE.jsonl ..."""
import collections, json, os, sys

RG = 26000101
skip = collections.Counter()
groups = 0
for path in sys.argv[1:]:
    seen, seenp, prev, buffed = set(), set(), None, collections.defaultdict(set)
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line); t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        new = [p for p in d.get('proj') or () if p[3] == RG and p[6] not in seenp and len(p) > 9]
        seenp.update(p[6] for p in new)
        if new and prev:
            rgs = [e for e in prev['ents'] if e[3] == RG and e[1] is not None]
            by = collections.defaultdict(list)
            for p in new:   # the launching Rune Giant: nearest to the projectile's first point
                rg = min(rgs, key=lambda e: (e[1] - p[1]) ** 2 + (e[2] - p[2]) ** 2) if rgs else None
                if rg:
                    by[rg[7]].append((rg, p[9]))
            for a, lst in by.items():
                rg = lst[0][0]; tg = {x for _, x in lst}
                r2 = lambda e: (e[1] - rg[1]) ** 2 + (e[2] - rg[2]) ** 2
                tgt = [e for e in prev['ents'] if e[7] in tg and e[1] is not None]
                if not tgt:
                    continue
                groups += 1
                far = max(r2(e) for e in tgt)
                for e in prev['ents']:
                    if e[7] == a or e[7] in tg or e[7] in buffed[a] or e[1] is None or r2(e) >= far:
                        continue
                    skip['own' if e[0] == rg[0] else 'enemy', e[3]] += 1
                buffed[a] |= tg
        prev = d
print('launch groups', groups)
for (side, cid), n in sorted(skip.items(), key=lambda x: (x[0][0], -x[1])):
    print('  skipped nearer than a target: %-5s card %-10s x%d' % (side, cid, n))
