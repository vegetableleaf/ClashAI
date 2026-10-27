"""SME on live-log matches (ticket A2b-3b): no replay recording; A2b-1's extracted inputs + the live reader's frames.

On pod 33920 (next to sme.py / SmeRun):
  python3 sme_live.py all   --inputs INPUTS.jsonl --frames FRAMEDIR --out OUT [--workers 20] [--only M1,M2]
  python3 sme_live.py one   --inputs INPUTS.jsonl --frames FRAMEDIR --out OUT --only MATCH
  python3 sme_live.py check --plan PLAN.json --frames FRAMEDIR/MATCH.jsonl --side 1 --out OUT   # score a given plan

Per match:
1. Plan: decks, levels, slot flags, towers, words from the input record. Seed 1 (the match is RNG-free: no draw after
   the deal); both deals forced: ours from the log, the opponent's = A2b-1's `opp_deal_fit`.
   Commands at the extractor's `tick` and point; given = run - 20; an ability names the side's latest play of its card.
2. Repair loop (inputs only): at the first true divergence d, try each command run in [d-120, d] at the other run ticks
   of its extracted window [lo, hi], and (not our own taps) the 8 points 500 units around its point. Keep the variant
   that moves d latest; stop when none does (max 25 rounds).
3. Score: every live frame. exact / torn_t1 (the whole frame equals sim t+1) / torn_mixed (isolated, every object held
   by sim t or t+1) / div. First true divergence = first div frame.
4. Over-fit guard: run ticks outside [lo, hi] (lo-2..hi+2) for the commands before the final d; reported, never kept.
5. Deal check: up to 3 more fitting opponent deal classes (other hand sets / queue orders); traces compared.
"""
import argparse, collections, itertools, json, os, re, sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sme  # noqa: E402
from sme import canon_sim, diff, run_batch, card_name  # noqa: E402

WIN = 120
MAX_ROUNDS = 40


def load_frames(path):
    return {f['t']: f for f in map(json.loads, open(path))}


KIND_T = int(os.environ.get('SME_KIND_T', '0'))  # round 6.6: a card -1 row is a tower only if the reader's kind says building


def canon_live(f, my_side):
    c = {'T': [], 'U': [], 'P': [], 'A': []}
    for side, x, y, card, hp, kind in f['E']:
        # card -1 = an id live_frames does not map. Towers read kind 12/13 (1,881,839 rows, all at the 6 tower points);
        # the other 1,426 card -1 rows read kind 14/15 (troops; at the 4 run20 onsets the Witch Mother's VoodooHog).
        tower = card == -1 and (not KIND_T or kind in (12, 13))
        c['T' if tower else 'U'].append((side, x, y, hp))
    for side, x, y, card in f['P']:
        c['P'].append((side, x, y))
    for side, x, y, card in f['A']:
        c['A'].append((side, x, y))
    c['S%d' % my_side] = (f['el'], tuple(f['hand']) if f['hand'] else None, None)
    return c


# Optional reader-representation map (env SME_REPR = a JSON file): {"drop": [crforge names the reader never lists],
# "as": {crforge name: the reader's class T/U/P/A}}. Built from the episode census, documented in SME.md.
REPR = json.load(open(os.environ['SME_REPR'])) if os.environ.get('SME_REPR') else {'drop': [], 'as': {}}


def repr_rows(o):
    """The sim's entity rows as the reader represents them (REPR: dropped rows, remapped classes)."""
    if not (REPR['drop'] or REPR['as'] or REPR.get('drop_no_hp')):
        return o['E']
    es = []
    for e in o['E']:
        if e[2] in REPR['drop'] or (REPR.get('drop_no_hp') and e[1] == 'C' and e[6] == -1 and e[2] not in REPR['as']):
            continue
        k = REPR['as'].get(e[2])
        if k:
            e = list(e)
            e[1] = {'U': 'C'}.get(k, k)
        es.append(e)
    return es


def sim_canon(o, my_side):
    c = canon_sim(dict(o, E=repr_rows(o)))
    c.pop('S%d' % (1 - my_side))
    return c


# ---------------------------------------------------------------- plan
def fx_spells():
    """Spell cards an area effect alone makes (no projectile, not deployed as a spell, no unit): Lightning, Earthquake,
    Poison, Freeze, Zap, Graveyard... A2b-1 dates these from the effect's countdown with RoyaleSim's rule (the area is
    made the tick after the command: run = made - 1); crforge makes it in the command's own step (run = made), as its
    Tornado rule already says. SME.md fix round 1."""
    j = json.load(open(os.path.join(sme.TABLES, 'spells_other.json')))
    out = set()
    for n, r in j['rows'].items():
        c = r['columns']
        if c.get('AreaEffectObject') and not c.get('Projectile') and not c.get('SpellAsDeploy') and not c.get('SummonCharacter'):
            out.add(n)
    return out


