"""Body-position input rules for crforge (ticket A2c-BP), each behind its own env flag. extract.match calls
apply(path, plays, sides, frames) right after crforge_casts; with every flag off it returns plays unchanged.

Charge buffs date a hero / champion ability exactly. The reader lists the buff with its countdown (remaining of a
99,999 ms duration), so the tick it was made is c = first sighting - (duration - remaining) / 50. crforge, given the
ability at run tick R, shows the same buff on line R+2 with one update spent, as the game shows it on c+1: R = c - 1
(window [R, R]). Probes: 083722 Valkyrie R=3095, 164443 Golden Knight R=743, positions exact from the charge on.

SME_BP_VALK=1: a hero Valkyrie cast_seen ability takes the ValkyrieHero_Charge start of its side nearest it within
[tick - 40, tick + 3]. cast_seen dates the cast from the later spin, 0-38 ticks after the charge began when the target
is out of reach. The extractor's second cast_seen cast of the same ability, 40-46 ticks after the first (crforge
refuses it: no charge left, 0x3f6), takes none and is dropped (35 of 73 casts on inputs_v5).

SME_BP_GK=1: Golden Knight casts. gk_dashes takes any burst over 100 units a tick; a Log / Barbarian Barrel push is
one, and so is a mislabelled one-tick frame pair (not_a_dash). Those are dropped; a GoldenKnightCharge start gives
R = c - 1 to the gk_dash cast within GK_NEAR of it, or a new cast. A direct dash (target in reach) shows the buff for a
tick or none, so a buff-less dash keeps gk_dashes' window."""
import json, os

VALK = int(os.environ.get('SME_BP_VALK', '0'))
GK = int(os.environ.get('SME_BP_GK', '0'))
VALK_BEFORE, VALK_AFTER, VALK_SECOND = 40, 3, 60
GK_ID, GK_NEAR, GK_GAP, GK_STEP = 26000074, 15, 100, 100
ROLLERS = {28000011, 28000015}  # Log, BarbLog (reader projectile card ids)
ROLL_DX, ROLL_DY = 2500, 1500


