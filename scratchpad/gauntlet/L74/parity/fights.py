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
  python fights.py buffs --out FILE         # phase-2 buff rows of the local captures, for PARITY_BUFFS=FILE (a pod)
  python fights.py attacks --out FILE       # phase-3 attack rows of the local captures, for PARITY_ATTACKS=FILE (a pod)
  run --infer target,phase: opt-in attack target / phase inference at setup (infer_attacks)
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
TOWER_SLOTS = ((9000, 3000), (3500, 6500), (14500, 6500), (9000, 29000), (3500, 25500), (14500, 25500))
# Live taps made short of elixir register only once the elixir is there (diag1016: all 215 own troop plays that came
# 12+ ticks after the match's median tap->spawn delay were short at the tap, vs 4.9% of on-time ones; the extra delay
# is the deficit x 45.5 ticks per elixir at single elixir, n 178; 22.9 at double, n 126). Spells and ability presses
# have no body to time them by, so their tick adds this wait.
TICKS_PER_ELIXIR = 45.5
HERO_IW_ABILITY_COST = 2           # card table hero_forms IceWizard_hero ability.mana_cost
# Tolerant card-level scoring (owner goal 10-16; CEILING.md). A card's bodies agree when they end alive/dead the same and
# deaths are within DEATH_TOL ticks (0.5 s); a swarm may miss floor(SWARM_SLACK x n) bodies. Its tower damage agrees
# within max(TOWER_FLOOR, TOWER_REL x the larger side). TOWER_FLOOR ~ one X-Bow bolt (98) and above one Log crown hit (51).
DEATH_TOL, SWARM_SLACK, TOWER_FLOOR, TOWER_REL = 10, .1, 100, .1
SPELL_WINDOW = 60                  # ticks after a cast in which a drop/death counts as the spell's hit
DIGGERS = {'Miner', 'GoblinDrill'}  # tunnel in: seen active on their way, deploying where they surface (Knight etc. can show
                                   # 13/15 -> 12/14 too: 31 of 531 Knights, so the rule is by card)
TOWER_RADIUS = 1400                # millitiles, king (princess 1000): attribution slack, not a law
FORMATION_SPAN = 15000             # millitiles: the widest one-play formation (Royal Recruits: 6 bodies 2.8 tiles apart)
PRIORITY = {'Xbow', 'Tesla', 'Tornado', 'Log', 'IceWizard', 'Rocket', 'Knight', 'Skeletons', 'MegaKnight', 'Golem',
            'ElixirGolem', 'SkeletonBalloon', 'Barbarians', 'Firecracker', 'MinionHorde', 'Giant'}
# Frame logs with the reader's per-body state / projectile / effect keys (--log-frames from 10-16, READER_VALIDATION_1016.md)
# are "ext" logs; everything below is used only for them, so older logs replay exactly as before.
SPELL_SOURCES = ('own_spell_tap+delay', 'spell_seen')
P2_DIR = ROOT/'scratchpad/gauntlet/L70/reader/re_phase2/validation'    # phase-2 captures: run.json names its frame log
P3_DIR = ROOT/'scratchpad/gauntlet/L70/reader/re_phase3'                # phase-3 captures carry the same phase-2 buff rows
P3_LIVE = ROOT/'icebow/data/p3_captures'   # live --capture-p3 (5e4818f): same run.json + frames.jsonl layout, gitignored


def p3_runs():
    """Every phase-3 capture: the manual probe runs and the live --capture-p3 ones."""
    return sorted(P3_DIR.glob('p3_*/run.json')) + sorted(P3_LIVE.glob('*/run.json'))


CAST, MID_JUMP = 10, (3, 5, 6)     # behavior_state_raw: hero cast; Mega Knight jump, river jump, tunnelling
STUN_BUFFS = ('Freeze', 'Tesla_EV1_WithDamage')   # phase-2 buff names the SIM holds as stun_ms (Freeze spell -> stun_ms, probed)
# Ice Wizard slows (all -30% walk / attack / spawn, IW_SLOW_1016.md): live buff name -> the SIM buff it is seeded as
# (Engine.slow_ids, probed: the SIM's after-slow and base deploy chill are its IceWizardSlowDown). The hero freeze
# (999,999 sentinel) is not a time and stays unset (an ability inside 100 ticks of t0 is a strict blocker anyway).
SLOW_BUFFS = {'IceWizardSlowDown': 'base', 'IceWizardCold': 'base', 'IceWizardHero_SlowBuff': 'base',
              'IceWizardHeroSlow': 'hero', 'IceWizardHeroCold': 'hero_cold'}
IW_SLOW_MS = 2500                  # an Ice Wizard shot's slow (both forms; re-armed on every hit)
SENTINEL_MS = 100000               # buff/effect remaining above this is "lives with its source", not a time
CHARGE_PER_MT = 4                  # SIM 0.1.35 charge_progress: +240 per tick at speed 60 (59 mt/tick), charged at range_raw x 40


# ---------------------------------------------------------------- live side (no engine import)

def read_match(path):
    """-> (match, None) or (None, reason). Frames: [(tick, [body])]; body keys: id side x y card_id hp max_hp kind tower."""
    frames, plays, outcome, abilities = {}, [], [], []
    hands = []                      # (tick, {name: form}) from public own_hand
    shots = []                      # (tick, side, card_id) public in-flight projectiles at decision ticks
    extra = {}                      # ext logs: tick -> (ents_state, proj, fx)
    side = None
    with open(path, 'rb') as f:
        for raw in f:
            head = raw[:40]
            if b'"frame"' in head:
                j = json.loads(raw)
                side = j['my_side']
                frames[j['tick']] = j['ents']           # duplicate tick: keep the last read
                if 'ents_state' in j:
                    extra[j['tick']] = (j['ents_state'], j.get('proj') or [], j.get('fx') or [])
            elif b'"decision"' in head:
                j = json.loads(raw); p = j.get('public') or {}
                hands.append((j['tick'], {h['name']: int(h.get('form', 0)) for h in p.get('own_hand', [])}))
                shots += [(j['tick'], q['side'], q['card_id']) for q in p.get('raw_projectiles', []) if q.get('card_id', -1) != -1]
            elif b'"play"' in head:
                j = json.loads(raw); plays.append(dict(tick=j['tick'], name=j['name'], xy=j['xy'], elixir=j.get('elixir')))
            elif b'"confirmed"' in head or b'"unconfirmed"' in head:
                j = json.loads(raw); outcome.append((j['event'], j['name'], j.get('intended')))
            elif b'"ability"' in head:
                j = json.loads(raw); abilities.append(dict(tick=j['tick'], confirmed=False, elixir=j.get('elixir')))
            elif b'"ability_confirmed"' in head:
                if abilities:
                    abilities[-1]['confirmed'] = True
    if not frames:
        return None, 'no_frames'
    ticks = sorted(frames)
    first = frames[ticks[0]]
    own_pr = {e[5] for e in first if e[3] == -1 and e[0] == side and e[6] == 13 and abs(e[1]-9000) > 1000}
    # Level-capped (classic / friendly) battles show capped towers on every account: an ext log counts when the own hand
    # is the icebow deck (the owner's 10-16 classic battles: princess 3052).
    if own_pr != {OWN_PRINCESS_MAX} and not (extra and any('Xbow' in h for _, h in hands)):
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
    proj, fx = {}, {}
    for t in ticks:
        bodies, where = [], {}
        for s_, x, y, cid, hp, mx, kind, addr in frames[t]:
            # A card-less row is a tower only on a tower slot: the reader also shows card-less moving rows (293 or 915 hp,
            # 491 of 182,352 frames), which took a tower's id and hp (diag1016: live tower damage < 0 in 12 fights).
            tower = cid == -1 and any(abs(x-tx) < 600 and abs(y-ty) < 600 for tx, ty in TOWER_SLOTS)
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
            where[addr] = bid
        if t in extra:
            # ents_state is parallel to ents: [behavior_state_raw, evo, level, generation id]. A projectile's source and
            # target are resolved to this frame's body ids (in-frame join only; the address is never kept).
            st, pr, ef = extra[t]
            for bd, s in zip(bodies, st):
                bd['state'], bd['gen'] = s[0], s[3]
            proj[t] = [(p[0], p[1], p[2], p[3], p[4], p[5], p[7], where.get(p[8]), where.get(p[9])) for p in pr]
            fx[t] = [(e[0], e[1], e[2], e[3], e[4], e[5], e[7]) for e in ef]
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
                abilities=[a for a in abilities if a['confirmed']], ext=bool(extra), proj=proj, fx=fx), None


def phase2_buffs(path):
    """{tick: {generation id: [(buff name, remaining ms)]}} from the phase-2 capture whose run.json names this frame log
    (joined on tick + generation id only, READER_VALIDATION_1016.md); {} when there is none. Phase-3 captures carry the
    same rows. PARITY_BUFFS=<file> (from `fights.py buffs --out <file>`: buff names and remaining ms only) replaces the
    capture directories, e.g. on a pod that has no reader captures."""
    if os.environ.get('PARITY_BUFFS'):
        rows = json.loads(Path(os.environ['PARITY_BUFFS']).read_text()).get(Path(path).name, {})
        return {int(t): {int(g): [tuple(b) for b in v] for g, v in u.items()} for t, u in rows.items()}
    for run in sorted(P2_DIR.glob('*/run.json')) + p3_runs():
        try:
            if json.loads(run.read_text()).get('live_log') != Path(path).name:
                continue
        except ValueError:
            continue
        out = {}
        with open(run.parent/'frames.jsonl', 'rb') as f:
            for raw in f:
                j = json.loads(raw); p = j.get('phase2') or {}
                if p.get('valid'):
                    out[j['game_tick']] = {u['generation']: [(b['name'], b['remaining_ms_raw']) for b in u['buffs']]
                                           for u in p.get('units', []) if u.get('buffs')}
        return out
    return {}


def phase3_attacks(path):
    """{tick: {generation id: [target gen, previous target gen, progress, load, pre-attack countdown, seq]}} from the
    phase-3 capture whose run.json names this frame log (bodies with an attack component only; joined on tick +
    generation id, never on address); {} when there is none. PARITY_ATTACKS=<file> (from `fights.py attacks --out
    <file>`) replaces the capture directory, e.g. on a pod."""
    if os.environ.get('PARITY_ATTACKS'):
        rows = json.loads(Path(os.environ['PARITY_ATTACKS']).read_text()).get(Path(path).name, {})
        return {int(t): {int(g): v for g, v in u.items()} for t, u in rows.items()}
    for run in p3_runs():
        try:
            if json.loads(run.read_text()).get('live_log') != Path(path).name:
                continue
        except ValueError:
            continue
        out = {}
        with open(run.parent/'frames.jsonl', 'rb') as f:
            for raw in f:
                j = json.loads(raw); p = j.get('phase3') or {}
                if p.get('valid'):
                    out[j['game_tick']] = {
                        b['generation']: [a['target_gen'], a['prev_target_gen'], a['progress_raw'], a['load_raw'], a['pre_raw'], a['seq_idx']]
                        for b in p.get('bodies', []) for a in [b.get('attack')] if a}
        return out
    return {}


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
            elif r['active'] is not None and b['kind'] in (12, 14) and 'land' not in r and t - r['first'] <= 80:
                r['land'] = (t, b['x'], b['y'])     # active first, deploying later: a digger (Miner) surfacing here
    return tr


def form_of(cid, c):
    return 2 if cid in (c.get('hero_form_id'), 203000023) else int(cid == c.get('evolution_form_id'))


def elixir_wait(tick, elixir, cost):
    """Ticks a tap made `cost - elixir` short waits before the live game plays it (TICKS_PER_ELIXIR; double elixir from
    tick 2400, triple from 4800)."""
    if elixir is None or cost is None or elixir >= cost:
        return 0
    return (cost - elixir) * TICKS_PER_ELIXIR / (1 if tick < 2400 else 2 if tick < 4800 else 3)


