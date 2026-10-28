"""SME-F1FIX: Rune Giant (GiantBuffer, 26000101) enchant projectiles in live logs. Per launch (a projectile id with owner
26000101 first seen): ticks since the Rune Giant was first listed, its target's card id and distance, and the Rune
Giant's own-side bodies listed in the frame before ranked by distance (the ones it could have picked). Visible board
only (ents / proj rows). python -I rg_census.py LIVE.jsonl ..."""
import json, os, sys

RG = 26000101


def frames(path):
    seen = set()
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line); t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        yield t, d


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


tot = dict(logs=0, rg=0, launch=0, own_char=0, nearest=0)
for path in sys.argv[1:]:
    born, seenp, prev, out = {}, set(), None, []
    for t, d in frames(path):
        for e in d['ents']:
            if e[3] == RG and e[7] not in born:
                born[e[7]] = t
        for p in d.get('proj') or ():
            if p[3] != RG or p[6] in seenp:
                continue
            seenp.add(p[6])
            src = prev or d
            rgs = [e for e in src['ents'] if e[3] == RG and e[1] is not None]
            em = {e[7]: e for e in d['ents']}
            tg = em.get(p[9]) if len(p) > 9 else None
            if not rgs or tg is None:
                out.append('  %5d launch: no Rune Giant / target listed' % t); continue
            rg = min(rgs, key=lambda e: dist(e[1:3], p[1:3]))
            cand = sorted((round(dist(e[1:3], rg[1:3])), e[3], e[7] == p[9]) for e in src['ents']
                          if e[0] == rg[0] and e[3] != RG and e[1] is not None and dist(e[1:3], rg[1:3]) <= 8500)
            tot['launch'] += 1
            tot['own_char'] += tg[0] == rg[0] and str(tg[3]).startswith('26')
            out.append('  %5d launch +%d ticks: target side %s card %s at %d | own bodies <= 8500 (dist, card, targeted): %s' % (
                t, t - born.get(rg[7], t), tg[0] == rg[0] and 'own' or 'ENEMY', tg[3], round(dist(tg[1:3], rg[1:3])), cand[:6]))
        prev = d
    if born:
        tot['logs'] += 1; tot['rg'] += len(born)
        print('==', os.path.basename(path), 'Rune Giant bodies', len(born), 'launches', len(seenp))
        print('\n'.join(out))
print('logs', tot['logs'], 'Rune Giant bodies', tot['rg'], 'launches', tot['launch'], 'at own characters', tot['own_char'])
