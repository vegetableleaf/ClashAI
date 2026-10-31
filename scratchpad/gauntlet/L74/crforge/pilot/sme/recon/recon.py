"""RECON: one general reconstruction of a live match's unseen / mis-dated events (design: ../RECON.md).

A hypothesis is an EDIT of the crforge plan (sme_live.plan_from's {"cmds": [...]}) at the first true divergence d:
  shift  one command's run tick              joint  several implicated commands' run ticks at once
  swap   two same-tick commands' order       point  a play's point (observed body point, or the +-500 grid)
  add    an unseen play (card from the side's deck)   drop  a play the extractor invented
Every edit must pass the hard game rules below BEFORE it costs an engine run; the engine (SME comparator, unchanged)
then scores the survivors (recon_search.py). Nothing here reads or changes the comparator.

Hard rules (each a function, each with planted checks in test_recon.py):
  cycle_ok   the side's play sequence admits a 4-card-cycle deal (ours: the known deal; theirs: any of 8!)
  elixir_ok  the side's bank (start E0, regen 1x / 2x / 3x, cap 10, cost at the run tick) never < -SLACK
  zone_ok    a troop / building lands in its side's half (CanDeployOnEnemySide cards anywhere)
  window     a run tick lies where the observations allow it: the extractor's [lo, hi], narrowed by
  travel     a moving spell's sightings: run = t1 - |p1 - origin| / speed (origin = caster's king; SpellAsDeploy = the
             point moved back MinDistance), when that is a whole tick
  visible    an ADDED (never-seen) spell must be one the reader can miss: on the board <= VIS_MAX ticks
"""
import itertools, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sme  # noqa: E402
import sme_live  # noqa: E402

TABLES = os.environ.get('RECON_TABLES') or (sme.TABLES if os.path.isdir(sme.TABLES) else
                                            r'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3')
sme.TABLES = TABLES                       # card_name reads the same tables
WIN = sme_live.WIN
KINGS = {0: (9000, 3000), 1: (9000, 29000)}
FWD = {0: 1, 1: -1}                       # forward = increasing y for side 0
RIVER = (15000, 17000)                    # side 0 owns y < 15000, side 1 y >= 17000 (tile rows 0-14 / 17-31)
POCKET = (21000, 11000)                   # a fallen enemy princess tower opens rows up to 20 (side 0) / from 11 (side 1)
ZONE_SLACK = 500                          # calibration knob: extracted points are body centres, not taps
SLACK = float(os.environ.get('RECON_ELIXIR_SLACK', '0.5'))   # calibration knob (field census in RECON.md)
REGEN = 1 / 56                            # elixir per tick at 1x (measured: own frames +0.0178 / tick, 3x +0.0537)
PHASES = (2400, 4800)                     # 2x from tick 2400, 3x from 4800 (fights.elixir_wait)
PRESS_BACK = 4                            # a press is tried at R in [d - 4, d - 1] (sme_live.GHOST_BACK)
REDATE = 600                              # a press is re-dated from at most this far after d (TOMB_HERO gaps seen: 253-508)
VIS_MAX = 2                               # an unseen spell is on the board at most this many ticks
GRID = 500
COST = {'shift': 1, 'swap': 1, 'joint': 2, 'point': 2, 'add': 3, 'drop': 3, 'repress': 2}
PRESS_UNITS = (0, 1, 2)                   # RECON-4: the unit of a card an ability press can name (cmdN_u); the extractor writes 0,
                                          # the hand rule TOMB_HERO hard-codes 2 -- here the engine picks it
BIRTH_REACH = 600                         # RECON-4: a body is NEW when no body of its card was within this of it one frame earlier
BIRTH_WIN = (-2, 24)                      # ... and first listed within these ticks of the play's run
REBIND = 2                                # RECON-4: a press is re-bound to one of the latest REBIND plays of its card before it
CLUSTER = 1500                            # new bodies within this of each other are one formation (one play)
ELIXIR_FREE = {'elixircollector', 'elixirgolem'}   # ponytail: decks that make elixir skip the bank rule (no model)