FX_SHIFT = int(os.environ.get('SME_FX_SHIFT', '0'))  # round 1: +1 run tick on fx-dated spell plays
GK_DASH = int(os.environ.get('SME_GK', '0'))          # round 2.2: Golden Knight ability casts from its dashes
GK_ID, GK_STEP, GK_LAG = 26000074, 100, 2               # card id; dash = > 100 units a tick; crforge: run R moves at R+2
GK_ACCEL = 63                                           # round 5.4: 1.5x the Golden Knight's ~42-unit walk
GK_FROM_ACCEL = int(os.environ.get('SME_GK_ACCEL', '0'))  # round 5.4: rejected (run21: 1 regression, -2,146 frames); off


CHAMP_BUFF = int(os.environ.get('SME_CHAMP', '0'))  # round 3.1
# ability buff -> (champion card, unit of its play that takes the command, crforge run-to-first-buff-line delay)
CHAMP_BUFFS = {'ArcherQueenRapid': ('ArcherQueen', 0, 4), 'BossBandit_ability_buff': ('BossBandit', 0, 4),
               'goblinstein_doctor_aura': ('Goblinstein', 1, 1)}


def buff_casts(frames):
    """Archer Queen / Boss Bandit / Goblinstein ability casts from the reader's phase-2 buff rows (frames 'B'): a buff
    instance's start = first sighting - (duration - remaining)/50; crforge shows the buff on R + delay (probe), so
    R in [start - delay - 1, start - delay + 1]. One cast per (side, buff) per 40 ticks."""
    out, last = [], {}
    for t in sorted(frames):
        for side, unit, buff, rem, dur in frames[t].get('B', []):
            if buff not in CHAMP_BUFFS or rem is None or dur is None:
                continue
            start = t - (dur - rem) // 50
            if start - last.get((side, buff), -10 ** 6) <= 40:
                continue
            last[(side, buff)] = start
            card, ui, lag = CHAMP_BUFFS[buff]
            R = start - lag
            out.append({'side': side, 'kind': 'ability', 'card': card, 'tick': R, 'run_ticks': [R - 1, R + 1],
                        'source': 'buff_seen', 'unit_index': ui})
    return out


def gk_dashes(frames):
    """Golden Knight ability casts, which A2b-1 never extracts (champions are not in seen_casts): the first frame of
    each dash burst, a GK body moving more than GK_STEP units a tick (walk ~30). Run tick window: the movement began
    in (t_prev, t], and crforge moves a GK on R+2 (probe), so R in [t_prev - 1, t - 2]."""
    out, ts = [], sorted(frames)
    dashing, lastcast, accel = {}, {}, {}
    for a, b in zip(ts, ts[1:]):
        dt = b - a
        if dt <= 0:
            continue
        for side in (0, 1):
            pa = [e for e in frames[a]['E'] if e[0] == side and e[3] == GK_ID]
            pb = [e for e in frames[b]['E'] if e[0] == side and e[3] == GK_ID]
            for e in pb:
                if not pa:
                    continue
                q = min(pa, key=lambda f: abs(f[1] - e[1]) + abs(f[2] - e[2]))
                v = (abs(q[1] - e[1]) + abs(q[2] - e[2])) / dt
                fast = v > GK_STEP
                # round 5.4: the dash starts below GK_STEP (84 a tick on its first frame, 164443@746): it begins at the
                # first frame of the run of frames faster than GK_ACCEL (1.5x the ~42 walk) that leads to the burst
                if v > GK_ACCEL:
                    accel.setdefault(side, (a, b))
                else:
                    accel.pop(side, None)
                if fast and not dashing.get(side) and b - lastcast.get(side, -10 ** 6) > 100:
                    lastcast[side] = b  # one cast per chain: a pause inside a dash chain is not a new cast
                    a0, b0 = accel.get(side, (a, b)) if GK_FROM_ACCEL else (a, b)
                    out.append({'side': side, 'kind': 'ability', 'card': 'GoldenKnight', 'tick': b0 - 2,
                                'run_ticks': [a0 - 1, b0 - 2], 'source': 'gk_dash'})
                dashing[side] = fast
    return out


VALK_LAG = int(os.environ.get('SME_VALK', '0'))  # round 4.2
OWN_CAST = int(os.environ.get('SME_OWN_CAST', '0'))  # round 6.2: own cast_seen presses dated by our elixir too


def valk_shift(p):
    """A hero Valkyrie cast dated from its first state-10 frame (seen_casts: RoyaleSim starts a cast on R+1, so R in
    [prev frame, first - 1]) goes 1 tick earlier for crforge, whose Valkyrie takes the ability's buffs on R+1 and starts
    its charge on R+2 (probe, SME.md round 4.2): R in [prev - 1, first - 2]. Over-fit probe on run13: 12 Valkyrie casts
    better at lo-1, no other hero's."""
    if p['kind'] == 'ability' and p['card'] == 'Valkyrie' and p.get('source') == 'cast_seen':
        return dict(p, tick=p['tick'] - 1, run_ticks=[p['run_ticks'][0] - 1, p['run_ticks'][1] - 1], dated='valk_charge')
    return p


