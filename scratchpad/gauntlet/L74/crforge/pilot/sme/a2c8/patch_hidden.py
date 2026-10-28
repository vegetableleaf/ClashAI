import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
fn = '''

def reader_hidden(path, cat):
    """A2c round 8 (SME_HIDDEN=1): bodies that leave the reader's ents list while a reader projectile still targets their
    address, i.e. the game object lives on unlisted. Census on the 138 matches (round 8): exactly 2, both a hero Mini
    PEKKA 2 ticks into its ability cast (181217@3041, 213436@778); crforge's body equals every projectile target point
    and dies on the same frame as the game's. -> [{side, name (crforge character), last (last ents tick), end (last tick a
    projectile targets it), track {tick: [x, y]}}]. The track point is the target point of a projectile already seen in
    the frame before (a projectile fired this frame can carry its fire-time point); a frame with only new projectiles
    takes their point if they agree."""
    last, prev, out_t = {}, set(), {}
    seen = set()
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        here = set()
        for e in d['ents']:
            last[e[7]] = (t, e)
            here.add(e[7])
        cur = set()
        for pr in d['proj']:
            a = pr[9] if len(pr) > 9 else None
            if a and a in last and a not in here:
                out_t.setdefault(a, {}).setdefault(t, []).append((pr[6] in prev, pr[4], pr[5]))
            cur.add(pr[6])
        prev = cur
    res = []
    for a, by_t in out_t.items():
        lt, e = last[a]
        ticks = sorted(t for t in by_t if t > lt)
        if not ticks:
            continue
        c = cat.get(e[3]) or {}
        name = c.get('hero_character') if e[3] == c.get('hero_form_id') else c.get('summon_character')
        track = {}
        for t in ticks:
            pts = {(x, y) for o, x, y in by_t[t] if o} or {(x, y) for o, x, y in by_t[t]}
            if len(pts) == 1:
                track[str(t)] = list(pts.pop())
        res.append(dict(side=e[0], name=name, last=lt, end=ticks[-1], track=track))
    return res
'''
anchor = '\n\ndef match(path, bl=None'
assert anchor in s and 'def reader_hidden' not in s
s = s.replace(anchor, fn + anchor, 1)
old = "                own_taps=[dict(tick=p['tick'], name=p['name'], x=p['x'], y=p['y']) for p in m['plays']]), None"
new = ("                own_taps=[dict(tick=p['tick'], name=p['name'], x=p['x'], y=p['y']) for p in m['plays']],\n"
       "                **(dict(reader_hidden=reader_hidden(path, cat)) if os.environ.get('SME_HIDDEN') == '1' else {})), None")
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ok')
