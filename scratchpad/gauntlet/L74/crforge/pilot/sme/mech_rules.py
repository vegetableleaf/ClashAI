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


# A2c-10 SME_IWGHOST10=1 (needs the raw live log): an opponent hero Ice Wizard press that was never cast. The ability
# waits for a valid target (an enemy with the hero's Cold / Slow buff, sme_live.iw_valid_ticks), and crforge's held press
# re-searches the hero's route. 211239's IW (play 4366) had a valid target only over [4511, 4762] and died at 4912 with no
# cast; a press at 4892 alone makes the match exact (4890, 4891, 4893 do not), and the reader shows nothing of it. Such a
# hero gets a 'ghost' press with window [max(play + 1, last valid frame + 1), last frame listed]: plan_from writes it as
# kind 'skip', and the fitter enables it only at an onset where that hero diverges (sme_live.variants_at).
IWGHOST10 = int(os.environ.get('SME_IWGHOST10', '0'))


def hero_lives(path, name='IceWizardHero'):
    """[(side, first tick, last tick)] of every generation of a hero unit in a raw live log (phase-2 units)."""
    import json
    life = {}
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40] or name.encode() not in line:
            continue
        d = json.loads(line)
        for u in (d.get('phase2') or {}).get('units', []):
            if u.get('name') == name:
                r = life.setdefault(u['generation'], [u['side'], d['tick'], d['tick']])
                r[2] = d['tick']
    return sorted(life.values(), key=lambda r: r[1])


def iw_ghosts(path, plays, my, log=None):
    import sme_live
    vt, lives, out = None, None, list(plays)
    for p in plays:
        if p['kind'] != 'play' or p['card'] != 'IceWizard' or p.get('form') != 2 or p['side'] == my:
            continue
        if lives is None:
            lives, vt = hero_lives(path), sme_live.iw_valid_ticks(path)
        s, k = p['side'], p['deck_index']
        g = next((r for r in lives if r[0] == s and p['tick'] - 2 <= r[1] <= p['tick'] + 30), None)
        if g is None:
            continue
        nxt = min((q['tick'] for q in plays if q is not p and q['side'] == s and q['deck_index'] == k and q['kind'] == 'play'
                   and q['tick'] > p['tick']), default=10 ** 9)
        if any(q['side'] == s and q['deck_index'] == k and q['kind'] == 'ability' and p['tick'] < q['tick'] < nxt for q in plays):
            continue   # cast (or its press dated): not a ghost
        lastv = max((t for t in vt if p['tick'] < t <= g[2] and vt[t][s]), default=None)
        lo, hi = max(p['tick'] + 1, (lastv or 0) + 1), min(g[2], nxt - 1)
        if lo > hi:
            continue
        if log is not None:
            log.append(('iw_ghost', s, p['tick'], [lo, hi]))
        out.append(dict(side=s, kind='ability', card='IceWizard', deck_index=k, name='IceWizard', form=0, run_ticks=[lo, hi],
                        tick=lo, source='iw_ghost', ghost=1))
    return out


def apply(path, plays, sides, frames, log=None):
    if IWGHOST10 and path:
        plays = iw_ghosts(path, plays, next(s for s in sides if sides[s].get('role') == 'us'), log)
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


# ENG-FIX4 (SME_ZAP_DOT=1, off by default): a ZapFreeze holder that also holds the Goblin Curse's damage buff may take one
#   curse hit in the same frame gap as the Zap. FRESH6 024716@1399: the opponent's group (c 1398, no Electro near) holds
#   our Knight (drop 363 = 306 + 57) and our princess tower (93 = 77 + 16), both with GoblinCurseDamage (character_buffs:
#   DamagePerSecond 14 / CrownTowerDamagePerHit 4 at base, HitFrequency 1000; 57 / 16 at level 16, the SIM's own curse
#   hit at 1399 without a Zap: Knight -57, tower -16); zap_is_cast rejected it and no Zap was replayed (first div 1399).
#   A hand-added Zap at (14480, 24740), R 1397 or 1398, makes the match 1764 / 1764 exact (R 1396: first div 1397).
#   Rule: such a holder's drop may be the Zap's (as below) plus exactly one curse hit of CURSE_DMG at the opponent's
#   Goblin Curse level (troop / crown tower); a level not in CURSE_DMG gets no allowance. Census (dev + FRESH1-6 scored
#   logs, `engfix/zg_census.txt`): of 422 rejected groups no extracted Zap explains, 8 have no Electro
#   body near and 1 holds GoblinCurseDamage (024716). ponytail: one curse hit, level 16 only; stacked curses or another
#   damage-over-time buff would need their own allowance.
ZAP_DOT = int(os.environ.get('SME_ZAP_DOT', '0'))
CURSE_DMG = {16: (57, 16)}   # (troop, crown tower) per Goblin Curse hit