def own_press_elixir(p, frames, my=None, own_ticks=()):
    """Our own ability press dated by our elixir (SME.md round 5.1): crforge takes the cost on the run tick R and shows
    it on line R+1, so the press runs in [prev, first - 1] of the frame pair where our elixir drops by >= 1.5 elixir,
    the drop nearest the tap-dated tick within 15 ticks. The tap-dated tick is kept when it is inside that window,
    else the window end nearest it. run17: the tap-dated tick lies outside the drop window on 6 of 15 presses.
    Round 6.2 (SME_OWN_CAST=1): also our own presses that have no logged tap and are dated from the reader's cast
    (cast_seen on side `my`; 125 of the 140 own presses); for those, a frame pair holding one of our card plays (own_ticks:
    their run ticks) is not a press drop (a Log / Tornado / X-Bow drop was taken for the press on 5 casts)."""
    own_cast = OWN_CAST and my is not None and p.get('source') == 'cast_seen' and p['side'] == my
    if p['kind'] != 'ability' or not (p.get('source') == 'own_press' or own_cast) or not frames:
        return p
    ts = sorted(frames)
    R = p['tick']
    drops = [(a, b) for a, b in zip(ts, ts[1:]) if R - 15 <= b <= R + 15 and frames[a]['el'] - frames[b]['el'] >= 15000
             and not (own_cast and any(a - 1 <= t <= b for t in own_ticks))]
    if not drops:
        return p
    a, b = min(drops, key=lambda ab: min(abs(ab[0] - R), abs(ab[1] - 1 - R)))
    lo, hi = a, max(a, b - 1)
    return dict(p, tick=min(max(R, lo), hi), run_ticks=[lo, hi], dated='own_elixir')


GOLEM_DEATH = int(os.environ.get('SME_GOLEM', '0'))  # round 2.3
GOLEM_HERO_ID = 203000038


def golem_death_cast(p, frames):
    """A hero Ice Golem 'ability cast' that is its death: seen_casts dates an instant hero's cast from its ability
    area row, and the hero golem's death areas carry the same card id (203000038). True when the cast's side has a
    hero golem body at the last frame <= R and none in the first frame >= R+2 (it died at the cast tick)."""
    if p['kind'] != 'ability' or p['card'] != 'IceGolemite' or p.get('source') != 'cast_seen':
        return False
    R, side = p['tick'], p['side']
    ts = sorted(frames)
    before = max((t for t in ts if t <= R), default=None)
    after = min((t for t in ts if t >= R + 2), default=None)
    has = lambda t: any(e[0] == side and e[3] == GOLEM_HERO_ID and e[4] > 0 for e in frames[t]['E'])  # noqa: E731
    return before is not None and after is not None and has(before) and not has(after)


IW_DEPLOY = int(os.environ.get('SME_IW_DEPLOY', '0'))  # round 6.7
IW_AREA_ID = 203000023


def iw_deploy_cast(p, frames, plays):
    """A hero Ice Wizard 'ability cast' that is the hero's deploy (SME.md round 6.7): seen_casts dates an instant hero's
    cast from its ability area row, and a hero Ice Wizard's deploy shows an area of that card id (203000023) on its own
    point (iwfx6.py): all 9 such areas with no countdown, and 1 at 1 ms, on the 138 matches sit on an Ice Wizard play's
    point on its first frame, each with a cast_seen cast 1-2 ticks before it (a real cast's areas read 50 ms then
    ~1,000,000 ms, 4-8 ticks after it, on the old Ice Wizard). True for a cast_seen Ice Wizard cast with a
    same-side Ice Wizard play 1-3 ticks later and an area row of 203000023 within 1 unit of that play's point on a frame
    in [play - 1, play + 2]."""
    if not IW_DEPLOY or p['kind'] != 'ability' or p['card'] != 'IceWizard' or p.get('source') != 'cast_seen':
        return False
    for q in plays:
        if q['kind'] == 'play' and q['card'] == 'IceWizard' and q['side'] == p['side'] and 1 <= q['tick'] - p['tick'] <= 3:
            if any(a[0] == q['side'] and a[3] == IW_AREA_ID and abs(a[1] - q['x']) <= 1 and abs(a[2] - q['y']) <= 1
                   for t in range(q['tick'] - 1, q['tick'] + 3) if t in frames for a in frames[t]['A']):
                return True
    return False


IW_AREA_DATE = int(os.environ.get('SME_IW_AREA', '0'))  # round 6.8


def iw_area_cast(p, fx, my):
    """An opponent hero Ice Wizard cast dated by its ability's first area (SME.md round 6.8, iwfx6.py). The ability
    makes an area of card 203000023 with a 50 ms life 4 ticks after the cast: first seen at R+4 with 50 ms left or at
    R+5 with 0 ms left on 16 of the 18 opponent casts. On the other 2 (014151@1266, 211239@5544) the cast_seen tick
    sits 2-3 ticks late. fx: fights.read_match rows tick -> [(side, x, y, cid, rem, _, gen)]. R = made - 4, made =
    first - (50 - rem) / 50, from the first such area in [R - 2, R + 10]. Our own casts keep the elixir dating."""
    if not IW_AREA_DATE or not fx or p['kind'] != 'ability' or p['card'] != 'IceWizard' or \
            p.get('source') != 'cast_seen' or p['side'] == my:
        return p
    R = p['tick']
    for t in range(R - 2, R + 11):
        e = next((e for e in fx.get(t, ()) if e[0] == p['side'] and e[3] == IW_AREA_ID and e[4] in (0, 50)), None)
        if e:
            r = t - (50 - e[4]) // 50 - 4
            return p if r == R else dict(p, tick=r, run_ticks=[r, r], dated='iw_area')
    return p


