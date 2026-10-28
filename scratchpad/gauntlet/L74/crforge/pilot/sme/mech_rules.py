"""Input rules from ticket A2c-M (crforge / unknown-mechanics cluster), each behind its own env flag. Same hook shape as
bp_rules: extract.match may call apply(path, plays, sides, frames) after bp_rules.apply; every flag off = plays unchanged.

SME_MECH_GB=1: the evolved Goblin Barrel's point. The evolved cast throws two barrels from the king, the real one at
the play point and a decoy at it mirrored across the arena's width (crforge ActionMirroredExtraSpell: decoy aim
18000 - x, same y; the game's flights agree, A2c-M). The extractor took the centroid of both, x = 9000. The real barrel
lands Goblins, the decoy GoblinDummy (fewer hp at the same level), both under the barrel's card id in the reader; the
play's x becomes the mean x of the higher-hp landing group.

SME_MECH_DRILL=1: a Goblin Drill play whose point is on a king tower. The drill digs from its king to the play point
(the reader shows the dig as a kind-15 body from the king), then surfaces as a kind-12 building. The extractor's
drill_surface found no surface for one evolved drill (225213@2415) and kept the dig's first point, on its own king;
crforge refused that play at its placement, then refused the match (evolution count unknown). The point becomes the
first kind-12 drill row of the side within DRILL_WIN ticks.

SME_MECH_HB=1: a hero Balloon ability (the Skeletrooper throw) dated from the throw's own projectile. crforge shows
BalloonHero_Skeletrooper_Projectile first on line R+3 (9 / 9 casts, hb_census.py); the reader shows it as a moving
projectile row of the hero Balloon card. seen_casts dates the cast from the trooper's landing with RoyaleSim's flight
model, which put R 1-9 ticks off on 4 of 11 casts. R = (first frame with the throw) - 3, window back to the frame
before it.

SME_MECH_ZAP=1 (needs the raw live log): a Zap dated from the ZapFreeze buff it puts on what it hits. The buff's made
tick c = first sighting - (500 - remaining) / 50 is exact. crforge, given the Zap at run R, hits on line R+1 with a
fresh buff, so R = c - 1. The area-effect dating (fx_made) gave R = c - 1 on 22 of 35 extracted Zaps and c - 2 on 12;
every Zap the SME repair moved went to c - 1 (100756@3433, 020550@3124), and 001702@2492 (Zap at c - 2: the evolved
Knight stunned a step early, a skeleton outside the area) is one of the 12. Window [c - 1, c - 1]."""
import os

GB = int(os.environ.get('SME_MECH_GB', '0'))
GB_ID, GB_WIN = 28000004, 150
DRILL = int(os.environ.get('SME_MECH_DRILL', '0'))
DRILL_IDS, DRILL_WIN = {27000013, 13000108}, 150  # GoblinDrill base / evolved reader ids
KINGS = ((9000, 3000), (9000, 29000))
HB = int(os.environ.get('SME_MECH_HB', '0'))
HB_ID, HB_LAG, HB_WIN = 203000006, 3, 40  # hero Balloon reader card; crforge throw line R+3
ZAP = int(os.environ.get('SME_MECH_ZAP', '0'))