def zap_is_cast(g, level, curse_level=None):
    """True when the group's evidence is a Zap of this level (SME_ZAP_ADD). curse_level: the caster's Goblin Curse level
    (SME_ZAP_DOT), None = no curse allowance."""
    import math
    zt, zc = ZAP_DMG.get(level, (None, None))
    if zt is None or not g['hits']:
        return False
    ok = 0
    ct, cc = CURSE_DMG.get(curse_level, (None, None)) if ZAP_DOT else (None, None)
    for h in g['hits'].values():
        if h['drop'] is None or h['name'].endswith('FloatingCube') or any('Fortify' in b for b in h['buffs']):
            continue   # no hp of its own (hero IW cube) / damage reduced (evolved Knight)
        tower = h['name'] in ('KingTower', 'PrincessTower')
        d = h['drop']
        if ct is not None and 'GoblinCurseDamage' in h['buffs']:   # SME_ZAP_DOT: one curse hit in the same gap is allowed
            d -= (cc if tower else ct) if not (abs(d - zc) <= 1 if tower else zt - 1 <= d <= zt + 13) else 0
        if not (abs(d - zc) <= 1 if tower else zt - 1 <= d <= zt + 13):
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
        elif not near and ZAP_ADD and zap_is_cast(g, level, sides[s]['levels'][deck[s].index('GoblinCurse')] if 'GoblinCurse' in deck[s] else None):
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


# SME_TOWER_ZAP=1 (ENG-SME, owner 10-28: build it, reversible, confirm as more cases appear): an unseen opponent Zap on a
#   crown tower. The reader shows no Zap at all (fights.unseen_zaps), and a tower the Zap kills holds no ZapFreeze buff, so
#   neither unseen_zaps (>= 2 hit bodies) nor ZAP_ADD (buff groups) sees a lone dying tower. FRESH1 000420: our princess
#   tower at 7 hp from 3032 leaves the list at 3519 (last listed 3517) with nothing near; one side-0 Zap at the tower, run
#   at 3517 or 3518, makes 3519-3681 exact (82 div -> 0; f1fix_zap_sweep_000420.txt). Rule: a princess tower of side v
#   last listed at tp with 0 < hp <= the opponent's Zap crown-tower damage (ZAP_DMG) is absent at the next frame t and the
#   next TZ_GONE frames (and was never missing before: a reader flicker), the opponent's deck holds Zap, and none of these
#   holds (each a reason in `blocked`): the king or
#   another tower of v leaves at t (a cascade) or no frame follows t; an opponent body (not a tower) within TZ_BODY, an
#   opponent projectile within TZ_PROJ (its point or its target) or an opponent area within TZ_FX of the tower on a frame
#   of [t - TZ_LOOK, t]; an opponent play within TZ_PLAY of it, any opponent Zap, or any opponent ability, run in
#   [t - TZ_PLAY_LOOK, t]; an opponent hidden-body window (extract.reader_hidden) over that span; a body of v within TZ_OWN
#   of the tower on frame tp or t (a Zap at the tower's centre would hit it). -> one opponent Zap at the tower's centre,
#   tick t - 1 (crforge hits on line R + 1, as SME_MECH_ZAP's R = c - 1; at 000420 R 3517 and 3518 tie, the latest is
#   taken), run window [max(tp, t - 2), t - 1] (the fitter may take the other tick). Kings are left out: a king's death
#   ends the match; so is anything after TZ_TIEBREAK (the overtime-end tie-break). Every firing goes to the record's `tower_zap` (f1fix/tower_zap_firings.py lists them for the owner).
TOWER_ZAP = int(os.environ.get('SME_TOWER_ZAP', '0'))
TZ_BODY, TZ_PROJ, TZ_FX, TZ_PLAY = 12000, 3000, 8000, 8000   # 'near' (Euclid units): X-Bow / Mortar reach 11.5 tiles + radii
TZ_LOOK, TZ_PLAY_LOOK, TZ_GONE, TZ_OWN = 20, 60, 3, ZAP_R + 1000
TOWER_PTS = set(KINGS) | {(x, y) for x in (3500, 14500) for y in (6500, 25500)}   # reader card -1 elsewhere = an unmapped body
TZ_TIEBREAK = 6000   # after 5:00 of game time: the overtime-end tie-break removes the lowest tower with nothing near
#   (FRESH1 001302@6167 and 003008@6152, both 1 hp, no Zap in the deck; regulation ends at tick 3681 on this build, so
#   overtime ends ~6081). ponytail: a fixed tick, not the match clock; a 3-minute overtime mode would need its end tick
# ENG-FIX4 (SME_TZ_REACH=1, off by default; needs SME_TOWER_ZAP=1): the enemy_body block uses each opponent body's own
#   reach instead of the flat TZ_BODY. FRESH4 235834@4612: our 19-hp princess tower leaves with nothing near; the opponent's
#   Witch (Range 5500) and Skeletons (500) all target it from >= ~10,900 units and lose their target at 4612; a hand-added
#   Zap at the tower, R 4611, makes the match 2271 / 2271 exact (control 2230 + 41 div), but TZ_BODY = 12000 (sized for
#   X-Bow / Mortar reach) blocked it. Reach of a body (its phase-2 name's table row, characters or buildings) = Range +
#   AreaDamageRadius + its CollisionRadius + the princess tower's (TZ_TOWER_R) + TZ_SLACK; a body with no row, no Range,
#   or a MultipleTargets / MultipleProjectiles row (chains, multi-shot) keeps TZ_BODY. A projectile in flight is the
#   enemy_projectile check; an area is enemy_area; a body that walks or dashes in is near on some frame of the span.
#   The same flag gives own_body_in_reach the Zap's own hit test (tz_own_reach) instead of TZ_OWN: at 235834 our hero Ice
#   Wizard (CollisionRadius 500) stands 3,150 / 3,032 units from the tower's centre at tp / t, outside ZAP_R + 500, and
#   the probe Zap at the centre leaves its hp at 1100 as the game does.
TZ_REACH = int(os.environ.get('SME_TZ_REACH', '0'))
TZ_TOWER_R, TZ_SLACK = 1000, 1000