def plan_from(rec, opp_deal, frames=None):
    me = rec['my_side']
    sides = rec['sides']
    cmds, last = [], {}
    fx = fx_spells() if FX_SHIFT else set()
    plays = []
    if CHAMP_BUFF and frames:
        for g in buff_casts(frames):
            deck = sides[str(g['side'])]['deck']
            if g['card'] in deck:
                plays.append(dict(g, deck_index=deck.index(g['card']), name=g['card'], form=0))
    if GK_DASH and frames:
        for g in gk_dashes(frames):
            deck = sides[str(g['side'])]['deck']
            if 'GoldenKnight' in deck:
                plays.append(dict(g, deck_index=deck.index('GoldenKnight'), name='GoldenKnight', form=0))
    for p in rec['plays']:
        # only countdown-dated casts (seen_casts' effect path gives lo = hi); a gap-dated one (Zap: 1 ms life, no
        # countdown to read) keeps its window -- run4 shifted those too and lost live_play_20261026_100756
        if FX_SHIFT and p['kind'] == 'play' and p.get('source') == 'spell_seen' and p['card'] in fx \
                and p['run_ticks'][0] == p['run_ticks'][1]:
            p = dict(p, tick=p['tick'] + FX_SHIFT, run_ticks=[p['run_ticks'][0] + FX_SHIFT, p['run_ticks'][1] + FX_SHIFT])
        if VALK_LAG:
            p = valk_shift(p)
        plays.append(p)
    if GOLEM_DEATH and frames:
        plays = [p for p in plays if not golem_death_cast(p, frames)]
    rec = dict(rec, plays=plays)
    for p in sorted(rec['plays'], key=lambda p: p['tick']):
        s, d = p['side'], p['deck_index']
        if p['kind'] == 'play':
            last[(s, d)] = len(cmds)
            cmds.append({"kind": "play", "given": p['tick'] - 20, "run": p['tick'], "side": s, "card": p['card'],
                         "level": sides[str(s)]['levels'][d], "x": p['x'], "y": p['y']})
        elif (s, d) in last:
            cmds.append({"kind": "ability", "given": p['tick'] - 20, "run": p['tick'], "side": s,
                         "unit": "cmd%d_%d" % (last[(s, d)], p.get('unit_index', 0))})
        else:
            continue
        cmds[-1]['_src'] = {'lo': p['run_ticks'][0], 'hi': p['run_ticks'][1], 'tick': p['tick'],
                            'source': p.get('source'), 'own': s == me}
    deals = [None, None]
    own = list(rec['deal'][str(me)])
    if own.count(-1) == 1:  # one queue card never seen: it is the one index missing
        own[own.index(-1)] = (set(range(8)) - set(own)).pop()
    deals[me] = own if sorted(own) == list(range(8)) else None
    deals[1 - me] = opp_deal
    return {"seed": 1, "playerData": [1, 1], "words": [sides['0']['word'], sides['1']['word']],
            "decks": [sides['0']['deck'], sides['1']['deck']], "slots": [sides['0']['slot_flags'], sides['1']['slot_flags']],
            "towers": [[sides[k]['towers']['king_level'], sides[k]['towers']['level'], sides[k]['towers']['group']]
                       for k in ('0', '1')],
            "deals": deals, "cmds": cmds}


def runnable(plan):
    return dict(plan, cmds=[{k: v for k, v in c.items() if k != '_src'} for c in plan['cmds']])


def fitting_classes(rec, limit=None):
    """Opponent deals that keep every extracted opponent play legal under the 4-card cycle, one per class
    (initial hand set x queue order; the order inside the hand changes no legality)."""
    opp = 1 - rec['my_side']
    seq = [p['deck_index'] for p in sorted(rec['plays'], key=lambda p: p['tick']) if p['side'] == opp and p['kind'] == 'play']
    out = []
    for hand in itertools.combinations(range(8), 4):
        rest = [i for i in range(8) if i not in hand]
        for q in itertools.permutations(rest):
            h, qu, ok = set(hand), list(q), True
            for d in seq:
                if d not in h:
                    ok = False
                    break
                h.remove(d); qu.append(d); h.add(qu.pop(0))
            if ok:
                out.append(list(hand) + list(q))
                if limit and len(out) >= limit:
                    return out
    return out


# ---------------------------------------------------------------- analysis
TORN_CMD = int(os.environ.get('SME_TORN_CMD', '0'))  # round 2.1
TORN_CMD3 = int(os.environ.get('SME_TORN_CMD3', '0'))  # round 6.2: the same read at triple elixir (regen 537 a tick)


HP_PH = int(os.environ.get('SME_HP_PLACEHOLDER', '0'))  # round 2.4
TORN_STEP = int(os.environ.get('SME_TORN_STEP', '0'))  # round 4.1
STEP_MOVE = 200  # game units: more than one step of the fastest walker read here (~180 per tick)
STEP_CLOCK = int(os.environ.get('SME_STEP_CLOCK', '0'))  # round 6.1: our elixir as the step clock
SNAP = int(os.environ.get('SME_BP_SNAP', '0'))  # A2c-BP: in-step reads by crforge's own in-step states
MIX_PH = int(os.environ.get('SME_BP_MIXPH', '0'))  # A2c-BP: torn_mixed reads the hp -1 placeholder as the main comparison does (round 2.4)