def buff_made(path, buff):
    """{(made tick, source side)} of the instances of a unit buff in a raw live log (phase-2 unit buffs only)."""
    import json
    last, out = {}, set()
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:30] or buff.encode() not in line:
            continue
        d = json.loads(line)
        for u in (d.get('phase2') or {}).get('units', []):
            for b in u['buffs']:
                if b['name'] == buff:
                    k = (u['generation'], b['address'])
                    if k not in last or b['remaining_ms_raw'] > last[k]:
                        out.add((d['tick'] - (b['duration_ms_raw'] - b['remaining_ms_raw']) // 50, b.get('source_side_cached')))
                    last[k] = b['remaining_ms_raw']
    return out


def hb_throw(p, frames):
    """(first frame with the throw, the frame before it) for hero Balloon ability p, or None. A throw is a new projectile
    row of the hero card that is at another point (100..1000 units on) in the next frame; a bomb falls in place."""
    s, ts = p['side'], sorted(frames)
    pts = lambda t: {(q[1], q[2]) for q in frames[t]['P'] if q[0] == s and q[3] == HB_ID}  # noqa: E731
    for i in range(1, len(ts) - 1):
        t = ts[i]
        if not (p['tick'] - HB_WIN <= t <= p['tick'] + HB_WIN):
            continue
        new = pts(t) - pts(ts[i - 1])
        nxt = pts(ts[i + 1])
        if any(100 <= abs(x - a) + abs(y - b) <= 1000 for x, y in new for a, b in nxt):
            return t, ts[i - 1]
    return None


def evo_barrel_x(p, frames):
    """The real barrel's x for an evolved Goblin Barrel play p, or None (not an evolved cast, or no landing seen)."""
    s, ts = p['side'], sorted(t for t in frames if p['run_ticks'][0] <= t <= p['run_ticks'][0] + GB_WIN)
    pair = next((t for t in ts if any(a[0] == b[0] == s and a[3] == b[3] == GB_ID and a[2] == b[2] and a[1] < 9000 < b[1]
                                      and abs(a[1] + b[1] - 18000) <= 2 for a in frames[t]['P'] for b in frames[t]['P'])), None)
    if pair is None:
        return None
    before = {(e[1], e[2]) for e in frames[pair]['E'] if e[0] == s and e[3] == GB_ID}
    for t in ts:
        if t <= pair:
            continue
        new = [e for e in frames[t]['E'] if e[0] == s and e[3] == GB_ID and (e[1], e[2]) not in before]
        left, right = [e for e in new if e[1] < 9000], [e for e in new if e[1] > 9000]
        if left and right:
            hl, hr = max(e[4] for e in left), max(e[4] for e in right)
            if hl == hr:
                return None
            g = left if hl > hr else right
            return round(sum(e[1] for e in g) / len(g))
    return None


def drill_surface(p, frames):
    """(x, y) where the drill of play p surfaced: the first kind-12 drill row of its side after the play."""
    for t in sorted(t for t in frames if p['run_ticks'][0] < t <= p['run_ticks'][0] + DRILL_WIN):
        for e in frames[t]['E']:
            if e[0] == p['side'] and e[3] in DRILL_IDS and e[5] == 12:
                return e[1], e[2]
    return None


def apply(path, plays, sides, frames, log=None):
    if not (GB or DRILL or HB or ZAP):
        return plays
    zap = buff_made(path, 'ZapFreeze') if ZAP and path and any(p['card'] == 'Zap' for p in plays) else set()
    out = []
    for p in plays:
        if GB and p['kind'] == 'play' and p['card'] == 'GoblinBarrel':
            x = evo_barrel_x(p, frames)
            if x is not None and x != p['x']:
                if log is not None:
                    log.append(('gb_evo_x', p['side'], p['tick'], p['x'], x))
                p = dict(p, x=x, tile=[x // 1000, p['tile'][1]], mech='gb_evo_x')
        if DRILL and p['kind'] == 'play' and p['card'] == 'GoblinDrill' and \
                any(abs(p['x'] - kx) < 2000 and abs(p['y'] - ky) < 2000 for kx, ky in KINGS):
            s = drill_surface(p, frames)
            if s is not None:
                if log is not None:
                    log.append(('drill_surface', p['side'], p['tick'], (p['x'], p['y']), s))
                p = dict(p, x=s[0], y=s[1], tile=[s[0] // 1000, s[1] // 1000], mech='drill_surface')
        if HB and p['kind'] == 'ability' and p['card'] == 'Balloon':
            th = hb_throw(p, frames)
            if th is not None:
                lo, hi = th[1] + 1 - HB_LAG, th[0] - HB_LAG
                if [lo, hi] != p['run_ticks']:
                    if log is not None:
                        log.append(('hb_throw', p['side'], p['tick'], p['run_ticks'], [lo, hi]))
                    p = dict(p, tick=p['tick'] if lo <= p['tick'] <= hi else hi, run_ticks=[lo, hi], mech='hb_throw')
        if zap and p['kind'] == 'play' and p['card'] == 'Zap':
            c = sorted(c for c, s in zap if s == p['side'] and 1 <= c - p['tick'] <= 2)
            if c and [c[0] - 1] * 2 != p['run_ticks']:
                if log is not None:
                    log.append(('zap_buff', p['side'], p['tick'], p['run_ticks'], c[0] - 1))
                p = dict(p, tick=c[0] - 1, run_ticks=[c[0] - 1, c[0] - 1], mech='zap_buff')
        out.append(p)
    return out


# A2c-9Z: Zaps the reader never shows, from the ZapFreeze buff groups (a2c9z/zap_census.py, SME.md "A2c-9Z").
# SME_ZAP_ADD=1: a buff group (made c, source side s) with no Zap play of s near is a Zap cast at R = c - 1 when s's deck
#   holds Zap (battle log), every hit body with a known hp drop took that level's Zap damage (troop/building 305..319 at
#   16, crown tower 77), and no Electro body of s (Electro Dragon / Giant / Wizard / Spirit: same damage per level) was
#   alive within ELECTRO_D of a hit over [c - 4, c + 1]. Census: 0 / 749 groups of decks without Zap pass (1 / 749
#   without the deck test); 18 / 19 groups of Zap decks without Electro cards; 30 / 36 extracted Zaps. Point: as below.
# SME_ZAP_POINT=1: an extracted Zap matched to a buff group keeps its point only if that point covers every buff holder
#   and every victim-side body that died in the hit gap (a crown tower too: 204518@1822 killed a 33-hp tower), and no victim-side body without the buff; else it becomes the
#   grid point (100 units) covering all holders, then most dead, then fewest unbuffed, then the widest margin (up to
#   ZAP_MARGIN) to every reach edge, then nearest the centroid.
ZAP_ADD = int(os.environ.get('SME_ZAP_ADD', '0'))
ZAP_POINT = int(os.environ.get('SME_ZAP_POINT', '0'))
ZAP_DMG = {16: (306, 77), 15: (279, 70), 14: (254, 64), 13: (231, 58)}   # (troop, crown tower); fights.ZAP_HITS
ZAP_R, ELECTRO_D = 2500, 9000   # ZapArea radius; Electro reach (census max 8,035: an Electro Dragon chain)
ZAP_TOL = 150                   # point-consistency slack, units (3 ticks of a medium-speed walk)
ZAP_MARGIN = 300                # grid tie-break: prefer points >= this far inside every holder's reach and outside the rest


def zap_groups(path):
    """[{c, s, hits: {addr: body}, pre, post, electro: [(x, y)]}] for every ZapFreeze group of a raw live log; a body is
    {side, name, x, y, hp, buffs}. pre / post: the bodies of the last frame before c / the first frame at or after c."""
    import json
    fr, last, G = [], {}, {}
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:30]:
            continue
        d = json.loads(line)
        ents = {e[7]: e for e in d.get('ents', [])}
        bodies = {}
        for u in (d.get('phase2') or {}).get('units', []):
            e = ents.get(u['address'])
            if e:
                bodies[u['address']] = dict(side=u['side'], name=u['name'], x=e[1], y=e[2], hp=e[4],
                                            buffs=[b['name'] for b in u['buffs']])
            for b in u['buffs']:
                if b['name'] != 'ZapFreeze':
                    continue
                k = (u['generation'], b['address'])
                if k not in last or b['remaining_ms_raw'] > last[k]:
                    c = d['tick'] - (b['duration_ms_raw'] - b['remaining_ms_raw']) // 50
                    G.setdefault((c, b.get('source_side_cached')), set()).add(u['address'])
                last[k] = b['remaining_ms_raw']
        fr.append((d['tick'], bodies))
    out = []
    for (c, s), addrs in sorted(G.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        pre = next((b for t, b in reversed(fr) if t < c), {})
        post = next((b for t, b in fr if t >= c), {})
        hits = {a: dict(post[a], drop=pre[a]['hp'] - post[a]['hp'] if a in pre else None) for a in addrs if a in post}
        el = [(b['x'], b['y']) for t, B in fr if c - 4 <= t <= c + 1 for b in B.values() if b['side'] == s and 'Electro' in b['name']]
        out.append(dict(c=c, s=s, hits=hits, pre=pre, post=post, electro=el))
    return out


def zap_is_cast(g, level):
    """True when the group's evidence is a Zap of this level (SME_ZAP_ADD)."""
    import math
    zt, zc = ZAP_DMG.get(level, (None, None))
    if zt is None or not g['hits']:
        return False
    ok = 0
    for h in g['hits'].values():
        if h['drop'] is None or h['name'].endswith('FloatingCube') or any('Fortify' in b for b in h['buffs']):
            continue   # no hp of its own (hero IW cube) / damage reduced (evolved Knight)
        if not (abs(h['drop'] - zc) <= 1 if h['name'] in ('KingTower', 'PrincessTower') else zt - 1 <= h['drop'] <= zt + 13):
            return False
        ok += 1
    return ok > 0 and not any(math.hypot(x - h['x'], y - h['y']) <= ELECTRO_D for x, y in g['electro'] for h in g['hits'].values())


def zap_point(g, level, stats, xy=None):
    """(x, y) of the Zap of group g: xy when it is consistent with the evidence, else the grid point (SME_ZAP_POINT)."""
    import math
    zt, zc = ZAP_DMG.get(level, (306, 77))
    v = 1 - g['s']
    rad = lambda b: (stats(b['name']) or {}).get('collision_radius_milli') or 500   # noqa: E731
    hit = list(g['hits'].values())
    dead = [b for a, b in g['pre'].items() if b['side'] == v and a not in g['post'] and 0 < b['hp'] <= (zc if 'Tower' in b['name'] else zt)
            and min(math.hypot(b['x'] - h['x'], b['y'] - h['y']) for h in hit) <= 2 * ZAP_R]
    rest = [b for a, b in g['post'].items() if b['side'] == v and a not in g['hits'] and b['hp'] > 0]
    cov = lambda b, x, y: math.hypot(b['x'] - x, b['y'] - y) <= ZAP_R + rad(b)   # noqa: E731
    near = lambda b, x, y, t: math.hypot(b['x'] - x, b['y'] - y) <= ZAP_R + rad(b) + t   # noqa: E731
    if xy is not None and all(near(b, *xy, ZAP_TOL) for b in hit + dead) and not any(near(b, *xy, -ZAP_TOL) for b in rest):
        return xy   # ZAP_TOL: frame positions are up to 2 ticks from the hit (180652 / 235355: 91 / 21 past the reach, exact)
    V = hit + dead
    cx, cy = sum(b['x'] for b in V) / len(V), sum(b['y'] for b in V) / len(V)
    best = None
    for gx in range(int(min(b['x'] for b in hit)) - ZAP_R, int(max(b['x'] for b in hit)) + ZAP_R + 1, 100):
        for gy in range(int(min(b['y'] for b in hit)) - ZAP_R, int(max(b['y'] for b in hit)) + ZAP_R + 1, 100):
            if not all(cov(b, gx, gy) for b in hit):
                continue
            m = min([ZAP_R + rad(b) - math.hypot(b['x'] - gx, b['y'] - gy) for b in hit] +
                    [math.hypot(b['x'] - gx, b['y'] - gy) - ZAP_R - rad(b) for b in rest if not cov(b, gx, gy)] + [ZAP_MARGIN])
            k = (sum(cov(b, gx, gy) for b in dead), -sum(cov(b, gx, gy) for b in rest), m, -math.hypot(gx - cx, gy - cy))
            if best is None or k > best[0]:
                best = (k, gx, gy)
    return (best[1], best[2]) if best else xy


def zap_buffs(path, plays, sides, stats, log=None):
    """SME_ZAP_ADD / SME_ZAP_POINT (above). sides: {side: side_info}; stats: extract.table_shims' stats."""
    deck = {s: sides[s]['deck'] for s in sides}
    if not any('Zap' in d for d in deck.values()):
        return plays
    plays, added = list(plays), False
    for g in zap_groups(path):
        s = g['s']
        if s not in deck or 'Zap' not in deck[s] or not g['hits']:
            continue
        k = deck[s].index('Zap')
        level = sides[s]['levels'][k]
        near = [i for i, p in enumerate(plays) if p['side'] == s and p['kind'] == 'play' and p['card'] == 'Zap'
                and abs(p['tick'] - (g['c'] - 1)) <= 3]
        if near and ZAP_POINT:
            i = min(near, key=lambda i: abs(plays[i]['tick'] - (g['c'] - 1)))
            p = plays[i]
            xy = zap_point(g, level, stats, (p['x'], p['y']))
            if xy != (p['x'], p['y']):
                if log is not None:
                    log.append(('zap_point', s, p['tick'], (p['x'], p['y']), xy))
                plays[i] = dict(p, x=xy[0], y=xy[1], tile=[xy[0] // 1000, xy[1] // 1000],
                                mech=(p.get('mech') + '+' if p.get('mech') else '') + 'zap_point')
        elif not near and ZAP_ADD and zap_is_cast(g, level):
            xy = zap_point(g, level, stats)
            if xy is None:
                continue
            R = g['c'] - 1
            if log is not None:
                log.append(('zap_add', s, R, xy))
            plays.append(dict(side=s, kind='play', card='Zap', deck_index=k, name='Zap', form=0, run_ticks=[R, R], tick=R,
                              source='spell_seen', x=xy[0], y=xy[1], tile=[xy[0] // 1000, xy[1] // 1000], n=0, inferred=True,
                              mech='zap_add'))
            added = True
    return sorted(plays, key=lambda p: p["tick"]) if added else plays