def tz_reach(tables, name):
    """SME_TZ_REACH: the opponent body's reach on a princess tower (Euclid units), TZ_BODY when the row cannot say."""
    c = zd_cols(tables, name) if name else {}
    if not c.get('Range') or c.get('MultipleTargets') or c.get('MultipleProjectiles'):
        return TZ_BODY
    return c['Range'] + (c.get('AreaDamageRadius') or 0) + (c.get('CollisionRadius') or 0) + TZ_TOWER_R + TZ_SLACK


def tz_own_reach(tables, name):
    """SME_TZ_REACH: how near the tower's centre a body of the tower's side is hit by a Zap there: crforge's circle test
    (AreaEffectEntity.filterListed: a non-building is hit when its centre is strictly within ZapArea's radius + its
    CollisionRadius); a building (a square test) or a body with no characters row keeps the flat TZ_OWN."""
    c = zd_cols(tables, name) if name else {}
    if not c.get('CollisionRadius') or name not in _ZD_ROWS[tables][0]:
        return TZ_OWN
    return ZAP_R + c['CollisionRadius']


def tz_names(path):
    """SME_TZ_REACH: {tick: {address: phase-2 name}} of a raw live log (zd_frames' first sample per tick)."""
    return {t: {a: b['name'] for a, b in B.items()} for t, B, _, _ in zd_frames(path)}


def raw_frames(path):
    """[(tick, ents, proj, fx)] of a raw live log, the first sample of each tick >= 0 (tower_vanish.py's reading)."""
    import json
    out, seen = [], set()
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        out.append((t, d.get('ents') or [], d.get('proj') or [], d.get('fx') or []))
    return out