def _no(why, *msg):
    if why is not None:
        why.append(msg)
    return False


def step_read(f, ot, ot1, me, why=None, min_movers=2):
    """A read inside step t+1 (SME.md round 4.1): the board has moved but the step's hits, removals, spawns and regen
    are not all in yet. True when every sim body that moves between t and t+1 is read at its t+1 point (at least two
    move; analyse also requires the frame to be isolated), every recorded body sits at the t+1 point of a sim body with that body's hp at t or t+1 (or the reader's
    placeholder -1), or at the t point of a body the step removes (hp 0 / -1 / its hp at t; hp 0 / -1 also within
    STEP_MOVE of it), every sim t+1 body not read is made in step t+1, every recorded projectile / area effect is at a
    t or t+1 point (a projectile the step removes also at a body's point, its impact) and every one not read is new in
    step t+1, and our elixir and hand are those of t or t+1."""
    rows = lambda o: {e[0]: e for e in repr_rows(o)}  # noqa: E731
    a, b = rows(ot), rows(ot1)
    bod = lambda d: {i: e for i, e in d.items() if e[1] in 'TC'}  # noqa: E731
    ba, bb = bod(a), bod(b)
    moving = [i for i in ba if i in bb and ba[i][4:6] != bb[i][4:6]]
    # round 6.1: our elixir changes every tick (regen), so a frame whose elixir is sim t+1's and not sim t's was read
    # after step t+1's regen. That is direct evidence of a read inside step t+1 and stands in for the mover count.
    clock = STEP_CLOCK and f['el'] == ot1['S'][me][0] != ot['S'][me][0]
    if len(moving) < min_movers and not clock:  # one mover cannot tell a step read from that body's own 1-tick lead (run15 audit, 4.1b)
        return _no(why, 'fewer than 2 bodies move')
    at1, at0 = collections.defaultdict(list), collections.defaultdict(list)
    for i, e in bb.items():
        at1[(e[3], e[4], e[5])].append(i)
    for i, e in ba.items():
        if i not in bb:
            at0[(e[3], e[4], e[5])].append(i)
    used = set()
    for side, x, y, card, hp, kind in f['E']:
        k = (side, x, y)
        i = next((i for i in at1.get(k, []) if i not in used and
                  (hp == -1 or hp == bb[i][6] or (i in ba and hp == ba[i][6]))), None)
        if i is None:
            i = next((i for i in at0.get(k, []) if i not in used and hp in (0, -1, ba[i][6])), None)
        if i is None and hp in (0, -1):  # killed in step t+1 after its move: read at hp 0 within a step of its t point
            i = next((i for i in ba if i not in bb and i not in used and ba[i][3] == side and
                      abs(ba[i][4] - x) + abs(ba[i][5] - y) <= STEP_MOVE), None)
        if i is None:
            return _no(why, 'recorded body unmatched', (side, x, y, hp))
        used.add(i)
    left = [bb[i][2:7] for i in bb if i not in used and i in ba]
    if left:
        return _no(why, 'sim body not read', left)
    for cls, key in (('P', 'P'), ('A', 'A')):
        pa = {i: e for i, e in a.items() if e[1] == cls}
        pb = {i: e for i, e in b.items() if e[1] == cls}
        pts = collections.defaultdict(list)
        for i, e in list(pa.items()) + list(pb.items()):
            pts[(e[3], e[4], e[5])].append(i)
        seen = set()
        gone = [i for i in pa if i not in pb]
        for r in f[key]:
            i = next((i for i in pts.get((r[0], r[1], r[2]), []) if i not in seen), None)
            if i is None and cls == 'P':  # a projectile read at its impact point (a body's point) in the step it hits
                hit = any((e[4], e[5]) == (r[1], r[2]) for e in list(ba.values()) + list(bb.values()))
                i = next((i for i in gone if i not in seen and pa[i][3] == r[0]), None) if hit else None
            if i is None:
                return _no(why, 'recorded %s unmatched' % cls, r)
            seen.add(i)
        left = [pb[i][2:6] for i in pb if i not in seen and i in pa]
        if left:
            return _no(why, 'sim %s not read' % cls, left)
    els = (ot['S'][me][0], ot1['S'][me][0])
    if f['el'] not in els:
        return _no(why, 'elixir', (f['el'], els))
    if f['hand'] and tuple(f['hand']) not in (tuple(ot['S'][me][1]), tuple(ot1['S'][me][1])):
        return _no(why, 'hand')
    return True


def fill_placeholder(r, s):
    """A recorded body with hp -1 is the reader's placeholder (its max_hp reads -1 too: 10,384 / 10,384 rows on the
    109 matches' live logs; hp_placeholder.py): it takes the hp of a sim body at the very same (side, x, y), if any."""
    simpos = {}
    for b in s['U']:
        simpos.setdefault(b[:3], b[3])
    out = dict(r)
    out['U'] = [(b[0], b[1], b[2], simpos.get(b[:3], b[3])) if b[3] == -1 else b for b in r['U']]
    return out