# ------------------------------------------------------------------ tables
class Tab:
    def __init__(self, path=TABLES):
        self.rows = {}
        for f in ('spells_characters', 'spells_buildings', 'spells_other', 'spells_evolved', 'spells_hero_form',
                  'projectiles', 'area_effect_objects', 'characters', 'buildings', 'character_abilities'):
            self.rows[f] = json.load(open(os.path.join(path, f + '.json')))['rows']

    def col(self, f, name):
        return ((self.rows[f].get(name) or {}).get('columns')) or {}

    def card(self, c):
        for f in ('spells_other', 'spells_characters', 'spells_buildings'):
            if c in self.rows[f]:
                return f, self.col(f, c)
        return None, {}

    def cost(self, c):
        return self.card(c)[1].get('ManaCost') or 0

    def ability_cost(self, c):
        """Elixir of the card's ability press: the champion's character Ability, else the hero ability row named after
        the card (ponytail: name match; 0 when none matches, which only makes the bank rule more permissive)."""
        ab = self.col('characters', self.card(c)[1].get('SummonCharacter')).get('Ability')
        rows = self.rows['character_abilities']
        if ab in rows:
            return rows[ab]['columns'].get('ManaCost') or 0
        key = re.sub(r'[^a-z]', '', c.lower()).rstrip('s') + 'hero'
        hit = [k for k in rows if re.sub(r'[^a-z]', '', k.lower()).startswith(key)]
        return (rows[hit[0]]['columns'].get('ManaCost') or 0) if len(hit) == 1 else 0

    def is_spell(self, c):
        return self.card(c)[0] == 'spells_other'

    def anywhere(self, c):
        return bool(self.card(c)[1].get('CanDeployOnEnemySide'))

    def projectile(self, c):
        """(speed per tick, MinDistance, SpellAsDeploy) of a spell that flies / rolls, else None."""
        f, col = self.card(c)
        p = self.col('projectiles', col.get('Projectile')) if f == 'spells_other' else {}
        return (p['Speed'], p.get('MinDistance') or 0, bool(col.get('SpellAsDeploy'))) if p.get('Speed') else None

    def radius(self, c):
        col = self.card(c)[1]
        return col.get('Radius') or self.col('projectiles', col.get('Projectile')).get('Radius') or \
            self.col('area_effect_objects', col.get('AreaEffectObject')).get('Radius')

    def area_life_ticks(self, c):
        ms = self.col('area_effect_objects', self.card(c)[1].get('AreaEffectObject')).get('LifeDuration')
        return None if ms is None else math.ceil(ms / 50)

    def names_of(self, c):
        """Every object name a play of card c can put on the board (the SIM's C: / P: / A: rows, the reader's card)."""
        out = {c}
        for f, n in (('spells_other', c), ('spells_characters', c), ('spells_buildings', c), ('spells_evolved', c + '_EV1'),
                     ('spells_hero_form', c + '_hero')):
            col = self.col(f, n)
            for k in ('SummonCharacter', 'SummonCharacterSecond', 'Projectile', 'AreaEffectObject'):
                if col.get(k):
                    out |= {col[k], col[k] + '_EV1', col[k] + '_hero'}
            if col:
                out.add(n)
        return {norm(x) for x in out}


def norm(name):
    return re.sub(r'^[A-Z]:', '', name or '').lower()


# ------------------------------------------------------------------ the plan
def plays_of(plan, side):
    """Deck indices of the side's play commands in run order (list order breaks ties, as crforge runs them)."""
    deck = plan['decks'][side]
    cs = sorted(((c['run'], k, c) for k, c in enumerate(plan['cmds']) if c['side'] == side and c['kind'] == 'play'),
                key=lambda x: x[:2])
    return [deck.index(c['card']) for _, _, c in cs if c['card'] in deck]


def fitting_deal(seq):
    """A deal (4-card hand + queue order) under which every play of seq is in hand, or None (sme_live.fitting_classes)."""
    fake = {'my_side': 1, 'plays': [{'side': 0, 'kind': 'play', 'deck_index': d, 'tick': k} for k, d in enumerate(seq)]}
    out = sme_live.fitting_classes(fake, 1)
    return out[0] if out else None


def cycle_ok(plan, side):
    seq = plays_of(plan, side)
    deal = plan['deals'][side]
    if deal is None:
        return fitting_deal(seq) is not None
    hand, queue = list(deal[:4]), list(deal[4:])
    for k in seq:
        if k not in hand:
            return False
        hand.remove(k); hand.append(queue.pop(0)); queue.append(k)
    return True


def bank_trace(plan, side, tab, e0):
    """[(run tick, bank after the command)] for the side's plays and ability presses, cost taken at the run tick
    (cap 10, 1x / 2x / 3x regen); None for a deck that makes elixir."""
    if ELIXIR_FREE & {re.sub(r'[^a-z]', '', c.lower()) for c in plan['decks'][0] + plan['decks'][1]}:
        return None
    cmds = plan['cmds']
    t, bank, out = 0, e0, [(0, e0)]
    for c in sorted((c for c in cmds if c['side'] == side and c['kind'] in ('play', 'ability')), key=lambda c: c['run']):
        bank = min(10.0, bank + regen(t, c['run']))
        t = c['run']
        if c['kind'] == 'play':
            bank -= tab.cost(c['card'])
        else:
            n = int(c['unit'][3:].split('_')[0])
            bank -= tab.ability_cost(cmds[n]['card']) if n < len(cmds) and cmds[n].get('card') else 0
        out.append((t, bank))
    return out


def bank_min(plan, side, tab, e0):
    tr = bank_trace(plan, side, tab, e0)
    return None if tr is None else min(b for _, b in tr)


def bank_at(trace, t):
    """The model bank at tick t (after every command run before t)."""
    t0, b = max((x for x in trace if x[0] < t), default=trace[0])
    return min(10.0, b + regen(t0, t))


def regen(a, b):
    """Elixir made between ticks a and b."""
    out, lo = 0.0, a
    for k, edge in enumerate(PHASES + (10 ** 9,)):
        if b <= lo:
            break
        if lo < edge:
            hi = min(b, edge)
            out += (hi - lo) * REGEN * (k + 1)
            lo = hi
    return out


def start_elixir(frames, plan, me, tab):
    """E0 from OUR bank at the first frame (both sides start alike): el - regen + costs of our plays run before it."""
    t0 = min(frames)
    spent = sum(tab.cost(c['card']) for c in plan['cmds'] if c['side'] == me and c['kind'] == 'play' and c['run'] < t0)
    return frames[t0]['el'] / 10000 - regen(0, t0) + spent


def elixir_ok(plan, side, tab, e0):
    low = bank_min(plan, side, tab, e0)
    return low is None or low >= -SLACK


def zone_ok(tab, card, side, x, y, down=()):
    """A troop / building / territory-bound spell lands in its side's half, or in the pocket (the enemy half's first
    POCKET units, x on the lane) of a lane whose enemy princess tower is down (down: lanes 0 = x < 9000, 1)."""
    if tab.anywhere(card):
        return True
    lane = 0 if x < 9000 else 1
    if side == 0:
        return y < (POCKET[0] if lane in down else RIVER[0]) + ZONE_SLACK
    return y >= (POCKET[1] if lane in down else RIVER[1]) - ZONE_SLACK


