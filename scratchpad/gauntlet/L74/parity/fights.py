"""S2 fight-level parity: cut frame-logged live matches into short FIGHTS, rebuild the SIM at each fight's start from
the live frame, replay the same deployments, and compare the SIM to the live frames.

Why fights, not whole matches: a whole-match replay diverges within seconds (TRIAGE.md, EARLY_END.md) and every later
row measures inherited error. Here every fight restarts from the live board:
  * towers: live hp (0 = down), king awake as the frame shows it;
  * every live body alive at the fight's start frame is a setup spawn (Battle.reset spawns: card, point, hp) at its
    exact position and hp; per-card levels are read off the bodies' max_hp (unit_hitpoints), not assumed;
  * every deployment inside the window is a normal play (deploy timer, formation, deploy effects) at the tick its first
    body appears in the live frames (own taps at their tap point; opponent at the first-seen centroid); own spells at
    tap + this match's measured tap->spawn delay; own Hero IW presses likewise.
Then the SIM is sampled at the live frame ticks and bodies are paired (setup: exact point; new: same card/side/form,
nearest, max_hp within 40%).

Public reader values only. Reader addresses are hashed per match and never written. No live control.

  python fights.py run   --out DIR [--files 'glob'] [--limit N] [--workers N] [--window 240]
  python fights.py score --out DIR          # scoreboard.json + SCOREBOARD.txt from DIR/matches/*.json
Engine: ROYALE_RUNTIME (pipeline.royale_runtime.activate) or PARITY_SIM_PATH=<unpacked wheel dir> (laptop prototype).
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity.core import load_catalog, ps, raw_xy

CARD_TABLE = 'client160402017_20261006'
OWN_PRINCESS_MAX = 4424            # icebow main account signature (HANDOFF; verify-mumu-account note)
GAP_SPLIT = 60                     # an address unseen this long is a new body (phase_stats Tracks rule)
QUARTER = 250                      # millitiles: the 1/4-tile position metric (upstream replay_parity "<=250")
NO_CARD = 65535
PRIORITY = {'Xbow', 'Tesla', 'Tornado', 'Log', 'IceWizard', 'Rocket', 'Knight', 'Skeletons', 'MegaKnight', 'Golem',
            'ElixirGolem', 'SkeletonBalloon', 'Barbarians', 'Firecracker', 'MinionHorde', 'Giant'}


# ---------------------------------------------------------------- live side (no engine import)

def read_match(path):
    """-> (match, None) or (None, reason). Frames: [(tick, [body])]; body keys: id side x y card_id hp max_hp kind tower."""
    frames, plays, outcome, abilities = {}, [], [], []
    hands = []                      # (tick, {name: form}) from public own_hand
    shots = []                      # (tick, side, card_id) public in-flight projectiles at decision ticks
    side = None
    with open(path, 'rb') as f:
        for raw in f:
            head = raw[:40]
            if b'"frame"' in head:
                j = json.loads(raw)
                side = j['my_side']
                frames[j['tick']] = j['ents']           # duplicate tick: keep the last read
            elif b'"decision"' in head:
                j = json.loads(raw); p = j.get('public') or {}
                hands.append((j['tick'], {h['name']: int(h.get('form', 0)) for h in p.get('own_hand', [])}))
                shots += [(j['tick'], q['side'], q['card_id']) for q in p.get('raw_projectiles', []) if q.get('card_id', -1) != -1]
            elif b'"play"' in head:
                j = json.loads(raw); plays.append(dict(tick=j['tick'], name=j['name'], xy=j['xy']))
            elif b'"confirmed"' in head or b'"unconfirmed"' in head:
                j = json.loads(raw); outcome.append((j['event'], j['name'], j.get('intended')))
            elif b'"ability"' in head:
                j = json.loads(raw); abilities.append(dict(tick=j['tick'], confirmed=False))
            elif b'"ability_confirmed"' in head:
                if abilities:
                    abilities[-1]['confirmed'] = True
    if not frames:
        return None, 'no_frames'
    ticks = sorted(frames)
    first = frames[ticks[0]]
    own_pr = {e[5] for e in first if e[3] == -1 and e[0] == side and e[6] == 13 and abs(e[1]-9000) > 1000}
    if own_pr != {OWN_PRINCESS_MAX}:
        return None, 'not_main_account'
    # confirmed own plays: each play is followed by exactly one confirmed/unconfirmed event, in order
    plays = [dict(p, xy=o[2] or p['xy']) for p, o in zip(plays, outcome) if o[0] == 'confirmed' and o[1] == p['name']]
    for p in plays:      # xy: the confirmation's unrounded 'intended' (the play event rounds to 4 decimals, which moves
                         # a tap sitting on a tile edge, e.g. 0.65625*32 = 21.0, into the tile below)
        prior = [h for t, h in hands if t <= p['tick']]
        p['form'] = prior[-1].get(p['name'], 0) if prior else 0
        x, y = raw_xy(side, 18-p['xy'][0]*18, p['xy'][1]*32)
        p['x'], p['y'] = x, y
    salt = hashlib.sha256(Path(path).name.encode()).hexdigest()[:8]
    seen, ids, out = {}, Counter(), []
    for t in ticks:
        bodies = []
        for s_, x, y, cid, hp, mx, kind, addr in frames[t]:
            tower = cid == -1
            if tower:
                bid = f'T{s_}' + ('K' if abs(x-9000) < 1000 else 'L' if x < 9000 else 'R')
            else:
                # Address hashed per match only to join observations; never exported raw.
                k = hashlib.sha256((salt+str(addr)).encode()).hexdigest()[:12]
                last = seen.get(k)
                if last is None or t-last[1] > GAP_SPLIT or last[2] != cid:
                    ids[k] += 1
                    last = (f'{k}.{ids[k]}', t, cid)
                seen[k] = (last[0], t, cid)
                bid = last[0]
            bodies.append(dict(id=bid, side=s_, x=x, y=y, card_id=cid, hp=hp, max_hp=mx, kind=kind, tower=tower))
        out.append((t, bodies))
    # The reader shows some bodies twice (Hero Ice Wizard: a second row on the same point that keeps full hp all its
    # life). A track co-located with another same-card, same-max_hp track on >= 90% of its samples is a shadow if its hp is higher.
    at, n, hp = defaultdict(list), Counter(), defaultdict(int)
    for t, bodies in out:
        for bd in bodies:
            if not bd['tower']:
                at[t, bd['side'], bd['card_id'], bd['max_hp'], bd['x'], bd['y']].append(bd['id'])  # a Ram and its rider differ in max_hp
                n[bd['id']] += 1; hp[bd['id']] += bd['hp']
    both = Counter()
    for ids_ in at.values():
        for a in ids_:
            for b in ids_:
                if a != b:
                    both[a, b] += 1
    dup = {a if hp[a]/n[a] > hp[b]/n[b] or (hp[a]/n[a] == hp[b]/n[b] and a > b) else b
           for (a, b), k in both.items() if k >= .9*min(n[a], n[b])}
    out = [(t, [bd for bd in bodies if bd['id'] not in dup]) for t, bodies in out]
    return dict(match=Path(path).stem, side=side, frames=out, plays=plays, shots=shots,
                abilities=[a for a in abilities if a['confirmed']]), None


def tracks(frames):
    tr = {}
    for t, bodies in frames:
        for b in bodies:
            if b['tower']:
                continue
            r = tr.get(b['id'])
            if r is None:
                tr[b['id']] = r = dict(id=b['id'], side=b['side'], card_id=b['card_id'], first=t, x=b['x'], y=b['y'],
                                       max_hp=b['max_hp'], active=None, traj=[])
            r['last'] = t
            r['traj'].append((t, b['x'], b['y']))
            if r['active'] is None and b['kind'] in (13, 15):
                r['active'] = t
    return tr


def form_of(cid, c):
    return 2 if cid in (c.get('hero_form_id'), 203000023) else int(cid == c.get('evolution_form_id'))


def deployments(m, catalog):
    """Live deployments: new body groups (children of a living/just-dead same-card body, or role-children by max_hp,
    are the SIM's job, not plays), own confirmed spells, own Hero IW presses."""
    tr = sorted(tracks(m['frames']).values(), key=lambda r: (r['first'], r['id']))
    t_start = m['frames'][0][0]
    top = defaultdict(int)
    for r in tr:
        top[r['side'], r['card_id']] = max(top[r['side'], r['card_id']], r['max_hp'])
    groups = []
    for r in tr:
        if r['first'] == t_start or catalog.get(r['card_id']) is None:
            continue
        def at(q, t):           # q's last sampled point at or before t
            return max((p for p in q['traj'] if p[0] <= t), default=q['traj'][0])
        near_parent = any(q['side'] == r['side'] and q['card_id'] == r['card_id'] and q['first'] < r['first'] - 4
                          and q['first'] <= r['first'] <= q['last'] + 15
                          and math.hypot(at(q, r['first'])[1]-r['x'], at(q, r['first'])[2]-r['y']) < 3000 for q in tr)
        if near_parent or r['max_hp'] < .45*top[r['side'], r['card_id']]:
            continue
        g = next((g for g in groups if g['side'] == r['side'] and g['card_id'] == r['card_id']
                  and r['first']-g['tick'] <= 6 and math.hypot(g['x']-r['x'], g['y']-r['y']) < 4000), None)
        if g:
            g['members'].append(r); n = len(g['members'])
            g['x'] += (r['x']-g['x'])/n; g['y'] += (r['y']-g['y'])/n
        else:
            groups.append(dict(side=r['side'], card_id=r['card_id'], tick=r['first'], x=r['x'], y=r['y'], members=[r]))
    out, used, delays = [], set(), []
    ticks = [t for t, _ in m['frames']]
    for g in groups:
        c = catalog[g['card_id']]
        # A play's unit is created on the tick after the play; the live unit was created somewhere in (prev frame, first
        # seen]: play so that the SIM's unit is born mid-gap.
        prev = ticks[bisect_left(ticks, g['tick'])-1]
        tick = (prev + 1 + g['tick'])//2 - 1
        ev = dict(kind='play', side=g['side'], name=c['display_name'], form=form_of(g['card_id'], c), tick=tick,
                  x=round(g['x']), y=round(g['y']), n=len(g['members']), source='first_seen',
                  spell_spawned=c.get('type') == 'spell')
        if g['side'] == m['side']:
            cand = [i for i, p in enumerate(m['plays']) if i not in used and p['name'] == ev['name']
                    and 0 <= g['tick']-p['tick'] <= 80]
            if cand:
                i = cand[-1]; used.add(i); p = m['plays'][i]
                ev.update(x=p['x'], y=p['y'], source='own_tap', tap=p['tick']); delays.append(tick-p['tick'])
        out.append(ev)
    delay = statistics.median(delays) if delays else 23
    for i, p in enumerate(m['plays']):
        c = next((c for c in catalog.values() if c['display_name'] == p['name']), None)
        if i in used or not c or c.get('type') != 'spell':
            continue
        out.append(dict(kind='play', side=m['side'], name=p['name'], form=p['form'], tick=round(p['tick']+delay),
                        x=p['x'], y=p['y'], n=0, source='own_spell_tap+delay', tap=p['tick'], spell_spawned=False))
    for a in m['abilities']:
        out.append(dict(kind='ability', side=m['side'], name='IceWizard', tick=round(a['tick']+delay), source='own_press'))
    return sorted(out, key=lambda e: (e['tick'], e['side'], e['name'])), delay


def cut(m, events, window):
    """One fight per deployment: start = the last frame strictly before it; length `window` ticks."""
    ticks = [t for t, _ in m['frames']]
    tr = tracks(m['frames'])
    fights = []
    for k, ev in enumerate(events):
        if ev['kind'] != 'play':
            continue
        i = bisect_left(ticks, ev['tick']) - 1
        # A body still deploying at the start frame cannot be set up mid-deploy: start before it was born instead.
        for _ in range(4):
            born = [tr[b['id']]['first'] for b in m['frames'][max(i, 0)][1]
                    if not b['tower'] and b['kind'] in (12, 14) and tr[b['id']]['first'] > ticks[max(i, 0)]-80]
            if not born or i < 0:
                break
            i = bisect_left(ticks, min(born)) - 1
        if i < 0:
            continue
        t0 = ticks[i]; t1 = t0 + window
        if t1 > ticks[-1]:
            continue
        fights.append(dict(anchor=k, t0=t0, t1=t1, frame0=i,
                           events=[j for j, e in enumerate(events) if t0 <= e['tick'] <= t1]))
    return fights


# ---------------------------------------------------------------- engine side

class Engine:
    def __init__(self):
        if os.environ.get('PARITY_SIM_PATH'):
            sys.path.insert(0, os.environ['PARITY_SIM_PATH'])
            self.stamp = dict(runtime='PARITY_SIM_PATH', path=os.environ['PARITY_SIM_PATH'])
        else:
            from pipeline.royale_runtime import activate
            self.stamp = activate()
        import royalesim as sim
        from importlib.metadata import version
        try:
            self.stamp['royalesim'] = version('royalesim')
        except Exception:
            self.stamp['royalesim'] = None
        if os.environ.get('ROYALE_RUNTIME') == '20261016-linux' and self.stamp['royalesim'] != '0.1.35':
            raise RuntimeError('ROYALE_RUNTIME=20261016-linux must be royalesim 0.1.35, got ' + str(self.stamp['royalesim']))
        self.sim = sim
        self.b = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides={'cards.CARD_TABLE': json.dumps(CARD_TABLE)})
        self.cat = [dict(zip(sim.CATALOGUE_FIELDS, r)) for r in json.loads(self.b.catalogue_json())]
        self.ids = {c['name']: i for i, c in enumerate(self.cat)}
        self.F = list(sim.ENTITY_FIELDS)
        self.k_order = [[p[0] for p in team] for team in self.b.tower_positions()]   # x subtiles per k
        self.grid = self.b.passable_half_cells()                                       # [hy][hx], 500 millitiles
        self._tower = {}
        self._form = {}
        self._proxy, self._own_unit = {}, None

    def passable(self, x, y):
        hx, hy = int(x//500), int(y//500)
        return 0 <= hy < len(self.grid) and 0 <= hx < len(self.grid[0]) and bool(self.grid[hy][hx])

    def nearest_passable(self, x, y, reach=2):
        hx, hy = int(x//500), int(y//500)
        cells = [(math.hypot(dx, dy), hx+dx, hy+dy) for dx in range(-reach, reach+1) for dy in range(-reach, reach+1)]
        best = min((c for c in cells if 0 <= c[2] < len(self.grid) and 0 <= c[1] < len(self.grid[0]) and self.grid[c[2]][c[1]]),
                   default=None)
        return (best[1]*500+250, best[2]*500+250) if best else None

    def level(self, name, max_hp):
        """Card level whose own unit has exactly this max_hp; None if no level matches."""
        cid = self.ids.get(name)
        if cid is None:
            return None
        for lv in range(16, 0, -1):
            try:
                rows = self.b.unit_hitpoints(cid, lv)
            except ValueError:
                continue
            if rows and rows[0][2] == max_hp:
                return lv
        return None

    def form_record(self, name, form, level):
        """(engine record index, hero_units template) of `name` played in `form`; probed once by a real play."""
        key = (name, form, level)
        if key not in self._form:
            from scratchpad.gauntlet.L74.parity.mechanics import load_edited
            b = self.b
            b.reset(1, [[self.ids['Knight']], [self.ids[name]]], 0, 200, None, None, [], forms=[[0], [form]],
                    levels=[[16], [level]], tower_levels=[15, 15])
            sv = json.loads(b.save()); after = json.loads(json.dumps(sv))
            for ev in after['players'][1]['evo']:
                ev['plays'] = ev['cycles']
            if after != sv:
                load_edited(b, sv, after)
            n0 = len(json.loads(b.save())['ents']['card'])
            r = b.step([(1, 0, 9000*18, 22000*18)], 0)[0]
            b.step([], 1)                  # the play's unit is created on the next tick
            ents = json.loads(b.save())
            if self.sim.DEPLOY_REASONS[r[1]] != 'OK' or len(ents['ents']['card']) <= n0:
                self._form[key] = None
            else:
                hero = [h for h in ents['hero_units'] if h['id']['index'] == n0]
                self._form[key] = (ents['ents']['card'][n0], hero[0] if hero else None)
        return self._form[key]

    def child_proxy(self, parent, max_hp):
        """(card, level) whose own unit is the unit `parent` makes with this max_hp (Witch's Skeleton -> Skeletons)."""
        key = (parent, max_hp)
        if key in self._proxy:
            return self._proxy[key]
        if self._own_unit is None:
            self._own_unit = defaultdict(list)
            for name, cid in self.ids.items():
                for lv in (11, 13, 9, 14, 15, 16):
                    try:
                        rows = self.b.unit_hitpoints(cid, lv)
                    except ValueError:
                        continue
                    if rows:
                        self._own_unit[rows[0][1]].append(name)
                    break
        unit = None
        for lv in range(16, 0, -1):
            try:
                rows = self.b.unit_hitpoints(self.ids[parent], lv)
            except (ValueError, KeyError):
                continue
            hit = next(((role, u) for role, u, hp in rows[1:] if hp == max_hp), None)
            if hit:
                if hit[0] == 'second_summon':      # made by the parent's own setup spawn (a Ram Rider's rider)
                    self._proxy[key] = ('__parent__', None)
                    return self._proxy[key]
                unit = hit[1]
                break
        out = None
        for card in self._own_unit.get(unit, []) if unit else []:
            lv = self.level(card, max_hp)
            if lv:
                out = (card, lv); break
        self._proxy[key] = out
        return out

    def tower_level(self, king, princess):
        for lv in range(16, 0, -1):
            if lv not in self._tower:
                try:
                    self.b.reset(1, [[0], [0]], 0, 200, None, None, [], tower_levels=[lv, lv])
                    p = json.loads(self.b.state_json())['players'][0]
                    self._tower[lv] = tuple(p['tower_max_hp'])
                except ValueError:
                    self._tower[lv] = None
            if self._tower[lv] and self._tower[lv][0] == king and self._tower[lv][1] == princess:
                return lv
        return None

    def bodies(self, catalog_by_name):
        st = json.loads(self.b.state_json())
        out = []
        for row in st['entities']:
            e = dict(zip(self.F, row))
            if e['card_id'] == -1:
                x = e['x']//18
                out.append(dict(id=f"T{e['team']}" + ('K' if abs(x-9000) < 1000 else 'L' if x < 9000 else 'R'),
                                side=e['team'], x=x, y=e['y']//18, hp=e['hp'], max_hp=e['max_hp'], tower=True))
                continue
            name = self.cat[e['card_id']]['name']
            c = catalog_by_name.get(name, {})
            form = 2 if e['status_flags'] & 16 else 1 if e['status_flags'] & 8 else 0
            out.append(dict(id=f"s{e['uid']}", side=e['team'], x=e['x']/18, y=e['y']/18, hp=e['hp'], max_hp=e['max_hp'],
                            name=name, form=form, deploying=e['deploy_ticks'] > 0, tower=False,
                            card_id=c.get('card_id')))
        return st, out


def run_fight(eng, m, events, fight, catalog, by_name, levels, tower_levels, top):
    sim, b = eng.sim, eng.b
    t0, t1 = fight['t0'], fight['t1']
    frames = [fr for fr in m['frames'] if t0 <= fr[0] <= t1]
    start = frames[0][1]
    flags = Counter()
    decks, forms, lv = [[], []], [[], []], [[], []]

    def need(side, name, form, level=None):
        if name not in eng.ids:
            flags['card_not_in_sim:'+name] += 1
            return False
        if name not in decks[side]:
            decks[side].append(name); forms[side].append(0)
            lv[side].append(levels.get((side, name)) or level or levels.get((side, '*')) or 15)
        i = decks[side].index(name)
        forms[side][i] = max(forms[side][i], form)
        return True

    spawns, setup = [], []

    def add(bd, name):
        x, y = bd['x'], bd['y']
        if not eng.cat[eng.ids[name]]['flying'] and not eng.passable(x, y):
            # A live ground body inside the SIM's impassable cells (river band, tower footprint): nearest passable
            # half-cell centre within 1 tile, else the body is refused.
            near = eng.nearest_passable(x, y)
            if near is None:
                flags['setup_spawn_refused'] += 1; return
            x, y = near; flags['setup_snapped'] += 1
        spawns.append((bd['side'], eng.ids[name], round(x*18), round(y*18), max(1, bd['hp'])))
        setup.append(dict(id=bd['id'], side=bd['side'], x=x, y=y, card_id=bd['card_id'], proxy=name != catalog[bd['card_id']]['display_name']))
    for bd in start:
        if bd['tower']:
            continue
        c = catalog.get(bd['card_id'])
        if c is None:
            flags['setup_unmapped_body'] += 1; continue
        form = form_of(bd['card_id'], c)
        if eng.level(c['display_name'], bd['max_hp']) is None:
            # Not the card's own unit at any level (max_hp says so): a child body (a Witch's Skeleton, a cube, a Golemite) is no card. Set it up as the card whose own unit is
            # the same unit at the same max_hp, if one exists (Witch Skeleton -> Skeletons); else the fight is not clean.
            proxy = eng.child_proxy(c['display_name'], bd['max_hp'])
            if proxy and proxy[0] == '__parent__':
                flags['setup_child_by_parent'] += 1; continue
            if proxy is None or not need(bd['side'], proxy[0], 0, proxy[1]):
                flags['setup_child_skipped'] += 1; continue
            flags['setup_child_as_card'] += 1
            add(bd, proxy[0])
            continue
        if bd['kind'] in (12, 14):
            flags['setup_was_deploying'] += 1
        if need(bd['side'], c['display_name'], form):
            add(bd, c['display_name'])
    evs = [events[j] for j in fight['events']]
    # Opponent champion / hero buttons are not logged: a fight with one on the board cannot replay its presses.
    heroes = set()
    for _, bodies in frames:
        for bd in bodies:
            c = catalog.get(bd['card_id'])
            if c and not bd['tower'] and bd['side'] != m['side'] and (form_of(bd['card_id'], c) == 2 or
                                                                   eng.cat[eng.ids[c['display_name']]].get('champion') if c['display_name'] in eng.ids else False):
                heroes.add(c['display_name'])
    for h in heroes:
        flags['opp_ability_unobserved:'+h] += 1
    # Opponent spells are not in the frames; a decision-tick projectile sighting marks the fight (Zap, Lightning,
    # Earthquake, Poison and Freeze are not projectiles and stay invisible).
    for t, s_, cid in m['shots']:
        c = catalog.get(cid)
        if s_ != m['side'] and c and c.get('type') == 'spell' and t0-30 <= t <= t1:
            flags['opp_spell_seen:'+c['display_name']] += 1
    for e in events:           # an effect already running at t0 is not public state: the fight cannot start from it
        if e['source'] == 'own_spell_tap+delay' and t0-60 <= e['tick'] < t0:
            flags['spell_in_flight_at_start'] += 1
        if e['kind'] == 'ability' and t0-100 <= e['tick'] < t0:
            flags['ability_active_at_start'] += 1
    for e in evs:
        if e['kind'] == 'play' and not need(e['side'], e['name'], e['form']):
            flags['event_card_missing'] += 1
        if e.get('spell_spawned'):
            flags['spell_spawned_units_timing_unknown'] += 1
    if any(e['kind'] == 'ability' for e in evs):
        need(m['side'], 'IceWizard', 2)
    for s_ in (0, 1):
        if not decks[s_]:
            need(s_, 'Knight', 0)
    tower_hp = [[0, 0, 0], [0, 0, 0]]
    king_awake = [False, False]
    for bd in start:
        if bd['tower']:
            k = 0 if bd['id'][-1] == 'K' else (1 if (bd['x'] < 9000) == (eng.k_order[bd['side']][1] < 162000) else 2)
            tower_hp[bd['side']][k] = max(0, bd['hp'])
            if k == 0 and bd['kind'] == 13:
                king_awake[bd['side']] = True
    reset = lambda sp: b.reset(1, [[eng.ids[n] for n in decks[0]], [eng.ids[n] for n in decks[1]]], 0, t0,
                               [10000, 10000], tower_hp, sp, forms=forms, levels=lv, tower_levels=tower_levels)
    try:
        try:
            reset(spawns)
        except ValueError:     # drop only the refused bodies (water, out of arena), not the fight
            ok = []
            for sp, bd in zip(spawns, setup):
                try:
                    reset([sp]); ok.append((sp, bd))
                except ValueError:
                    flags['setup_spawn_refused'] += 1
            spawns, setup = [k[0] for k in ok], [k[1] for k in ok]
            reset(spawns)
    except ValueError as e:
        return dict(error='reset:'+str(e)[:200])
    from scratchpad.gauntlet.L74.parity.mechanics import load_edited
    sv = json.loads(b.save()); pub = json.loads(b.state_json())
    internal = {t: dict(zip(pub['players'][t]['deck'], sv['players'][t]['hand']+sv['players'][t]['queue'])) for t in (0, 1)}
    if any(king_awake) and sv.get('king_active') != king_awake:
        after = json.loads(json.dumps(sv)); after['king_active'] = king_awake
        try:
            load_edited(b, sv, after)
        except Exception:
            flags['king_awake_not_set'] += 1
    # Setup spawns are base cards. An evo/hero body (same stats; the form lives in the engine record) gets its form's
    # record swapped in, plus a fresh hero_units entry for a hero (its button state before t0 is not public).
    formed = [(bd, form_of(bd['card_id'], catalog[bd['card_id']])) for bd in setup if not bd['proxy']]
    formed = [(bd, f) for bd, f in formed if f]
    if formed:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        for bd, f in formed:
            name = catalog[bd['card_id']]['display_name']
            rec = eng.form_record(name, f, lv[bd['side']][decks[bd['side']].index(name)])
            i = next((i for i in range(len(E['card'])) if E['alive'][i] and E['team'][i] == ('Blue', 'Red')[bd['side']]
                      and E['pos'][i] == {'x': round(bd['x']*18), 'y': round(bd['y']*18)} and E['kind'][i] in ('Troop', 'Building')), None)
            if rec is None or i is None:
                flags['setup_form_not_set'] += 1; continue
            if E['source'][i] == E['card'][i]:
                E['source'][i] = rec[0]
            E['card'][i] = rec[0]
            if rec[1] is not None:
                after['hero_units'].append(dict(rec[1], id={'index': i, 'generation': E['generation'][i]}))
            flags['setup_form_swapped'] += 1
        try:
            load_edited(b, before, after)
        except Exception:
            flags['setup_form_not_set'] += len(formed)

    # Target state is not public, and a setup spawn starts with none, so it may pick a nearer troop where the live unit
    # kept shooting a tower (a locked X-Bow). Lock a setup body onto an enemy tower when the body stood still over the
    # last second, the tower is in reach (14 tiles centre to centre for a building, 7 for a troop) and that tower lost hp in that second.
    locks = tower_locks(m, fight, setup, catalog)
    if locks:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        team = ('Blue', 'Red')
        for bd, (tside, tx, ty) in locks:
            i = next((i for i in range(len(E['card'])) if E['alive'][i] and E['team'][i] == team[bd['side']]
                      and E['pos'][i] == {'x': round(bd['x']*18), 'y': round(bd['y']*18)} and E['kind'][i] in ('Troop', 'Building')), None)
            t = next((i for i in range(len(E['card'])) if E['alive'][i] and E['team'][i] == team[tside]
                      and E['kind'][i] in ('KingTower', 'PrincessTower') and abs(E['pos'][i]['x']-tx*18) < 18000
                      and abs(E['pos'][i]['y']-ty*18) < 18000), None)
            if i is None or t is None:
                continue
            E['target'][i] = {'index': t, 'generation': E['generation'][t]}; E['target_locked'][i] = True
            flags['setup_target_tower'] += 1
        try:
            load_edited(b, before, after)
        except Exception:
            flags['setup_target_not_set'] += 1

    def play(e):
        before = json.loads(b.save()); after = json.loads(json.dumps(before))
        p = after['players'][e['side']]
        if e['kind'] == 'play':
            ic = internal[e['side']][eng.ids[e['name']]]
            rest = [c for c in p['hand']+p['queue'] if c not in (ic, NO_CARD)]
            p['hand'] = [ic]+rest[:3]; p['queue'] = rest[3:]
            for ev in p.get('evo', []):
                if ev['card'] == ic:
                    ev['plays'] = ev['cycles'] if e['form'] == 1 else 0
        p['mana'] = after['calib']['max_mana']*after['mana_unit']; p['refill_ms'] = 0
        if after != before:
            load_edited(b, before, after)
        slot = 0 if e['kind'] == 'play' else sim.HAND_SIZE
        r = b.step([(e['side'], slot, round(e['x']*18) if 'x' in e else 0, round(e['y']*18) if 'y' in e else 0)], 0)[0]
        return sim.DEPLOY_REASONS[r[1]]

    rows = []                  # (tick, live bodies, sim bodies)
    cursor = 0; refused = Counter()
    for tick, live in frames:
        while cursor < len(evs) and evs[cursor]['tick'] <= tick:
            e = evs[cursor]; cursor += 1
            now = json.loads(b.state_json())['tick']
            if now < e['tick']:
                b.step([], e['tick']-now)
            reason = play(e)
            if reason != 'OK':
                refused[reason] += 1
        st = json.loads(b.state_json())
        if st['tick'] < tick:
            b.step([], tick-st['tick'])
        st, simb = eng.bodies(by_name)
        if st['tick'] != tick:
            flags['sim_game_over'] += 1
            break
        rows.append((tick, live, simb))
    for k, v in refused.items():
        flags['play_refused:'+k] += v
    return measure(rows, setup, flags, catalog, eng.stamp)


def tower_locks(m, fight, setup, catalog, look=20):
    """[(setup body, (tower side, x, y))] for setup bodies that were shooting an enemy tower at t0 (see run_fight)."""
    t0 = fight['t0']; i0 = fight['frame0']
    j = next((j for j in range(i0, -1, -1) if m['frames'][j][0] <= t0-look), None)
    if j is None:
        return []
    then = {b['id']: b for b in m['frames'][j][1]}
    now = {b['id']: b for b in m['frames'][i0][1]}
    hit = [b for k, b in now.items() if b['tower'] and k in then and b['hp'] < then[k]['hp']]
    out = []
    for bd in setup:
        a, z = now.get(bd['id']), then.get(bd['id'])
        if bd.get('proxy') or a is None or z is None or math.hypot(a['x']-z['x'], a['y']-z['y']) > 100 or a['kind'] not in (13, 15):
            continue
        reach = 14000 if catalog[a['card_id']].get('type') == 'building' else 7000   # X-Bow: 11.5 range + tower size
        cands = sorted((math.hypot(t['x']-a['x'], t['y']-a['y']), t['side'], t['x'], t['y']) for t in hit if t['side'] != a['side'])
        if cands and cands[0][0] <= reach:
            out.append((bd, cands[0][1:]))
    return out


def pair_frame(pairs, live, simb, catalog):
    """Grow live-id -> sim-id pairing: same side, display name, form and max_hp within 40%, nearest within 2.5 tiles."""
    taken = set(pairs.values())
    cand = []
    for a in live:
        if a['tower'] or pairs.get(a['id']) is not None:
            continue
        c = catalog.get(a['card_id'])
        if c is None:
            continue
        for s_ in simb:
            if s_['tower'] or s_['id'] in taken or s_['side'] != a['side'] or s_.get('name') != c['display_name']:
                continue
            if s_['form'] != form_of(a['card_id'], c) or not .6 <= s_['max_hp']/max(1, a['max_hp']) <= 1.67:
                continue
            d = math.hypot(a['x']-s_['x'], a['y']-s_['y'])
            if d < 2500:
                cand.append((d, a['id'], s_['id']))
    for d, a, s_ in sorted(cand):
        if pairs.get(a) is None and s_ not in taken:
            pairs[a] = s_; taken.add(s_)


def measure(rows, setup, flags, catalog, stamp):
    if not rows:
        return dict(flags=dict(flags), error='no_rows')
    setup_ids = {bd['id'] for bd in setup}
    pairs = {i: None for i in setup_ids}
    # setup pairing: each setup spawn sits on its live point at t0 (spawn order is canonical, not list order). By point,
    # not name, so a child set up as a proxy card (a Witch's Skeleton as a Skeletons body) pairs too.
    _, live0, sim0 = rows[0]
    free = [s for s in sim0 if not s['tower']]
    for a in setup:
        if free:
            d, s = min((math.hypot(a['x']-s['x'], a['y']-s['y']), s['id']) for s in free if s['side'] == a['side'])                 if any(s['side'] == a['side'] for s in free) else (1e9, None)
            if d < 60:
                pairs[a['id']] = s; free = [f for f in free if f['id'] != s]
    life = {}                  # id -> [first, last, first active tick, card_id, side]  (live ids and sim ids)
    err = defaultdict(lambda: ([], []))
    signed = {}                # live id -> sim hp - live hp at the last common frame (+ = the SIM dealt less damage)
    pair_tick = {}             # live id -> first tick it was compared (its pairing tick)
    for tick, live, simb in rows:
        pair_frame(pairs, live, simb, catalog)
        S = {s['id']: s for s in simb}
        for a in live + simb:
            if a['tower']:
                continue
            r = life.setdefault(a['id'], [tick, tick, None, a.get('card_id'), a['side']])
            r[1] = tick
            active = (a['kind'] in (13, 15)) if 'kind' in a else not a['deploying']
            if r[2] is None and active:
                r[2] = tick
        for a in live:
            sid = pairs.get(a['id'])
            if not a['tower'] and sid in S:
                s = S[sid]
                err[a['id']][0].append(math.hypot(a['x']-s['x'], a['y']-s['y'])); err[a['id']][1].append(abs(a['hp']-s['hp']))
                signed[a['id']] = s['hp'] - a['hp']
                pair_tick.setdefault(a['id'], tick)
    t0, t_end = rows[0][0], rows[-1][0]
    dead = lambda r: r[1] if r[1] < t_end else None             # None = alive at window end (censored)
    deploy = lambda r: (r[2]-r[0]) if r[2] is not None and r[0] > t0 else None
    bodies = []
    for lid, r in life.items():
        if lid.startswith('s'):
            continue
        c = catalog.get(r[3], {}); sid = pairs.get(lid); s = life.get(sid)
        pos, hp = err[lid]
        bodies.append(dict(name=c.get('display_name', str(r[3])), form=form_of(r[3], c) if c else 0, side=r[4],
                           paired=s is not None, setup=lid in setup_ids, born=r[0],
                           live_death=dead(r), sim_death=dead(s) if s else None,
                           frames=len(pos), quarter=sum(p <= QUARTER for p in pos),
                           pos_med=statistics.median(pos) if pos else None, pos_end=pos[-1] if pos else None,
                           pos_first=pos[0] if pos else None, paired_at=pair_tick.get(lid),
                           hp_med=statistics.median(hp) if hp else None, hp_signed_end=signed.get(lid),
                           deploy_live=deploy(r), deploy_sim=deploy(s) if s else None))
    paired_sim = set(pairs.values())
    sim_only = [i for i in life if i.startswith('s') and i not in paired_sim]
    tower0 = {b['id']: b['hp'] for b in rows[0][1] if b['tower']}
    stower0 = {b['id']: b['hp'] for b in rows[0][2] if b['tower']}
    tl = {b['id']: b['hp'] for b in rows[-1][1] if b['tower']}
    ts = {b['id']: b['hp'] for b in rows[-1][2] if b['tower']}
    towers = {k: dict(live=tower0[k]-max(0, tl.get(k, 0)), sim=stower0.get(k, 0)-max(0, ts.get(k, 0))) for k in tower0}
    return dict(t_end=t_end, flags=dict(flags), bodies=bodies, sim_only=len(sim_only), towers=towers, stamp=stamp)


def run_match(path, window, out_dir):
    out = Path(out_dir)/'matches'/(Path(path).stem+'.json')
    if out.exists():
        return json.loads(out.read_text())['summary']
    t_start = time.monotonic()
    catalog, by_name = load_catalog()
    m, reason = read_match(path)
    if m is None:
        res = dict(match=Path(path).stem, skipped=reason)
        out.write_text(json.dumps(dict(summary=res)))
        return res
    events, delay = deployments(m, catalog)
    fights = cut(m, events, window)
    eng = Engine()
    # levels from the bodies' max_hp: per (side, card); '*' = the side's modal level for cards never seen as a body
    levels, seen = {}, Counter()
    for t, bodies in m['frames']:
        for bd in bodies:
            c = catalog.get(bd['card_id'])
            if bd['tower'] or c is None or (bd['side'], c['display_name']) in levels or form_of(bd['card_id'], c) == 1:
                continue
            lv = eng.level(c['display_name'], bd['max_hp'])
            if lv:
                levels[bd['side'], c['display_name']] = lv; seen[bd['side'], lv] += 1
    for s_ in (0, 1):
        mode = [lv for (ss, lv), _ in seen.most_common() if ss == s_]
        levels[s_, '*'] = mode[0] if mode else 15
    t0b = m['frames'][0][1]
    tw = []
    for s_ in (0, 1):
        k = next((b['max_hp'] for b in t0b if b['tower'] and b['side'] == s_ and b['id'].endswith('K')), None)
        p = next((b['max_hp'] for b in t0b if b['tower'] and b['side'] == s_ and not b['id'].endswith('K')), None)
        tw.append(eng.tower_level(k, p) or levels[s_, '*'])
    top = defaultdict(int)
    for r in tracks(m['frames']).values():
        top[r['side'], r['card_id']] = max(top[r['side'], r['card_id']], r['max_hp'])
    cap = int(os.environ.get('PARITY_MAX_FIGHTS', 0))
    if cap and len(fights) > cap:      # prototype: spread the cap over the match
        fights = fights[::len(fights)//cap][:cap]
    results = []
    for f in fights:
        anchor = events[f['anchor']]
        try:
            r = run_fight(eng, m, events, f, catalog, by_name, levels, tw, top)
        except Exception as e:      # one fight's engine refusal must not drop the match
            r = dict(error=type(e).__name__+':'+str(e)[:200])
        r.update(t0=f['t0'], t1=f['t1'], anchor={k: anchor[k] for k in ('side', 'name', 'form', 'tick', 'source')},
                 own=anchor['side'] == m['side'], obs=m['side'],
                 events=[{k: events[j].get(k) for k in ('kind', 'side', 'name', 'form', 'tick', 'source')} for j in f['events']])
        results.append(r)
    # Geometry probe: live ground-body samples inside cells the SIM calls impassable (river band, footprints).
    blocked, ground = Counter(), Counter()
    for t, bodies in m['frames'][::5]:
        for bd in bodies:
            c = catalog.get(bd['card_id'])
            if bd['tower'] or c is None or c['display_name'] not in eng.ids or eng.cat[eng.ids[c['display_name']]]['flying']                     or bd['max_hp'] < .45*top[bd['side'], bd['card_id']] or c.get('type') != 'troop':
                continue
            ground[c['display_name']] += 1
            if not eng.passable(bd['x'], bd['y']):
                blocked[c['display_name']] += 1
    summary = dict(match=m['match'], side=m['side'], fights=len(results), errors=sum('error' in r for r in results),
                   ground_samples=dict(ground), ground_in_impassable=dict(blocked),
                   spell_delay_ticks=delay, levels={f'{s}:{n}': v for (s, n), v in levels.items()}, tower_levels=tw,
                   seconds=round(time.monotonic()-t_start, 1), stamp=eng.stamp)
    out.write_text(json.dumps(dict(summary=summary, fights=results), allow_nan=False))
    return summary


# ---------------------------------------------------------------- scoreboard

def fight_verdict(r, tower_tol):
    """Outcome agreement = the fight's focus bodies end alive/dead the same, the first body to die is the same, and each
    tower's damage is within max(tol, 15%). Focus = the anchor's own bodies; for a spell anchor, the enemy bodies on the
    board when it was cast."""
    a = r['anchor']
    bodies = [b for b in r['bodies'] if b['paired']]
    if a['source'] == 'own_spell_tap+delay':
        focus = [b for b in bodies if b['setup'] and b['side'] != a['side']]
    else:
        focus = [b for b in bodies if b['name'] == a['name'] and b['side'] == a['side'] and not b['setup']
                 and abs(b['born'] - a['tick']) <= 12]
    focus = focus or bodies
    alive_agree = all((b['live_death'] is None) == (b['sim_death'] is None) for b in focus)
    tower_err = sum(abs(t['live']-t['sim']) for t in r['towers'].values())
    tower_agree = all(abs(t['live']-t['sim']) <= max(tower_tol, .15*abs(t['live'])) for t in r['towers'].values())
    dies = lambda key: sorted((b[key], b['name'], b['side']) for b in bodies if b[key] is not None)
    fl, fs = dies('live_death'), dies('sim_death')
    first_agree = (fl[0][1:] == fs[0][1:]) if fl and fs else (not fl and not fs)
    dt = [abs(b['live_death']-b['sim_death']) for b in focus if b['live_death'] is not None and b['sim_death'] is not None]
    unpaired = sum(not b['paired'] for b in r['bodies']) + r['sim_only']
    return dict(agree=alive_agree and tower_agree and first_agree, alive_agree=alive_agree, tower_agree=tower_agree,
                first_death_agree=first_agree, tower_err=tower_err, death_dt=dt, unpaired=unpaired,
                quarter=(sum(b['quarter'] for b in focus), sum(b['frames'] for b in focus)))


CLEAN_BLOCKERS = ('opp_spell_seen', 'opp_ability_unobserved', 'setup_child_skipped', 'setup_form_not_set', 'setup_was_deploying', 'spell_in_flight_at_start',
                  'ability_active_at_start', 'setup_unmapped_body', 'setup_spawn_refused', 'event_card_missing',
                  'spell_spawned_units_timing_unknown', 'card_not_in_sim', 'play_refused', 'sim_game_over')


HIDDEN_INFO = ('opp_spell_seen', 'opp_ability_unobserved')


def is_clean(r, mode='strict'):
    """strict: no blocker at all. core: hidden opponent actions allowed (spells, hero/champion buttons). all: any fight."""
    if mode == 'all':
        return True
    skip = HIDDEN_INFO if mode == 'core' else ()
    return not any(k.startswith(CLEAN_BLOCKERS) and not k.startswith(skip) for k in r['flags'])


def score(out_dir, tower_tol=150, worst=5, mode='strict'):
    files = sorted((Path(out_dir)/'matches').glob('*.json'))
    matches, fights, skipped = 0, [], Counter()
    for p in files:
        d = json.loads(p.read_text())
        if d['summary'].get('skipped'):
            skipped[d['summary']['skipped']] += 1; continue
        matches += 1
        for r in d['fights']:
            if 'error' in r:
                skipped['fight_error'] += 1; continue
            r['match'] = d['summary']['match']; r['verdict'] = fight_verdict(r, tower_tol)
            fights.append(r)
    clean = [r for r in fights if is_clean(r, mode)]
    groups = defaultdict(list)
    for r in clean:
        a = r['anchor']; label = ('own ' if r['own'] else 'opp ') + a['name'] + ('', ' evo', ' hero')[a['form']]
        groups['anchor', label].append(r)
        for other in {(b['name'], b['side']) for b in r['bodies'] if b['side'] != a['side']}:
            groups['interaction', f"{label} vs {other[0]}"].append(r)
    units = defaultdict(list)
    for r in clean:
        for b in r['bodies']:
            if b['paired']:
                units[('own ' if b['side'] == r['obs'] else 'opp ') + b['name'] + ('', ' evo', ' hero')[b['form']]].append((r, b))
    rows = []
    for (kind, label), rs in groups.items():
        v = [r['verdict'] for r in rs]
        mis = 1 - sum(x['agree'] for x in v)/len(v)
        terr = statistics.median(x['tower_err'] for x in v)
        dts = [d for x in v for d in x['death_dt']]
        q = (sum(x['quarter'][0] for x in v), sum(x['quarter'][1] for x in v))
        freq = len(rs)/max(1, matches)
        bad = sorted(rs, key=lambda r: (-r['verdict']['tower_err'] - 200*(not r['verdict']['alive_agree'])))[:worst]
        rows.append(dict(kind=kind, group=label, n=len(rs), per_match=round(freq, 3), outcome_agree=round(1-mis, 3),
                         alive_agree=round(sum(x['alive_agree'] for x in v)/len(v), 3),
                         first_death_agree=round(sum(x['first_death_agree'] for x in v)/len(v), 3),
                         tower_err_median=terr, tower_err_mean=round(statistics.fmean(x['tower_err'] for x in v), 1),
                         death_dt_median_s=statistics.median(dts)/20 if dts else None, death_n=len(dts),
                         quarter_tile=round(q[0]/q[1], 3) if q[1] else None,
                         unpaired_mean=round(statistics.fmean(x['unpaired'] for x in v), 2),
                         priority=any(w in PRIORITY for w in label.replace(' vs ', ' ').split()),
                         # impact: fights per match that the SIM decides differently, weighted up by tower-hp error
                         impact=round(freq*(mis + statistics.fmean(x['tower_err'] for x in v)/1000), 4),
                         worst=[dict(match=r['match'], t0=r['t0'], tower_err=r['verdict']['tower_err'],
                                     alive_agree=r['verdict']['alive_agree']) for r in bad]))
    unit_rows = []
    for label, items in units.items():
        bs = [b for _, b in items]
        dd = [abs(b['live_death']-b['sim_death']) for b in bs if b['live_death'] is not None and b['sim_death'] is not None]
        surv = sum((b['live_death'] is None) == (b['sim_death'] is None) for b in bs)/len(bs)
        q = (sum(b['quarter'] for b in bs), sum(b['frames'] for b in bs))
        dep = [b['deploy_sim']-b['deploy_live'] for b in bs if b['deploy_sim'] is not None and b['deploy_live'] is not None]
        sdd = [b['sim_death']-b['live_death'] for b in bs if b['live_death'] is not None and b['sim_death'] is not None]
        shp = [b['hp_signed_end'] for b in bs if b.get('hp_signed_end') is not None]
        live_only = sum(b['live_death'] is not None and b['sim_death'] is None for b in bs)
        sim_only = sum(b['live_death'] is None and b['sim_death'] is not None for b in bs)
        unit_rows.append(dict(unit=label, n=len(bs), survival_agree=round(surv, 3), dies_live_only=live_only,
                              dies_sim_only=sim_only, death_dt_median_s=statistics.median(dd)/20 if dd else None,
                              quarter_tile=round(q[0]/q[1], 3) if q[1] else None,
                              pos_median=statistics.median([b['pos_med'] for b in bs if b['pos_med'] is not None] or [0]),
                              hp_err_median=statistics.median([b['hp_med'] for b in bs if b['hp_med'] is not None] or [0]),
                              deploy_sim_minus_live_ticks=statistics.median(dep) if dep else None, deploy_n=len(dep),
                              death_sim_minus_live_s=statistics.median(sdd)/20 if sdd else None,
                              hp_sim_minus_live_end_mean=round(statistics.fmean(shp), 1) if shp else None))
    rows.sort(key=lambda r: -r['impact'])
    unit_rows.sort(key=lambda r: -r['n']*(1-r['survival_agree']))
    flags = Counter(k.split(':')[0] for r in fights for k in r['flags'])
    v = [r['verdict'] for r in clean]
    head = dict(matches=matches, skipped=dict(skipped), fights=len(fights), clean=len(clean), clean_mode=mode,
                clean_by_mode={k: sum(is_clean(r, k) for r in fights) for k in ('strict', 'core', 'all')},
                flag_counts=dict(flags),
                outcome_agree=round(sum(x['agree'] for x in v)/len(v), 3) if v else None,
                quarter_tile=round(sum(x['quarter'][0] for x in v)/max(1, sum(x['quarter'][1] for x in v)), 3),
                tower_tol=tower_tol, stamp=next((json.loads(p.read_text())['summary'].get('stamp') for p in files
                                                 if not json.loads(p.read_text())['summary'].get('skipped')), None))
    out = dict(head=head, groups=rows, units=unit_rows)
    Path(out_dir, f'scoreboard_{mode}.json').write_text(json.dumps(out, indent=1))
    Path(out_dir, f'SCOREBOARD_{mode}.txt').write_text(text(out))
    return out


def text(sb, top=25):
    h = sb['head']
    L = [f"fights {h['fights']} (clean[{h['clean_mode']}] {h['clean']}; by mode {h['clean_by_mode']}) in {h['matches']} matches; outcome agree {h['outcome_agree']}; "
         f"1/4-tile {h['quarter_tile']}; skipped {h['skipped']}; flags {h['flag_counts']}; stamp {h['stamp']}",
         '', 'GROUPS by impact (fights/match x (1-outcome agree + mean tower err/1000))',
         'kind | group | n | /match | agree | alive | 1st death | tower err med/mean | death dt s (n) | 1/4 tile | impact']
    for r in sb['groups'][:top]:
        L.append(f"{r['kind'][:5]} | {r['group']} | {r['n']} | {r['per_match']} | {r['outcome_agree']} | {r['alive_agree']} | "
                 f"{r['first_death_agree']} | {r['tower_err_median']}/{r['tower_err_mean']} | {r['death_dt_median_s']} ({r['death_n']}) | "
                 f"{r['quarter_tile']} | {r['impact']}{' *' if r['priority'] else ''}")
        L.append('      worst: ' + '; '.join(f"{w['match']}@{w['t0']} terr {w['tower_err']}" for w in r['worst'][:3]))
    L += ['', 'UNITS (paired bodies) by n x survival disagreement',
          'unit | n | survival agree | dies live only | dies sim only | death dt s (sim-live) | 1/4 tile | pos med | hp err med | hp sim-live at end | deploy sim-live ticks (n)']
    for u in sb['units'][:top]:
        L.append(f"{u['unit']} | {u['n']} | {u['survival_agree']} | {u['dies_live_only']} | {u['dies_sim_only']} | {u['death_dt_median_s']} "
                 f"({u['death_sim_minus_live_s']}) | {u['quarter_tile']} | {u['pos_median']:.0f} | {u['hp_err_median']:.0f} | "
                 f"{u['hp_sim_minus_live_end_mean']} | {u['deploy_sim_minus_live_ticks']} ({u['deploy_n']})")
    return '\n'.join(L)+'\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=['run', 'score'])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--live', type=Path, default=ps.LIVE)
    ap.add_argument('--files', default='live_play_2026101[5-9]_*.jsonl')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--stride', type=int, default=1, help='every Nth matching file (a spread prototype sample)')
    ap.add_argument('--max-fights', type=int, default=0, help='prototype: cap fights per match (0 = all)')
    ap.add_argument('--window', type=int, default=240, help='fight length, ticks (240 = 12 s)')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--clean', choices=['strict', 'core', 'all'], default='strict', help='score: which fights count (is_clean)')
    a = ap.parse_args()
    if a.mode == 'score':
        for mode in ('strict', 'core', 'all'):
            score(a.out, mode=mode)
        print(text(score(a.out, mode=a.clean))); return 0
    (a.out/'matches').mkdir(parents=True, exist_ok=True)
    paths = sorted(a.live.glob(a.files))[::a.stride]
    if a.limit:
        paths = paths[:a.limit]
    if a.max_fights:
        os.environ['PARITY_MAX_FIGHTS'] = str(a.max_fights)
    t = time.monotonic()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_match, str(p), a.window, str(a.out)): p for p in paths}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                s = f.result()
            except Exception as e:
                s = dict(match=futs[f].stem, crash=type(e).__name__+':'+str(e)[:200])
            print(f"{n}/{len(paths)} {s.get('match')} fights={s.get('fights')} err={s.get('errors')} "
                  f"skip={s.get('skipped')} crash={s.get('crash')} {time.monotonic()-t:.0f}s", flush=True)
    for mode in ('strict', 'core', 'all'):
        score(a.out, mode=mode)
    print(text(score(a.out, mode=a.clean)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