def tower_zaps(fr, plays, sides, hidden=(), names=None, tables=None):
    """SME_TOWER_ZAP (above). fr: raw_frames; sides: {side: side_info}; hidden: extract.reader_hidden rows; names /
    tables (SME_TZ_REACH): tz_names of the log and the crforge tables dir, None = the flat TZ_BODY.
    -> (plays, fired, blocked): fired / blocked = evidence dicts (blocked: low-hp removals with the reason)."""
    import math
    tw = lambda f: {(e[0], e[1], e[2]): e for e in f[1] if e[3] == -1 and (e[1], e[2]) in TOWER_PTS}   # noqa: E731
    dist = lambda x, y, a, b: math.hypot(a - x, b - y) if a is not None and b is not None else math.inf   # noqa: E731
    fired, blocked, add = [], [], []
    for i in range(len(fr) - 1):
        tp, t = fr[i][0], fr[i + 1][0]
        A, B = tw(fr[i]), tw(fr[i + 1])
        for key, e in A.items():
            v, x, y, h = e[0], e[1], e[2], e[4]
            if key in B or x == KINGS[0][0]:
                continue
            o = 1 - v
            deck = (sides.get(o) or {}).get('deck') or []
            lv = sides[o]['levels'][deck.index('Zap')] if 'Zap' in deck else 16
            zc = ZAP_DMG.get(lv, (None, None))[1]
            if zc is None or h is None or not 0 < h <= zc:
                continue
            ev = dict(tower=[v, x, y], hp=h, tp=tp, t=t, zap_level=lv)
            span = [f for f in fr if t - TZ_LOOK <= f[0] <= t]
            near = lambda rows, r: [q for f in span for q in f[rows] if q[0] == o and dist(x, y, q[1], q[2]) <= r]   # noqa: E731
            if names is None:
                bodies = [q for q in near(1, TZ_BODY) if q[3] != -1]
            else:   # SME_TZ_REACH: each body's own reach (tz_reach)
                bodies = [q for f in span for q in f[1] if q[0] == o and q[3] != -1 and dist(x, y, q[1], q[2]) <= tz_reach(
                    tables, names.get(f[0], {}).get(q[7] if len(q) > 7 else None))]
            proj = [q for f in span for q in f[2] if q[0] == o and min(dist(x, y, q[1], q[2]),
                                                                          dist(x, y, *(q[4:6] if len(q) > 5 else (None, None)))) <= TZ_PROJ]
            ops = [p for p in plays if p['side'] == o and t - TZ_PLAY_LOOK <= p['tick'] <= t and (
                p['kind'] == 'ability' or p.get('card') == 'Zap'
                or (p['kind'] == 'play' and dist(x, y, p.get('x'), p.get('y')) <= TZ_PLAY))]
            if names is None:
                own = [q for f in fr[i:i + 2] for q in f[1] if q[0] == v and q[3] != -1 and dist(x, y, q[1], q[2]) <= TZ_OWN]
            else:   # SME_TZ_REACH: the Zap's own circle test on each body (tz_own_reach)
                own = [q for f in fr[i:i + 2] for q in f[1] if q[0] == v and q[3] != -1 and dist(x, y, q[1], q[2]) < tz_own_reach(
                    tables, names.get(f[0], {}).get(q[7] if len(q) > 7 else None))]
            why = ('no_zap_in_deck' if 'Zap' not in deck else
                   'relisted' if any(key in tw(f) for f in fr[i + 2:i + 2 + TZ_GONE]) else
                   'flicker' if any(key not in tw(f) for f in fr[:i]) else
                   'cascade' if (v, *KINGS[v]) not in B or any(k[0] == v and k not in B for k in A if k != key) else
                   'match_end' if i + 2 >= len(fr) else
                   'tiebreak_window' if t > TZ_TIEBREAK else
                   'enemy_body' if bodies else
                   'enemy_projectile' if proj else
                   'enemy_area' if near(3, TZ_FX) else
                   'opp_play' if ops else
                   'hidden_body' if any(hb['side'] == o and hb['last'] <= t and hb['end'] >= t - TZ_PLAY_LOOK for hb in hidden) else
                   'own_body_in_reach' if own else None)
            if why:
                blocked.append(dict(ev, why=why, plays=[(p['card'] or p['name'], p['tick']) for p in ops][:4]))
                continue
            R = t - 1
            fired.append(dict(ev, R=R, run_ticks=[max(tp, t - 2), R]))
            add.append(dict(side=o, kind='play', card='Zap', deck_index=deck.index('Zap'), name='Zap', form=0,
                            run_ticks=[max(tp, t - 2), R], tick=R, source='spell_seen', x=x, y=y, tile=[x // 1000, y // 1000],
                            n=0, inferred=True, mech='tower_zap'))
    return (sorted(list(plays) + add, key=lambda p: p['tick']) if add else plays), fired, blocked


# ENG-FIX3 (SME_ZAP_DEAD=1, off by default): an unseen opponent Zap that kills every body it reaches. The reader shows no
#   Zap (fights.unseen_zaps); a body the Zap kills holds no ZapFreeze buff (SME_ZAP_ADD) and shows no hp drop (unseen_zaps
#   needs one hit survivor), so a Zap whose every victim dies is seen by no rule. FRESH5 021310@1986: our three full-hp
#   Skeletons (130 <= the level-16 Zap's 306), up to 1,100 units apart, leave the list together between 1984 and 1986;
#   the only opponent troop (Mega Knight, AreaDamageRadius 1300 around its target) is hitting our X-Bow 2,700+ away, no
#   opponent projectile / area / play is near, and the opponent's deck (battle log) holds Zap, its 8-card cycle placing
#   the Zap exactly there (MegaKnight 1847, BarbLog 1875, [Zap], MiniPekka 2447 ... MegaKnight 2808, BarbLog 2865, Zap
#   2958). One side-0 Zap at (12800, 17300), run 1984 or 1985, makes the match 1765 / 1765 exact (1983: 1 div).
#   Rule: in one frame gap (tp, t] with t - tp <= 3, >= ZD_MIN non-tower bodies of side v listed at tp with
#   0 < hp <= the opponent's Zap troop damage (ZAP_DMG) are absent at t and the next ZD_GONE frames, the opponent's deck
#   holds Zap, and none of these holds (each a reason in `blocked`): a victim is kamikaze or spawns on death (Kamikaze /
#   DeathSpawnCharacter: it may leave by itself); an opponent projectile (point or target) within ZD_PROJ or an opponent
#   area within ZD_FX of a victim on a frame of [t - ZD_LOOK, t]; an opponent splash body (AreaDamageRadius) at tp whose
#   splash centre (itself under SelfAsAoeCenter, else its phase-3 target; itself when the target is unknown, then with its
#   Range added) is within the radius + the victim's radius + ZD_SLACK of a victim; an opponent body (a tower too) whose
#   phase-3 target is a victim on one of the 3 frames up to tp (census: an Electro Wizard's two-target hit killed two
#   Skeletons in FRESH2 120406, exact without a Zap); an opponent Electro body within ELECTRO_D of a victim on the frames
#   tp - 2 .. t + 1 (as SME_ZAP_ADD; dev 090406: a hero Electro Wizard); an opponent body within ZD_PROJ of a victim at
#   tp that is not plainly busy elsewhere: busy = a known phase-3 target, moved <= ZD_STILL over the 2 frames before tp
#   and over (tp, t], and a table row with no SelfAsAoeCenter / Kamikaze / Ability / MultipleTargets / charge (FRESH4
#   192245: an evolved Battle Ram's charge push killed two Skeletons, exact without a Zap; 021310's Mega Knight stands
#   still hitting our X-Bow); an opponent kamikaze body within
#   ZD_PROJ of a victim at tp, or an opponent body within ZD_PROJ of a victim that leaves at t (death damage); an
#   opponent play or ability run in [t - ZD_LOOK, t], or an opponent Zap within ZD_ZAP ticks; an opponent hidden-body
#   window (extract.reader_hidden) over [t - ZD_LOOK, t]; the match ends within ZD_GONE frames; no grid point (100 units)
#   reaches every victim (ZAP_R + its radius) while reaching no body of v listed at t (towers too). -> one opponent Zap at
#   that point (widest margin up to ZAP_MARGIN, then nearest the victims' centroid), tick t - 1, run window
#   [max(tp, t - 2), t - 1] (as SME_TOWER_ZAP). Every firing goes to the record's `zap_dead` (blocked ones are returned).
ZAP_DEAD = int(os.environ.get('SME_ZAP_DEAD', '0'))
ZD_MIN, ZD_GONE, ZD_LOOK, ZD_ZAP = 2, 3, 20, 30
ZD_PROJ, ZD_FX, ZD_SLACK, ZD_STILL = 3000, 4000, 300, 100
_ZD_ROWS = {}


def zd_cols(tables, name):
    """The crforge table columns of a character / building by name ({} if none)."""
    import json
    from pathlib import Path
    if tables not in _ZD_ROWS:
        _ZD_ROWS[tables] = [json.load(open(Path(tables) / f'{f}.json'))['rows'] for f in ('characters', 'buildings')]
    for rows in _ZD_ROWS[tables]:
        if name in rows:
            return rows[name].get('columns', {})
    return {}


def zd_frames(path):
    """[(tick, {addr: body}, proj, fx)] of a raw live log, the first sample of each tick >= 0; a body is
    dict(side, x, y, hp, tower, name, gen, tgt) (name / gen from phase 2, tgt = phase-3 attack target generation)."""
    import json
    out, seen = [], set()
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        p2 = {u['address']: u for u in (d.get('phase2') or {}).get('units', [])}
        p3 = {b['generation']: ((b.get('attack') or {}).get('target_gen')) for b in (d.get('phase3') or {}).get('bodies', [])}
        bodies = {}
        for e in d.get('ents') or []:
            u = p2.get(e[7]) or {}
            bodies[e[7]] = dict(side=e[0], x=e[1], y=e[2], hp=e[4], tower=e[3] == -1, name=u.get('name'),
                                gen=u.get('generation'), tgt=p3.get(u.get('generation')))
        out.append((t, bodies, d.get('proj') or [], d.get('fx') or []))
    return out


def zap_dead(fr, plays, sides, tables, hidden=()):
    """SME_ZAP_DEAD (above). fr: zd_frames; sides: {side: side_info}; tables: the crforge tables dir; hidden:
    extract.reader_hidden rows. -> (plays, fired, blocked): evidence dicts."""
    import math
    dist = lambda a, b: math.hypot(a['x'] - b['x'], a['y'] - b['y'])   # noqa: E731
    rad = lambda b: zd_cols(tables, 'PrincessTower' if b['tower'] and not b['name'] else b['name']).get('CollisionRadius') or 500   # noqa: E731
    fired, blocked, add = [], [], []
    for i in range(len(fr) - 1):
        (tp, A, _, _), (t, B, _, _) = fr[i], fr[i + 1]
        if t - tp > 3:
            continue
        for v in (0, 1):
            o = 1 - v
            deck = (sides.get(o) or {}).get('deck') or []
            if 'Zap' not in deck:
                continue
            zt = ZAP_DMG.get(sides[o]['levels'][deck.index('Zap')], (None, None))[0]
            vic = [b for a, b in A.items() if b['side'] == v and not b['tower'] and b['hp'] is not None and 0 < b['hp'] <= zt
                   and a not in B and all(a not in f[1] for f in fr[i + 2:i + 2 + ZD_GONE])]
            if len(vic) < ZD_MIN:
                continue
            ev = dict(side=v, tp=tp, t=t, victims=[[b['name'], b['x'], b['y'], b['hp']] for b in vic])
            span = [f for f in fr if t - ZD_LOOK <= f[0] <= t]
            near = lambda q, r: any(math.hypot(q[0] - b['x'], q[1] - b['y']) <= r for b in vic)   # noqa: E731
            proj = [q for f in span for q in f[2] if q[0] == o and (near(q[1:3], ZD_PROJ) or len(q) > 5 and near(q[4:6], ZD_PROJ))]
            fx = [q for f in span for q in f[3] if q[0] == o and near(q[1:3], ZD_FX)]
            byg = {b['gen']: b for b in A.values() if b['gen'] is not None}
            splash = []
            for b in A.values():
                c = zd_cols(tables, b['name']) if b['side'] == o and not b['tower'] and b['name'] else {}
                if not c.get('AreaDamageRadius'):
                    continue
                ctr, r = (b, c['AreaDamageRadius']) if c.get('SelfAsAoeCenter') else \
                    (byg[b['tgt']], c['AreaDamageRadius']) if b['tgt'] in byg else (b, c['AreaDamageRadius'] + (c.get('Range') or 0))
                if any(dist(ctr, w) <= r + rad(w) + ZD_SLACK for w in vic):
                    splash.append(b['name'])
            vg = {w['gen'] for w in vic}
            el = [b['name'] for f in fr[max(0, i - 2):i + 2] for b in f[1].values() if b['side'] == o and 'Electro' in (b['name'] or '')
                  and near((b['x'], b['y']), ELECTRO_D)]
            past = {a: b for f in fr[max(0, i - 2):i] for a, b in f[1].items()}
            busy = []
            for a_, b in A.items():
                if b['side'] != o or b['tower'] or not near((b['x'], b['y']), ZD_PROJ):
                    continue
                c = zd_cols(tables, b['name']) if b['name'] else {}
                q = B.get(a_) or b
                moved = max(dist(b, q), dist(past.get(a_, b), b))
                if b['tgt'] not in byg or moved > ZD_STILL or c.get('SelfAsAoeCenter') or c.get('Kamikaze') or c.get('Ability') \
                        or c.get('MultipleTargets') or c.get('OnStartChargingAction') or c.get('ChargeRange') or not c:
                    busy.append(b['name'])
            att = [b['name'] or 'tower' for f in fr[max(0, i - 2):i + 1] for b in f[1].values() if b['side'] == o and b['tgt'] in vg]
            kam = [b['name'] for b in A.values() if b['side'] == o and not b['tower'] and b['name']
                   and zd_cols(tables, b['name']).get('Kamikaze') and near((b['x'], b['y']), ZD_PROJ)]
            gone = [b['name'] for a, b in A.items() if b['side'] == o and not b['tower'] and a not in B and near((b['x'], b['y']), ZD_PROJ)]
            ops = [p for p in plays if p['side'] == o and (t - ZD_LOOK <= p['tick'] <= t or p.get('card') == 'Zap' and abs(p['tick'] - t) <= ZD_ZAP)]
            vc = [zd_cols(tables, b['name']) for b in vic]
            why = ('self_leaving_victim' if any(c.get('Kamikaze') or c.get('DeathSpawnCharacter') for c in vc) or any(not b['name'] for b in vic) else
                   'match_end' if i + 2 + ZD_GONE > len(fr) else
                   'enemy_projectile' if proj else
                   'enemy_area' if fx else
                   'enemy_splash' if splash else
                   'enemy_targets_victim' if att else
                   'electro' if el else
                   'enemy_body_near' if busy else
                   'enemy_kamikaze' if kam else
                   'enemy_death' if gone else
                   'opp_play' if ops else
                   'hidden_body' if any(hb['side'] == o and hb['last'] <= t and hb['end'] >= t - ZD_LOOK for hb in hidden) else None)
            xy = None
            if not why:
                rest = [b for b in B.values() if b['side'] == v]
                cx, cy = sum(b['x'] for b in vic) / len(vic), sum(b['y'] for b in vic) / len(vic)
                best = None
                for gx in range(min(b['x'] for b in vic) - ZAP_R, max(b['x'] for b in vic) + ZAP_R + 1, 100):
                    for gy in range(min(b['y'] for b in vic) - ZAP_R, max(b['y'] for b in vic) + ZAP_R + 1, 100):
                        m = min([ZAP_R + rad(b) - math.hypot(b['x'] - gx, b['y'] - gy) for b in vic] +
                                [math.hypot(b['x'] - gx, b['y'] - gy) - ZAP_R - rad(b) for b in rest] + [ZAP_MARGIN])
                        if m < 0:
                            continue
                        k = (m, -math.hypot(gx - cx, gy - cy))
                        if best is None or k > best[0]:
                            best = (k, gx, gy)
                why = None if best else 'no_point'
                xy = (best[1], best[2]) if best else None
            if why:
                blocked.append(dict(ev, why=why, detail=(proj or fx or splash or att or el or busy or kam or gone or [(p.get('card') or p['name'], p['tick']) for p in ops])[:4]))
                continue
            R = t - 1
            fired.append(dict(ev, R=R, run_ticks=[max(tp, t - 2), R], x=xy[0], y=xy[1]))
            add.append(dict(side=o, kind='play', card='Zap', deck_index=deck.index('Zap'), name='Zap', form=0,
                            run_ticks=[max(tp, t - 2), R], tick=R, source='spell_seen', x=xy[0], y=xy[1],
                            tile=[xy[0] // 1000, xy[1] // 1000], n=0, inferred=True, mech='zap_dead'))
    return (sorted(list(plays) + add, key=lambda p: p['tick']) if add else plays), fired, blocked


# ENG-FIX (SME_TOMB_HERO=1): the hero Tombstone's ability press. The press has no cast state, no pending flag and no
# ability area in the reader (FRESH2 100341@2930, FRESH3 145600@1308: phase-2 ability {pending_on_body 0,
# cast_timer_ms_raw 0} on every frame before it). Its one public effect is the row swap crforge also makes on the press
# step (TombstoneHeroTest.theTapWakesTheMonster): the passive monster (same generation) is listed as
# TombstoneHero_Monster_Active. The swap is the press only: Tombstone_hero_Ability is a pressed champion ability
# (ManaCost 5, MaxCharges 1, OnActivationAction Tombstone_hero_OnAbilityActivationGroup); 144 / 207 passive monsters
# on 50 logs never swap (tomb_census.txt). It may come while the building stands (42) or after the building's death,
# while the passive monster lingers on its drain (21; dev 164130@939, 185736@4012: the broken dummy listed, passive hp
# 195 / 703 of 846, then active 6,748). -> one ability row on
# the play's monster (unit 2 of the hero row's three listed characters: dummy, building, monster), R = t - TOMB_LAG,
# window [tp, t - 1] (tp = the last frame with the passive row). TOMB_LAG = 2: with the window [tp, t - 1] the fitter
# put all 3 presses of the two matches on t - 2 (145600: 1308 -> 1306, 3620 -> 3618; 100341: 2930 -> 2928), and both
# matches went exact (ENG-FIX t1). SME_TOMB_PIN=1 pins the window to [R, R] (the per-lag over-fit probe). A cast_seen 'Tombstone' ability is the active
# monster's death area (TombstoneHero card, 2,000 ms, at its death point, skeletons on the next frame: 4 / 4 on the two
# matches), not a press: it is dropped.
TOMB_HERO = int(os.environ.get('SME_TOMB_HERO', '0'))
TOMB_LAG = int(os.environ.get('SME_TOMB_LAG', '2'))
TOMB_PIN = int(os.environ.get('SME_TOMB_PIN', '0'))
TOMB_UNIT = 2


def tomb_swaps(path):
    """[(side, generation, tp, t, building listed at t)] of a raw live log: the passive hero Tombstone monster first
    listed active at t (last passive at tp)."""
    import json
    last, out, done = {}, [], set()
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40] or b'TombstoneHero' not in line:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0:
            continue
        us = (d.get('phase2') or {}).get('units', [])
        build = {u.get('side') for u in us if u.get('name') == 'TombstoneHero'}
        for u in us:
            n, g, s = u.get('name'), u.get('generation'), u.get('side')
            if n == 'TombstoneHero_Monster_Passive':
                last[g] = t
            elif n == 'TombstoneHero_Monster_Active' and g in last and g not in done:
                done.add(g)
                out.append((s, g, last[g], t, s in build))
    return out


def tomb_presses(path, plays, sides, log=None):
    """SME_TOMB_HERO (above). sides: {side: side_info}. Swaps whose side has no hero Tombstone in its deck are skipped."""
    out = [p for p in plays if not (p['kind'] == 'ability' and p['card'] == 'Tombstone' and p.get('source') == 'cast_seen')]
    if log is not None:
        log.extend(('tomb_drop_cast', p['side'], p['tick']) for p in plays if p not in out)
    for s, g, tp, t, standing in tomb_swaps(path):
        deck = sides[s]['deck']
        if 'Tombstone' not in deck:
            continue
        R = t - TOMB_LAG
        out.append(dict(side=s, kind='ability', card='Tombstone', deck_index=deck.index('Tombstone'), name='Tombstone', form=0,
                        run_ticks=[R, R] if TOMB_PIN else [min(tp, R), max(t - 1, R)], tick=R, source='tomb_active', unit_index=TOMB_UNIT,
                        tomb_swap=[tp, t, int(standing)]))
        if log is not None:
            log.append(('tomb_press', s, g, tp, t, R))
    return plays if out == plays else out   # no hero Tombstone event: the same plays object (inputs byte-identical)


# ENG-FIX (SME_BB_RISE=1): a Boss Bandit ability press whose buff the reader never shows. Casts are dated from the
# BossBandit_ability_buff (sme_live.buff_casts: R = buff start - 4). The press itself shows as the body's state-10 rise
# (ents_state) with phase-2 ability cast_timer_ms_raw c, and the buff starts at rise + c: 11 / 11 casts with a buff on
# dev 138 + FRESH2 + FRESH3 (engfix/bb_census.txt, c = 2 or 3). FRESH2 091720@3517: the rise (c = 2) came one frame
# before the Boss Bandit died (a tower shot at 3518), so no buff and no cast; crforge, without the press, landed the
# Boss Bandit's 392 hit on our evo Knight at 3518 that the cast had cancelled in the game (its attack progress reset to
# 0 at 3517). -> for a rise with no buff instance starting in [t, t + BB_SEEK]: start = t + c, R = start - 4, window
# [R - 1, R + 1] (buff_casts' window), unit 0. ponytail: Boss Bandit only (the one champion seen this way).
BB_RISE = int(os.environ.get('SME_BB_RISE', '0'))
BB_SEEK, BB_LAG = 10, 4   # BB_LAG = sme_live.CHAMP_BUFFS['BossBandit_ability_buff'][2]


def bb_rises(path):
    """[(side, generation, rise tick, cast_timer, buff start or None)] of a raw live log's Boss Bandit state-10 rises."""
    import json
    bb, st, rises, buffs = {}, {}, [], {}
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40] or b'BossBandit' not in line:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0:
            continue
        us = {u.get('generation'): u for u in (d.get('phase2') or {}).get('units', []) if u.get('name') == 'BossBandit'}
        for g, u in us.items():
            bb[g] = u.get('side')
            for b in u.get('buffs') or []:
                if isinstance(b, dict) and b.get('name') == 'BossBandit_ability_buff' and b.get('remaining_ms_raw') is not None:
                    buffs.setdefault((g, b.get('address')), t - (b['duration_ms_raw'] - b['remaining_ms_raw']) // 50)
        for row in d.get('ents_state') or []:
            s, g = row[0], row[-1]
            if g in bb:
                if s == 10 and st.get(g) != 10:
                    rises.append((bb[g], g, t, ((us.get(g) or {}).get('ability') or {}).get('cast_timer_ms_raw')))
                st[g] = s
    return [(s, g, t, c, min((v for (gg, _), v in buffs.items() if gg == g and t <= v <= t + BB_SEEK), default=None))
            for s, g, t, c in rises]


def bb_presses(path, plays, sides, log=None):
    """SME_BB_RISE (above). Adds a cast only for a rise without a buff; the same plays object when none."""
    add = []
    for s, g, t, c, b in bb_rises(path):
        if b is not None or c is None or 'BossBandit' not in sides[s]['deck']:
            continue
        R = t + c - BB_LAG
        add.append(dict(side=s, kind='ability', card='BossBandit', deck_index=sides[s]['deck'].index('BossBandit'),
                        name='BossBandit', form=0, run_ticks=[R - 1, R + 1], tick=R, source='bb_rise', unit_index=0,
                        bb_rise=[t, c]))
        if log is not None:
            log.append(('bb_rise', s, g, t, c, R))
    return plays + add if add else plays