def towers_down(frames, side, t):
    """Lanes whose ENEMY princess tower is not listed in the last frame at or before t."""
    ts = [u for u in frames if u <= t]
    if not ts:
        return set()
    f = frames[max(ts)]
    y = 25500 if side == 0 else 6500
    up = {0 if e[1] < 9000 else 1 for e in f['E'] if e[0] == 1 - side and e[3] == -1 and e[2] == y and e[1] in (3500, 14500)}
    return {0, 1} - up


def travel_runs(cmd, frames, tab):
    """Run ticks a moving spell's first two sightings allow (whole ticks only), or None when the rule says nothing."""
    pj = tab.projectile(cmd.get('card', ''))
    if cmd['kind'] != 'play' or not pj:
        return None
    v, mind, as_deploy = pj
    s = cmd['side']
    o = (cmd['x'], cmd['y'] - FWD[s] * mind) if as_deploy else KINGS[s]
    lo = cmd['_src']['lo']
    seen = []
    for t in sorted(t for t in frames if lo < t <= lo + 40):
        for q in frames[t]['P']:
            if q[0] == s and sme.card_name(q[3]) == cmd['card'] and on_line(o, (cmd['x'], cmd['y']), q[1:3]):
                seen.append((t, q[1], q[2]))
                break
        if len(seen) == 2:
            break
    if not seen:
        return None
    t1, x1, y1 = seen[0]
    k = math.hypot(x1 - o[0], y1 - o[1]) / v
    return {t1 - round(k)} if abs(k - round(k)) < 0.05 else None


def on_line(a, b, p, tol=60):
    (ax, ay), (bx, by), (px, py) = a, b, p
    L = math.hypot(bx - ax, by - ay)
    return L > 0 and abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / L <= tol


# ------------------------------------------------------------------ edits
def apply_edit(plan, e):
    """New plan with edit e applied: command order kept by run tick, ability 'cmdN_k' references remapped,
    the deal of every side with an unknown deal recomputed (crforge plays from a forced deal)."""
    cmds = [dict(c) for c in plan['cmds']]
    ids = list(range(len(cmds)))                 # ids[k] = old index of the command now at k (None = added)
    op = e['op']
    if op == 'shift':
        cmds[e['i']].update(run=e['run'], given=e['run'] - 20)
    elif op == 'joint':
        for i, R in e['runs'].items():
            cmds[int(i)].update(run=R, given=R - 20)
    elif op == 'point':
        cmds[e['i']].update(x=e['x'], y=e['y'])
    elif op == 'repress':                        # an ability press re-dated and re-bound (play n, unit u)
        cmds[e['i']].update(run=e['run'], given=e['run'] - 20, unit='cmd%d_%d' % (e['n'], e['u']))
    elif op == 'swap':
        i, j = e['i'], e['j']
        cmds[i], cmds[j] = cmds[j], cmds[i]
        ids[i], ids[j] = ids[j], ids[i]
    elif op == 'drop':
        if any(c.get('unit', '').split('_')[0] == 'cmd%d' % e['i'] for c in cmds):
            return None                          # an ability of the play would name nothing
        del cmds[e['i']]
        del ids[e['i']]
    elif op == 'add':
        k = e['pos']
        cmds.insert(k, dict(e['cmd']))
        ids.insert(k, None)
    if op in ('shift', 'joint', 'add', 'repress'):  # keep run order; a stable sort keeps same-tick order
        order = sorted(range(len(cmds)), key=lambda k: cmds[k]['run'])
        cmds, ids = [cmds[k] for k in order], [ids[k] for k in order]
    new_of = {old: k for k, old in enumerate(ids) if old is not None}
    for c in cmds:
        if c.get('unit'):
            n, u = c['unit'][3:].split('_')
            if int(n) not in new_of:
                return None
            c['unit'] = 'cmd%d_%s' % (new_of[int(n)], u)
    p = dict(plan, cmds=cmds, deals=list(plan['deals']))
    for s in (0, 1):                             # an unknown deal is re-fitted only when the old one stops fitting
        if plan.get('_deal_unknown', [False, True])[s] and not cycle_ok(p, s):
            p['deals'][s] = fitting_deal(plays_of(p, s)) or plan['deals'][s]
    return p


def legal(plan, side, tab, e0, me):
    """The hard rules on one side after an edit; -> None if legal, else the rule broken."""
    if plan is None:
        return 'unit_ref'
    if plan.get('_cycle_base', (True, True))[side] and not cycle_ok(plan, side):
        return 'cycle'                           # a side whose extracted plays already break the cycle is not tested
    if side != me and plan.get('_elixir_base', (True, True))[side] and not elixir_ok(plan, side, tab, e0):
        return 'elixir'
    return None


# ------------------------------------------------------------------ hypotheses
def implicated(plan, tab, d, detail):
    """Commands run in [d - WIN, d] whose card can make an object the first-divergence diff names."""
    names = {norm(r[2]) for r in detail if r[2]}
    return [i for i, c in enumerate(plan['cmds']) if d - WIN <= c['run'] <= d and c['kind'] == 'play'
            and tab.names_of(c['card']) & names]


def run_set(c, frames, tab):
    s = c['_src']
    tr = travel_runs(c, frames, tab)
    win = set(range(s['lo'], s['hi'] + 1))
    return (tr & win or tr) if tr else win