def cmd_pass_read(d, by, t, me):
    """A read inside step t, after its command pass and before its regen and spawns (SME.md round 2.1): the board
    equals sim t, and our elixir is sim t's minus whole elixir exactly, the elixir step t+1 then reaches by its regen
    alone (178 or 357, one or double rate; with SME_TORN_CMD3=1 also 537, triple rate: 12 of run20's 138 onsets)."""
    if not d or any(x[0] != 'S%d_elixir' % me for x in d) or t + 1 not in by:
        return False
    r, s = d[0][1], d[0][2]
    nxt = by[t + 1]['S'][me][0]
    regen = (178, 179, 357, 358) + ((536, 537, 538) if TORN_CMD3 else ())
    return (s - r) % 10000 == 0 and 10000 <= s - r <= 100000 and (nxt - r) in regen


def analyse(obs, frames, me, lo=0, hi=10 ** 9):
    by = {o['t']: o for o in obs}
    ts = [t for t in sorted(frames) if lo <= t <= hi and t in by]
    cls, ds = {}, {}
    for t in ts:
        r = canon_live(frames[t], me)
        if HP_PH:
            r = fill_placeholder(r, sim_canon(by[t], me))
        d = diff(r, sim_canon(by[t], me))
        ds[t] = d
        if not d:
            cls[t] = 'exact'
        elif t + 1 in by and not diff(r, sim_canon(by[t + 1], me)):
            cls[t] = 'torn_t1'
        elif TORN_CMD and cmd_pass_read(d, by, t, me):
            cls[t] = 'torn_cmd'
        elif TORN_STEP and t + 1 in by and step_read(frames[t], by[t], by[t + 1], me):
            cls[t] = 'torn_step'
        else:
            cls[t] = 'div'
    for i, t in enumerate(ts):  # isolated frames whose every object is held by sim t or t+1
        if cls[t] != 'div' or t + 1 not in by:
            continue
        nb = [cls.get(ts[j]) for j in (i - 1, i + 1) if 0 <= j < len(ts)]
        if any(c == 'div' for c in nb):
            continue
        r, a, b = canon_live(frames[t], me), sim_canon(by[t], me), sim_canon(by[t + 1], me)
        # A2c-BP (SME_BP_MIXPH): a recorded body at hp -1 is the reader's placeholder (round 2.4), held by a sim body at
        # its very (side, x, y) at t or t+1, whatever that body's hp; the main comparison already fills it the same way
        pos = {k: {y[:3] for y in a[k] + b[k]} for k in 'TU'} if MIX_PH else {}
        if all(x in a[k] or x in b[k] or (k in pos and x[3] == -1 and x[:3] in pos[k]) for k in 'TUPA' for x in r[k]) and \
                all(r[k] in (a.get(k), b.get(k)) or r[k][0] in (a.get(k, (None,))[0], b.get(k, (None,))[0])
                    for k in r if k.startswith('S')):
            cls[t] = 'torn_mixed'
    for i, t in enumerate(ts):  # 4.1b: a step read is isolated; a run of them is a persistent lead (run15 audit)
        if cls[t] == 'torn_step' and any(cls.get(ts[j]) in ('div', 'torn_step') for j in (i - 1, i + 1) if 0 <= j < len(ts)):
            cls[t] = 'div'
    first = next((t for t in ts if cls[t] == 'div'), None)
    cnt = collections.Counter(cls.values())
    return {'frames': len(ts), 'counts': dict(cnt), 'first': first, 'first_diff': ds.get(first), 'cls': cls,
            'missing_in_sim': sum(1 for t in frames if lo <= t <= hi and t not in by)}


def variants_at(plan, d, rec_frames_end):
    vs = []
    for i, c in enumerate(plan['cmds']):
        s = c['_src']
        if not (d - WIN <= c['run'] <= d):
            continue
        for R in range(s['lo'], s['hi'] + 1):
            if R != c['run']:
                vs.append((i, {'run': R, 'given': R - 20}))
        if c['kind'] == 'play' and not s['own']:
            for dx, dy in itertools.product((-500, 0, 500), repeat=2):
                if dx or dy:
                    vs.append((i, {'x': c['x'] + dx, 'y': c['y'] + dy}))
    return vs


def apply(plan, i, ch):
    p = json.loads(json.dumps(plan))
    p['cmds'][i].update(ch)
    return p


def episodes(an):
    """Runs of consecutive div frames: [start, end, healed] (healed = a non-div frame follows)."""
    ts = sorted(an['cls'])
    out, cur = [], None
    for t in ts:
        if an['cls'][t] == 'div':
            if cur is None:
                cur = [t, t, False]
            cur[1] = t
        elif cur is not None:
            cur[2] = True
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return out


def objective(an, hi, skip):
    """(first div frame outside the given-up episodes, - div frames outside them): larger is better."""
    div = [t for t, c in an['cls'].items() if c == 'div' and not any(a <= t <= b for a, b in skip)]
    return (min(div) if div else hi + 1, -len(div))


