"""SME-F1FIX: does the live Rune Giant stop moving when it buffs (giantbuffer_no_move_on_buff, ExecuteIfTrue hit_timer != 0)?
Per launch tick L (its enchant projectiles first seen), the Rune Giant's per-frame step (units) over [L - 24, L + 24] and
whether it was attacking (an RG-owned non-enchant projectile or a hp drop on a building it stands by is not read: its
step before L tells walking from standing). Visible board only. python -I rg_move.py LIVE.jsonl ..."""
import json, os, sys

RG = 26000101
for path in sys.argv[1:]:
    seen, seenp, pos, launches = set(), set(), {}, []
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line); t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        for e in d['ents']:
            if e[3] == RG and e[1] is not None:
                pos.setdefault(e[7], {})[t] = (e[1], e[2])
        for p in d.get('proj') or ():
            if p[3] == RG and p[6] not in seenp:
                seenp.add(p[6])
                a = min(pos, key=lambda a: min(((x - p[1]) ** 2 + (y - p[2]) ** 2) for x, y in [pos[a].get(t) or (10 ** 6, 10 ** 6)]))
                if (a, t) not in launches:
                    launches.append((a, t))
    for a, L in launches:
        tr = pos[a]
        ts = [t for t in sorted(tr) if L - 24 <= t <= L + 24]
        steps = ['%d:%d' % (t - L, abs(tr[t][0] - tr[u][0]) + abs(tr[t][1] - tr[u][1])) for u, t in zip(ts, ts[1:])]
        print(os.path.basename(path)[10:], L, ' '.join(steps))