def victims(detail):
    """(side, x, y) of bodies the live game damaged or removed and the SIM did not: SIM-only bodies with no live body
    within 300 units, and live bodies at the SIM body's point with less hp."""
    out = []
    for kind, x, _, near in detail:
        if not isinstance(x, (list, tuple)):
            continue                              # S*_elixir rows carry a number, not a body (SME-REBUILD: 201103, 001856)
        if len(x) > 3 and x[3] < 0:
            continue                              # the reader's hp -1 placeholder says nothing about damage
        if kind in ('U_sim_only', 'T_sim_only') and (near is None or abs(near[0]) + abs(near[1]) > 300):
            out.append((x[0], x[1], x[2]))
        elif kind in ('U_rec_only', 'T_rec_only') and near and near[0] == near[1] == 0 and len(near) > 2 and near[2] > 0:
            out.append((x[0], x[1], x[2]))
    return out


def overhit(detail):
    """(side, x, y) of bodies the SIM damaged and the live game did not: a SIM-only row whose live twin sits at its point with
    more hp (RECON-4, 091720: our Knight 392 lower in the SIM because a hit landed that did not in the game)."""
    return [(r[1][0], r[1][1], r[1][2]) for r in detail if r[0] == 'U_sim_only' and isinstance(r[1], (list, tuple))
            and r[3] and r[3][0] == r[3][1] == 0 and len(r[3]) > 2 and r[3][2] > 0]


def prev_frame(frames, d):
    return max((t for t in frames if t < d), default=d - 1)


def first_seen(frames, side, card, x, y, d, reach=1500):
    """Earliest tick (scanning back from d) a body of the side and card is listed within reach of (x, y), and the centre of
    the card's bodies listed then (a formation's point)."""
    t0, first = None, []
    for t in sorted((t for t in frames if d - WIN <= t <= d), reverse=True):
        hit = [e for e in frames[t]['E'] if e[0] == side and sme.card_name(e[3]) == card
               and math.hypot(e[1] - x, e[2] - y) <= reach]
        if not hit:
            break
        t0, x, y, first = t, hit[0][1], hit[0][2], hit
    if first:
        x, y = round(sum(e[1] for e in first) / len(first)), round(sum(e[2] for e in first) / len(first))
    return t0, x, y


def born_points(frames, side, card, run):
    """RECON-4 (own point without a distance cap): where the bodies of (side, card) NEW around run were first listed, one point
    per formation. New = first listed in run + BIRTH_WIN with no body of that card within BIRTH_REACH one frame earlier. -> [(x, y)]"""
    ts = sorted(frames)
    for k, t in enumerate(ts):
        if k == 0 or not (run + BIRTH_WIN[0] <= t <= run + BIRTH_WIN[1]):
            continue
        bodies = lambda u: [e for e in frames[u]['E'] if e[0] == side and sme.card_name(e[3]) == card]   # noqa: E731
        old = bodies(ts[k - 1])
        new = [e for e in bodies(t) if all(math.hypot(e[1] - o[1], e[2] - o[2]) > BIRTH_REACH for o in old)]
        if not new:
            continue
        groups = []
        for e in new:
            for g in groups:
                if math.hypot(e[1] - g[0][1], e[2] - g[0][2]) <= CLUSTER:
                    g.append(e)
                    break
            else:
                groups.append([e])
        return [(round(sum(e[1] for e in g) / len(g)), round(sum(e[2] for e in g) / len(g))) for g in groups]
    return []


def add_cmd(plan, side, card, R, x, y, lo, hi):
    return {'kind': 'play', 'given': R - 20, 'run': R, 'side': side, 'card': card,
            'level': plan['levels'][side][plan['decks'][side].index(card)], 'x': int(x), 'y': int(y),
            '_src': {'lo': lo, 'hi': hi, 'tick': R, 'source': 'recon_add', 'own': False}}


def add_positions(plan, R):
    """List positions an added command can take at run R: after every command run before R, and each same-tick slot."""
    before = sum(1 for c in plan['cmds'] if c['run'] < R)
    same = sum(1 for c in plan['cmds'] if c['run'] == R)
    return range(before, before + same + 1)