def buff_starts(path, buff):
    """[(side, made tick)] of each instance of the buff in a raw live log (a new instance: a new body generation, or
    its remaining going up)."""
    out, last = [], {}
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40] or buff.encode() not in line:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0:
            continue
        for u in (d.get('phase2') or {}).get('units', []):
            for b in u.get('buffs') or []:
                if b.get('name') != buff or b.get('remaining_ms_raw') is None or b.get('duration_ms_raw') is None:
                    continue
                rem, dur, g = b['remaining_ms_raw'], b['duration_ms_raw'], u['generation']
                new = g not in last or rem > last[g]
                last[g] = rem
                if new:
                    out.append((u['side'], t - (dur - rem) // 50))
    return out


def valk_from_buff(plays, starts):
    cand = sorted((abs(p['tick'] - c), i, c) for i, p in enumerate(plays)
                  if p['kind'] == 'ability' and p['card'] == 'Valkyrie' and p.get('source') == 'cast_seen'
                  for s, c in starts if s == p['side'] and p['tick'] - VALK_BEFORE <= c <= p['tick'] + VALK_AFTER)
    taken, done, out = set(), set(), list(plays)
    for _, i, c in cand:
        if i in done or c in taken:
            continue
        done.add(i)
        taken.add(c)
        out[i] = dict(plays[i], tick=c - 1, run_ticks=[c - 1, c - 1], dated='valk_buff')
    # the second cast_seen cast of one ability (its spin read again 40-46 ticks after the first; no charge start of its
    # own; crforge refuses it, NO_CHARGES): dropped, so the inputs hold no command the game never ran
    second = {i for i, p in enumerate(plays) if p['kind'] == 'ability' and p['card'] == 'Valkyrie'
              and p.get('source') == 'cast_seen' and i not in done
              and any(plays[j]['side'] == p['side'] and 0 < p['tick'] - plays[j]['tick'] <= VALK_SECOND for j in done)}
    return [p for i, p in enumerate(out) if i not in second]


def _gk_move(p, frames, a, b):
    """(start body, displacement) of the knight of p's side between frames a and b (nearest body pairing)."""
    ga = [e for e in frames[a]['E'] if e[0] == p['side'] and e[3] == GK_ID]
    gb = [e for e in frames[b]['E'] if e[0] == p['side'] and e[3] == GK_ID]
    if not ga or not gb:
        return None, None
    e1 = min(((e, f) for e in ga for f in gb), key=lambda ef: abs(ef[0][1] - ef[1][1]) + abs(ef[0][2] - ef[1][2]))
    return e1[0], (e1[1][1] - e1[0][1], e1[1][2] - e1[0][2])


def not_a_dash(p, frames):
    """A gk_dash burst (frames a = lo + 1, b = hi + 2) that is no ability:
    - a roller push: an enemy Log / Barbarian Barrel within ROLL_DX across and ROLL_DY along of the knight at a or b,
      and the knight moved along the roller's travel (a side-0 roller travels +y, a side-1 roller -y);
      212917@4554, 030315@642, 180652@5298 / 5779 (the true casts are charge-buff starts or none); 184912@4970 moved
      against the Log's travel and is a real dash (dropping it moved that onset 4972 earlier, bpgk1);
    - a one-tick frame pair whose speed does not hold over two ticks (a mislabelled reader frame): 001141@5389, a fresh
      knight walking 58 a tick, 138 units 'in one tick' between frames labelled 5390 / 5391."""
    a, b = p['run_ticks'][0] + 1, p['run_ticks'][1] + 2
    if a not in frames or b not in frames:
        return False
    e0, mv = _gk_move(p, frames, a, b)
    if e0 is None:
        return False
    for t in (a, b):
        for q in frames[t]['P']:
            if q[0] != p['side'] and q[3] in ROLLERS and abs(q[1] - e0[1]) <= ROLL_DX and abs(q[2] - e0[2]) <= ROLL_DY \
                    and mv[1] * (1 if q[0] == 0 else -1) > 0:
                return True
    if b - a == 1:
        b2 = min((t for t in frames if t >= a + 2), default=None)
        e2, mv2 = _gk_move(p, frames, a, b2) if b2 is not None else (None, None)
        if e2 is not None and (abs(mv2[0]) + abs(mv2[1])) / (b2 - a) <= GK_STEP:
            return True
    return False


def gk_from_buff(plays, starts, frames, sides):
    out = [p for p in plays if not (p.get('source') == 'gk_dash' and not_a_dash(p, frames))]
    last = {}
    for s, c in sorted(starts, key=lambda x: x[1]):
        if c - last.get(s, -10 ** 6) <= GK_GAP:
            continue
        last[s] = c
        R = c - 1
        near = [i for i, p in enumerate(out) if p.get('source') == 'gk_dash' and p['side'] == s and abs(p['tick'] - R) <= GK_NEAR]
        if near:
            i = min(near, key=lambda i: abs(out[i]['tick'] - R))
            out[i] = dict(out[i], tick=R, run_ticks=[R, R], dated='gk_buff')
            continue
        deck = sides[str(s)]['deck'] if str(s) in sides else sides[s]['deck']
        if 'GoldenKnight' in deck:
            out.append({'side': s, 'kind': 'ability', 'card': 'GoldenKnight', 'tick': R, 'run_ticks': [R, R],
                        'source': 'gk_buff', 'deck_index': deck.index('GoldenKnight'), 'name': 'GoldenKnight', 'form': 0})
    return out


GIANT = int(os.environ.get('SME_BP_GIANT', '0'))
GIANT_LAG = 9  # crforge: ability run R -> the giant stops on line R+1, the victim's GiantHero_Slap_Stun on line R+9


def giant_from_stun(plays, starts, sides):
    """SME_BP_GIANT=1: hero Giant ability casts, which seen_casts never gives (no state-10 frame, no area row, no buff on
    the giant). The slap leaves GiantHero_Slap_Stun on its victim (enemy side) with a countdown: made c, R = c - 9
    (probe 234837: R = 1052 stops the giant on 1053 and stuns on 1061, both as the game). One cast per side per 100
    ticks; only a side whose Giant slot is the hero (slot flag 2)."""
    out, last = list(plays), {}
    for vs, c in sorted(starts, key=lambda x: x[1]):
        s = 1 - vs
        sd = sides[str(s)] if str(s) in sides else sides[s]
        k = next((k for k in range(8) if sd['deck'][k] == 'Giant' and sd['slot_flags'][k] == 2), None)
        if k is None or c - last.get(s, -10 ** 6) <= GK_GAP:
            continue
        last[s] = c
        R = c - GIANT_LAG
        out.append({'side': s, 'kind': 'ability', 'card': 'Giant', 'tick': R, 'run_ticks': [R, R], 'source': 'giant_stun',
                    'deck_index': k, 'name': 'Giant', 'form': 0})
    return out


def apply(path, plays, sides=None, frames=None):
    if GIANT:
        plays = giant_from_stun(plays, buff_starts(path, 'GiantHero_Slap_Stun'), sides)
    if RASCALS:
        plays = rascals_point(plays, frames)
    if VALK:
        plays = valk_from_buff(plays, buff_starts(path, 'ValkyrieHero_Charge'))
    if GK:
        plays = gk_from_buff(plays, buff_starts(path, 'GoldenKnightCharge'), frames, sides)
    if PRESS:
        plays = press_from_drop(plays, frames, sides)
    return plays


PRESS = int(os.environ.get('SME_BP_PRESS', '0'))
PRESS_BEFORE, PRESS_DROP = 300, 15000


def press_from_drop(plays, frames, sides):
    """SME_BP_PRESS=1 (A2c-BP2): our own cast_seen ability with no elixir drop at its tick takes the nearest earlier
    drop that no card play or other ability of ours explains. The game takes the cost on the press; the cast (state 10)
    can come much later: 094126 drop 3483 -> 3485 (2 elixir), cast_seen 3651, and crforge given the press at R = 3483 is
    exact on our elixir and on the hero Ice Wizard's path from 3485 on (it holds the cast as the game does).
    own_press_elixir looks only 15 ticks either side. Census (bp/press_census.py, inputs_v9_bpall): 140 own abilities,
    126 on a drop, 14 on none; 7 drops unexplained, 2 of them before an own cast_seen cast (094126 gap 166, 100018
    gap 23). Window [a, b - 1] of the frame pair (a, b): crforge shows the cost on line R + 1."""
    side = lambda s: sides[str(s)] if str(s) in sides else sides[s]  # noqa: E731
    my = next(s for s in (0, 1) if side(s).get('role') == 'us')
    ts = sorted(frames)
    drops = [(a, b) for a, b in zip(ts, ts[1:]) if frames[a]['el'] - frames[b]['el'] >= PRESS_DROP]
    own = [p for p in plays if p['side'] == my]
    runs = [t for p in own if p['kind'] == 'play' for t in range(p['run_ticks'][0], p['run_ticks'][1] + 1)]
    abil = [p['tick'] for p in own if p['kind'] == 'ability']
    free = [(a, b) for a, b in drops if not any(a - 1 <= t <= b for t in runs + abil)]
    out = []
    for p in plays:
        if p['kind'] == 'ability' and p['side'] == my and p.get('source') == 'cast_seen' and \
                not any(a - 1 <= p['tick'] <= b for a, b in drops):
            c = [(a, b) for a, b in free if p['tick'] - PRESS_BEFORE <= b <= p['tick']
                 and not any(b <= t < p['tick'] for t in abil)]
            if c:
                a, b = max(c, key=lambda ab: ab[1])
                free.remove((a, b))
                p = dict(p, tick=b - 1, run_ticks=[a, b - 1], dated='press_drop')
        out.append(p)
    return out


RASCALS = int(os.environ.get('SME_BP_RASCALS', '0'))
RASCALS_ID, GIRL_DY, GIRL_DX = 26000053, 1213, 1223
BACK_LO, BACK_HI = 1100, 30900


def rascals_point(plays, frames):
    """SME_BP_RASCALS=1: an opponent Rascals play's y from its two girls. fights.deployments (H-RASCALS) puts the point
    LEAD_AHEAD = 2000 behind the boy (RoyaleSim's formation). crforge stands the girls GIRL_DY behind the point and
    the boy 1,740 ahead of it, clamped to the deploy column: at 040821@2113 the boy is clamped (17509, point 18509), the
    old point 19509 put crforge's girls 1,000 off (probe: y = 18509 gives every body exact). The girls are the first two
    new Rascals bodies of the side at one y, GIRL_DX either side of a common x, within 8 ticks after the play."""
    out = []
    for p in plays:
        if p['kind'] == 'play' and p['card'] == 'Rascals' and p.get('source') == 'first_seen':
            fwd = 1 if p['side'] == 0 else -1
            old = {(e[1], e[2]) for t in frames if p['tick'] - 30 <= t <= p['tick'] for e in frames[t]['E']
                   if e[0] == p['side'] and e[3] == RASCALS_ID}
            for t in sorted(t for t in frames if p['tick'] < t <= p['tick'] + 8):
                es = [e for e in frames[t]['E'] if e[0] == p['side'] and e[3] == RASCALS_ID and (e[1], e[2]) not in old]
                pair = [(a, b) for a in es for b in es if a[2] == b[2] and abs((b[1] - a[1]) - 2 * GIRL_DX) <= 2
                        and abs(p['x'] - (a[1] + b[1]) / 2) <= 600 and abs(a[2] + GIRL_DY * fwd - p['y']) <= 2500]
                # girls clamped at the back edge (004901@268, 010613@2186: y 31000) say nothing of the point: keep it
                if pair and BACK_LO < pair[0][0][2] < BACK_HI:
                    a, b = pair[0]
                    p = dict(p, y=a[2] + GIRL_DY * fwd, dated=(p.get('dated') or '') + 'rascals_girls')
                    break
        out.append(p)
    return out
