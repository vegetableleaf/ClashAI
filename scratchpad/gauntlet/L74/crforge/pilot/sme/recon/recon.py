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
VIS_MAX = 2                               # an unseen spell is on the board at most this many ticks
GRID = 500
COST = {'shift': 1, 'swap': 1, 'joint': 2, 'point': 2, 'add': 3, 'drop': 3}
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
    if op in ('shift', 'joint', 'add'):          # keep run order; a stable sort keeps same-tick order
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
        if len(x) > 3 and x[3] < 0:
            continue                              # the reader's hp -1 placeholder says nothing about damage
        if kind in ('U_sim_only', 'T_sim_only') and (near is None or abs(near[0]) + abs(near[1]) > 300):
            out.append((x[0], x[1], x[2]))
        elif kind in ('U_rec_only', 'T_rec_only') and near and near[0] == near[1] == 0 and len(near) > 2 and near[2] > 0:
            out.append((x[0], x[1], x[2]))
    return out


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
        if c['kind'] != 'play' or tab.is_spell(c['card']):
            continue
        t0, bx, by = first_seen(frames, c['side'], c['card'], c['x'], c['y'], min(d, c['run'] + 8), 3000)
        if t0 is not None and math.hypot(bx - c['x'], by - c['y']) >= 300 and zone_ok(tab, c['card'], c['side'], bx, by, towers_down(frames, c['side'], c['run'])):
            out.append(({'op': 'point', 'i': i, 'x': bx, 'y': by}, COST['point']))
        if not c['_src']['own']:
            for dx, dy in itertools.product((-GRID, 0, GRID), repeat=2):
                if (dx or dy) and zone_ok(tab, c['card'], c['side'], c['x'] + dx, c['y'] + dy,
                                                     towers_down(frames, c['side'], c['run'])):
                    out.append(({'op': 'point', 'i': i, 'x': c['x'] + dx, 'y': c['y'] + dy}, COST['point'] + 1))
    # drop: an implicated opponent play (own plays are taps the bot made)
    for i in imp:
        if not cmds[i]['_src']['own']:
            out.append(({'op': 'drop', 'i': i}, COST['drop']))
    # press: an ability press of the side's latest play of an implicated card that has one (hero / champion)
    for i in imp:
        c = cmds[i]
        if not tab.ability_cost(c['card']) or any(k > i and cmds[k].get('card') == c['card'] and cmds[k]['side'] == c['side']
                                                  for k in range(len(cmds))):
            continue
        for R in range(max(c['run'] + 1, d - PRESS_BACK), d):
            a = {'kind': 'ability', 'given': R - 20, 'run': R, 'side': c['side'], 'unit': 'cmd%d_0' % i,
                 '_src': {'lo': R, 'hi': R, 'tick': R, 'source': 'recon_add', 'own': c['_src']['own']}}
            for k in add_positions(plan, R):
                out.append(({'op': 'add', 'pos': k, 'cmd': a}, COST['add']))
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
        if card is None or any(cmds[i]['card'] == card and cmds[i]['side'] == s for i in near if cmds[i]['kind'] == 'play'):
            continue
        t0, bx, by = first_seen(frames, s, card, x[1], x[2], d)
        if t0 is None or not zone_ok(tab, card, s, bx, by, towers_down(frames, s, t0)):
            continue
        tp0 = prev_frame(frames, t0)
        for R in range(tp0 - 1, t0):
            for k in add_positions(plan, R):
                out.append(({'op': 'add', 'pos': k, 'cmd': add_cmd(plan, s, card, R, bx, by, tp0 - 1, t0 - 1)}, COST['add']))
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