def hypotheses(plan, frames, d, detail, tab, me):
    """-> [(edit, cost)]: every edit at the first divergence d that passes the hard rules (the engine scores them)."""
    out = []
    cmds = plan['cmds']
    near = [i for i, c in enumerate(cmds) if d - WIN <= c['run'] <= d or c['_src']['lo'] <= d < c['run']]
    imp = implicated(plan, tab, d, detail)
    # shift: each command near d, every run tick its observations allow
    for i in near:
        c = cmds[i]
        if c['kind'] == 'skip':
            continue
        for R in sorted(run_set(c, frames, tab) - {c['run']}):
            out.append(({'op': 'shift', 'i': i, 'run': R}, COST['shift']))
    # joint: the implicated commands moved together (cartesian product of their run sets, current included)
    if len(imp) >= 2:
        sets = [sorted(run_set(cmds[i], frames, tab) | {cmds[i]['run']}) for i in imp]
        for combo in itertools.islice(itertools.product(*sets), 64):
            ch = {i: R for i, R in zip(imp, combo) if R != cmds[i]['run']}
            if len(ch) >= 2:
                out.append(({'op': 'joint', 'runs': ch}, COST['joint']))
    # swap: two commands on one run tick (crforge runs them in list order; the game in its own order)
    for i, j in itertools.combinations(near, 2):
        if cmds[i]['run'] == cmds[j]['run'] and cmds[i]['kind'] != 'skip' != cmds[j]['kind']:
            out.append(({'op': 'swap', 'i': i, 'j': j}, COST['swap']))
    # point: the observed body point (first listed body of the play), and the +-500 grid for opponent plays
    for i in near:
        c = cmds[i]
        if c['kind'] != 'play':
            continue
        if not tab.is_spell(c['card']):           # a spell has no body point; its grid below is the fitter's (172955: Zap)
            t0, bx, by = first_seen(frames, c['side'], c['card'], c['x'], c['y'], min(d, c['run'] + 8), 3000)
            if t0 is not None and math.hypot(bx - c['x'], by - c['y']) >= 300 and zone_ok(tab, c['card'], c['side'], bx, by, towers_down(frames, c['side'], c['run'])):
                out.append(({'op': 'point', 'i': i, 'x': bx, 'y': by}, COST['point']))
        for bx, by in born_points(frames, c['side'], c['card'], c['run']):   # RECON-4: no distance cap
            if math.hypot(bx - c['x'], by - c['y']) >= 300 and zone_ok(tab, c['card'], c['side'], bx, by, towers_down(frames, c['side'], c['run'])) \
                    and not any(k != i and o.get('card') == c['card'] and o['side'] == c['side'] and o['kind'] == 'play'
                                and abs(o['run'] - c['run']) <= BIRTH_WIN[1] and math.hypot(bx - o['x'], by - o['y']) < 300
                                for k, o in enumerate(cmds)):
                out.append(({'op': 'point', 'i': i, 'x': bx, 'y': by}, COST['point'] + 1))
        if not c['_src']['own']:
            for dx, dy in itertools.product((-GRID, 0, GRID), repeat=2):
                if (dx or dy) and zone_ok(tab, c['card'], c['side'], c['x'] + dx, c['y'] + dy,
                                                     towers_down(frames, c['side'], c['run'])):
                    out.append(({'op': 'point', 'i': i, 'x': c['x'] + dx, 'y': c['y'] + dy}, COST['point'] + 1))
    # drop (RECON-4): an opponent play (own plays are taps the bot made) or an ability press of either side near d; the diff's names
    # only rank them (implicated first): a tower hp row or an elixir-only row names no card (130148, 001856, 230352)
    dropped = set()
    for i in near:
        c = cmds[i]
        if c['kind'] == 'ability' or (c['kind'] == 'play' and not c['_src']['own']):
            dropped.add(i)
            out.append(({'op': 'drop', 'i': i}, COST['drop'] + (0 if i in imp else 1)))
    # drop: cycle repair -- a side whose play sequence breaks the cycle (our deal known, theirs: any of 8!): each opponent play
    # whose removal restores a fitting deal, wherever it is (031310: a phantom Zap at 3680 made the whole match run a wrong deal)
    for s_ in (0, 1):
        if s_ != me and not cycle_ok(plan, s_):
            for i, c in enumerate(cmds):
                if c['side'] == s_ and c['kind'] == 'play' and i not in dropped:
                    q = apply_edit(plan, {'op': 'drop', 'i': i})
                    if q is not None and cycle_ok(q, s_):
                        out.append(({'op': 'drop', 'i': i}, COST['drop']))
    # press (RECON-4: the unit is an edit dimension): an ability press of the latest play of a card that has one, for the cards the
    # diff names, and for the other side's ability cards alive at d when the diff shows a victim of that side (091720: the
    # Boss Bandit's press, the diff names our Knight)
    tp0 = prev_frame(frames, d)
    pressers = set(imp)
    for v, _, _ in victims(detail) + overhit(detail):
        for i, c in enumerate(cmds):
            if c['kind'] == 'play' and c['side'] == 1 - v and c['run'] <= d and tp0 in frames and any(
                    e[0] == c['side'] and sme.card_name(e[3]) == c['card'] for e in frames[tp0]['E']):
                pressers.add(i)
    for i in sorted(pressers):
        c = cmds[i]
        if c['kind'] != 'play' or not tab.ability_cost(c['card']) or any(
                k > i and cmds[k].get('card') == c['card'] and cmds[k]['side'] == c['side'] and cmds[k]['kind'] == 'play'
                for k in range(len(cmds))):
            continue
        for R in range(max(c['run'] + 1, d - PRESS_BACK), d):
            for u in PRESS_UNITS:
                a = {'kind': 'ability', 'given': R - 20, 'run': R, 'side': c['side'], 'unit': 'cmd%d_%d' % (i, u),
                     '_src': {'lo': R, 'hi': R, 'tick': R, 'source': 'recon_add', 'own': c['_src']['own']}}
                for k in add_positions(plan, R):
                    out.append(({'op': 'add', 'pos': k, 'cmd': a}, COST['add'] + (u != 0)))
    # repress (RECON-4: re-bound, unit chosen): a later-extracted press of a card the diff names, re-dated to just before d, bound
    # to any earlier play of that card and side (the press has no cast state: the extractor dates it at the cast it sees, binds
    # it to the newest play and writes no unit; hero Tombstone 165724: extracted 940 / bound to the play at 4333, true 4077 / the play at 3433)
    names = {norm(r[2]) for r in detail if r[2]}
    for i, c in enumerate(cmds):
        if c['kind'] == 'ability' and d < c['run'] <= d + REDATE:
            n0, u0 = (int(x) for x in c['unit'][3:].split('_'))
            if n0 < len(cmds) and tab.names_of(cmds[n0].get('card', '')) & names:
                card, side = cmds[n0]['card'], cmds[n0]['side']
                plays = [k for k, o in enumerate(cmds) if o['kind'] == 'play' and o['card'] == card and o['side'] == side]
                for R in range(d - PRESS_BACK, d):
                    for n in dict.fromkeys([n0] + [k for k in plays if cmds[k]['run'] < R][-REBIND:]):
                        if cmds[n]['run'] >= R:
                            continue
                        for u in dict.fromkeys((u0,) + PRESS_UNITS):
                            out.append(({'op': 'repress', 'i': i, 'run': R, 'n': n, 'u': u},
                                        COST['repress'] + (u != u0) + (n != n0)))
    # add (a): an unseen spell of the other side whose radius covers every victim of one side
    vic = victims(detail)
    tp = prev_frame(frames, d)
    for v in (0, 1):
        vs = [(x, y) for s, x, y in vic if s == v]
        if not vs:
            continue
        o = 1 - v
        cx, cy = sum(x for x, _ in vs) / len(vs), sum(y for _, y in vs) / len(vs)
        for card in plan['decks'][o]:
            r = tab.radius(card)
            if not tab.is_spell(card) or not r:
                continue
            pj = tab.projectile(card)
            if pj and pj[2]:
                continue                          # a roller is on the board for many ticks: never unseen
            for dx, dy in itertools.product((-GRID, 0, GRID), repeat=2):
                px, py = cx + dx, cy + dy
                if any(math.hypot(x - px, y - py) > r + ZONE_SLACK for x, y in vs):
                    continue
                fly = math.ceil(math.hypot(px - KINGS[o][0], py - KINGS[o][1]) / pj[0]) if pj else 0
                vis = fly if pj else (tab.area_life_ticks(card) or 0)
                if vis > VIS_MAX:
                    continue
                for R in range(tp - fly, d - fly):
                    for k in add_positions(plan, R):
                        e = {'op': 'add', 'pos': k, 'cmd': add_cmd(plan, o, card, R, px, py, tp - fly, d - 1 - fly)}
                        out.append((e, COST['add'] + (dx != 0 or dy != 0)))
    # add (b): a body the reader lists and the SIM lacks, of a deck card no near command plays
    for kind, x, name, nb in detail:
        if kind != 'U_rec_only' or not name or (nb and abs(nb[0]) + abs(nb[1]) <= 300):
            continue
        s = x[0]
        card = name if name in plan['decks'][s] else None
        if card is None:
            continue
        # two anchors for the missing play: where the body chain leads back to (first_seen: a body listed for many ticks) and the
        # body's own row at d (the first divergence is the tick it appears when it was not listed before; RECON-4, 101018: the
        # chain led into an older same-card body)
        t0, bx, by = first_seen(frames, s, card, x[1], x[2], d)
        for t0_, bx_, by_ in dict.fromkeys([(t0, bx, by), (d, x[1], x[2])]):
            if t0_ is None or not zone_ok(tab, card, s, bx_, by_, towers_down(frames, s, t0_)):
                continue
            # a missing play unless a play of that card and side runs where the body was born (a living same-card body no
            # longer blocks it)
            if any(cmds[i].get('card') == card and cmds[i]['side'] == s and cmds[i]['kind'] == 'play' and t0_ - 12 <= cmds[i]['run'] <= t0_ + 1
                   for i in range(len(cmds))):
                continue
            tp0 = prev_frame(frames, t0_)
            for R in range(tp0 - 1, t0_):
                for k in add_positions(plan, R):
                    out.append(({'op': 'add', 'pos': k, 'cmd': add_cmd(plan, s, card, R, bx_, by_, tp0 - 1, t0_ - 1)}, COST['add']))
    return out