def base_run(plan, frames, me, end, work, log):
    """Full run; an ability naming a unit its play never made (the play was refused) is dropped and logged."""
    for _ in range(10):
        o = run_batch([(runnable(plan), end + 3, 0)], work)[0]
        if o is not None:
            return o, analyse(o, frames, me)
        msg = sme.ERRORS.get(0, '')
        mm = re.search(r'(cmd\d+) names cmd\d+_\d+, which no play', msg)
        if not mm:
            log.append({'error': msg[:300]})
            return None, None
        i = int(mm.group(1)[3:])
        plan['cmds'][i]['kind'] = 'skip'
        log.append({'dropped_ability': i, 'why': msg[:200]})
    return None, None


def fit_match(rec, frames, out):
    me = rec['my_side']
    end = max(frames)
    deal = rec['opp_deal_fit']
    if deal is None:  # no fitting deal (an opponent play missed or invented): the first deal, refused plays expected
        deal = list(range(8))
    plan = plan_from(rec, deal, frames)
    work = os.path.join(out, 'work')
    log = []
    o, an = base_run(plan, frames, me, end, work, log)
    if o is None:
        return {'error': (log[-1].get('error') if log else '') or 'base plan failed', 'log': log}, plan, None
    given_up = []  # onsets of episodes that no input change in reach fixes
    for rnd in range(MAX_ROUNDS):
        eps = [e for e in episodes(an) if e[0] not in given_up]
        if not eps:
            break
        d = eps[0][0]
        skip = [(e[0], e[1]) for e in episodes(an) if e[0] in given_up]
        vs = variants_at(plan, d, end)
        lo, hi = max(0, d - WIN - 5), min(end, d + 400)
        best = None
        if vs:
            outs = run_batch([(runnable(apply(plan, i, ch)), hi + 3, lo) for i, ch in vs], work)
            for (i, ch), ob in zip(vs, outs):
                if ob is None:
                    continue
                key = objective(analyse(ob, frames, me, lo, hi), hi, skip)
                if best is None or key > best[0]:
                    best = (key, i, ch)
        if best is None or best[0][0] <= d:
            given_up.append(d)
            log.append({'round': rnd, 'd': d, 'variants': len(vs), 'best_first': best and best[0][0], 'kept': False})
            continue
        plan = apply(plan, best[1], best[2])
        o, an = base_run(plan, frames, me, end, work, log)
        if o is None:
            return {'error': 'a kept variant failed', 'log': log}, plan, None
        log.append({'round': rnd, 'd': d, 'variants': len(vs), 'cmd': best[1], 'change': best[2], 'new_first': an['first']})
    return {'log': log, 'given_up': given_up}, plan, (o, an)


def overfit_probe(plan, frames, me, d, end, out):
    """Run ticks outside each command's window, for the commands in [d-WIN, d]: does any move d later?"""
    if d is None:
        return []
    vs = []
    for i, c in enumerate(plan['cmds']):
        s = c['_src']
        if d - WIN <= c['run'] <= d:
            for R in list(range(s['lo'] - 2, s['lo'])) + list(range(s['hi'] + 1, s['hi'] + 3)):
                vs.append((i, {'run': R, 'given': R - 20}))
    if not vs:
        return []
    lo, hi = max(0, d - WIN - 5), min(end, d + 400)
    outs = run_batch([(runnable(apply(plan, i, ch)), hi + 3, lo) for i, ch in vs], os.path.join(out, 'work'))
    res = []
    for (i, ch), ob in zip(vs, outs):
        if ob is None:
            continue
        f2 = analyse(ob, frames, me, lo, hi)['first']
        if f2 is None or f2 > d:
            c = plan['cmds'][i]
            res.append({'cmd': i, 'card': c.get('card', 'ability'), 'side': c['side'], 'window': [c['_src']['lo'], c['_src']['hi']],
                        'run': ch['run'], 'first_div': f2})
    return res


def describe_first(o_by, frames, me, t):
    """The first true divergence with card names: recorded-only and sim-only objects."""
    if t is None:
        return None
    f, s = frames[t], o_by[t]
    r = canon_live(f, me)
    d = diff(r, sim_canon(s, me))
    names_r = {(e[0], e[1], e[2], e[4]): card_name(e[3]) or 'tower' if e[3] != -1 else 'tower' for e in f['E']}
    names_r.update({(p[0], p[1], p[2]): 'P:' + str(card_name(p[3]) if p[3] != -1 else 'tower_shot') for p in f['P']})
    names_r.update({(a[0], a[1], a[2]): 'A:' + str(card_name(a[3])) for a in f['A']})
    names_s = {}
    for e in s['E']:
        key = (e[3], e[4], e[5], e[6]) if e[1] in 'TC' else (e[3], e[4], e[5])
        names_s[key] = e[1] + ':' + e[2]
    out = []
    for kind, x, near in d:
        nm = names_r.get(x) if 'rec_only' in kind else names_s.get(x) if 'sim_only' in kind else None
        out.append([kind, list(x) if isinstance(x, tuple) else x, nm, list(near) if isinstance(near, tuple) else near])
    return out