def seen_casts(m, catalog, life=None):
    """Ext logs: spells (both sides) from projectile / effect rows, and hero ability casts (both sides) from state-10
    bursts or, for an instant-cast hero, its ability effect row. Every tick is the SIM's play/press tick: the SIM
    creates the spell / starts the cast on the tick after the command (probed on 0.1.35: Rocket, Log, Tornado, Poison,
    Freeze, Goblin Barrel, Hero Knight, Hero Ice Wizard), so a first sighting in (prev frame, first] gives tick =
    mid-gap - 1, as for a body. An effect row counts down 50 ms a tick from its full life: its creation tick is exact.
    life: spell name -> area-effect life ms (None: first sighting = creation)."""
    ticks = [t for t, _ in m['frames']]
    def gap(first):
        prev = ticks[max(0, bisect_left(ticks, first)-1)]
        prev = prev if prev < first else first - 2
        return dict(tick=(prev + 1 + first)//2 - 1, lo=prev, hi=max(prev, first-1))
    kind = lambda cid: (catalog.get(cid) or {}).get('type')
    name = lambda cid: (catalog.get(cid) or {}).get('display_name')
    shots, fxs = {}, {}
    for t in ticks:
        for p in m['proj'].get(t, ()):
            if kind(p[3]) == 'spell':
                r = shots.setdefault(p[6], dict(first=t, side=p[0], cid=p[3], x=p[4], y=p[5]))
                r['last'] = t
        for e in m['fx'].get(t, ()):
            r = fxs.setdefault(e[6], dict(first=t, side=e[0], cid=e[3], x=e[1], y=e[2], rem=e[4]))
            r['last'] = t
    out = []
    # Projectile spells: a throw then a roll (Log, Barbarian Barrel) or waves (Arrows) are one cast; the cast point is
    # the first shot's target point (READER_VALIDATION_1016: target point = cast point, source = King Tower).
    for r in sorted(shots.values(), key=lambda r: r['first']):
        c = next((c for c in out if c['side'] == r['side'] and c['cid'] == r['cid'] and r['first'] - c['seen'] <= 30), None)
        if c:
            c['end'] = max(c['end'], r['last']); continue
        out.append(dict(gap(r['first']), kind='play', side=r['side'], cid=r['cid'], name=name(r['cid']), form=0,
                        x=r['x'], y=r['y'], n=0, source='spell_seen', spell_spawned=False, seen=r['first'], end=r['last']))
    for r in sorted(fxs.values(), key=lambda r: r['first']):
        if kind(r['cid']) != 'spell' or any(c['side'] == r['side'] and c['cid'] == r['cid'] and c['seen'] <= r['first'] <= c['end'] + 20
                                            for c in out):
            continue
        full = life(name(r['cid'])) if life else None
        made = r['first'] - (round((full - r['rem'])/50) if full and 0 < r['rem'] <= full else 0)
        out.append(dict(kind='play', side=r['side'], cid=r['cid'], name=name(r['cid']), form=0, tick=made-1, lo=made-1,
                        hi=made-1, x=r['x'], y=r['y'], n=0, source='spell_seen', spell_spawned=False, seen=r['first'],
                        end=r['last'], made=made))
    # A cast whose area row comes FIRST and whose projectile rows follow (Lightning: the area at the cast point, then the
    # bolts on their targets ~20 ticks later; Royal Delivery: the area, then the box landing 40 ticks later) was kept
    # twice above -- the area cast and a projectile 'cast' at a bolt's target -- and the SIM replayed it twice (two
    # Lightnings on one Knight). The area row is the cast (its creation tick is exact): drop the projectile twin.
    # (diag_night/log, spell audit: 8 Lightning and 4 Royal Delivery casts doubled on the ext logs.)
    made = [c for c in out if 'made' in c]
    out = [c for c in out if 'made' in c or not any(f['side'] == c['side'] and f['cid'] == c['cid']
                                                     and f['made'] <= c['seen'] <= f['made'] + 45 for f in made)]
    # Hero casts: the first state-10 frame of a burst; an instant hero (no cast time) shows only its ability effect,
    # card = the hero's card (Hero Ice Wizard: the freeze area). Champions are not counted here (untested on video).
    casts, prev = [], {}
    for t, bodies in m['frames']:
        for bd in bodies:
            c = catalog.get(bd['card_id'])
            if bd['tower'] or c is None or form_of(bd['card_id'], c) != 2:
                continue
            if bd.get('state') == CAST and prev.get(bd['id']) != CAST:
                casts.append((t, bd['side'], c['display_name']))
            prev[bd['id']] = bd.get('state')
    heroes = {}
    for t, bodies in m['frames']:
        for bd in bodies:
            c = catalog.get(bd['card_id'])
            if not bd['tower'] and c and form_of(bd['card_id'], c) == 2:
                heroes.setdefault((bd['side'], c['display_name']), []).append(t)
    for r in sorted(fxs.values(), key=lambda r: r['first']):
        k = (r['side'], name(r['cid']))
        if kind(r['cid']) == 'spell' or not any(abs(t - r['first']) <= 4 for t in heroes.get(k, ())):
            continue
        if not any(s == k[0] and n == k[1] and -10 <= r['first'] - t <= 40 for t, s, n in casts):
            casts.append((r['first'], k[0], k[1]))
    for t, s, n in sorted(casts):
        out.append(dict(gap(t), kind='ability', side=s, name=n, source='cast_seen', seen=t, end=t))
    for e in out:
        e.pop('cid', None)
    return sorted(out, key=lambda e: (e['tick'], e['side'], e['name']))


def deployments(m, catalog, life=None, own_unit=None):
    """Live deployments: new body groups (children of a living/just-dead same-card body, or role-children by max_hp,
    are the SIM's job, not plays), own confirmed spells, own Hero IW presses. Ext logs: spells and hero casts of both
    sides as seen (seen_casts); an own tap or press stays only where nothing was seen for it."""
    seen = seen_casts(m, catalog, life) if m.get('ext') else []
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
        c = catalog[r['card_id']]
        # A hero's ability object can share the card id and dwarf its units (Hero Goblins: a 3720 / 4090 hp object over
        # 293 / 323 hp goblins), so the max_hp rule dropped every Hero Goblins play as a role-child (diag_night/knight).
        # A hero body whose max_hp IS the card's own unit at some level (own_unit = Engine.level) is a play's body.
        child_by_hp = r['max_hp'] < .45*top[r['side'], r['card_id']] and not (
            own_unit and form_of(r['card_id'], c) == 2 and own_unit(c['display_name'], r['max_hp']))
        if near_parent or child_by_hp:
            continue
        if c.get('type') == 'spell' and any(e['kind'] == 'play' and e['side'] == r['side'] and e['name'] == c['display_name']
                                            and e['seen'] <= r['first'] <= e['end'] + 60 for e in seen):
            continue           # a seen Goblin Barrel / Barbarian Barrel cast: the SIM spawns its bodies
        # One play's bodies: same side and card, first seen within 6 ticks of each other, within FORMATION_SPAN of the
        # group's centroid (a Royal Recruits line spans 14 tiles and a Skeleton Army 5: a 4-tile rule split them into
        # 3-4 / 2 plays, and the SIM then deployed 18-24 recruits).
        g = next((g for g in groups if g['side'] == r['side'] and g['card_id'] == r['card_id']
                  and r['first']-g['tick'] <= 6 and math.hypot(g['x']-r['x'], g['y']-r['y']) < FORMATION_SPAN), None)
        if g:
            g['members'].append(r); n = len(g['members'])
            g['x'] += (r['x']-g['x'])/n; g['y'] += (r['y']-g['y'])/n
        else:
            groups.append(dict(side=r['side'], card_id=r['card_id'], tick=r['first'], x=r['x'], y=r['y'], members=[r]))
    out, used, delays, waits = [], set(), [], []
    ticks = [t for t, _ in m['frames']]
    for g in groups:
        c = catalog[g['card_id']]
        # A play's unit is created on the tick after the play; the live unit was created somewhere in (prev frame, first
        # seen]: play so that the SIM's unit is born mid-gap.
        prev = ticks[bisect_left(ticks, g['tick'])-1]
        tick = (prev + 1 + g['tick'])//2 - 1
        # lo..hi: every tick the live creation could have come from (the frame gap); the ceiling draws from it
        ev = dict(kind='play', side=g['side'], name=c['display_name'], form=form_of(g['card_id'], c), tick=tick,
                  x=round(g['x']), y=round(g['y']), n=len(g['members']), source='first_seen',
                  spell_spawned=c.get('type') == 'spell', lo=prev, hi=max(prev, g['tick']-1))
        land = [r['land'] for r in g['members'] if 'land' in r] if c['display_name'] in DIGGERS else []
        if land:
            # A Miner is seen tunnelling from its own side (active rows) before it surfaces (deploying rows): the play's
            # point is where it surfaces, not where it was first seen (ceiling subset: every opp Miner was replayed
            # walking from near its king tower, 0 tower damage vs 93-342 live).
            ev.update(x=round(statistics.fmean(p[1] for p in land)), y=round(statistics.fmean(p[2] for p in land)), dig=True)
        if g['side'] == m['side']:
            cand = [i for i, p in enumerate(m['plays']) if i not in used and p['name'] == ev['name']
                    and 0 <= g['tick']-p['tick'] <= 80]
            if cand:
                i = cand[-1]; used.add(i); p = m['plays'][i]
                ev.update(x=p['x'], y=p['y'], source='own_tap', tap=p['tick']); delays.append(tick-p['tick'])
                waits.append(elixir_wait(p['tick'], p.get('elixir'), c.get('elixir')))
        out.append(ev)
    delay = statistics.median(delays) if delays else 23
    # A spell's tick (tap + delay + wait) errs like a troop play's: this match's own troop residuals, clipped to the
    # p5..p95 band of 10-15 matches (-3..+3 ticks; 87% within +-2), are the ceiling's draw for spells and presses.
    jit = sorted(max(-3, min(3, round(d - delay - w))) for d, w in zip(delays, waits)) or [0]
    for i, p in enumerate(m['plays']):
        c = next((c for c in catalog.values() if c['display_name'] == p['name']), None)
        if i in used or not c or c.get('type') != 'spell':
            continue
        if any(e['side'] == m['side'] and e['name'] == p['name'] and p['tick'] <= e['tick'] <= p['tick'] + 100 for e in seen):
            continue           # seen cast replaces the tap estimate
        wait = elixir_wait(p['tick'], p.get('elixir'), c.get('elixir'))
        out.append(dict(kind='play', side=m['side'], name=p['name'], form=p['form'], tick=round(p['tick']+delay+wait),
                        x=p['x'], y=p['y'], n=0, source='own_spell_tap+delay', tap=p['tick'], spell_spawned=False,
                        elixir_wait=round(wait), jit=jit))
    for a in m['abilities']:
        wait = elixir_wait(a['tick'], a.get('elixir'), HERO_IW_ABILITY_COST)
        tick = round(a['tick']+delay+wait)
        if any(e['kind'] == 'ability' and e['side'] == m['side'] and abs(e['tick'] - tick) <= 30 for e in seen):
            continue
        out.append(dict(kind='ability', side=m['side'], name='IceWizard', tick=tick, source='own_press',
                        elixir_wait=round(wait), jit=jit))
    out += seen
    return sorted(out, key=lambda e: (e['tick'], e['side'], e['name'])), delay


def cut(m, events, window):
    """One fight per deployment: start = the last frame strictly before it; length `window` ticks."""
    ticks = [t for t, _ in m['frames']]
    tr = tracks(m['frames'])
    # A parent gone before the start frame whose death spawn is first seen after it (a Skeleton Balloon's skeletons land
    # ~12 ticks after its death) is on no board and in no play, so the SIM would never make those bodies. Start on the
    # parent's last frame instead: it is set up alive with its live hp, the shot that kills it is injected as in flight,
    # and the SIM makes the children itself (diag_night/log, 171357@1655). (parent last seen, children first seen) pairs,
    # by deployments()' near-parent rule.
    fam, pend = defaultdict(list), set()
    for r in tr.values():
        fam[r['side'], r['card_id']].append(r)
    for rs in fam.values():
        for r in rs:
            for q in rs:
                if q is not r and q['last'] < r['first'] <= q['last'] + 15 and r['max_hp'] < q['max_hp']:
                    at = max((p for p in q['traj'] if p[0] <= r['first']), default=q['traj'][0])
                    if math.hypot(at[1] - r['x'], at[2] - r['y']) < 3000:
                        pend.add((q['last'], r['first']))
    fights = []
    for k, ev in enumerate(events):
        if ev['kind'] != 'play':
            continue
        i = bisect_left(ticks, ev['tick']) - 1
        # A body still deploying at the start frame cannot be set up mid-deploy: start before it was born instead.
        # A death spawn pending at the start frame: start on its parent's last frame (above).
        for _ in range(4):
            born = [tr[b['id']]['first'] for b in m['frames'][max(i, 0)][1]
                    if not b['tower'] and b['kind'] in (12, 14) and tr[b['id']]['first'] > ticks[max(i, 0)]-80]
            dead = [lo for lo, hi in pend if i >= 0 and lo < ticks[i] < hi]
            if not (born or dead) or i < 0:
                break
            i = min(([bisect_left(ticks, min(born)) - 1] if born else []) + ([bisect_left(ticks, min(dead))] if dead else []))
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
        # PARITY_OVERRIDES='{"status.ATTRACT_ONSET": "<arm>", ...}': per-law calibration overrides for law A/Bs (diag_night/skel
        # law_override_hook); unset = the runtime's own arms, outputs byte-identical
        extra = {k: json.dumps(v) for k, v in json.loads(os.environ.get('PARITY_OVERRIDES') or '{}').items()}
        self.b = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides={'cards.CARD_TABLE': json.dumps(CARD_TABLE), **extra})
        if extra:
            self.stamp['overrides'] = sorted(extra)
        self.cat = [dict(zip(sim.CATALOGUE_FIELDS, r)) for r in json.loads(self.b.catalogue_json())]
        self.ids = {c['name']: i for i, c in enumerate(self.cat)}
        self.F = list(sim.ENTITY_FIELDS)
        self.k_order = [[p[0] for p in team] for team in self.b.tower_positions()]   # x subtiles per k
        self.grid = self.b.passable_half_cells()                                       # [hy][hx], 500 millitiles
        self._tower = {}
        self._form = {}
        self._proxy, self._own_unit = {}, None
        try:                       # card-table rows (hit speed, load time, range, hide timers) for the ceiling and attribution
            d = json.loads(sim.EMBEDDED_CARDS_160402017_JSON)
            self._stats = {c['name']: c for c in d['cards']} | {t['name']: t for t in d['towers']}
        except (AttributeError, KeyError, ValueError):
            self._stats = {}

    def stats(self, name):
        return self._stats.get(name, {})

    def effect_life(self, name, key='life_duration_ms'):
        """Area-effect life (or buff time) of spell `name`, ms (card table); None without one."""
        return ((self.stats(name).get('spell') or {}).get('area_effect_object') or {}).get(key)

    def reach(self, name):
        """Attack reach (range + own radius, millitiles) of engine card `name`, for tower-damage attribution."""
        c = self.stats(name)
        return (c.get('range_milli') or 1000) + (c.get('collision_radius_milli') or 500)

    def passable(self, x, y):
        hx, hy = int(x//500), int(y//500)
        return 0 <= hy < len(self.grid) and 0 <= hx < len(self.grid[0]) and bool(self.grid[hy][hx])

    def nearest_passable(self, x, y, reach=2, inset=20):
        """The nearest point inside a passable half-cell (`inset` millitiles in from its edge), not the cell's centre: a
        live body 65 mt over the bridge edge was moved 380 mt to a centre, into a tower's reach 4 ticks early
        (diag_night/knight 175459@3198)."""
        hx, hy = int(x//500), int(y//500)
        best = None
        for cx in range(hx-reach, hx+reach+1):
            for cy in range(hy-reach, hy+reach+1):
                if 0 <= cy < len(self.grid) and 0 <= cx < len(self.grid[0]) and self.grid[cy][cx]:
                    px = min(max(x, cx*500+inset), cx*500+500-inset); py = min(max(y, cy*500+inset), cy*500+500-inset)
                    d = math.hypot(px-x, py-y)
                    if best is None or d < best[0]:
                        best = (d, px, py)
        return (best[1], best[2]) if best else None

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

    def child_entity(self, parent, form, max_hp):
        """(entity columns, its 4 buff slots) of the `max_hp` second-summon unit a real play of `parent` in `form`
        creates, at the level whose unit_hitpoints role row has that hp; None if no level / no such unit. Probed once in
        a scratch battle (resets the battle: the caller restores its state by load_edited)."""
        key = ('child', parent, form, max_hp)
        if key in self._form:
            return self._form[key]
        from scratchpad.gauntlet.L74.parity.mechanics import load_edited
        out, b, K = None, self.b, 18
        lvl = None
        for lv in range(16, 0, -1):
            try:
                rows = b.unit_hitpoints(self.ids[parent], lv)
            except (ValueError, KeyError):
                continue
            if any(role == 'second_summon' and hp == max_hp for role, _, hp in rows[1:]):
                lvl = lv; break
        if lvl is not None:
            try:
                b.reset(1, [[self.ids['Knight']], [self.ids[parent]]], 0, 200, None, None, [], forms=[[0], [form]],
                        levels=[[11], [lvl]], tower_levels=[11, 11])
                sv = json.loads(b.save()); after = json.loads(json.dumps(sv))
                for ev in after['players'][1]['evo']:
                    ev['plays'] = ev['cycles'] if form == 1 else 0
                after['players'][1]['mana'] = after['calib']['max_mana']*after['mana_unit']
                if after != sv:
                    load_edited(b, sv, after)
                n0 = len(json.loads(b.save())['ents']['card'])
                r = b.step([(1, 0, 9000*K, 22000*K)], 0)[0]
                b.step([], 2)
                E = json.loads(b.save())['ents']
                i = next((i for i in range(n0, len(E['card'])) if E['alive'][i] and E['max_hp'][i] == max_hp
                          and E['kind'][i] == 'Troop'), None) if self.sim.DEPLOY_REASONS[r[1]] == 'OK' else None
                if i is not None:
                    n = len(E['card'])
                    out = ({k: v[i] for k, v in E.items() if isinstance(v, list) and len(v) == n}, E['buffs'][4*i:4*i+4])
            except (ValueError, KeyError):
                out = None
        self._form[key] = out
        return out

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

    def spell_damage(self, name, side, level):
        """First hp drop a `side` cast of spell `name` at `level` deals to a still, huge-hp enemy Golem (None: no hit)."""
        key = ('dmg', name, side, level)
        if key not in self._form:
            b, y = self.b, (20000 if side == 1 else 12000)            # the caster's own half: the Log is territory-bound
            decks = [[self.ids[name]], [self.ids[name]]]
            try:
                b.reset(1, decks, 0, 200, [10000, 10000], None, [(1-side, self.ids['Golem'], 9000*18, y*18, 10**6)],
                        levels=[[level], [level]], tower_levels=[15, 15])
            except ValueError:                                      # no such level for this rarity
                self._form[key] = None
                return None
            gi = self.F.index('card_id')
            hp = lambda: next(dict(zip(self.F, r))['hp'] for r in json.loads(b.state_json())['entities'] if r[gi] == self.ids['Golem'])
            hp0 = hp(); dmg = None
            b.step([(side, 0, 9000*18, y*18)], 0)
            for _ in range(100):
                b.step([], 1)
                if hp() < hp0:
                    dmg = hp0 - hp(); break
            self._form[key] = dmg
        return self._form[key]

    def slow_ids(self):
        """{'base' | 'hero' | 'hero_cold': SIM buff id} of the Ice Wizard slows (SLOW_BUFFS). Ids are interned per table,
        so they are read off a probe (IW_SLOW_1016 §2): a red Giant next to a hero IW played from hand carries the deploy
        chill first, then the shot slow; next to a spawned base IW, the base slow. Resets the battle: call before a
        fight's setup (cached)."""
        if 'slow' not in self._form:
            b, K, out = self.b, 18000, {}

            def seen(forms, spawns, cmds):
                b.reset(1, [[self.ids['IceWizard']], [self.ids['Giant']]], 0, 200, [10000, 10000], [[4824, 0, 0], [4824, 3052, 3052]],
                        spawns, forms=forms, levels=[[11], [11]], tower_levels=[11, 11])
                b.step(cmds, 0)
                order = []
                for _ in range(80):
                    b.step([], 1)
                    E = json.loads(b.save())['ents']
                    n = len(E['alive']); slots = len(E['buffs']) // n
                    g = next(i for i in range(n) if E['alive'][i] and E['team'][i] == 'Red' and E['kind'][i] == 'Troop')
                    order += [s['id'] for s in E['buffs'][g*slots:(g+1)*slots] if s['id'] and s['id'] not in order]
                return order
            giant = (1, self.ids['Giant'], 9*K, 9*K, -1)
            try:
                hero = seen([[2], [0]], [giant], [(0, 0, 9*K, 7*K)])
                base = seen([[0], [0]], [giant, (0, self.ids['IceWizard'], 9*K, 7*K, -1)], [])
                if len(hero) >= 2 and base:
                    out = dict(hero_cold=hero[0], hero=hero[1], base=base[0])
            except (ValueError, StopIteration):
                pass
            self._form['slow'] = out
        return self._form['slow']

    def spawn_table(self, name, probe=True):
        """{k: (spawn_ms, spawn_wave_left)} a spawner card's record holds on the tick its k-th child of a wave is born, in
        the steady cycle (from the second wave on), probed on a lone setup spawn; None for a card that spawns no timed
        waves. probe=False reads the cache only (a probe resets the battle: run_fight probes before its setup)."""
        key = ('spawn', name)
        if key not in self._form and probe:
            st = self.stats(name)
            out = None
            if (st.get('spawner') or {}).get('pause_time_ms') or (st.get('interval_spawner') or {}).get('interval_ms'):
                b = self.b
                b.reset(1, [[self.ids['Knight']], [self.ids[name]]], 0, 200, None, [[4824, 0, 0], [4824, 0, 0]],
                        [(1, self.ids[name], 9000*18, 24000*18, -1)], levels=[[15], [15]], tower_levels=[15, 15])
                E = json.loads(b.save())['ents']
                i = next(j for j in range(len(E['alive'])) if E['alive'][j] and E['kind'][j] not in ('KingTower', 'PrincessTower'))
                seen = {j for j in range(len(E['alive'])) if E['alive'][j]}
                births = []                  # (tick, children born, spawn_ms, wave_left)
                for t in range(1, 640):
                    b.step([], 1)
                    E = json.loads(b.save())['ents']
                    new = [j for j in range(len(E['alive'])) if E['alive'][j] and j not in seen and E['spawned_by'][j] is not None]
                    seen |= {j for j in range(len(E['alive'])) if E['alive'][j]}
                    if new:
                        births.append((t, len(new), E['spawn_ms'][i], E['spawn_wave_left'][i]))
                    if not E['alive'][i]:
                        break
                gap = ((st.get('spawner') or {}).get('interval_ms') or 0)//50 + 3
                waves, k = [], 0
                for j, (t, n, ms, wl) in enumerate(births):
                    k = k + n if j and t - births[j-1][0] <= gap else n
                    if not (j and t - births[j-1][0] <= gap):
                        waves.append({})
                    waves[-1][k] = (ms, wl)
                if len(waves) >= 2:          # the second wave: a cycle that started from a wave, as a live one has
                    out = waves[1]
            self._form[key] = out
        return self._form.get(key)

    def shot_template(self, name, form, level):
        """A real in-flight projectile record (save()['projectiles'] row) shot by engine card `name` played in `form` at
        `level`, or by a 'PrincessTower' / 'KingTower' at tower level `level`, at a still Golem: the template for a
        projectile already flying at a fight's t0 (run_fight). None: the card shoots no projectile. Resets the battle:
        call before a fight's setup (cached)."""
        key = ('shot', name, form, level)
        if key not in self._form:
            from scratchpad.gauntlet.L74.parity.mechanics import load_edited
            b, K, out = self.b, 18, None
            try:
                if name in ('PrincessTower', 'KingTower'):
                    b.reset(1, [[self.ids['Knight']], [self.ids['Knight']]], 0, 200, None, None,
                            [(1, self.ids['Golem'], 9000*K, (9500 if name == 'KingTower' else 11000)*K, 10**6)],
                            levels=[[11], [11]], tower_levels=[level, level])
                    if name == 'KingTower':
                        sv = json.loads(b.save()); after = json.loads(json.dumps(sv)); after['king_active'] = [True, True]
                        load_edited(b, sv, after)
                    firer = lambda E, i: E['kind'][i] == name and E['team'][i] == 'Blue'
                else:
                    b.reset(1, [[self.ids['Knight']], [self.ids[name]]], 0, 200, None, None,
                            [(0, self.ids['Golem'], 9000*K, 19500*K, 10**6)], forms=[[0], [form]], levels=[[11], [level]],
                            tower_levels=[11, 11])
                    sv = json.loads(b.save()); after = json.loads(json.dumps(sv))
                    for ev in after['players'][1]['evo']:
                        ev['plays'] = ev['cycles'] if form == 1 else 0
                    after['players'][1]['mana'] = after['calib']['max_mana']*after['mana_unit']
                    if after != sv:
                        load_edited(b, sv, after)
                    n0 = len(json.loads(b.save())['ents']['card'])
                    b.step([(1, 0, 9000*K, 24000*K)], 0)
                    firer = lambda E, i: i == n0
                for _ in range(200):
                    b.step([], 1)
                    sv = json.loads(b.save())
                    E = sv['ents']
                    hit = [p for p in sv['projectiles'] if p.get('firer') and firer(E, p['firer']['index'])]
                    if hit:
                        out = hit[0]; break
            except (ValueError, KeyError, StopIteration):
                out = None
            self._form[key] = out
        return self._form[key]

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


def run_fight(eng, m, events, fight, catalog, by_name, levels, tower_levels, top, ceiling=0):
    sim, b = eng.sim, eng.b
    t0, t1 = fight['t0'], fight['t1']
    anchor = events[fight['anchor']]
    spell = None
    if anchor['source'] in SPELL_SOURCES and anchor['name'] in eng.ids:
        # probed before this fight's reset (spell_damage resets the battle); cached by spell_levels
        d = eng.spell_damage(anchor['name'], anchor['side'], levels.get((anchor['side'], anchor['name'])) or levels.get((anchor['side'], '*')) or 15)
        c = eng.stats(anchor['name']); sp = (c.get('projectile') or {}).get('spawn_projectile') or {}
        reach = max(c.get('area_damage_radius_milli') or 0, (c.get('spell') or {}).get('radius_milli') or 0,
                    (sp.get('projectile_range_milli') or 0) + (sp.get('projectile_radius_milli') or 0)) + TOWER_RADIUS
        # a damage-over-time spell deals its hits through its area's buff, whose crown % is the one that applies (Tornado:
        # buff 30 %, area 100 %, top level none; diag_night/skel: live Tornado ticks on a crown tower are 40-41 of a 134 d,
        # so the old dt = d made the >= 0.8 dt test fire only on coincident X-Bow + Tornado drops)
        buff = ((c.get('spell') or {}).get('area_effect_object') or {}).get('buff') or {}
        crown = c.get('crown_tower_damage_percent') or (buff.get('crown_tower_damage_percent') if buff.get('damage_per_second') else None) or 100
        spell = dict(d=d or 0, dt=(d or 0)*crown/100, x=anchor['x'], y=anchor['y'], reach=reach)
        pj = c.get('projectile') or {}
        if sp.get('projectile_range_milli') and sp.get('projectile_radius_milli') and sp.get('speed') and pj.get('speed'):
            # A rolling spell (the Log, the Barbarian Barrel) hits only what its box rolls over: thrown from min_distance
            # behind the cast point, it lands ceil(min_distance / throw speed) ticks after the play tick and rolls
            # `speed` a tick (table units = millitiles a tick; measured on the 19 failing own-Log fights of the captured
            # cohort: live and SIM rolls land within 1 tick of this and of each other). diag_night/log/REPORT.md.
            def body(name, max_hp, form):
                # (radius, flying) of a body; a child carries its parent's card (a Skeleton Balloon's skeletons):
                # read the card whose own unit it is (Engine.child_proxy), a rider-like child as a ground body
                if not form and name in eng.ids and eng.level(name, max_hp) is None:
                    proxy = eng.child_proxy(name, max_hp)
                    if not proxy or proxy[0] == '__parent__':
                        return 500, False
                    name = proxy[0]
                st = eng.stats(name) or {}
                return (st.get('collision_radius_milli') or 500,
                        bool(eng.cat[eng.ids[name]]['flying']) if name in eng.ids else False)
            spell.update(roll=dict(x=anchor['x'], y=anchor['y'], t=anchor['tick'] + math.ceil((pj.get('min_distance_milli') or 0)/pj['speed']),
                                   v=sp['speed'], len=sp['projectile_range_milli'], hw=sp['projectile_radius_milli'],
                                   hd=sp.get('projectile_radius_y_milli') or 0, fwd=1 if anchor['side'] == 0 else -1,
                                   air=bool(sp.get('aoe_to_air'))), body=body)
    if m['ext']:
        eng.slow_ids()             # probed before this fight's reset (it resets the battle); cached
    roster = None
    if anchor['kind'] == 'play' and anchor.get('form') == 2 and anchor['name'] in eng.ids:
        # A hero's ability summon (Hero Ice Wizard: its IceWizardHero_IceCube, 352 hp at level 14, a 5 s body the live
        # reader and the SIM both label with the hero's card) is ability state, not one of the card's bodies: the card
        # view counts only the card's own units (unit_hitpoints roles at its level) and the bodies born with the play.
        lvl = levels.get((anchor['side'], anchor['name'])) or levels.get((anchor['side'], '*')) or 15
        try:
            roster = {hp for _, _, hp in eng.b.unit_hitpoints(eng.ids[anchor['name']], lvl)}
        except ValueError:
            roster = None
    frames = [fr for fr in m['frames'] if t0 <= fr[0] <= t1]
    start = frames[0][1]
    for bd in start:               # spawner cycles on the t0 board: probed before this fight's reset (it resets the battle)
        c = catalog.get(bd['card_id'])
        if not bd['tower'] and c and c['display_name'] in eng.ids:
            eng.spawn_table(c['display_name'])
    flags = Counter()
    shots = inflight_shots(m, fight, start, catalog, levels, tower_levels) if m['ext'] else []
    for s_ in shots:               # templates probed before this fight's reset (a probe resets the battle); cached
        s_['tpl'] = eng.shot_template(*s_['key'])
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
    by_parent = []                 # (live body, card, form): second-summon children left to the parent's setup spawn

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
        setup.append(dict(id=bd['id'], side=bd['side'], x=x, y=y, card_id=bd['card_id'], proxy=name != catalog[bd['card_id']]['display_name'],
                          worn=bd['hp'] < bd['max_hp']))
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
                flags['setup_child_by_parent'] += 1; by_parent.append((bd, c['display_name'], form_of(bd['card_id'], c))); continue
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
    # Ext logs show hero casts (seen_casts: they are events); champions stay unobserved.
    heroes = set()
    for _, bodies in frames:
        for bd in bodies:
            c = catalog.get(bd['card_id'])
            if c and not bd['tower'] and bd['side'] != m['side'] and (form_of(bd['card_id'], c) == 2 and not m['ext'] or
                                                                   eng.cat[eng.ids[c['display_name']]].get('champion') if c['display_name'] in eng.ids else False):
                heroes.add(c['display_name'])
    for h in heroes:
        flags['opp_ability_unobserved:'+h] += 1
    # Opponent spells are not in old frames; a decision-tick projectile sighting marks the fight (Zap, Lightning,
    # Earthquake, Poison and Freeze are not projectiles and stay invisible). Ext logs replay every seen spell instead.
    for t, s_, cid in ([] if m['ext'] else m['shots']):
        c = catalog.get(cid)
        if s_ != m['side'] and c and c.get('type') == 'spell' and t0-30 <= t <= t1:
            flags['opp_spell_seen:'+c['display_name']] += 1
    for e in events:           # an effect already running at t0 is not public state: the fight cannot start from it
        if e['source'] == 'own_spell_tap+delay' and t0-60 <= e['tick'] < t0:
            flags['spell_in_flight_at_start'] += 1
        # a seen spell still flying / its area still on the board at t0; a Freeze's state is its stuns (set below)
        if e['source'] == 'spell_seen' and e['tick'] < t0 <= e['end'] and e['name'] != 'Freeze':
            flags['spell_in_flight_at_start'] += 1
        if e['kind'] == 'ability' and t0-100 <= e['tick'] < t0:
            flags['ability_active_at_start'] += 1
    for e in evs:
        if e['kind'] == 'play' and not need(e['side'], e['name'], e['form']):
            flags['event_card_missing'] += 1
        if e.get('spell_spawned'):
            flags['spell_spawned_units_timing_unknown'] += 1
    for e in evs:
        if e['kind'] == 'ability':
            need(e['side'], e['name'], 2)
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

    # A second-summon child is left to its parent's setup spawn, which makes a Ram Rider's rider or a Goblin Giant's
    # Spear Goblins; but a Rascals boy's spawn makes no girls, and Spear Goblins whose Giant died have no parent to come
    # from (diag_night/knight: 171357, 2 girls at 417 hp missing, the Knight they killed live survived). Where the SIM
    # holds fewer bodies of the card than setup spawns + such children, the children with no SIM body of their card
    # within 1.5 tiles are cloned from the unit a real play of the parent creates (Engine.child_entity), at their live
    # point, hp and side, active (deploy over), with no target; they join `setup` so pairing and the phase-3 seeds see
    # them. Only the column values the clone must own are changed (identity, position, hp, timers, links).
    if by_parent:
        _, simb = eng.bodies(by_name)
        have = Counter((s_['side'], s_['name']) for s_ in simb if not s_['tower'])
        need_ = Counter((bd['side'], name) for bd, name, _ in by_parent)
        for sp, bd in zip(spawns, setup):
            need_[bd['side'], eng.cat[sp[1]]['name']] += 1
        miss = []
        for k_, n_ in need_.items():
            lack = n_ - have[k_]
            kids = [x for x in by_parent if (x[0]['side'], x[1]) == k_]
            if lack <= 0 or not kids:
                continue
            far = [x for x in kids if not any(s_['side'] == k_[0] and s_.get('name') == k_[1] and
                                               math.hypot(s_['x']-x[0]['x'], s_['y']-x[0]['y']) <= 1500 for s_ in simb)]
            miss += (far + [x for x in kids if x not in far])[:lack]
        if miss:
            before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
            tk = after['tick']
            for bd, name, form in miss:
                rec = eng.child_entity(name, form, bd['max_hp'])        # resets the battle; `after` restores it
                if rec is None:
                    flags['setup_child_skipped:by_parent_unprobed'] += 1; continue
                cols, slots = rec
                n = len(E['card'])
                tm = ('Blue', 'Red')[bd['side']]
                v = json.loads(json.dumps(cols))
                v.update(team=tm, generation=0, alive=True, pos={'x': round(bd['x']*18), 'y': round(bd['y']*18)},
                         hp=max(1, bd['hp']), team_seq=after['ents']['team_counter'][bd['side']], creation_seq=after['ents']['creation_counter'],
                         spawn_tick=tk, last_plan_tick=tk, deploy_ms=0, stagger_ms=0, target=None, target_locked=False,
                         attack_phase='Idle', attack_ms=0, attack_load_ms=0, fired_at=None, chase_dropped=None,
                         chase_inside=None, chase_last_pos={'x': round(bd['x']*18), 'y': round(bd['y']*18)},
                         attached_to=None, attach_offset={'x': 0, 'y': 0}, spawned_by=None, route=[], route_goal=None,
                         seg_dir={'x': 0, 'y': 0}, move_frac={'x': 0, 'y': 0}, facing={'x': 0, 'y': 256 if bd['side'] == 0 else -256},
                         spawn_lane=0 if bd['x'] < 9000 else 1)
                missing_cols = [k for k, col in E.items() if isinstance(col, list) and len(col) == n and k not in v]
                if missing_cols:
                    flags['setup_child_skipped:by_parent_columns'] += 1; continue
                for k, col in E.items():
                    if isinstance(col, list) and len(col) == n:
                        col.append(v[k])
                E['buffs'].extend(json.loads(json.dumps(slots)))
                E['team_counter'][bd['side']] += 1; E['creation_counter'] += 1
                setup.append(dict(id=bd['id'], side=bd['side'], x=bd['x'], y=bd['y'], card_id=bd['card_id'], proxy=False,
                                  worn=bd['hp'] < bd['max_hp']))
                flags['setup_child_cloned'] += 1
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_child_skipped:by_parent_not_set'] += 1
                del setup[len(setup)-flags['setup_child_cloned']:]
                flags['setup_child_cloned'] = 0

    # Target state is not public, and a setup spawn starts with none, so it may pick a nearer troop where the live unit
    # kept shooting a tower (a locked X-Bow). Lock a setup body onto an enemy tower when the body stood still over the
    # last second, the tower is in reach (14 tiles centre to centre for a building, 7 for a troop) and that tower lost hp in that second.
    # Ext logs replace the guess: a projectile in flight up to t0 names its shooter's target (seen_targets).
    team = ('Blue', 'Red')

    def ent(E, ref):
        """SIM entity index of ('body', setup body) (its exact setup point) or ('tower', side, x, y)."""
        if ref[0] == 'tower':
            return next((i for i in range(len(E['card'])) if E['alive'][i] and E['team'][i] == team[ref[1]]
                         and E['kind'][i] in ('KingTower', 'PrincessTower') and abs(E['pos'][i]['x']-ref[2]*18) < 18000
                         and abs(E['pos'][i]['y']-ref[3]*18) < 18000), None)
        bd = ref[1]
        return next((i for i in range(len(E['card'])) if E['alive'][i] and E['team'][i] == team[bd['side']]
                     and E['pos'][i] == {'x': round(bd['x']*18), 'y': round(bd['y']*18)} and E['kind'][i] in ('Troop', 'Building')), None)
    locks = (seen_targets(m, fight, setup, start) if m['ext'] else
             [(('body', bd), ('tower',)+tw) for bd, tw in tower_locks(m, fight, setup, catalog)])
    if locks:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        for src, tgt in locks:
            i = ent(E, src)
            t = ent(E, tgt)
            if i is None or t is None:
                continue
            E['target'][i] = {'index': t, 'generation': E['generation'][t]}; E['target_locked'][i] = True
            flags['setup_target_seen' if m['ext'] else 'setup_target_tower'] += 1
        try:
            load_edited(b, before, after)
        except Exception:
            flags['setup_target_not_set'] += 1

    # A shield breaks before any hp is lost, but a setup spawn gets a full one: a setup body below its max_hp has none left
    # (diag1016: Royal Recruits and Dark Princes kept a shield the live unit had lost, and the Log broke it instead of
    # hitting hp).
    worn = [bd for bd in setup if bd.get('worn')]
    if worn:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        team = ('Blue', 'Red')
        for bd in worn:
            i = next((i for i in range(len(E['card'])) if E['alive'][i] and E['team'][i] == team[bd['side']]
                      and E['pos'][i] == {'x': round(bd['x']*18), 'y': round(bd['y']*18)} and E['kind'][i] in ('Troop', 'Building')), None)
            if i is not None and E['shield'][i] > 0:
                E['shield'][i] = 0; flags['setup_shield_broken'] += 1
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_shield_not_set'] += 1

    # Spawner timers from any frame log; ext logs also: Tesla hidden/up, charge, stun-type status and Ice Wizard slows at t0
    # as the reader shows them (start_state; its ext parts read keys old logs do not have and add nothing there).
    seen_hide = {}
    edits, more = start_state(eng, m, fight, setup, start, events, catalog)
    flags.update(more)
    # Phase-3 logs: every t0-board body's attack target and state as the reader shows it (observed: the ceiling keeps it)
    more_edits, observed, more = phase3_state(eng, m, fight, setup, start, catalog)
    edits += more_edits; flags.update(more)
    before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
    for ref, kv in edits:
        i = ent(E, ref)
        if i is None:
            flags['setup_state_not_found'] += 1; continue
        for k, v in kv.items():
            if k == 'buff':
                if not set_buff(E, i, *v):
                    flags['setup_buff_no_slot'] += 1
            elif k == 'target':
                j = ent(E, v) if v else None
                E['target'][i] = {'index': j, 'generation': E['generation'][j]} if j is not None else None
            else:
                E[k][i] = v
        if 'hide' in kv:
            seen_hide[ref[1]['id']] = kv['hide']
    if after != before:
        try:
            load_edited(b, before, after)
        except Exception:
            flags['setup_state_not_set'] += 1

    # Ext logs: troop / building / tower projectiles already flying at t0 (the reader's proj rows) land in the live game
    # a few ticks later; a setup board has none, so their damage (and splash, slow) was lost (diag_night/tesla: 11 of 17
    # failing Tesla fights start with such a hit, e.g. a Blowdart dart 314 -> 163 on a Knight at t0 + 2). Each one is
    # injected as the firer card's real projectile record (Engine.shot_template), at its live position, aimed at its
    # live target's SIM body.
    if shots:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        # proxies included (diag_night/knight H6): a Witch's / Tombstone's skeleton set up as a Skeletons body is a real
        # SIM body on the live point; 13 + 7 + 2 strict t0 shots at them were skipped as 'target'
        by_setup = {bd['id']: bd for bd in setup}
        towers_ = {bd['id']: ('tower', bd['side'], bd['x'], bd['y']) for bd in start if bd['tower'] and bd['hp'] > 0}
        ref = lambda k: ('body', by_setup[k]) if k in by_setup else towers_.get(k)
        for s_ in shots:
            i, j = (ent(E, ref(s_['src'])) if ref(s_['src']) else None), (ent(E, ref(s_['tgt'])) if ref(s_['tgt']) else None)
            if s_['tpl'] is None or i is None or j is None:
                flags['setup_shot_skipped:' + ('no_template' if s_['tpl'] is None else 'source' if i is None else 'target')] += 1
                continue
            p = json.loads(json.dumps(s_['tpl']))
            p.update(team=E['team'][i], pos={'x': round(s_['x']*18), 'y': round(s_['y']*18)}, aim=dict(E['pos'][j]),
                     target={'index': j, 'generation': E['generation'][j]}, firer={'index': i, 'generation': E['generation'][i]},
                     firer_card=E['card'][i], frac={'x': 0, 'y': 0})
            after['projectiles'].append(p); flags['setup_shot_in_flight'] += 1
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_shot_not_set'] += 1

    # Opt-in inference (PARITY_INFER=target,phase; item 8): the SIM's attack clock advances 50 ms a tick while engaged
    # and a hit lands (melee) / launches (ranged) each time it reaches a multiple of HitSpeed (probed on 0.1.35), so a
    # body that last hit e ms before t0 gets attack_ms = e mod HitSpeed and its reload left; its target = that victim.
    infer = set(filter(None, os.environ.get('PARITY_INFER', '').split(',')))
    inferred = {}
    if infer:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        refs = {bd['id']: ('body', bd) for bd in setup if not bd.get('proxy')}
        refs.update({bd['id']: ('tower', bd['side'], bd['x'], bd['y']) for bd in start if bd['tower'] and bd['hp'] > 0})
        idx = {k: ent(E, r) for k, r in refs.items()}
        live0 = {bd['id']: bd for bd in start}
        atk = {}
        for k, i in idx.items():
            if i is None:
                continue
            bd = live0[k]
            st = eng.stats(('KingTower' if k.endswith('K') else 'PrincessTower') if bd['tower'] else catalog[bd['card_id']]['display_name'])
            if not st.get('hit_speed_ms') or not E['damage'][i] or E['hide'][i] == 'Hidden':
                continue
            atk[k] = dict(dmg=E['damage'][i], dmg_tower=E['damage'][i]*(st.get('crown_tower_damage_percent') or 100)//100,
                          reach=(st.get('range_milli') or 0) + E['radius'][i]/18 + 800, hs=st['hit_speed_ms'],
                          lt=st.get('load_time_ms') or 0, speed=(st.get('projectile') or {}).get('speed'))
        for k, (lo, hi, v) in infer_attacks(m, fight, atk).items():
            i, a = idx[k], atk[k]
            j = idx.get(v)
            if 'target' in infer and j is not None and not E['target_locked'][i]:
                E['target'][i] = {'index': j, 'generation': E['generation'][j]}; E['target_locked'][i] = True
                flags['infer_target'] += 1
            if 'phase' in infer:
                e = round((t0 - (lo + hi)/2))*50
                # no hit for over a cycle (two for a projectile attacker, whose newest shot is often still in flight at t0:
                # on the 10-16 ext logs its drop-based phase mod HitSpeed was within 100 ms of the seen launch in 65 of 74
                # such cases): not fighting steadily, leave the setup default
                if e > a['hs']*(2 if a['speed'] else 1) + 100:
                    flags['infer_phase_stale'] += 1; continue
                ms = e % a['hs']
                E['attack_ms'][i] = ms; E['attack_phase'][i] = 'Windup' if ms else 'Cooldown'
                E['attack_load_ms'][i] = max(0, a['lt'] - e)
                inferred[k] = ((t0 - hi)*50, (t0 - lo)*50, a['hs'], a['lt'])
                flags['infer_phase'] += 1
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['infer_not_set'] += 1; inferred = {}

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

    def simulate(rng=None):
        """(rows, refused, game over). rng None: the replay as built. Else: the setup state reloaded, hidden state redrawn
        (perturb) and each play's tick redrawn from its frame gap / the match's tap residuals (noise ceiling)."""
        ticked = sorted(((e['tick'] if rng is None else jitter_tick(e, rng)), i) for i, e in enumerate(evs))
        if rng is not None:
            b.load(base.encode() if isinstance(base, str) else base)
            perturbed.update(perturb(eng, rng, hist, who, towers0, seen_hide, inferred, observed))
        rows = []                  # (tick, live bodies, sim bodies)
        cursor = 0; refused = Counter(); over = False
        for tick, live in frames:
            while cursor < len(ticked) and ticked[cursor][0] <= tick:
                et, i = ticked[cursor]; cursor += 1
                now = json.loads(b.state_json())['tick']
                if now < et:
                    b.step([], et-now)
                reason = play(evs[i])
                if reason != 'OK':
                    refused[reason] += 1
            st = json.loads(b.state_json())
            if st['tick'] < tick:
                b.step([], tick-st['tick'])
            st, simb = eng.bodies(by_name)
            if st['tick'] != tick:
                over = True
                break
            rows.append((tick, live, simb))
        return rows, refused, over

    base = b.save(); perturbed = Counter()
    rows, refused, over = simulate()
    if over:
        flags['sim_game_over'] += 1
    for k, v in refused.items():
        flags['play_refused:'+k] += v
    res = measure(rows, setup, flags, catalog, eng.stamp)
    if not rows or anchor['kind'] != 'play':
        return res
    until = min((e['tick'] for e in evs if e['kind'] == 'play' and e['side'] == anchor['side'] and e['name'] == anchor['name']
                 and e['tick'] > anchor['tick']), default=t1+1)
    view = lambda rows_, k: card_view(rows_, k, initial_pairs(rows_, setup, catalog), anchor, until, spell, eng.reach, catalog,
                                      roster=roster)
    card = dict(live=view(rows, 1), sim=[view(rows, 2)])
    if ceiling:
        import random
        bad = Counter()
        hist = engagement(m, fight, eng, catalog)
        who = {(('Blue', 'Red')[sp[0]], sp[2], sp[3]): bd['id'] for sp, bd in zip(spawns, setup)}
        towers0 = [(bd['id'], bd['side'], bd['x'], bd['y']) for bd in start if bd['tower']]
        for k in range(1, ceiling+1):
            # Seeded on the fight's identity, not its event index: a harness change that adds an event earlier in the match
            # must not re-draw every later fight's perturbations (diag_night/knight concern, measured 0.75 -> 0.625).
            rows_k, refused_k, over_k = simulate(random.Random(
                f"{m['match']}:{t0}:{anchor['tick']}:{anchor['side']}:{anchor['name']}:{k}"))
            bad.update(refused_k); bad['game_over'] += over_k
            card['sim'].append(view(rows_k, 2) if rows_k else None)
        card['perturbed'] = dict(perturbed); card['ceiling_refused'] = dict(bad)
    res['card'] = card
    return res


def jitter_tick(e, rng):
    """A play's tick redrawn within what the live log cannot pin down: the frame gap for a first-seen body, the match's
    own troop tap residuals for a spell or a press."""
    if 'lo' in e:
        return rng.randint(e['lo'], e['hi'])
    if e.get('jit'):
        return e['tick'] + rng.choice(e['jit'])
    return e['tick']


def engagement(m, fight, eng, catalog, back=60):
    """{live id: (e, r, near)} from the live frames of the `back` ticks up to t0, for every body and tower on the t0
    board: e = ticks it has had an enemy in attack reach without a break up to t0 (0: none at t0); r = ticks since an
    enemy was last in reach (None: in reach at t0, or not in the window); near = an enemy within 8 tiles at any of those
    frames. Reach = range + both collision radii; air / ground / buildings-only as the card table says."""
    t0, i0 = fight['t0'], fight['frame0']
    frames = [fr for fr in m['frames'][max(0, i0-40):i0+1] if fr[0] >= t0-back]

    def card(bd):
        if bd['tower']:
            k = 'KingTower' if bd['id'].endswith('K') else 'PrincessTower'
            return eng.stats(k), False, True
        c = catalog.get(bd['card_id'])
        name = c and c['display_name']
        if name not in eng.ids:
            return None
        st = eng.stats(name)
        return st, bool(eng.cat[eng.ids[name]]['flying']), st.get('kind') == 'building'
    seen = {}
    for t, bodies in frames:
        live = [(bd, card(bd)) for bd in bodies if not bd['tower'] or bd['hp'] > 0]
        live = [(bd, c) for bd, c in live if c]
        for bd, (st, _, _) in live:
            reach = (st.get('range_milli') or 0) + (st.get('collision_radius_milli') or 500)
            inr = near = False
            for od, (ost, ofly, obld) in live:
                if od['side'] == bd['side']:
                    continue
                d = math.hypot(od['x']-bd['x'], od['y']-bd['y'])
                near = near or d <= 8000
                ok = (st.get('attacks_air') if ofly else st.get('attacks_ground', True)) and (obld or not st.get('target_only_buildings'))
                inr = inr or (ok and d <= reach + (ost.get('collision_radius_milli') or 500))
            r = seen.setdefault(bd['id'], dict(run=None, last=None, near=False))
            r['near'] |= near
            if inr:
                r['last'] = t
                r['run'] = t if r['run'] is None else r['run']
            else:
                r['run'] = None
    info = {}
    for k, r in seen.items():
        at0 = r['last'] is not None and r['last'] == t0
        info[k] = (t0 - r['run'] + 1 if at0 and r['run'] is not None else 0,
                   None if at0 or r['last'] is None else t0 - r['last'], r['near'])
    return info


def perturb(eng, rng, hist, who, towers0, seen=None, inferred=None, observed=()):
    """Redraw, on the freshly set-up board, the per-unit state the reader cannot see, within what the live frames of the
    last 3 s allow (engagement(); CEILING.md). Per body or tower on the t0 board:
      * enemy in reach at t0 for e ticks: target uniform over the enemies in reach (a tower lock is kept); swing progress
        uniform over [0, HitSpeed) if e x 50 ms >= HitSpeed, else over [0, LoadTime + e x 50 + 100] (it came into reach
        e ticks ago, maybe not fully reloaded);
      * none in reach at t0, last in reach r ticks ago with r x 50 < LoadTime: reload uniform over [0, LoadTime - r x 50]
        (it may have fired just before); otherwise fully reloaded (the setup default, untouched);
      * a Tesla: Rising (in reach for less than UpTime), Up (in reach, or out of reach for less than HideTime), else
        Hidden, from the same history; its timer +-100 ms (one frame);
      * a shield still up at setup, on a body that had an enemy within 8 tiles: uniform over [0, shield].
    Hidden opponent spells are NOT injected. seen: {live id: 'Up' | 'Hidden'} Tesla states the reader showed at t0 (ext
    logs): a seen Hidden stays Hidden; a seen Up is never redrawn Hidden (Rising stays possible: the rise is shorter than
    one frame gap). inferred: {live id: (elapsed lo ms, elapsed hi ms, HitSpeed, LoadTime)} from the opt-in attack
    inference: the swing is redrawn only within that range (the last hit's frame gap), its target is kept. observed:
    live ids whose target and attack state were set from phase-3 rows (phase3_state): only their shield is redrawn.
    Returns counts of what was redrawn."""
    from scratchpad.gauntlet.L74.parity.mechanics import load_edited
    b = eng.b
    before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
    names = {}
    for row in json.loads(b.state_json())['entities']:
        e = dict(zip(eng.F, row))
        if e['card_id'] != -1:
            names[('Blue', 'Red')[e['team']], e['x'], e['y']] = eng.cat[e['card_id']]['name']
    live = [i for i in range(len(E['card'])) if E['alive'][i]]
    towers = {'KingTower', 'PrincessTower'}
    out = Counter()
    for i in live:
        kind, team, pos = E['kind'][i], E['team'][i], E['pos'][i]
        if kind in towers:
            side = ('Blue', 'Red').index(team)
            if kind == 'KingTower' and not after['king_active'][side]:
                continue
            c = eng.stats(kind)
            lid = next((k for k, s_, x, y in towers0 if s_ == side and math.hypot(x*18-pos['x'], y*18-pos['y']) < 18000), None)
        elif kind in ('Troop', 'Building'):
            c = eng.stats(names.get((team, pos['x'], pos['y'])))
            lid = who.get((team, pos['x'], pos['y']))
        else:
            continue
        h = hist.get(lid)
        if h is None:
            out['no_history'] += 1
            continue
        e_t, r_t, near = h
        if E['shield'][i] > 0 and near:
            E['shield'][i] = rng.randint(0, E['shield'][i]); out['shield'] += 1
        if lid in observed:
            out['attack_observed'] += 1
            continue
        up = True
        if c.get('hides_when_not_attacking'):
            ut, ht = c.get('up_time_ms') or 0, c.get('hide_time_ms') or 0
            if e_t and e_t*50 < ut:
                st, ms, cap = 'Rising', ut - e_t*50, ut
            elif e_t or (r_t is not None and r_t*50 < ht):
                st, ms, cap = 'Up', ht - (r_t or 0)*50, ht
            else:
                st, ms, cap = 'Hidden', 0, 0
            if seen and lid in seen:
                if seen[lid] == 'Hidden':
                    st, ms, cap = 'Hidden', 0, 0
                elif st == 'Hidden':
                    st, ms, cap = 'Up', ht, ht
            E['hide'][i] = st
            E['hide_ms'][i] = max(0, min(cap, ms + rng.choice((-100, -50, 0, 50, 100)))) if cap else 0
            up = st == 'Up'; out['tesla_'+st] += 1
            if not up:
                E['target'][i] = None; E['target_locked'][i] = False; E['attack_ms'][i] = 0; E['attack_phase'][i] = 'Idle'
        if inferred and lid in inferred and up:
            elo, ehi, hs, lt = inferred[lid]
            e = rng.randrange(elo, ehi + 1, 50)
            E['attack_ms'][i] = e % hs; E['attack_phase'][i] = 'Windup' if e % hs else 'Cooldown'
            E['attack_load_ms'][i] = max(0, lt - e); out['swing_inferred'] += 1
            continue
        hs, lt = c.get('hit_speed_ms') or 0, c.get('load_time_ms') or 0
        if hs <= 0 or c.get('load_first_hit') or not up:
            continue
        reach = (c.get('range_milli') or 0)*18 + E['radius'][i]
        cand = []
        for j in live:
            if E['team'][j] == team or E['kind'][j] not in towers | {'Troop', 'Building'} or E['hide'][j] == 'Hidden':
                continue
            if c.get('target_only_buildings') and E['kind'][j] == 'Troop':
                continue
            if not (c.get('attacks_air') if E['flying'][j] else c.get('attacks_ground', True)):
                continue
            if math.hypot(E['pos'][j]['x']-pos['x'], E['pos'][j]['y']-pos['y']) <= reach + E['radius'][j]:
                cand.append(j)
        if cand and e_t:
            if not (E['target_locked'][i] and E['target'][i]):
                j = rng.choice(cand)
                E['target'][i] = {'index': j, 'generation': E['generation'][j]}
                out['target_ambiguous'] += len(cand) > 1
            top = hs - 50 if e_t*50 >= hs else min(hs - 50, lt + e_t*50 + 100)
            p = rng.randrange(0, top + 1, 50)
            E['attack_ms'][i] = p; E['attack_phase'][i] = 'Windup' if p else 'Idle'; E['attack_load_ms'][i] = 0
            out['swing'] += 1
        elif not e_t and r_t is not None and r_t*50 < lt:
            E['attack_load_ms'][i] = rng.randrange(0, lt - r_t*50 + 1, 50); out['reload'] += 1
    if after != before:
        try:
            load_edited(b, before, after)
        except Exception:
            out['perturb_not_set'] += 1
    return out


def rolled(roll, x, y, r, lo, hi):
    """Does a rolling spell's box (roll: landing tick t, speed v, length len, half width hw, half depth hd, direction
    fwd, centre x / y = the cast point) touch the disc (x, y, r) on some tick in lo..hi?"""
    a, b = max(lo, roll['t']), min(hi, roll['t'] + math.ceil(roll['len']/roll['v']))
    if a > b or abs(x - roll['x']) > roll['hw'] + r:
        return False
    ya, yb = (roll['y'] + roll['fwd']*min(roll['len'], roll['v']*(t - roll['t'])) for t in (a, b))
    return min(ya, yb) - roll['hd'] - r <= y <= max(ya, yb) + roll['hd'] + r


def card_view(rows, which, pairs, anchor, until, spell, reach, catalog, window=SPELL_WINDOW, roster=None):
    """What the anchor card did in one run: which = 1 the live frames, 2 the SIM's. Bodies are keyed by live id (a SIM
    body by its paired live id, else its own 's' id).
      own:   death tick (None = alive at the window end) of every body of the anchor's side and card that is not on the
             board at t0 and is born from anchor tick - 2 until the next same-card play (children included);
      tower: tower damage attributed to those bodies: each tower drop between two frames is split evenly over the
             distinct cards (the anchor's bodies counting as one) with a body in reach (range + radii) at the earlier frame;
      for an own spell: hit = enemy bodies that, within `window` ticks of the cast, drop >= half its body damage d in
             one frame gap, or vanish in one with hp <= d within `reach` of the cast point; enemy = death tick if killed
             by the spell (gone within 2 frames of its first hit; a later death is other cards' doing), else None;
             tower = the spell's crown damage per enemy tower in reach whose largest one-gap drop in that window is
             >= 80% of it.
    roster: max_hp values of the card's own units (hero anchors); a body with another max_hp born more than 12 ticks
    after the play is an ability summon and is not one of the card's bodies."""
    inv = {s: a for a, s in pairs.items() if s} if which == 2 else {}
    key = lambda bd: inv.get(bd['id'], bd['id'])
    name = lambda bd: bd['name'] if which == 2 else catalog.get(bd['card_id'], {}).get('display_name')
    t_end, tick, side = rows[-1][0], anchor['tick'], anchor['side']
    at0 = {bd['id'] for bd in rows[0][which] if not bd['tower']}
    life = {}
    for t, *bodies in rows:
        for bd in bodies[which-1]:
            if not bd['tower']:
                r = life.setdefault(key(bd), [t, t, bd['side'], name(bd), bd['id'] in at0, bd['max_hp']])
                r[1] = t
    death = lambda k: life[k][1] if life[k][1] < t_end else None
    if spell:
        lo, hi = tick-2, tick+window
        roll = spell.get('roll')
        first, enemy, drop, under = {}, {}, defaultdict(int), set()   # first: key -> tick of its first spell-sized hit
        for (ta, *ba), (tb, *bb) in zip(rows, rows[1:]):
            if not lo <= tb <= hi:
                continue
            prev = {key(bd): bd for bd in ba[which-1]}
            for bd in bb[which-1]:
                k = key(bd); p = prev.get(k)
                if bd['tower']:
                    if p and bd['side'] != side and math.hypot(bd['x']-spell['x'], bd['y']-spell['y']) <= spell['reach']:
                        drop[k] = max(drop[k], p['hp'] - max(0, bd['hp']))
                elif bd['side'] != side and not k.startswith('s'):
                    enemy[k] = None
                    if roll is None and p and p['hp'] - bd['hp'] >= spell['d']/2:
                        first.setdefault(k, tb)
            for k, p in prev.items():
                if p['tower'] or p['side'] == side or k.startswith('s'):
                    continue
                if roll is not None:        # rolled over in this gap (the live roll lands 0-1 tick after the table's): pass tick = gap end
                    r, fly = spell['body'](name(p), p['max_hp'], p['form'] if which == 2 else form_of(p['card_id'], catalog.get(p['card_id'], {})))
                    if life[k][0] == ta and rolled(roll, p['x'], p['y'], r, ta - 1, ta):
                        under.add(k)        # born under the box: not rolled over (live: the Hero Goblins' object, 0 of 3 hit)
                    if k not in first and k not in under and (roll['air'] or not fly) and rolled(roll, p['x'], p['y'], r, ta - 1, tb):
                        enemy[k] = None; first[k] = tb
                elif death(k) == ta and p['hp'] <= spell['d'] and math.hypot(p['x']-spell['x'], p['y']-spell['y']) <= spell['reach']:
                    enemy[k] = None; first.setdefault(k, ta)   # gone in this gap: a hit if the spell could kill it there
        for k, t in first.items():          # killed by the spell: gone within 2 frames of its first hit
            if death(k) is not None and death(k) <= t + 4:
                enemy[k] = death(k)
        tower = sum(spell['dt'] for v in drop.values() if spell['dt'] and v >= .8*spell['dt'])
        out = dict(spell=True, hit=sorted(first), enemy=enemy, tower=round(tower), end=t_end)
        if roll is not None:                # card_agree compares these bodies' deaths up to the earlier pass + 4
            out.update(passed=first, died={k: death(k) for k, r in life.items() if r[2] != side and not k.startswith('s')})
        return out
    own = {k for k, r in life.items() if r[2] == side and r[3] == anchor['name'] and not r[4] and tick-2 <= r[0] < until
           and (roster is None or r[5] in roster or r[0] <= tick + 12)}
    tower = 0.
    for (ta, *ba), (tb, *bb) in zip(rows, rows[1:]):
        now = {bd['id']: bd['hp'] for bd in bb[which-1] if bd['tower']}
        for tw in ba[which-1]:
            dmg = tw['hp'] - max(0, now.get(tw['id'], 0)) if tw['tower'] else 0
            if dmg <= 0:
                continue
            cards = {('A' if key(bd) in own else (bd['side'], name(bd))) for bd in ba[which-1]
                     if not bd['tower'] and bd['side'] != tw['side'] and name(bd)
                     and math.hypot(bd['x']-tw['x'], bd['y']-tw['y']) <= reach(name(bd)) + TOWER_RADIUS}
            if 'A' in cards:
                tower += dmg/len(cards)
    return dict(spell=False, own=sorted((death(k) for k in own), key=lambda d: (d is None, d or 0)), tower=round(tower), end=t_end)


def card_agree(a, b):
    """(agree, body mismatches, bodies, tower ok) of two card views of the same fight (live vs SIM, or SIM vs SIM)."""
    if a['spell'] and 'passed' in a and 'passed' in b:
        # A rolling spell: every body its box rolled over in either run, compared by its death (any cause) up to the
        # earlier pass + 4 ticks; a later death is other cards' doing (None), a body the run never had is 'missing'.
        def fate(v, k, h):
            if k not in v['died']:
                return 'missing'
            d = v['died'][k]
            return d if d is not None and d <= h else None
        pairs = []
        for k in set(a['passed']) | set(b['passed']):
            h = min(v['passed'][k] for v in (a, b) if k in v['passed']) + 4
            pairs.append((fate(a, k, h), fate(b, k, h)))
    elif a['spell']:
        keys = set(a['hit']) | set(b['hit'])
        pairs = [(a['enemy'].get(k, 'missing'), b['enemy'].get(k, 'missing')) for k in keys]
    else:
        n = max(len(a['own']), len(b['own']))
        pairs = list(zip(a['own'] + ['missing']*(n-len(a['own'])), b['own'] + ['missing']*(n-len(b['own']))))
    # A death in the last DEATH_TOL ticks of the window against a body alive at its end is not a disagreement: the alive
    # one may die within DEATH_TOL after the end (interval censoring; views without 'end', older outputs, keep the
    # strict rule).
    end = min(a.get('end') or 10**9, b.get('end') or 10**9)
    late = lambda d: d is not None and d >= end - DEATH_TOL
    same = lambda x, y: 'missing' not in (x, y) and (((x is None) == (y is None) and (x is None or abs(x-y) <= DEATH_TOL))
                                                     or (x is None and late(y)) or (y is None and late(x)))
    mis = sum(not same(x, y) for x, y in pairs)
    tower_ok = abs(a['tower']-b['tower']) <= max(TOWER_FLOOR, TOWER_REL*max(a['tower'], b['tower']))
    return mis <= int(SWARM_SLACK*len(pairs)) and tower_ok, mis, len(pairs), tower_ok


def seen_targets(m, fight, setup, start, look=20):
    """Ext logs: [(source ref, target ref)] from projectiles in flight in the `look` ticks up to t0 whose shooter and target
    are both on the t0 board (ranged units and towers; the latest shot per shooter wins). The reader's target is the
    engine's (target point = target body, READER_VALIDATION_1016). ref: ('body', setup body) | ('tower', side, x, y).
    Tesla and melee targets have no projectile and stay unset."""
    t0, i0 = fight['t0'], fight['frame0']
    by = {bd['id']: bd for bd in setup}
    towers = {bd['id']: ('tower', bd['side'], bd['x'], bd['y']) for bd in start if bd['tower'] and bd['hp'] > 0}
    ref = lambda k: ('body', by[k]) if k in by else towers.get(k)
    last = {}
    for t, _ in m['frames'][max(0, i0-look):i0+1]:
        if t < t0 - look:
            continue
        for p in m['proj'].get(t, ()):
            s, g = (ref(p[7]) if p[7] else None), (ref(p[8]) if p[8] else None)
            if s and g:
                last[p[7]] = (s, g)
    return list(last.values())


def infer_attacks(m, fight, atk, look=100):
    """Opt-in (PARITY_INFER, item 8): each t0-board attacker's last hit before t0, inferred from the live frames of the
    last `look` ticks. atk: {live id: dict(dmg, dmg_tower, reach, speed)} (speed: projectile mt/tick, None = melee/instant).
      * a victim's one-gap hp drop equal (+-1) to exactly one in-reach enemy's per-hit damage (or +-2 to exactly one pair's
        sum) is that attacker's hit, somewhere in (earlier frame, later frame]; a projectile attacker's hit is its launch,
        so the travel time (distance / speed) is taken off;
      * ext logs: a ranged attacker's launches are its projectiles' first sightings (source = that body), victim = target.
    Returns {live id: (lo, hi, victim id)}: the last hit's tick range and its victim (nearest one for a splash)."""
    t0, i0 = fight['t0'], fight['frame0']
    fr = [f for f in m['frames'][max(0, i0-80):i0+1] if f[0] >= t0 - look]
    ext = {a for a, s in atk.items() if s['speed'] and m.get('ext')}
    seen = {p[6] for p in m.get('proj', {}).get(fr[0][0], ())} if fr else set()
    last = {}

    def credit(a, lo, hi, v, d):
        if a not in last or (hi, -d) >= (last[a][1], -last[a][3]):
            last[a] = (lo, hi, v, d)
    for (ta, A), (tb, B) in zip(fr, fr[1:]):
        prev = {bd['id']: bd for bd in A}
        for p in m.get('proj', {}).get(tb, ()):
            if p[6] not in seen:
                seen.add(p[6])
                if p[7] in ext and p[8] and p[7] in prev and p[8] in prev:
                    credit(p[7], ta+1, tb, p[8], math.hypot(prev[p[7]]['x']-prev[p[8]]['x'], prev[p[7]]['y']-prev[p[8]]['y']))
        for v in B:
            p = prev.get(v['id'])
            if not p or v['hp'] >= p['hp']:
                continue
            d = p['hp'] - v['hp']
            dist = {a: math.hypot(prev[a]['x']-p['x'], prev[a]['y']-p['y']) for a in atk
                    if a in prev and a not in ext and prev[a]['side'] != v['side']}
            cand = [a for a, x in dist.items() if x <= atk[a]['reach']]
            dd = lambda a: atk[a]['dmg_tower'] if v['tower'] else atk[a]['dmg']
            hits = [a for a in cand if abs(d - dd(a)) <= 1]
            if not hits:
                two = [(a, b) for j, a in enumerate(cand) for b in cand[j+1:] if abs(d - dd(a) - dd(b)) <= 2]
                hits = list(two[0]) if len(two) == 1 else []
            if len(hits) > 2 or (len(hits) == 2 and abs(d - dd(hits[0]) - dd(hits[1])) > 2):
                continue                                   # several attackers deal this damage: ambiguous
            for a in hits:
                tr = math.ceil(dist[a]/atk[a]['speed']) if atk[a]['speed'] else 0
                credit(a, ta+1-tr, tb-tr, v['id'], dist[a])
    return {a: r[:3] for a, r in last.items()}


def start_state(eng, m, fight, setup, start, events, catalog):
    """Ext logs: ([(ref, {SIM entity field: value})], flags) for the t0 board, from what the reader shows:
      * Tesla: behavior_state_raw 0 = Hidden, 2 = Up (hide timer full);
      * a charger (card table 'charge') walking in state 1: charged if its last frame gap ran >= 1.6x its walk speed,
        else charge_progress = walked millitiles x CHARGE_PER_MT (below the charge threshold);
      * a body in a Mega Knight jump, river jump or tunnel (state 3 / 5 / 6): no SIM setup -> flag setup_mid_jump;
      * stun-type status: from the phase-2 buffs at t0 (STUN_BUFFS -> stun_ms; any other buff is flagged status_unset:<name>),
        else from a seen Freeze still running (bodies and towers within its radius at the cast -> stun_ms left).
    A proxy (child set up as another card) gets nothing."""
    t0, i0 = fight['t0'], fight['frame0']
    out, flags = [], Counter()
    live = {bd['id']: bd for bd in start}
    by = {bd['id']: bd for bd in setup}
    hist = defaultdict(list)
    for t, bodies in m['frames'][max(0, i0-60):i0+1]:
        for bd in bodies:
            hist[bd['id']].append((t, bd['x'], bd['y'], bd.get('state')))
    for bd in setup:
        a = live.get(bd['id'])
        st = a.get('state') if a else None
        if st is None or bd.get('proxy'):
            continue
        c = eng.stats(catalog[a['card_id']]['display_name'])
        if st in MID_JUMP:
            flags[f'setup_mid_jump:{st}'] += 1
        if c.get('hides_when_not_attacking') and st in (0, 2):
            out.append((('body', bd), dict(hide='Up', hide_ms=c.get('hide_time_ms') or 0) if st == 2 else dict(hide='Hidden', hide_ms=0)))
            flags['setup_tesla_' + ('up' if st == 2 else 'hidden')] += 1
        ch = c.get('charge')
        if ch and st == 1 and len(hist[bd['id']]) >= 2:
            h = hist[bd['id']]
            (ta, xa, ya, _), (tb, xb, yb, _) = h[-2], h[-1]
            if math.hypot(xb-xa, yb-ya)/max(1, tb-ta) >= 1.6*(c.get('speed') or 60):
                out.append((('body', bd), dict(charged=True, charge_progress=0))); flags['setup_charged'] += 1
            else:
                walked = 0.
                for (_, x0, y0, s0), (_, x1, y1, _) in zip(h[-2::-1], h[::-1]):
                    if s0 != 1:
                        break
                    walked += math.hypot(x1-x0, y1-y0)
                full = (ch.get('charge_range_raw') or 0)*10*CHARGE_PER_MT
                out.append((('body', bd), dict(charge_progress=min(round(walked*CHARGE_PER_MT), max(0, full-1)))))
                flags['setup_charge_progress'] += 1
    # Spawner timers: a setup spawn starts its cycle fresh (Fire Spirit Hut 1950 ms, Tombstone at once), the live one is
    # mid-cycle. Its last wave is seen: children of the same side and card, smaller max_hp, first seen within 3.5 tiles
    # of it. The SIM record is set to what it holds that many ticks after the same child of a wave (spawn_table).
    tick_of = [t for t, _ in m['frames']]
    tr = None
    for bd in setup:
        a = live.get(bd['id'])
        tab = eng.spawn_table(catalog[a['card_id']]['display_name'], probe=False) if a and not bd.get('proxy') else None
        if not tab:
            continue
        if tr is None:
            tr = tracks(m['frames'][max(0, i0-200):i0+1])
        kids = []
        for r in tr.values():
            if r['side'] != a['side'] or r['card_id'] != a['card_id'] or r['id'] == a['id'] or r['max_hp'] >= .9*a['max_hp']:
                continue
            p = next((q for q in hist.get(a['id'], ()) if q[0] == r['first']), None) or                 next(((t, b['x'], b['y']) for t, bodies in m['frames'][max(0, i0-200):i0+1] if t == r['first']
                      for b in bodies if b['id'] == a['id']), None)
            if p and math.hypot(p[1]-r['x'], p[2]-r['y']) <= 3500:
                j = bisect_left(tick_of, r['first'])
                prev = tick_of[j-1] if j else r['first'] - 2
                kids.append((prev + 1 + r['first'])//2)
        if not kids:
            flags['setup_spawner_unseen'] += 1; continue
        kids.sort()
        last, k = kids[-1], 1
        for t in kids[-2::-1]:
            if last - t > 13:
                break
            k += 1
        ms, wl = tab[min(tab, key=lambda q: abs(q - k))]
        left = ms - 50*(t0 - last)
        if left <= 0:
            flags['setup_spawner_overdue'] += 1; continue
        out.append((('body', bd), dict(spawn_ms=left, spawn_wave_left=wl))); flags['setup_spawner_seen'] += 1
    buffs = m.get('buffs') or {}
    tb = max((t for t in buffs if t0-6 <= t <= t0), default=None)
    def ref_of(bd):
        return ('tower', bd['side'], bd['x'], bd['y']) if bd['tower'] else (('body', by[bd['id']]) if bd['id'] in by else None)
    if tb is not None:
        gens = {bd['gen']: bd for bd in start if 'gen' in bd}
        for g, rows in buffs[tb].items():
            bd = gens.get(g)
            r = ref_of(bd) if bd else None
            for name, rem in rows:
                rem -= 50*(t0-tb)
                if r is None or rem <= 0 or rem > SENTINEL_MS:
                    continue
                if name in STUN_BUFFS:
                    out.append((r, dict(stun_ms=rem))); flags['setup_stun_buff'] += 1
                elif name in SLOW_BUFFS and eng.slow_ids().get(SLOW_BUFFS[name]):
                    out.append((r, dict(buff=(eng.slow_ids()[SLOW_BUFFS[name]], rem)))); flags['setup_slow_buff'] += 1
                else:
                    flags['status_unset:'+name] += 1
        return out, flags
    # No phase-2 rows: an Ice Wizard shot that hit a t0-board body within IW_SLOW_MS before t0 left its slow running.
    for k, (form, rem) in iw_shots(m, fight, catalog).items():
        r = ref_of(live[k]) if k in live else None
        sid = eng.slow_ids().get('hero' if form == 2 else 'base')
        if r and sid:
            out.append((r, dict(buff=(sid, rem)))); flags['setup_slow_shot'] += 1
    bt, rad = eng.effect_life('Freeze', 'buff_time_ms') or 3500, eng.stats('Freeze').get('area_damage_radius_milli') or 3000
    for e in events:
        if e.get('source') != 'spell_seen' or e['name'] != 'Freeze' or not e.get('made') or not e['made'] <= t0 < e['made'] + bt//50:
            continue
        at = next((bodies for t, bodies in m['frames'] if t >= e['made']), [])
        hit = {bd['id'] for bd in at if bd['side'] != e['side'] and (not bd['tower'] or bd['hp'] > 0)
               and math.hypot(bd['x']-e['x'], bd['y']-e['y']) <= rad + (1000 if bd['tower'] else 500)}
        for k in hit:
            r = ref_of(live[k]) if k in live else None
            if r:
                out.append((r, dict(stun_ms=bt - 50*(t0-e['made'])))); flags['setup_stun_fx'] += 1
    return out, flags


def phase3_state(eng, m, fight, setup, start, catalog):
    """Logs with phase-3 rows (m['attacks']): ([(ref, {SIM entity field: value})], {live id}, flags) -- the attack state
    of every t0-board body (setup bodies and towers, not proxies) as the reader shows it at t0, or at t0 - 1 advanced one
    tick by the measured rule (ATTACK_PHASE_1016: progress += step, 50 / 35 under an Ice Wizard slow / 0 frozen,
    carried across hits; the load timer re-armed to LoadTime on the crossing tick, else -50, held while frozen):
      * attack_ms = progress (the SIM's count-up counter, same rule), attack_load_ms = load;
      * attack_phase: Idle at progress 0, Cooldown on the fire tick (progress mod HitSpeed < step), else Windup;
      * target = the body / tower with the target's generation id (None when the reader shows none); target_locked as
        the SIM sets it after a step (projectile attackers in Windup; probed on 0.1.35: Musketeer / X-Bow 1, Knight /
        Tesla 0).
    Not set (no SIM field): the previous target, the pre-attack countdown, the attack-sequence index (flagged when
    non-zero). The live ids returned are observed: the ceiling does not redraw their attack state (perturb)."""
    att = m.get('attacks') or {}
    t0 = fight['t0']
    tb = max((t for t in att if t0 - 1 <= t <= t0), default=None)
    out, seen, flags = [], set(), Counter()
    if tb is None:
        return out, seen, flags
    by = {bd['id']: bd for bd in setup}
    gens = {bd['gen']: bd for bd in start if 'gen' in bd}

    def ref_of(bd):
        return ('tower', bd['side'], bd['x'], bd['y']) if bd['tower'] else (('body', by[bd['id']]) if bd['id'] in by else None)
    buffs = (m.get('buffs') or {}).get(max((t for t in m.get('buffs') or {} if t0 - 6 <= t <= t0), default=None), {})
    for g, (tg, _prev, prog, load, pre, seq) in att[tb].items():
        bd = gens.get(g)
        r = ref_of(bd) if bd and (bd['tower'] or not by.get(bd['id'], {}).get('proxy')) else None
        if r is None or (bd['tower'] and bd['hp'] <= 0):
            continue
        st = eng.stats(('KingTower' if bd['id'].endswith('K') else 'PrincessTower') if bd['tower'] else catalog[bd['card_id']]['display_name'])
        hs, lt = st.get('hit_speed_ms') or 0, max(0, st.get('load_time_ms') or 0)
        if hs <= 0:
            flags['setup_p3_no_hit_speed'] += 1; continue
        names = [n for n, _ in buffs.get(g, ())]
        # ponytail: Freeze / Rage-type buffs other than these names step 50; add their multipliers if a capture shows one
        step = 0 if any('Freeze' in n or n in STUN_BUFFS for n in names) else 35 if any(n in SLOW_BUFFS for n in names) else 50
        if tb < t0:
            if prog > 0:
                load = lt if (prog + step)//hs > prog//hs else load if step == 0 else max(0, load - 50)
                prog += step
            else:
                load = max(0, load - 50)
        tref = None
        if tg is not None:
            tbd = gens.get(tg)
            tref = ref_of(tbd) if tbd and (tbd['tower'] or not by.get(tbd['id'], {}).get('proxy')) else None
            if tref is None:
                flags['setup_p3_target_unresolved'] += 1
        phase = 'Idle' if prog <= 0 else 'Cooldown' if prog % hs < step else 'Windup'
        out.append((r, dict(attack_ms=prog, attack_load_ms=load, attack_phase=phase, target=tref,
                            target_locked=bool(st.get('projectile')) and phase == 'Windup' and tref is not None)))
        seen.add(bd['id']); flags['setup_p3_attack'] += 1
        flags['setup_p3_pre_unset'] += pre != 0
        flags['setup_p3_seq_unset'] += seq != 0
    flags['setup_p3_from_previous_tick'] += tb < t0 and bool(out)
    return out, seen, +flags


def set_buff(E, i, bid, ms):
    """Write buff `bid` with `ms` left into entity i's first free slot of a save's ents; False if none is free. The
    save's buffs list is FLAT (IW_SLOW_1016 §2): entity i owns buffs[i*slots:(i+1)*slots], slots = len(buffs) // n."""
    slots = len(E['buffs']) // len(E['alive'])
    j = next((i*slots + j for j in range(slots) if not E['buffs'][i*slots + j]['id']), None)
    if j is None:
        return False
    E['buffs'][j] = dict(E['buffs'][j], id=bid, ms=ms)
    return True


def iw_shots(m, fight, catalog):
    """Ext logs: {live id: (shooter form, slow ms left at t0)} for t0-board bodies an Ice Wizard projectile hit within
    IW_SLOW_MS before t0 (shooter = the projectile's card, any form). A projectile is last seen the frame before it hits:
    the hit is taken at that sighting + 1 tick; one still flying at t0 is left out (the SIM has no setup for it). The
    latest hit per target wins (each hit re-arms the slow). Splash victims other than the target are not seen."""
    t0, i0 = fight['t0'], fight['frame0']
    shots = {}
    for t, _ in m['frames'][max(0, i0-IW_SLOW_MS//50):i0+1]:
        for p in m.get('proj', {}).get(t, ()):
            c = catalog.get(p[3])
            if c and c['display_name'] == 'IceWizard' and p[8]:
                shots[p[6]] = (t, p[8], form_of(p[3], c))
    out = {}
    for last, tgt, form in sorted(shots.values()):
        rem = IW_SLOW_MS - 50*(t0 - last - 1)
        if last < t0 and 0 < rem <= IW_SLOW_MS:
            out[tgt] = (form, rem)
    return out


def inflight_shots(m, fight, start, catalog, levels, tower_levels):
    """Ext logs: the projectiles in flight at t0 (the t0 frame's proj rows) that a t0-board body or tower fired at a
    t0-board body or tower -> [dict(src, tgt: live ids, x, y: its live position, key: Engine.shot_template key)]. Spells
    are left out (seen casts; spell_in_flight_at_start), and so are shots without a source or a target (kamikaze Fire /
    Ice Spirits, a Bowler's rolling boulder, an Executioner's returning axe)."""
    by = {bd['id']: bd for bd in start}
    out = []
    for p in m['proj'].get(fight['t0'], ()):
        if (catalog.get(p[3]) or {}).get('type') == 'spell':
            continue
        src, tgt = by.get(p[7]), by.get(p[8])
        if not src or not tgt or (tgt['tower'] and tgt['hp'] <= 0):
            continue
        if src['tower']:
            key = ('KingTower' if src['id'].endswith('K') else 'PrincessTower', 0, tower_levels[src['side']])
        else:
            c = catalog.get(src['card_id'])
            if c is None:
                continue
            name = c['display_name']
            key = (name, form_of(src['card_id'], c), levels.get((src['side'], name)) or levels.get((src['side'], '*')) or 15)
        out.append(dict(src=src['id'], tgt=tgt['id'], x=p[1], y=p[2], key=key))
    return out


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


def initial_pairs(rows, setup, catalog=None):
    """live id -> sim id. Setup pairing: each setup spawn sits on its live point at t0 (spawn order is canonical, not list
    order). By point, not name, so a child set up as a proxy card (a Witch's Skeleton as a Skeletons body) pairs too.
    With `catalog`, the pairing is also grown over every row (pair_frame), as measure() grows it."""
    pairs = {bd['id']: None for bd in setup}
    _, live0, sim0 = rows[0]
    free = [s for s in sim0 if not s['tower']]
    for a in setup:
        if free:
            d, s = min((math.hypot(a['x']-s['x'], a['y']-s['y']), s['id']) for s in free if s['side'] == a['side'])                 if any(s['side'] == a['side'] for s in free) else (1e9, None)
            if d < 60:
                pairs[a['id']] = s; free = [f for f in free if f['id'] != s]
    if catalog is not None:
        for _, live, simb in rows:
            pair_frame(pairs, live, simb, catalog)
    return pairs


def measure(rows, setup, flags, catalog, stamp):
    if not rows:
        return dict(flags=dict(flags), error='no_rows')
    setup_ids = {bd['id'] for bd in setup}
    pairs = initial_pairs(rows, setup)
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


def run_match(path, window, out_dir, ceiling=0):
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
    eng = Engine()
    events, delay = deployments(m, catalog, eng.effect_life, own_unit=lambda n, hp: eng.level(n, hp) is not None)
    fights = cut(m, events, window)
    m['buffs'] = phase2_buffs(path) if m['ext'] else {}
    m['attacks'] = phase3_attacks(path) if m['ext'] else {}
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
    levels.update(spell_levels(m, events, eng, catalog))
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
            r = run_fight(eng, m, events, f, catalog, by_name, levels, tw, top, ceiling)
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
                   seconds=round(time.monotonic()-t_start, 1), stamp=eng.stamp, ceiling_k=ceiling)
    if m['ext']:
        summary.update(ext=True, phase2=bool(m['buffs']),
                       seen=dict(Counter(f"{e['kind']}:{'own' if e['side'] == m['side'] else 'opp'}:{e['name']}"
                                         for e in events if e['source'] in ('spell_seen', 'cast_seen'))))
        if m['attacks']:
            summary['phase3'] = True
    out.write_text(json.dumps(dict(summary=summary, fights=results), allow_nan=False))
    return summary


def spell_drops(m, events, name, look=70, side=None, towers=False):
    """Single-frame hp drops on enemy non-tower bodies (towers=True: on standing enemy crown towers) within `look`
    ticks of each `side` (default own) cast of spell `name`."""
    side = m['side'] if side is None else side
    ticks = [t for t, _ in m['frames']]
    out = Counter()
    for e in events:
        if e['source'] not in SPELL_SOURCES or e['name'] != name or e.get('side', m['side']) != side:
            continue
        i = bisect_left(ticks, e['tick'] - 4)
        win = [{b['id']: b for b in bodies} for t, bodies in m['frames'][max(0, i-1):] if t <= e['tick'] + look]
        for a, b in zip(win, win[1:]):
            for k, z in b.items():
                if k in a and z['tower'] == towers and z['side'] != side and z['hp'] < a[k]['hp'] and (not towers or a[k]['hp'] > 0):
                    out[a[k]['hp'] - (max(0, z['hp']) if towers else z['hp'])] += 1
    return out


def spell_levels(m, events, eng, catalog, lo=6):
    """{(own side, spell): level} for own spells whose SIM damage at that level is the most frequent exact live drop
    (>= 2 drops). A spell is never seen as a body, so its level is otherwise the side's modal level: the own Log is
    level 15 live (390 per hit, 465 drops) while the modal 16 hits for 429 (diag1016)."""
    out = {}
    spells = [e for e in events if e['source'] in SPELL_SOURCES]
    for name in {e['name'] for e in spells}:          # a set, as before: old logs keep their levels' key order
        if name not in eng.ids:
            continue
        for side in sorted({e.get('side', m['side']) for e in spells if e['name'] == name}):
            drops = spell_drops(m, events, name, side=side)
            score = []
            for lv in range(16, lo-1, -1):
                d = eng.spell_damage(name, side, lv)
                if d:
                    score.append((drops[d], lv))
            best = max(score, default=(0, None))
            if best[0] >= 2:
                out[side, name] = best[1]
                continue
            # Fewer than 2 exact drops (an opponent spell is often cast once or twice: 221839's opponent Log is level 12,
            # one exact 295 drop, while the side's modal troop level 16 hits for 429): the level with the most exact
            # drops on bodies plus exact crown-tower drops (+-1, the crown rounding; only for a spell whose card carries
            # its crown percent: an area spell's lives on its area object), if that level is the only one with the most
            # (diag_night/log, second round).
            pct = eng.stats(name).get('crown_tower_damage_percent')
            towers = spell_drops(m, events, name, side=side, towers=True) if pct else Counter()
            ev = Counter()
            for lv in range(16, lo-1, -1):
                d = eng.spell_damage(name, side, lv)
                if d:
                    ev[lv] = drops[d] + (sum(towers[round(d*pct/100) + j] for j in (-1, 0, 1)) if pct else 0)
            top = ev.most_common(2)
            if top and top[0][1] >= 1 and (len(top) == 1 or top[1][1] < top[0][1]):
                out[side, name] = top[0][0]
    return out


# ---------------------------------------------------------------- scoreboard

def fight_verdict(r, tower_tol):
    """Outcome agreement = the fight's focus bodies end alive/dead the same, the first body to die is the same, and each
    tower's damage is within max(tol, 15%). Focus = the anchor's own bodies; for a spell anchor, the enemy bodies on the
    board when it was cast."""
    a = r['anchor']
    bodies = [b for b in r['bodies'] if b['paired']]
    if a['source'] in SPELL_SOURCES:
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
                  'spell_spawned_units_timing_unknown', 'card_not_in_sim', 'play_refused', 'sim_game_over',
                  'setup_mid_jump')


HIDDEN_INFO = ('opp_spell_seen', 'opp_ability_unobserved')


def is_clean(r, mode='strict'):
    """strict: no blocker at all. core: hidden opponent actions allowed (spells, hero/champion buttons). all: any fight."""
    if mode == 'all':
        return True
    skip = HIDDEN_INFO if mode == 'core' else ()
    return not any(k.startswith(CLEAN_BLOCKERS) and not k.startswith(skip) for k in r['flags'])


GOAL_CARD, GOAL_ALL, GOAL_N = .95, .975, 30     # owner goal RAISED 10-16 night (was .90 / .95): normalised lower 95% CI per card / overall; min n


def card_scores(r):
    """One fight's tolerant card agreements (CEILING.md), or None without card views:
    a0 live vs the unperturbed SIM; aK live vs the perturbed SIMs (mean); ceil the perturbed SIMs pairwise (mean);
    plus body-mismatch and tower-failure counts for live (vs unperturbed) and ceiling (pairwise)."""
    c = r.get('card')
    if not c or c['sim'][0] is None:
        return None
    L, s0, P = c['live'], c['sim'][0], [s for s in c['sim'][1:] if s is not None]
    a0 = card_agree(L, s0)
    aP = [card_agree(L, s) for s in P]
    pp = [card_agree(P[i], P[j]) for i in range(len(P)) for j in range(i+1, len(P))]
    mean = lambda xs, k: sum(x[k] for x in xs)/len(xs)
    return dict(a0=a0[0], aK=mean(aP, 0) if aP else a0[0], ceil=mean(pp, 0) if pp else None,
                bmis=a0[1], bn=a0[2], tfail=not a0[3],
                bmis_c=mean(pp, 1) if pp else None, bn_c=mean(pp, 2) if pp else None, tfail_c=1-mean(pp, 3) if pp else None)


def boot_ci(items, f, B=2000, seed=0):
    """95% percentile CI of f(list of values) under a bootstrap that resamples MATCHES (fights in a match share
    windows and hidden state). items: [(match, value)]."""
    import random
    by = defaultdict(list)
    for k, v in items:
        by[k].append(v)
    keys, rng, out = sorted(by), random.Random(seed), []
    for _ in range(B):
        v = f([x for k in rng.choices(keys, k=len(keys)) for x in by[k]])
        if v is not None:
            out.append(v)
    out.sort()
    return (round(out[int(.025*len(out))], 3), round(out[max(0, int(.975*len(out))-1)], 3)) if out else (None, None)


def ceiling_table(out_dir, clean, mode):
    """Per-card tolerant agreement vs the noise ceiling -> ceiling_{mode}.json + CEILING_{mode}.txt."""
    groups = defaultdict(list)
    for r in clean:
        s = card_scores(r)
        if s is None:
            continue
        a = r['anchor']
        s.update(match=r['match'], outcome=r['verdict']['agree'])
        groups[('own ' if r['own'] else 'opp ') + a['name'] + ('', ' evo', ' hero')[a['form']]].append(s)
    agree = lambda xs: sum(x['aK'] for x in xs)/len(xs)
    def norm(xs):
        c = [x['ceil'] for x in xs if x['ceil'] is not None]
        return agree(xs)/(sum(c)/len(c)) if c and sum(c) else None
    def row(label, xs, goal):
        ceil = [x['ceil'] for x in xs if x['ceil'] is not None]
        items = [(x['match'], x) for x in xs]
        nm = norm(xs); nlo, nhi = boot_ci(items, norm)
        flag = ('insufficient n' if len(xs) < GOAL_N else 'no ceiling' if nm is None else
                'MEETS' if nlo is not None and nlo >= goal else 'below')
        bn, bnc = sum(x['bn'] for x in xs), sum(x['bn_c'] or 0 for x in xs)
        return dict(card=label, n=len(xs), matches=len({x['match'] for x in xs}),
                    agree_unperturbed=round(sum(x['a0'] for x in xs)/len(xs), 3),
                    agree=round(agree(xs), 3), agree_ci=boot_ci(items, agree),
                    ceiling=round(sum(ceil)/len(ceil), 3) if ceil else None,
                    normalised=round(nm, 3) if nm is not None else None, normalised_ci=(nlo, nhi), goal=goal, flag=flag,
                    whole_fight_outcome=round(sum(x['outcome'] for x in xs)/len(xs), 3),
                    body_miss=round(sum(x['bmis'] for x in xs)/bn, 3) if bn else None,
                    body_miss_ceiling=round(sum(x['bmis_c'] or 0 for x in xs)/bnc, 3) if bnc else None,
                    tower_fail=round(sum(x['tfail'] for x in xs)/len(xs), 3),
                    tower_fail_ceiling=round(sum(x['tfail_c'] for x in xs if x['tfail_c'] is not None)/len(ceil), 3) if ceil else None)
    rows = sorted((row(k, v, GOAL_CARD) for k, v in groups.items()), key=lambda r: -r['n'])
    every = [x for v in groups.values() for x in v]
    overall = row('OVERALL', every, GOAL_ALL) if every else None
    out = dict(mode=mode, definitions=dict(DEATH_TOL=DEATH_TOL, SWARM_SLACK=SWARM_SLACK, TOWER_FLOOR=TOWER_FLOOR,
                                           TOWER_REL=TOWER_REL, SPELL_WINDOW=SPELL_WINDOW, GOAL_CARD=GOAL_CARD,
                                           GOAL_ALL=GOAL_ALL, GOAL_N=GOAL_N),
               k=max((len(r['card']['sim'])-1 for r in clean if r.get('card')), default=0), overall=overall, cards=rows)
    Path(out_dir, f'ceiling_{mode}.json').write_text(json.dumps(out, indent=1))
    f = lambda r: (f"{r['card']} | {r['n']} | {r['matches']} | {r['agree_unperturbed']} | {r['agree']} {list(r['agree_ci'])} | "
                   f"{r['ceiling']} | {r['normalised']} {list(r['normalised_ci'])} | {r['flag']} | {r['whole_fight_outcome']} | "
                   f"{r['body_miss']}/{r['body_miss_ceiling']} | {r['tower_fail']}/{r['tower_fail_ceiling']}")
    L = [f"CEILING [{mode}] K={out['k']} perturbed replays per fight; tolerant card agreement (CEILING.md); goal: normalised "
         f"lower 95% CI >= {GOAL_CARD} per card (n >= {GOAL_N}), >= {GOAL_ALL} overall", '',
         'card | n | matches | agree unperturbed | agree (live vs perturbed) [95% CI] | ceiling (perturbed pairwise) | '
         'normalised [95% CI] | flag | whole-fight outcome | body miss live/ceiling | tower fail live/ceiling']
    L += [f(overall), ''] if overall else []
    L += [f(r) for r in rows]
    Path(out_dir, f'CEILING_{mode}.txt').write_text('\n'.join(L)+'\n')
    return out


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
    ceiling_table(out_dir, clean, mode)
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
    ap.add_argument('mode', choices=['run', 'score', 'buffs', 'attacks'])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--live', type=Path, default=ps.LIVE)
    ap.add_argument('--files', default='live_play_2026101[5-9]_*.jsonl')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--stride', type=int, default=1, help='every Nth matching file (a spread prototype sample)')
    ap.add_argument('--max-fights', type=int, default=0, help='prototype: cap fights per match (0 = all)')
    ap.add_argument('--window', type=int, default=240, help='fight length, ticks (240 = 12 s)')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--ceiling', type=int, default=0, help='noise ceiling: K perturbed SIM replays per fight (0 = off; CEILING.md)')
    ap.add_argument('--clean', choices=['strict', 'core', 'all'], default='strict', help='score: which fights count (is_clean)')
    ap.add_argument('--infer', default='', help="opt-in attack inference at setup: 'target', 'phase' or 'target,phase' (PARITY_INFER)")
    a = ap.parse_args()
    if a.mode == 'buffs':      # phase-2 buff rows of every local capture -> one file for PARITY_BUFFS (no addresses)
        logs = {json.loads(r.read_text()).get('live_log') for r in sorted(P2_DIR.glob('*/run.json')) + p3_runs()}
        out = {n: phase2_buffs(n) for n in sorted(filter(None, logs))}
        a.out.write_text(json.dumps(out))
        print({n: len(v) for n, v in out.items()}); return 0
    if a.mode == 'attacks':    # phase-3 attack rows (generation ids, counters; no addresses) -> one file for PARITY_ATTACKS
        logs = {json.loads(r.read_text()).get('live_log') for r in p3_runs()}
        out = {n: phase3_attacks(n) for n in sorted(filter(None, logs))}
        a.out.write_text(json.dumps(out, separators=(',', ':')))
        print({n: len(v) for n, v in out.items()}); return 0
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
    if a.infer:
        os.environ['PARITY_INFER'] = a.infer
    t = time.monotonic()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_match, str(p), a.window, str(a.out), a.ceiling): p for p in paths}
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