def legal_hypotheses(plan, frames, d, detail, tab, me, e0, why=None):
    """hypotheses() filtered by the hard rules; why (a Counter) collects the reasons edits were refused."""
    keep = []
    for e, cost in hypotheses(plan, frames, d, detail, tab, me):
        p = apply_edit(plan, e)
        sides = {cmd_side(plan, e)}
        bad = next((b for b in (legal(p, s, tab, e0, me) for s in sides) if b), None) if p else 'unit_ref'
        if bad:
            if why is not None:
                why[bad] += 1
            continue
        keep.append((e, cost, p))
    return keep


def cmd_side(plan, e):
    if e['op'] == 'add':
        return e['cmd']['side']
    i = e.get('i', next(iter(e.get('runs', {0: 0}))))
    return plan['cmds'][int(i)]['side']


def describe(plan, e):
    c = e['cmd'] if e['op'] == 'add' else plan['cmds'][int(e.get('i', next(iter(e.get('runs', {0: 0})))))]
    if e['op'] == 'repress':
        return 'repress s%d cmd%d_%d R%d (was %s)' % (c['side'], e['n'], e['u'], e['run'], c['unit'])
    tag = '%s s%d %s' % (e['op'], c['side'], c.get('card', c.get('unit')))
    if e['op'] == 'add' and c['kind'] == 'ability':
        n = int(c['unit'][3:].split('_')[0])
        return 'press s%d %s (cmd%d) R%d pos%d' % (c['side'], plan['cmds'][n].get('card'), n, c['run'], e['pos'])
    if e['op'] == 'add':
        return tag + ' R%d (%d,%d) pos%d' % (c['run'], c['x'], c['y'], e['pos'])
    if e['op'] == 'joint':
        return 'joint ' + ', '.join('%s->%d' % (plan['cmds'][int(i)].get('card'), R) for i, R in e['runs'].items())
    if e['op'] == 'swap':
        return 'swap %s s%d <-> %s s%d @%d' % (plan['cmds'][e['i']].get('card'), plan['cmds'][e['i']]['side'],
                                              plan['cmds'][e['j']].get('card'), plan['cmds'][e['j']]['side'],
                                              plan['cmds'][e['i']]['run'])
    return tag + ' ' + json.dumps({k: v for k, v in e.items() if k not in ('op', 'i')})