def do_match(args):
    rec, frames_path, out = args
    m = rec['match']
    mo = os.path.join(out, m)
    os.makedirs(mo, exist_ok=True)
    try:
        frames = load_frames(frames_path)
        me, end = rec['my_side'], max(frames)
        info, plan, final = fit_match(rec, frames, mo)
        if final is None:
            res = {'match': m, **info}
        else:
            o, an = final
            if SNAP:  # A2c-BP: isolated div frames that are crforge's own in-step states (bp_snap.py)
                import bp_snap
                an = bp_snap.reclass(runnable(plan), frames, me, an, o, os.path.join(mo, 'work'))
            by = {x['t']: x for x in o}
            plays = [p for x in o for p in x['plays']]
            moved = [(c.get('card', 'ability'), c['run'] - c['_src']['tick']) for c in plan['cmds'] if c['run'] != c['_src']['tick']]
            res = {'match': m, 'flags': rec['flags'], 'opp_fitting_deals': rec['opp_fitting_deals'],
                   'frames': an['frames'], 'counts': an['counts'], 'missing_in_sim': an['missing_in_sim'],
                   'exact_share': an['counts'].get('exact', 0) / max(an['frames'], 1),
                   'first_div': an['first'], 'first_detail': describe_first(by, frames, me, an['first']),
                   'sim_end': o[-1]['t'], 'live_end': end, 'commands': len(plan['cmds']),
                   'refused_plays': [p for p in plays if p[4] != 0 or not p[2]],
                   'nonzero_offset': moved, 'points_moved': sum(1 for c in plan['cmds'] if c['kind'] == 'play' and
                                                               (c['x'], c['y']) != tuple(_orig_xy(rec, c))),
                   'repair': info['log'],
                   'torn_ticks': sorted(t for t, c in an['cls'].items() if c.startswith('torn')),
                   'torn_t1_ticks': sorted(t for t, c in an['cls'].items() if c == 'torn_t1')}
            eps = episodes(an)
            res['episodes'] = [{'start': a, 'end': b, 'healed': h, 'frames': sum(1 for t in an['cls'] if a <= t <= b),
                                'detail': describe_first(by, frames, me, a) if k < 12 else None}
                               for k, (a, b, h) in enumerate(eps)]
            res['overfit'] = [x for a, _, _ in eps[:5] for x in overfit_probe(plan, frames, me, a, end, mo)]
            res['given_up'] = info.get('given_up')
            # deal check: other fitting classes must give the same trace on every frame tick
            if rec['opp_deal_fit'] is not None:
                alts = [d for d in fitting_classes(rec, 400) if d != rec['opp_deal_fit']]
                pick = [alts[i] for i in sorted({0, len(alts) // 2, len(alts) - 1}) if alts] if alts else []
                jobs = [(runnable(dict(plan, deals=[d if k != me else plan['deals'][k] for k in (0, 1)])), end + 3, 0)
                        for d in pick]
                outs = run_batch(jobs, os.path.join(mo, 'work')) if jobs else []
                base = [json.dumps([x['E'], x['S'][me]]) for x in o]
                res['deal_check'] = {'classes_tested': len(pick), 'identical': [ob is not None and
                                     [json.dumps([x['E'], x['S'][me]]) for x in ob] == base for ob in outs]}
        json.dump(plan, open(os.path.join(mo, 'plan.json'), 'w'), indent=0)
    except Exception as e:  # one bad match must not stop the batch
        import traceback
        res = {'match': m, 'error': repr(e), 'trace': traceback.format_exc()[-1500:]}
    json.dump(res, open(os.path.join(mo, 'result.json'), 'w'), indent=1, default=str)
    return res


def _orig_xy(rec, c):
    for p in rec['plays']:
        if p['kind'] == 'play' and p['side'] == c['side'] and p['tick'] == c['_src']['tick'] and p['card'] == c.get('card'):
            return p['x'], p['y']
    return c['x'], c['y']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['all', 'one', 'check'])
    ap.add_argument('--inputs'); ap.add_argument('--frames'); ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=20); ap.add_argument('--only')
    ap.add_argument('--plan'); ap.add_argument('--side', type=int)
    a = ap.parse_args()
    if a.mode == 'check':
        frames = load_frames(a.frames)
        plan = json.load(open(a.plan))
        o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(a.out, 'work'))[0]
        an = analyse(o, frames, a.side)
        by = {x['t']: x for x in o}
        print(json.dumps({k: an[k] for k in ('frames', 'counts', 'first', 'missing_in_sim')}))
        print('first', json.dumps(describe_first(by, frames, a.side, an['first']))[:2500])
        print('torn', sorted(t for t, c in an['cls'].items() if c.startswith('torn')))
        return
    recs = [json.loads(l) for l in open(a.inputs)]
    if a.only:
        keep = set(a.only.split(','))
        recs = [r for r in recs if r['match'] in keep]
    jobs = [(r, os.path.join(a.frames, r['match'] + '.jsonl'), a.out) for r in recs]
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'results.jsonl'), 'a') as w, ProcessPoolExecutor(a.workers if a.mode == 'all' else 1) as ex:
        for res in ex.map(do_match, jobs):
            w.write(json.dumps(res, default=str) + '\n'); w.flush()
            print(res['match'], res.get('error') or (res.get('counts'), res.get('first_div')), flush=True)


if __name__ == '__main__':
    main()
