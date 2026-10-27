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