def base_plan(rec, frames):
    """sme_live.plan_from on the record, plus which deals RECON may recompute (the side whose deal is not known)."""
    plan = sme_live.plan_from(rec, rec['opp_deal_fit'] or list(range(8)), frames)
    plan['levels'] = [rec['sides']['0']['levels'], rec['sides']['1']['levels']]
    unk = [True, True]
    unk[rec['my_side']] = False
    plan['_deal_unknown'] = unk
    plan['_cycle_base'] = [cycle_ok(plan, s) for s in (0, 1)]
    return plan


def with_elixir_base(plan, tab, e0):
    """Mark which sides' extracted plays already pass the bank rule (a side that fails it is not tested)."""
    plan['_elixir_base'] = [elixir_ok(plan, s, tab, e0) for s in (0, 1)]
    return plan


def runnable(plan):
    """The plan crforge reads (RECON's bookkeeping fields stripped)."""
    p = {k: v for k, v in plan.items() if not k.startswith('_') and k != 'levels'}
    return dict(p, cmds=[{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']])   # = sme_live.runnable


# ------------------------------------------------------------------ RECON-5: deck-constrained cycle repair (cyc.py; RECON.md section 12)
sys.path.insert(0, HERE)
import cyc  # noqa: E402

CYC_MAX_COST = 4          # repairs up to this many edits (unseen plays + invented plays + Mirror readings) are generated
CYC_POOL = 400            # optimal repairs enumerated before ranking (cyc.repairs cap)
CYC_CAP = int(os.environ.get('RECON_CYC_CAP', '24'))   # engine-scored repairs per match (best by prior)
GHOST_MARGIN = 1000       # a no-effect spell lands this far (plus its radius) from every listed body / tower


def seq_of(plan, side):
    """[(run, command index)] of the side's play commands whose card is a deck card, in plays_of's order."""
    deck = plan['decks'][side]
    return sorted(((c['run'], k) for k, c in enumerate(plan['cmds'])
                   if c['side'] == side and c['kind'] == 'play' and c['card'] in deck))


def deck_conflicts(plan, side):
    """Play commands of the side whose card is not one of its 8 deck cards: a wrong deck (or a mislabelled play). A side with a
    conflict is never repaired (the cycle model is only valid for the true deck)."""
    return [c for c in plan['cmds'] if c['side'] == side and c['kind'] == 'play' and c['card'] not in plan['decks'][side]]


def best_prefix_deal(seq):
    """The deal that lets the most plays of seq run when a play whose card is not in hand is refused (the engine's behaviour):
    for a sequence that fits no deal this replaces the identity deal (RECON-5: its first refused play, tick ~200-500, was the
    early divergence of the opponent_no_fitting_deal records). First best state wins (ties: the lowest state index)."""
    best, bs = -1, None
    for s0, st in enumerate(cyc.STATES):
        s, n = s0, 0
        for h in seq:
            t = cyc.TR[s].get(h)
            if t is not None:
                s, n = t, n + 1
        if n > best:
            best, bs = n, s0
    return cyc.deal_of(cyc.STATES[bs]), best


def harmless_point(frames, T, side, card, tab):
    """A grid point in the caster's half where a spell cast at tick T touches nothing: the point farthest from every body, tower,
    projectile and area the reader lists around T (a rolling spell: from every point of its path, a fixed 12,000 long)."""
    ts = [t for t in frames if t <= T]
    f = frames[max(ts)] if ts else None
    objs = [(e[1], e[2]) for e in f['E']] + [(q[1], q[2]) for q in f['P']] + [(a[1], a[2]) for a in f['A']] if f else []
    r = (tab.radius(card) or 2500) + GHOST_MARGIN
    roll = bool(tab.projectile(card))
    ys = range(500, 14501, 500) if side == 0 else range(17500, 31501, 500)
    best, bp = -1, None
    for x in range(500, 17501, 500):
        for y in ys:
            pts = [(x, y + FWD[side] * d) for d in range(0, 12001, 1500)] if roll else [(x, y)]
            if roll and not all(0 <= py <= 32000 for _, py in pts):
                continue
            if not zone_ok(tab, card, side, x, y):
                continue
            d = min((math.hypot(ox - px, oy - py) for ox, oy in objs for px, py in pts), default=10 ** 6)
            if d > best:
                best, bp = d, (x, y)
    return bp if best >= r else None


def _cmd_ins(plan, side, card, T, x, y):
    c = add_cmd(plan, side, card, T, x, y, T, T)
    c['_src']['cyc'] = True
    return c


def cycle_repairs(plan, frames, side, tab, e0, cap=CYC_CAP, end=None):
    """Engine-scorable repaired plans for a side whose play sequence fits no deal. -> [(description, cost, plan)], best prior first.
    A repair = the fewest edits (cyc.repairs: unseen plays of SPELL cards, invented plays dropped, one play read as the Mirror) after
    which the sequence is a legal 4-card cycle; the unseen spells run mid-gap between their neighbours (the elixir rule picks
    among a few slots) at a point that touches nothing. [] when the side already fits or no repair <= CYC_MAX_COST exists."""
    deck = plan['decks'][side]
    if deck_conflicts(plan, side):
        return []
    sq = seq_of(plan, side)
    seq = [deck.index(plan['cmds'][k]['card']) for _, k in sq]
    if cyc.fits(seq):
        return []
    spells = [i for i, c in enumerate(deck) if c and tab.is_spell(c)]
    mir = deck.index('Mirror') if 'Mirror' in deck else None
    cost, reps = cyc.repairs(seq, ins_cards=spells, mirror=mir, allow_drop=True, cap=CYC_POOL, max_cost=CYC_MAX_COST)
    if cost is None:
        return []

    def prior(rep):     # an invented play is likelier when it was a spell sighting than when bodies were seen
        ins, rel, _ = rep
        drops = [r[1] for r in rel if isinstance(r, tuple)]
        return (len(ins) + len(rel)
                + sum(0 if plan['cmds'][sq[j][1]]['_src'].get('source') == 'spell_seen' else 1 for j in drops), len(drops))

    out = []
    end = end or max(frames)
    for ins, rel, deal in sorted(reps, key=prior):
        p = dict(plan, cmds=[dict(c) for c in plan['cmds']], deals=list(plan['deals']))
        what, drop_k = [], []
        for r in rel:
            if isinstance(r, tuple):
                drop_k.append(sq[r[1]][1])
                what.append('drop s%d %s R%d' % (side, plan['cmds'][sq[r[1]][1]]['card'], sq[r[1]][0]))
            elif mir is not None:
                k = sq[r][1]
                what.append('mirror s%d %s R%d' % (side, p['cmds'][k]['card'], sq[r][0]))
                p['cmds'][k]['card'] = 'Mirror'
                p['cmds'][k]['level'] = plan['levels'][side][mir]
        bad = False
        for k in sorted(drop_k, reverse=True):
            p = apply_edit(p, {'op': 'drop', 'i': k})
            if p is None:
                bad = True
                break
        if bad:
            continue
        gaps = collections_defaultdict_list()
        for i, h in ins:
            gaps[i].append(h)
        for i, hs in sorted(gaps.items()):
            a = sq[i - 1][0] if i > 0 else 0
            b = sq[i][0] if i < len(sq) else end
            for j, h in enumerate(hs):
                T = a + (b - a) * (j + 1) // (len(hs) + 1)
                if not a < T < b:
                    bad = True
                    break
                pt = harmless_point(frames, T, side, deck[h], tab)
                if pt is None:
                    bad = True
                    break
                e = {'op': 'add', 'pos': next(iter(add_positions(p, T))), 'cmd': _cmd_ins(p, side, deck[h], T, *pt)}
                p = apply_edit(p, e)
                if p is None:
                    bad = True
                    break
                what.append('ins s%d %s R%d (%d,%d)' % (side, deck[h], T, pt[0], pt[1]))
            if bad:
                break
        if bad:
            continue
        p['deals'][side] = list(deal)
        p['_cycle_base'] = [cycle_ok(p, s) for s in (0, 1)]
        if not p['_cycle_base'][side]:
            continue                                  # cannot happen when cyc and plays_of agree; checked, not assumed
        if plan.get('_elixir_base', (True, True))[side] and not elixir_ok(p, side, tab, e0):
            continue
        out.append(('cyc ' + '; '.join(what), cost, p))
        if len(out) >= cap:
            break
    return out


def collections_defaultdict_list():
    import collections
    return collections.defaultdict(list)


# ------------------------------------------------------------------ RECON-5: our own taps (the bot's action log) restore missed own plays
TAP_MATCH = 120           # a tap and an extracted play of the same card within this many ticks of tap + own_delay are one play
TAP_WIN = (-2, 3)         # an own_tap play's tick is tap + own_delay + {-2..3} on 12,543 matched plays (point = the tap's point on all)


def unmatched_taps(rec, plan, me):
    """Own taps no extracted own play explains (greedy by tap order, the nearest same-card play within TAP_MATCH of tap + own_delay).
    Our taps are the bot's own action log: a tap the game ran is a play, whatever the reader saw. 20 / 20 own_cycle_fail records
    (FRESH2-9) have exactly one such tap and 355 cycle-clean records have 2 (RECON.md section 12.4)."""
    deck = plan['decks'][me]
    plays = [(c['run'], k) for k, c in enumerate(plan['cmds']) if c['side'] == me and c['kind'] == 'play']
    used, out = set(), []
    for t in rec.get('own_taps') or ():
        if t['name'] not in deck:
            continue
        run = t['tick'] + rec['own_delay']
        near = [(abs(r - run), k) for r, k in plays if k not in used and plan['cmds'][k]['card'] == t['name'] and abs(r - run) <= TAP_MATCH]
        if near:
            used.add(min(near)[1])
        else:
            out.append(t)
    return out


def restore_taps(rec, plan, me, taps=None):
    """-> (description, plan with every unmatched own tap added as an own play at the tap's point and run tick + own_delay), or None."""
    taps = unmatched_taps(rec, plan, me) if taps is None else taps
    if not taps:
        return None
    p, what = plan, []
    for t in taps:
        R = int(round(t['tick'] + rec['own_delay']))        # own_delay / tap ticks can be floats in the record (RECON-5 dev: 3 records)
        c = add_cmd(p, me, t['name'], R, t['x'], t['y'], R + TAP_WIN[0], R + TAP_WIN[1])
        c['_src'].update(own=True, source='own_tap', tap_restore=True)
        p = apply_edit(p, {'op': 'add', 'pos': next(iter(add_positions(p, R))), 'cmd': c})
        if p is None:
            return None
        what.append('%s R%d (%d,%d)' % (t['name'], R, t['x'], t['y']))
    p['_cycle_base'] = [cycle_ok(p, s) for s in (0, 1)]
    return 'tap s%d ' % me + '; '.join(what), p
