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
# W19 round 2 (client-dated card tables): a capture from the 2026-10-19 balance update on replays on that client's table
# (fork fin16: client160402017_20261019, the Skeletons' 500 ring + middle-column split, W23's stat changes); older captures
# keep the 10-06 table. The update shipped between our last pre-update main-account match (10-19 08:47) and the first after
# it (13:56); W23 dated it 05:58-06:03 from exact-value tower hits. PARITY_TABLE_1019=0 keeps every match on the 10-06 table (a pre-fin16 wheel has no 10-19 table).
TABLE_1019, TABLE_1019_FROM = 'client160402017_20261019', '20261019_0600'   # W23: the update landed 05:58:41-06:03:27 EDT
DATED_TABLES = os.environ.get('PARITY_TABLE_1019', '0') == '1'


def table_for(stem):
    return TABLE_1019 if DATED_TABLES and stem[10:23] >= TABLE_1019_FROM else CARD_TABLE
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
CUBE_LAG = 6                       # H-CUBE-DATE: the SIM makes a Hero IW ice cube 6 ticks after the press (cubeprobe.py)
# Tolerant card-level scoring (owner goal 10-16; CEILING.md). A card's bodies agree when they end alive/dead the same and
# deaths are within DEATH_TOL ticks (0.5 s); a swarm may miss floor(SWARM_SLACK x n) bodies. Its tower damage agrees
# within max(TOWER_FLOOR, TOWER_REL x the larger side). TOWER_FLOOR ~ one X-Bow bolt (98) and above one Log crown hit (51).
DEATH_TOL, SWARM_SLACK, TOWER_FLOOR, TOWER_REL = 10, .1, 100, .1
TIME_OUT_TICK = 6000               # the ladder match's end (180 s + 120 s overtime at 20 ticks/s), the live frames' tick base
LEAD_AHEAD = {'Rascals': 2000}     # the SIM formation's lead body ahead of its play point (H-RASCALS). ponytail: hardcoded; probe the formation if another card needs it
SPELL_WINDOW = 60                 # ticks after a cast in which a drop/death counts as the spell's hit
# H-PRESPELL (cut): the DEFAULT since the lead's 10-20 decision ('spawn'); PARITY_PRESPELL=off restores the pre-10-20 cohort, 'all' widens it
PRESPELL = {'off': ''}.get(os.environ.get('PARITY_PRESPELL', 'spawn'), os.environ.get('PARITY_PRESPELL', 'spawn'))
PRESPELL_SPAWN = {'GoblinBarrel', 'Graveyard'}
# H-CHAMP-CASTS (W8 round 5, default on; PARITY_CHAMP_CASTS=0 off): the champions whose press shows a state-10 burst live (Skeleton King,
# Monk, Mighty Miner; the Golden Knight shows none) are dated from it as hero casts are, replayed through the ability slot,
# and no longer flag their fights opp_ability_unobserved on ext logs
CHAMP_CASTS = os.environ.get('PARITY_CHAMP_CASTS', '1') != '0'   # the default since 10-20 (as H-PRESPELL); PARITY_CHAMP_CASTS=0 restores
CHAMP_STATE10 = {'SkeletonKing', 'Monk', 'MightyMiner'} | set(filter(None, os.environ.get('SME_CHAMP_EXTRA', '').split(',')))   # SME-F1FIX-3: SME_CHAMP_EXTRA=LittlePrince (off by default)
SPAWN_SLOW = os.environ.get('PARITY_SPAWN_SLOW', '1') == '1'   # H-SPAWN-SLOW (W19 round 1, kept: +11 / -4 on 43,867 fights); PARITY_SPAWN_SLOW=0 restores
FORM_ORACLE = set(filter(None, os.environ.get('PARITY_FORM_ORACLE', '').split(',')))   # W19 DIAGNOSTIC oracle (cards), never a default
FORM_SYM = set(filter(None, os.environ.get('PARITY_FORM_SYM', '').split(',')))         # W19 round-2 probe (cards), opt-in
FORM_SYM_FROM = os.environ.get('PARITY_FORM_SYM_FROM', '20261019_0600')               # matches from this stamp on
# ENG-FIX (SME_OWN_SPAWN=1, off by default): a confirmed own play of a one-body card whose confirmation saw the body
# >= OWN_SPAWN_ERR tiles from the tap (err_tiles) takes the body's point (the confirmation's 'spawn', the reader's first
# body) as its point. FRESH3 142926@254: the Knight tapped at 211 went unconfirmed at 245, the bot re-tapped at 248
# elsewhere, the game ran the first tap (body at (5499, 24499), err_tiles 7.6); the play kept the second tap's point,
# 3,000 / 7,000 off. Census on dev 138 + FRESH1 9 + FRESH2 + FRESH3 (engfix/spawn_census.txt): one-body plays have
# err_tiles 0 .. 0.5 (0.5 = the Knight back-row half-tile clamp, 71) or >= 1.0 (4: 104806 Knight 1.0, 110715 X-Bow 1.0,
# 141254 Knight 3.16, 142926 Knight 7.61). Skeletons (a 3-body spread whose 'spawn' is one centroid) read up to 1.16 and
# are left alone. ponytail: the icebow deck's one-body cards by name; another own deck adds its cards.
OWN_SPAWN = os.environ.get('SME_OWN_SPAWN', '0') == '1'
OWN_NEARDEAD = os.environ.get('SME_OWN_NEARDEAD', '0') == '1'   # ENG-FIX, deployments' H-NEARPARENT (comment there)
OWN_BODYPT = os.environ.get('SME_OWN_BODYPT', '0') == '1'       # ENG-FIX, deployments' own-tap pairing (comment there)
OWN_BODYPT_D = 750                                               # units: the Knight back-row clamp moves 500
OWN_BODYPT3 = os.environ.get('SME_OWN_BODYPT3', '0') == '1'     # ENG-FIX5, deployments' own-tap pairing (comment there)
NEAR_BIGGER = os.environ.get('SME_NEAR_BIGGER', '0') == '1'     # ENG-FIX, deployments' near list (comment there)
NEAR_BIGGER2 = os.environ.get('SME_NEAR_BIGGER2', '0') == '1'   # ENG-FIX2, the narrower NEAR_BIGGER (comment there)
# ENG-FIX2 (SME_SPELL_KING=1, off by default): a king-thrown projectile spell is dated by how far it flew. Its first two
# sightings give the speed v per tick; if the first lies on the line king -> aim (<= 50 units off) and k = |P1 - king| / v
# is whole (+-0.05), crforge's run tick is first - k (the SIM's shot is k steps from the king on frame first). The window
# [lo, hi] is kept; only the default tick moves, and only inside it. Census FRESH4 (engfix/spellk_*.tsv): Fireball,
# Rocket, Snowball, Goblin Barrel 285 / 285 king-sourced shots on the line with k whole; 138 / 138 exactness-validated
# fitted runs equal first - k, the mid-gap default was wrong on 72. 151109@925: a Snowball and our Log first seen on one
# frame, both one tick early; the repair moves one command at a time, so neither move alone moved the first div.
SPELL_KING = os.environ.get('SME_SPELL_KING', '0') == '1'
SPELL_KING_OFF, SPELL_KING_FRAC = 50, .05
OWN_SPAWN_ERR = 0.75
OWN_SPAWN_CARDS = {'Knight', 'Xbow', 'Tesla', 'IceWizard'}
DIGGERS = {'Miner', 'GoblinDrill'}  # tunnel in: seen active on their way, deploying where they surface (Knight etc. can show
                                   # 13/15 -> 12/14 too: 31 of 531 Knights, so the rule is by card)
TOWER_RADIUS = 1400                # millitiles, king (princess 1000): attribution slack, not a law
FORMATION_SPAN = 15000             # millitiles: the widest one-play formation (Royal Recruits: 6 bodies 2.8 tiles apart)
PRIORITY = {'Xbow', 'Tesla', 'Tornado', 'Log', 'IceWizard', 'Rocket', 'Knight', 'Skeletons', 'MegaKnight', 'Golem',
            'ElixirGolem', 'SkeletonBalloon', 'Barbarians', 'Firecracker', 'MinionHorde', 'Giant'}
# Frame logs with the reader's per-body state / projectile / effect keys (--log-frames from 10-16, READER_VALIDATION_1016.md)
# are "ext" logs; everything below is used only for them, so older logs replay exactly as before.
SPELL_SOURCES = ('own_spell_tap+delay', 'spell_seen')
PULL_AREAS = ('Tornado',)          # fx-dated pulling areas whose SIM command goes on the area's made tick (seen_casts)
# Crown tower troops a side may field in its princess slots (RoyaleSim card.rs TOWER_TROOPS; their `units` rows): the
# Dagger Duchess, the Cannoneer, the Royal Chef. Their table LoadTime (Princess 0): Duchess 0, Cannoneer 1400, Chef 200.
TOWER_TROOPS = ('DaggerDuchess', 'Cannoneer', 'ChefTower')
TROOP_LOAD_MS = {'PrincessTower': 0, 'DaggerDuchess': 0, 'Cannoneer': 1400, 'ChefTower': 200}
P2_DIR = ROOT/'scratchpad/gauntlet/L70/reader/re_phase2/validation'    # phase-2 captures: run.json names its frame log
P3_DIR = ROOT/'scratchpad/gauntlet/L70/reader/re_phase3'                # phase-3 captures carry the same phase-2 buff rows
P3_LIVE = ROOT/'icebow/data/p3_captures'   # live --capture-p3 (5e4818f): same run.json + frames.jsonl layout, gitignored
P3B_SMOKE = ROOT/'icebow/data/p3b_smoke'   # 10-17 phase-3b probe runs beside the live reader (READER_PHASE3B.md), gitignored


def p3_runs():
    """Every phase-3 capture: the manual probe runs and the live --capture-p3 ones."""
    return sorted(P3_DIR.glob('p3_*/run.json')) + sorted(P3_LIVE.glob('*/run.json'))


CAST, MID_JUMP = 10, (3, 5, 6)     # behavior_state_raw: hero cast; Mega Knight jump, river jump, tunnelling
STUN_BUFFS = ('Freeze', 'Tesla_EV1_WithDamage', 'ZapFreeze')   # phase-2 buff names the SIM holds as stun_ms (Freeze spell -> stun_ms,
# probed; ZapFreeze: the Zap's -100 speed / hit-speed stun, flagged status_unset before H-ZAP, diag_night/r5c 112457@3032)
# Ice Wizard slows (all -30% walk / attack / spawn, IW_SLOW_1016.md): live buff name -> the SIM buff it is seeded as
# (Engine.slow_ids, probed: the SIM's after-slow and base deploy chill are its IceWizardSlowDown). The hero freeze
# (999,999 sentinel) is not a time and stays unset (an ability inside 100 ticks of t0 is a strict blocker anyway).
SLOW_BUFFS = {'IceWizardSlowDown': 'base', 'IceWizardCold': 'base', 'IceWizardHero_SlowBuff': 'base',
              'IceWizardHeroSlow': 'hero', 'IceWizardHeroCold': 'hero_cold'}
SNARE_BUFF = 'BolaSnare'           # the Ram Rider's bola buff (phase-2 name = SIM table name; Engine.snare_id)
IW_SLOW_MS = 2500                  # an Ice Wizard shot's slow (both forms; re-armed on every hit)
SENTINEL_MS = 100000               # buff/effect remaining above this is "lives with its source", not a time
SNIPE_AMMO, SNIPE_FROM_MT = 3, 7500           # Evo Musketeer AmmoCount (card table); a live shot from beyond 7.5 tiles is a snipe
HERO_THROWERS = ('Balloon',)      # hero forms whose ability is a thrown unit (card.rs AbilityEffect::Throw)
HB_SPEEDS = (201, 201, 201, 201, 243, 274, 299, 320, 338, 354, 368, 380, 391, 402, 411, 420)  # BalloonHero_Ability ramp, mt/tick
GM_SIGNAL_MS, GM_COOLDOWN_MS = 1000, 5000   # fork state.rs ROCKET_SIGNAL_MS / ROCKET_COOLDOWN_MS
EVO_RING_MS = 1500                 # an Evo Tesla ring's life (live area rows count 1500 -> 0, 50 a tick)
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
                j = json.loads(raw); outcome.append((j['event'], j['name'], j.get('intended'), j.get('spawn'), j.get('err_tiles')))
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
    # PARITY_ANY_DECK=1 (opt-in, W8 10-20): also an ext log whose own deck is not icebow (the owner's classic-challenge parity
    # battles, where the bot plays decks built from the rare cards); unset = this gate unchanged
    if own_pr != {OWN_PRINCESS_MAX} and not (extra and any('Xbow' in h for _, h in hands)) \
            and not (extra and hands and os.environ.get('PARITY_ANY_DECK') == '1'):
        return None, 'not_main_account'
    # confirmed own plays: each play is followed by exactly one confirmed/unconfirmed event, in order
    plays = [dict(p, xy=o[2] or p['xy']) if not (OWN_SPAWN and p['name'] in OWN_SPAWN_CARDS and o[3] and len(o[3]) == 1
                                                 and (o[4] or 0) >= OWN_SPAWN_ERR)
             else dict(p, xy=list(o[3][0]), spawn_moved=round(o[4], 2))
             for p, o in zip(plays, outcome) if o[0] == 'confirmed' and o[1] == p['name']]
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
                # An address the game hands to a new body of the same card inside GAP_SPLIT is a new body when max_hp
                # jumps past the pairing band (a Skeleton Balloon's 773 -> one of its 119 skeletons 16 ticks after its
                # death: diag_night/r4e H-REUSE, 2 of 2 such jumps on the 218 captured logs); a level step (an Evo
                # Electro Giant's delevel, ~10 %) or a -1 reader row keeps the id.
                jump = last is not None and mx > 0 and last[3] > 0 and not .6 <= mx/last[3] <= 1.67
                if last is None or t-last[1] > GAP_SPLIT or last[2] != cid or jump:
                    ids[k] += 1
                    last = (f'{k}.{ids[k]}', t, cid, mx)
                seen[k] = (last[0], t, cid, mx if mx > 0 else last[3])
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
           # H-SHADOW-SHORT (diag_night/r5c): a short-lived shadow is off on one sample (its first: 130511@770, a Hero IW dead
           # 8 ticks after its play, co-located on 4 of 5 samples), so one off sample is allowed once a pair has >= 4 samples
           for (a, b), k in both.items() if k >= .9*min(n[a], n[b]) or k >= min(n[a], n[b]) - 1 >= 3}
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


def phase3_births(path):
    """{generation id: [C, card tick]} for every body the capture first shows after its first frame, from the phase-3b
    per-body fields (READER_PHASE3B.md; 400 / 403 inside their first-sighting gap): C = its creation frame tick
    (reader_val/validate_p3.creation_tick: deploy stamp + 1 while deploying, else card tick + 1, else first sighting -
    active ms / 50), card tick = the tick of the card play that made it (-1: made by another body). From the first
    capture of this frame log that carries the stamps (live --capture-p3, then the 10-17 smoke runs); {} without one
    (older captures: every placement keeps its frame gap). PARITY_ATTACKS=<file>: its '_births' rows."""
    if os.environ.get('PARITY_ATTACKS'):
        # ponytail: a second read of the file phase3_attacks reads (+~4 s a match on the 131 MB attacks5.json); one shared load if it matters
        rows = json.loads(Path(os.environ['PARITY_ATTACKS']).read_text()).get('_births', {}).get(Path(path).name, {})
        return {int(g): v for g, v in rows.items()}
    from scratchpad.gauntlet.L74.parity.reader_val.validate_p3 import creation_tick
    for run in p3_runs() + sorted(P3B_SMOKE.glob('*/run.json')):
        try:
            if json.loads(run.read_text()).get('live_log') != Path(path).name:
                continue
        except ValueError:
            continue
        out, seen, last = {}, set(), None
        with open(run.parent/'frames.jsonl', 'rb') as f:
            for raw in f:
                j = json.loads(raw); p = j.get('phase3') or {}
                if not (j.get('battle_active') and p.get('valid')):
                    continue
                if last is not None and j['game_tick'] < last:
                    break                      # the next battle: generation ids start over
                beh = {e['category']: e.get('behavior_state_raw') for e in j['entities']}
                for b in p.get('bodies', []):
                    g = b['generation']
                    if g in seen or 'deploy_tick_raw' not in b:
                        continue
                    seen.add(g)
                    c, _ = (None, None) if last is None else creation_tick(  # first frame: made before the capture
                        j['game_tick'], b['deploy_remaining_raw'], b['deploy_tick_raw'], b['card_tick_raw'],
                        b.get('active_ms_raw'), beh.get(g))
                    if c is not None:
                        out[g] = [c, b['card_tick_raw']]
                last = j['game_tick']
        if out:
            return out
    return {}


def phase3_shields(path):
    """{tick: {generation id: shield hp}} for every body whose phase-3c capture row carries a shield (shield_max_raw > 0:
    Guards, Royal Recruits, Dark Prince, Evo Wizard, Hero Knight; READER_PHASE3C.md), from the first capture of this frame
    log that has the 3c fields; {} without one (older captures). PARITY_ATTACKS=<file>: its '_shields' rows."""
    if os.environ.get('PARITY_ATTACKS'):
        rows = json.loads(Path(os.environ['PARITY_ATTACKS']).read_text()).get('_shields', {}).get(Path(path).name, {})
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
                if b'shield_max_raw' not in raw:
                    continue
                j = json.loads(raw); p = j.get('phase3') or {}
                if p.get('valid'):
                    u = {b['generation']: b['shield_hp_raw'] for b in p.get('bodies', [])
                         if (b.get('shield_max_raw') or 0) > 0 and b.get('shield_hp_raw') is not None}
                    if u:
                        out[j['game_tick']] = u
        if out:
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
                                       max_hp=b['max_hp'], active=None, traj=[], gen=b.get('gen'))
            r['last'] = t
            r['traj'].append((t, b['x'], b['y']))
            if r['active'] is None and b['kind'] in (13, 15):
                r['active'] = t
            elif r['active'] is not None and b['kind'] in (12, 14) and 'land' not in r and t - r['first'] <= 80:
                r['land'] = (t, b['x'], b['y'])     # active first, deploying later: a digger (Miner) surfacing here
    return tr


def drill_surface(tr, side, card_id, after):
    """H-DRILL-SURFACE (W8 round 3): where a Goblin Drill came up. Its dig and the building it leaves are two bodies (two
    tracks); the building's first point, a static track of the same side and card first seen 20..150 ticks after `after`.
    The bot's tap on an exact tile corner is snapped by the game: 49 of 93 drill taps in the 10-20 battles came up 1 tile
    off ((3000, 23000) -> (2000, 22000)), where the SIM, put down at the tap, dealt a median 315 tower damage against 125."""
    for q in tr:
        if q['side'] == side and q['card_id'] == card_id and after + 20 <= q['first'] <= after + 150 and                 max(abs(x - q['x']) + abs(y - q['y']) for _, x, y in q['traj']) < 300:
            return round(q['x']), round(q['y'])
    return None


def form_of(cid, c):
    return 2 if cid in (c.get('hero_form_id'), 203000023) else int(cid == c.get('evolution_form_id'))


def elixir_wait(tick, elixir, cost):
    """Ticks a tap made `cost - elixir` short waits before the live game plays it (TICKS_PER_ELIXIR; double elixir from
    tick 2400, triple from 4800)."""
    if elixir is None or cost is None or elixir >= cost:
        return 0
    return (cost - elixir) * TICKS_PER_ELIXIR / (1 if tick < 2400 else 2 if tick < 4800 else 3)


def king_flight(r):
    """SME_SPELL_KING: whole ticks a projectile flew from its side's king (first sighting r['pos'], second r['pos2']),
    or None: not king-sourced, no second sighting, off the king -> aim line, or not a whole number of steps."""
    if not str(r.get('src') or '').endswith('K') or 'pos2' not in r:
        return None
    (x1, y1), (t2, x2, y2) = r['pos'], r['pos2']
    v = math.hypot(x2 - x1, y2 - y1) / (t2 - r['first'])
    kx, ky = min((TOWER_SLOTS[0], TOWER_SLOTS[3]), key=lambda K: math.hypot(x1 - K[0], y1 - K[1]))  # <= 3 steps out
    ax, ay = r['x'] - kx, r['y'] - ky
    if v <= 0 or abs(ax * (y1 - ky) - ay * (x1 - kx)) > SPELL_KING_OFF * (math.hypot(ax, ay) or 1):
        return None
    k = math.hypot(x1 - kx, y1 - ky) / v
    return round(k) if abs(k - round(k)) <= SPELL_KING_FRAC else None


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
                r = shots.setdefault(p[6], dict(first=t, side=p[0], cid=p[3], x=p[4], y=p[5], pos=(p[1], p[2]), src=p[7]))
                if t > r['first'] and 'pos2' not in r:
                    r['pos2'] = (t, p[1], p[2])
                r['last'] = t
        for e in m['fx'].get(t, ()):
            r = fxs.setdefault(e[6], dict(first=t, side=e[0], cid=e[3], x=e[1], y=e[2], rem=e[4]))
            r['last'] = t
    out = []
    # Projectile spells: a throw then a roll (Log, Barbarian Barrel) or waves (Arrows) are one cast; the cast point is
    # the first shot's target point (READER_VALIDATION_1016: target point = cast point, source = King Tower) -- for a
    # spell of many shots first seen together (Arrows: 30 arrows on one frame, each aimed at its own point of the area)
    # the centre of their target points (diag_night/r3b 000957@659: the first arrow's point lay 651 off that centre, the
    # SIM's Arrows missed the Tesla the live ones hit three times).
    for r in sorted(shots.values(), key=lambda r: r['first']):
        c = next((c for c in out if c['side'] == r['side'] and c['cid'] == r['cid'] and r['first'] - c['seen'] <= 30), None)
        if c:
            if r['first'] == c['seen']:
                c['aims'].append((r['x'], r['y']))
                c['x'], c['y'] = (round(sum(a[0] for a in c['aims'])/len(c['aims'])), round(sum(a[1] for a in c['aims'])/len(c['aims'])))
            c['end'] = max(c['end'], r['last']); continue
        out.append(dict(gap(r['first']), kind='play', side=r['side'], cid=r['cid'], name=name(r['cid']), form=0,
                        x=r['x'], y=r['y'], n=0, source='spell_seen', spell_spawned=False, seen=r['first'], end=r['last'],
                        aims=[(r['x'], r['y'])]))
        if SPELL_KING:
            out[-1]['king_k'] = king_flight(r)
    for c in out:                                  # SME_SPELL_KING: one-shot casts only (Arrows' shots fly off the line)
        k = c.pop('king_k', None)
        if k is not None and len(c['aims']) == 1 and c['lo'] <= c['seen'] - k <= c['hi']:
            c['tick'], c['king_dated'] = c['seen'] - k, k
    for r in sorted(fxs.values(), key=lambda r: r['first']):
        if kind(r['cid']) != 'spell' or any(c['side'] == r['side'] and c['cid'] == r['cid'] and c['seen'] <= r['first'] <= c['end'] + 20
                                            for c in out):
            continue
        full = life(name(r['cid'])) if life else None
        made = r['first'] - (round((full - r['rem'])/50) if full and 0 < r['rem'] <= full else 0)
        # A pulling area (the Tornado) runs a tick later on its own clock than the SIM's area made the tick after the
        # command: live victims are first pulled on made + 3 and first damaged on made + 13 (fx-dated casts on the 218
        # captured logs: 268 of ~290 first pulled gaps, 166 of ~180 first pulse gaps), the SIM's on made + 2 / + 12 with the
        # command on made - 1 (diag_night/r4e H-TORNADO-DATE): its command goes on `made`.
        lag = 1 if name(r['cid']) in PULL_AREAS else 0
        out.append(dict(kind='play', side=r['side'], cid=r['cid'], name=name(r['cid']), form=0, tick=made-1+lag, lo=made-1+lag,
                        hi=made-1+lag, x=r['x'], y=r['y'], n=0, source='spell_seen', spell_spawned=False, seen=r['first'],
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
            if bd['tower'] or c is None or (form_of(bd['card_id'], c) != 2 and not (CHAMP_CASTS and c['display_name'] in CHAMP_STATE10)):
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
    # The Hero Balloon's throw (card.rs AbilityEffect::Throw, its Skeletrooper) shows no cast state and no effect row: the
    # reader sees only the Skeletrooper, a body of the hero's card with another max_hp, deploying (state 4) where it
    # lands (diag_night/r3a 234407@3888: 688 / 688 hp at t3928 under a 2436 hp hero; no event, so the SIM never threw it,
    # and 10 Hero Balloon troopers in imperfect strict fights were never made). The press is put before its first
    # sighting by the SIM's press -> trooper lag: seek + spawn (2 ticks) + the throw's moves from the hero's point to the
    # trooper's at the table's ramp (BalloonHero_Ability speeds, native millitiles a tick, a step up every 3 moves); the
    # hero's point is read at the press tick so found (two passes). The throw itself is not public.
    pos = {}
    for t, bodies in m['frames']:
        for bd in bodies:
            pos[t, bd['id']] = (bd['x'], bd['y'])
    def throw_lag(t, hero, at):
        lag = 2
        for _ in range(2):
            hp_ = pos.get((min((tt for tt, _ in m['frames'] if tt >= t - lag), default=t), hero)) or pos.get((t, hero))
            d, n, run = math.dist(hp_, at), 0, 0
            while run < d and n < 200:
                run += HB_SPEEDS[min(n // 3, len(HB_SPEEDS) - 1)]; n += 1
            lag = 2 + n
        return lag
    born = {}
    for t, bodies in m['frames']:
        for bd in bodies:
            c = catalog.get(bd['card_id'])
            if bd['tower'] or c is None or c['display_name'] not in HERO_THROWERS or form_of(bd['card_id'], c) != 2 or bd['id'] in born:
                continue
            born[bd['id']] = t
            hero = next((o for o in bodies if o['card_id'] == bd['card_id'] and o['side'] == bd['side'] and o['max_hp'] > bd['max_hp']
                         and not o['tower']), None)
            # only a throw the reader saw (a projectile row of the hero's card from the hero in the 40 ticks before; 17 of
            # 18 on the captured logs): an unseen one (234407 t3928) is not public, and a guessed one landed 1.5 tiles off
            # and broke an agreeing fight (234407@3846)
            seen_throw = hero is not None and any(q[3] == bd['card_id'] and q[7] == hero['id']
                                                  for tt in range(t - 40, t + 1) for q in m['proj'].get(tt, ()))
            if bd.get('state') == 4 and hero is not None and not seen_throw:
                # an unseen throw (234407 t3928): the trooper lands where and when it is first seen (diag_night/r3c); the
                # landing blow's area row, if shown, made a 'cast' there, which this landing replaces
                k = (bd['side'], c['display_name'])
                casts[:] = [(tt, s, n) for tt, s, n in casts if not (s == k[0] and n == k[1] and t - 12 <= tt <= t + 5)]
                out.append(dict(gap(t), kind='throw', side=bd['side'], name=c['display_name'], form=2, x=bd['x'], y=bd['y'],
                                source='throw_landed', seen=t, end=t))
            if bd.get('state') == 4 and seen_throw:
                k = (bd['side'], c['display_name'])
                tc = t - throw_lag(t, hero['id'], (bd['x'], bd['y']))
                # the landing blow's area row, when the reader shows one, already made a 'cast' on the landing tick (one
                # charge: a second press is refused ABILITY_SPENT): the throw's press replaces it
                casts[:] = [(tt, s, n) for tt, s, n in casts if not (s == k[0] and n == k[1] and tc - 10 <= tt <= t + 5)]
                casts.append((tc, k[0], k[1]))
    # H-CUBE-DATE (diag_night/r7d): a Hero Ice Wizard cast dated from its state-10 frame put the SIM's ice cube 2-3 ticks
    # late. The SIM makes the cube 6 ticks after the press (cubeprobe.py); the live cube's phase-3b creation tick C is 3
    # (44) or 4 (31) ticks after the state-10 estimate on 60 upgraded logs (cubebirth.py), and on the bucket dossiers the
    # live cube is first seen 4 ticks after the replayed press in 79 / 80 casts, the SIM's 6 in 73 / 75 (cubelag.py;
    # 20261017_230816@475: the cube 4 ticks late froze a Witch wave late). The cube is the cast's public effect: a cast
    # whose cube (a body of the hero's card, max hp below half the hero's) shows within 20 ticks is dated CUBE_LAG before
    # the cube's creation tick when the capture stamps it (exact), else CUBE_LAG before its first sighting (the frame
    # gap's width kept: the ceiling draws from it).
    cubes = defaultdict(list)
    seen_cube = set()
    for t, bodies in m['frames']:
        for bd in bodies:
            c = catalog.get(bd['card_id'])
            if bd['tower'] or c is None or c['display_name'] != 'IceWizard' or form_of(bd['card_id'], c) != 2 or bd['id'] in seen_cube:
                continue
            hero = max((o['max_hp'] for o in bodies if o['card_id'] == bd['card_id'] and o['side'] == bd['side'] and not o['tower']), default=0)
            if 0 < bd['max_hp'] < hero / 2:
                born = (m.get('births') or {}).get(bd.get('gen'))
                seen_cube.add(bd['id']); cubes[bd['side']].append((t, born[0] if born else None))
    for t, s, n in sorted(casts):
        e = dict(gap(t), kind='ability', side=s, name=n, source='cast_seen', seen=t, end=t)
        cf = next((c for c in cubes.get(s, ()) if t <= c[0] <= t + 20), None) if n == 'IceWizard' else None
        if cf is not None and cf[1] is not None:
            e.update(tick=cf[1] - CUBE_LAG, lo=cf[1] - CUBE_LAG, hi=cf[1] - CUBE_LAG, cube=cf[0], cube_born=cf[1])
        elif cf is not None:
            d = cf[0] - CUBE_LAG - e['tick']
            e.update(tick=e['tick'] + d, lo=e['lo'] + d, hi=e['hi'] + d, cube=cf[0])
        out.append(e)
    for e in out:
        e.pop('cid', None); e.pop('aims', None)
    return sorted(out, key=lambda e: (e['tick'], e['side'], e['name']))


ZAP_HITS = {16: (306, 307, 77), 15: (279, 280, 70), 14: (254, 255, 64), 13: (231, 232, 58)}   # SIM Zap drops (troop, building,
# crown tower) per level on the 160402017 table (diag_night/log/sim_spell_table.jsonl). ponytail: table constants; re-probe on a new table
ZAP_R = 2500                       # ZapArea radius_milli (card table)
ZAP_TWINS = ('Barbarians', 'BattleRam', 'BarbarianHut', 'EliteBarbarians')   # melee hits sized like a same-level Zap (124601@682)


def unseen_zaps(m, catalog, seen, stats):
    """H-ZAP (diag_night/r5c): the reader shows no Zap at all (no projectile, no area row on any of the 83 upgraded logs), so
    an opponent Zap was never replayed while the fight stayed strict (132100@3454: our X-Bow and Tesla, 2.9 tiles apart,
    -307 each in one frame gap = a level-16 Zap; the live X-Bow, stunned, retargets a Ronin, the SIM's keeps hitting the
    tower: 1862 vs 980 tower damage). Its effect is public: one frame gap (<= 3 ticks) in which >= 2 bodies of one side
    take that level's Zap drop (troop +-1, building + decay, crown tower +-1), or one does and another body within
    2 x radius dies with hp <= the drop. Not when the same bodies repeat it within 12 ticks (a chaining attacker), an
    Electro Wizard of the caster's side appeared in the 30 ticks before (its deploy zap), or a seen spell of that side
    explains it. Cast point: the grid point (100 mt) covering every hit body (radius + body radius) and the most dead
    ones, then the fewest untouched bodies of that side, then nearest the victims' centroid. Command tick: the drop shows
    one tick after the SIM's command (probed: zapdelay.py), so the gap (ta, tb] gives tick ta..tb-1."""
    rad = lambda b: (stats('PrincessTower') if b['tower'] else stats((catalog.get(b['card_id']) or {}).get('display_name'))
                     ).get('collision_radius_milli') or 500
    kind = lambda b: 'tower' if b['tower'] else (catalog.get(b['card_id']) or {}).get('type')
    first = {}
    for t, bodies in m['frames']:
        for b in bodies:
            first.setdefault(b['id'], (t, b))
    ewiz = [(t, b['side']) for t, b in first.values() if (catalog.get(b['card_id']) or {}).get('display_name') == 'ElectroWizard']
    cands, fr = [], m['frames']
    # ENG-SME (SME_ZAP_CHAIN1=1): a body that takes the same drop (+-1) in another frame gap within 12 ticks has a
    # periodic attacker, so that drop is no Zap evidence. FRESH2 130148@3404: our tower takes 77 every 4-6 ticks from the
    # opponent's hero Valkyrie (3384 .. 3408) and our 15-hp hero IW dies in the same gap -> a false level-16 Zap; crforge,
    # given it, sits 77 below the game from 3404 (first divergence). The old repeat test needs the same SET of hit bodies.
    chain = os.environ.get('SME_ZAP_CHAIN1') == '1'
    seen_drops = defaultdict(list)
    if chain:
        for (ta, A), (tb, B) in zip(fr, fr[1:]):
            pa = {b['id']: b for b in A}
            for b in B:
                p = pa.get(b['id'])
                if tb - ta <= 3 and p and p['hp'] > 0 and b['hp'] >= 0 and p['hp'] != b['hp']:
                    seen_drops[b['id']].append((tb, p['hp'] - b['hp']))
    periodic = lambda i, t, d: any(t2 != t and abs(t2 - t) <= 12 and abs(d2 - d) <= 1 for t2, d2 in seen_drops[i])  # noqa: E731
    for (ta, A), (tb, B) in zip(fr, fr[1:]):
        if tb - ta > 3:
            continue
        pa, ids = {b['id']: b for b in A}, {b['id'] for b in B}
        for v in (0, 1):
            for lv, (zt, zb, zc) in ZAP_HITS.items():
                hit = []
                for b in B:
                    p = pa.get(b['id'])
                    if not p or b['side'] != v or p['hp'] <= 0 or b['hp'] < 0:
                        continue
                    d, k = p['hp'] - b['hp'], kind(b)
                    # a body with a caster-side ZAP_TWINS troop within 2 tiles may have taken a melee hit of the same size (a level-L
                    # Barbarian hits for that level's Zap damage: 124601@682 was two Barbarian swings, diag_night/r5c)
                    melee = any(o['side'] != v and not o['tower'] and (catalog.get(o['card_id']) or {}).get('display_name') in ZAP_TWINS
                                and math.hypot(o['x']-p['x'], o['y']-p['y']) <= 2000 + rad(o) + rad(p) for o in A)
                    if not melee and (abs(d - zc) <= 1 if k == 'tower' else zb <= d <= zb + 5*(tb - ta) if k == 'building' else abs(d - zt) <= 1)                             and not (chain and periodic(b['id'], tb, d)):
                        hit.append(p)
                dead = [p for k_, p in pa.items() if k_ not in ids and p['side'] == v and not p['tower'] and 0 < p['hp'] <= zt
                        and hit and min(math.hypot(p['x']-h['x'], p['y']-h['y']) for h in hit) <= 2*ZAP_R]
                if hit and len(hit) + len(dead) >= 2:
                    rest = [p for p in A if p['side'] == v and p['id'] in ids and p not in hit and p['hp'] > 0]
                    cands.append((tb, ta, v, lv, hit, dead, rest))
    out = []
    for c in cands:
        tb, ta, v, lv, hit, dead, rest = c
        vid = {p['id'] for p in hit}
        if any(o is not c and o[0] != tb and abs(o[0] - tb) <= 12 and {p['id'] for p in o[4]} == vid for o in cands) \
                or any(s == 1 - v and tb - 30 <= t <= tb for t, s in ewiz) \
                or any(e['side'] == 1 - v and e['kind'] == 'play' and tb - 20 <= e['seen'] <= tb + 2 for e in seen) \
                or any(o is not c and o[0] == tb and o[2] == v and (len(o[4]) + len(o[5]), o[3]) > (len(hit) + len(dead), lv) for o in cands):
            continue
        V = hit + dead
        cx, cy = sum(p['x'] for p in V)/len(V), sum(p['y'] for p in V)/len(V)
        best = None
        for gx in range(int(min(p['x'] for p in V)) - ZAP_R, int(max(p['x'] for p in V)) + ZAP_R + 1, 100):
            for gy in range(int(min(p['y'] for p in V)) - ZAP_R, int(max(p['y'] for p in V)) + ZAP_R + 1, 100):
                cov = lambda p: math.hypot(p['x']-gx, p['y']-gy) <= ZAP_R + rad(p)
                if not all(cov(p) for p in hit):
                    continue
                s = (sum(map(cov, dead)), -sum(map(cov, rest)), -math.hypot(gx-cx, gy-cy))
                if best is None or s > best[0]:
                    best = (s, gx, gy)
        if best:
            out.append(dict(kind='play', side=1-v, name='Zap', form=0, tick=(ta + 1 + tb)//2 - 1, lo=ta, hi=tb - 1, x=best[1],
                            y=best[2], n=0, source='spell_seen', spell_spawned=False, seen=tb, end=tb, inferred=True))
    return out


def deployments(m, catalog, life=None, own_unit=None, stats=None):
    """Live deployments: new body groups (children of a living/just-dead same-card body, or role-children by max_hp,
    are the SIM's job, not plays), own confirmed spells, own Hero IW presses. Ext logs: spells and hero casts of both
    sides as seen (seen_casts); an own tap or press stays only where nothing was seen for it."""
    seen = seen_casts(m, catalog, life) if m.get('ext') else []
    if m.get('ext') and stats:
        seen += unseen_zaps(m, catalog, seen, stats)
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
        near = [q for q in tr if q['side'] == r['side'] and q['card_id'] == r['card_id'] and q['first'] < r['first'] - 4
                and q['first'] <= r['first'] <= q['last'] + 15
                and math.hypot(at(q, r['first'])[1]-r['x'], at(q, r['first'])[2]-r['y']) < 3000]
        # ENG-FIX (SME_NEAR_BIGGER=1, off by default): a body is no child of a LIVING smaller body of its card (a child is
        # smaller than its maker; a larger one born at its maker's death, a Phoenix from its egg, still counts: the maker
        # is not living). FRESH2 101018@5968: a second Goblinstein (monster 3578 hp, doctor 1153) beside the first play's
        # living doctor (479 / 1153 hp, 1,394 units away) was dropped as that doctor's child; its doctor as a role-child.
        if NEAR_BIGGER:
            near = [q for q in near if not (q['max_hp'] < .95*r['max_hp'] and q['last'] > r['first'] + 2)]
        # ENG-FIX2 (SME_NEAR_BIGGER2=1, off by default): NEAR_BIGGER only for a body whose max hp (+-1%) equals a body of an
        # EARLIER play group of its side and card (a group started > 6 ticks before it): one card at one level makes bodies of
        # one max hp, so a second play repeats it. NEAR_BIGGER's dev false plays all have a new max hp: hero Dark Prince
        # 2167 beside plays of 1918, hero Musketeer 2454 beside 1153, the Little Prince guardian 2556 beside 1116; FRESH2
        # 101018's second Goblinstein monster 3578 = the first play's monster (engfix/nearbig2_*). Tried and rejected: the
        # smaller body from an earlier play only (kept 6 / 7 dev logs' false plays); own-unit hp + deploying + own half
        # (FRESH2 081253: a hero Musketeer 2454 body deploying in its own half).
        if NEAR_BIGGER2 and any(g['side'] == r['side'] and g['card_id'] == r['card_id'] and g['tick'] < r['first'] - 6
                                and any(abs(b['max_hp'] - r['max_hp']) <= .01 * r['max_hp'] for b in g['members'])
                                for g in groups):
            near = [q for q in near if not (q['max_hp'] < .95*r['max_hp'] and q['last'] > r['first'] + 2)]
        c = catalog[r['card_id']]
        # H-NEARPARENT (diag_night/r5c): a body of the card's own unit (a level's max_hp) next to a LIVING same-size body of
        # its card is a second play, not that body's child (children are smaller, or born at their parent's death): 40 such
        # plays on the 311 captured logs (25 own, every one confirmed: Hero IW x13, Tesla x5, Knight x3, ...; 120801@4021 a
        # second Wizard 2.8 tiles from the first) were dropped and never replayed. Not for spells, evos (Evo Skeletons
        # duplicate), champions (an ability may show a same-card body), a seen Mirror / Clone cast; an opponent body must be
        # deploying when first seen (a play: its Hero Wizard / Elite Archer / Bowler re-plays deploy on a tile centre), an
        # own body needs a confirmed play of its card.
        f = form_of(r['card_id'], c)
        replay = bool(near) and own_unit is not None and c.get('type') != 'spell' and f != 1 and not c.get('active_ability') \
            and all(q['last'] > r['first'] + 2 and .95 <= q['max_hp']/max(1, r['max_hp']) <= 1.05 for q in near) \
            and own_unit(c['display_name'], r['max_hp']) \
            and not any(e['side'] == r['side'] and e['name'] in ('Mirror', 'Clone') and r['first'] - 60 <= e['tick'] <= r['first'] for e in seen) \
            and (any(p['name'] == c['display_name'] and 0 <= r['first'] - p['tick'] <= 80 for p in m['plays']) if r['side'] == m['side'] else r['active'] is None or r['active'] > r['first'])
        # ENG-FIX (SME_OWN_NEARDEAD=1, off by default): an OWN body of the card's own unit, deploying when first seen, with a
        # confirmed tap of its card 0..80 ticks before, next to same-size bodies of its card that all died within 2 ticks of
        # its birth, is that tap's play, not a child born at the parent's death (no icebow card spawns its own card on
        # death). FRESH3 142334@1693: our hero Ice Wizard tapped at 1669 (confirmed, elixir drop 2.57) was born at 1693,
        # 2,954 units from our earlier hero Ice Wizard that died at 1692; the play was dropped, crforge kept 3 elixir more.
        if OWN_NEARDEAD and near and not replay and r['side'] == m['side'] and own_unit is not None and c.get('type') != 'spell'                 and f != 1 and not c.get('active_ability') and (r['active'] is None or r['active'] > r['first'])                 and all(q['last'] <= r['first'] + 2 and .95 <= q['max_hp']/max(1, r['max_hp']) <= 1.05 for q in near)                 and own_unit(c['display_name'], r['max_hp'])                 and any(p['name'] == c['display_name'] and 0 <= r['first'] - p['tick'] <= 80 for p in m['plays']):
            replay = True
        near_parent = bool(near) and not replay
        # A hero's ability object can share the card id and dwarf its units (Hero Goblins: a 3720 / 4090 hp object over
        # 293 / 323 hp goblins), so the max_hp rule dropped every Hero Goblins play as a role-child (diag_night/knight).
        # A hero body whose max_hp IS the card's own unit at some level (own_unit = Engine.level) is a play's body.
        # SME-F1FIX-3 (SME_CHAMP_OWN=1, off by default): the same exemption for a champion whose ability body shares its
        # card id and out-sizes it (Little Prince 1116 hp, guardian 2556: 0.437 < .45 made every Little Prince play a child).
        child_by_hp = r['max_hp'] < .45*top[r['side'], r['card_id']] and not (
            own_unit and (form_of(r['card_id'], c) == 2 or (os.environ.get('SME_CHAMP_OWN') == '1' and c.get('rarity') == 'Champion'))
            and own_unit(c['display_name'], r['max_hp']))
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
        lo, hi = prev, max(prev, g['tick']-1)
        # Phase-3b captures (m['births']) time the play exactly: the card tick of the play that made its bodies (= deploy
        # stamp for a card troop; the play itself for a staggered one, e.g. Recruits, whose deploys start later), for a
        # body made by another one its creation tick - 1; the earliest member. Not redrawn by the ceiling (lo = hi). A
        # spell's bodies (Goblin Barrel goblins: card tick = the cast) keep the gap: the play stands for their landing.
        born = [k if k >= 0 else bc - 1 for r in g['members'] for bc, k in [m.get('births', {}).get(r['gen'], (None, -1))]
                if bc is not None]
        if born and c.get('type') != 'spell':
            tick = lo = hi = min(born)
        ev = dict(kind='play', side=g['side'], name=c['display_name'], form=form_of(g['card_id'], c), tick=tick,
                  x=round(g['x']), y=round(g['y']), n=len(g['members']), source='first_seen',
                  spell_spawned=c.get('type') == 'spell', lo=lo, hi=hi)
        land = [r['land'] for r in g['members'] if 'land' in r] if c['display_name'] in DIGGERS else []
        if not land and c['display_name'] == 'GoblinDrill' and os.environ.get('PARITY_DRILL_TAP') != '1':
            s = drill_surface(tr, g['side'], g['card_id'], g['tick'])
            if s and (abs(s[0] - g['x']) + abs(s[1] - g['y'])) > 300:
                land = [(None, s[0], s[1])]
        if land:
            # A Miner is seen tunnelling from its own side (active rows) before it surfaces (deploying rows): the play's
            # point is where it surfaces, not where it was first seen (ceiling subset: every opp Miner was replayed
            # walking from near its king tower, 0 tower damage vs 93-342 live).
            ev.update(x=round(statistics.fmean(p[1] for p in land)), y=round(statistics.fmean(p[2] for p in land)), dig=True)
        elif c['display_name'] in LEAD_AHEAD:
            # H-RASCALS: the group is the formation's lead body alone (the rest are children); the SIM stands it LEAD_AHEAD
            # ahead of the play point, so the point is that far behind it (toward the side's own king).
            ky = next((bd['y'] for bd in m['frames'][0][1] if bd['tower'] and bd['side'] == g['side'] and bd['id'].endswith('K')), None)
            fwd = 1 if ky is not None and ky < 16000 else -1
            rest = [q['y'] for q in tr if q['side'] == g['side'] and q['card_id'] == g['card_id'] and abs(q['first'] - g['tick']) <= 6
                    and q['max_hp'] < .45*top[g['side'], g['card_id']]]
            # only a full formation (the girls > 2000 behind; 2954 live): a river-edge play is compressed (1223) and the old
            # point agreed there (diag_night/r4c rasgeom.py: 20261016_171357 / 214220 plays on y 14500)
            if ky is not None and rest and (ev['y'] - statistics.fmean(rest))*fwd > LEAD_AHEAD[c['display_name']]:
                ev['y'] = round(ev['y'] - LEAD_AHEAD[c['display_name']]*fwd)
        if g['side'] == m['side']:
            cand = [i for i, p in enumerate(m['plays']) if i not in used and p['name'] == ev['name']
                    and 0 <= g['tick']-p['tick'] <= 80]
            if cand:
                i = cand[-1]; used.add(i); p = m['plays'][i]
                ev.update(x=p['x'], y=p['y'], source='own_tap', tap=p['tick']); delays.append(tick-p['tick'])
                # ENG-FIX (SME_OWN_BODYPT=1, off by default): a one-body own play whose body the reader first saw
                # >= OWN_BODYPT_D from the tap keeps the body's point (the game's placement). SME_OWN_SPAWN reads the
                # bot's confirmation, which is empty when the bot never saw the body: FRESH4 220244@3374 and 222707@1653
                # (confirmation spawn [], latency 42 / 46 ticks; the game's Knight 1 / 2 tiles off the tap).
                if OWN_BODYPT and ev['name'] in OWN_SPAWN_CARDS and len(g['members']) == 1                         and math.hypot(g['x'] - p['x'], g['y'] - p['y']) >= OWN_BODYPT_D:
                    ev.update(x=round(g['x']), y=round(g['y']), body_moved=[p['x'], p['y']])
                # ENG-FIX5 (SME_OWN_BODYPT3=1, off by default): the same for our Skeletons (3 bodies; the group point is the
                # formation's, as for the opponent's first_seen plays). FRESH8 075729@2917: tap (500, 13500), the game's three
                # Skeletons at (10001, 7212) / (10500, 8079) / (11002, 7212), deploying, centre (10500, 7500).
                elif OWN_BODYPT3 and ev['name'] == 'Skeletons' and len(g['members']) == 3 and math.hypot(g['x'] - p['x'], g['y'] - p['y']) >= OWN_BODYPT_D:
                    ev.update(x=round(g['x']), y=round(g['y']), body_moved=[p['x'], p['y']])
                if ev['name'] == 'GoblinDrill' and os.environ.get('PARITY_DRILL_TAP') != '1':   # H-DRILL-SURFACE
                    s = drill_surface(tr, g['side'], g['card_id'], p['tick'])
                    if s:
                        ev.update(x=s[0], y=s[1], dig=True)
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
    # H-PRESS-DEAD (diag_night/r6b): a press replayed from its tap (no cast seen) needs an own Hero Ice Wizard on the board at
    # its tick; with none on the last frame at or before it, the live press did nothing (5 of the 20 tap-only presses of the
    # 126 upgraded matches; 055812@4019 the hero died on 4175, the press estimate fell on 4189 and the SIM, whose hero
    # lived on, froze an Electro Giant the live one never was).
    own_hero = {t for t, bodies in m['frames'] if any(bd['side'] == m['side'] and not bd['tower'] and
                (catalog.get(bd['card_id']) or {}).get('display_name') == 'IceWizard' and
                form_of(bd['card_id'], catalog[bd['card_id']]) == 2 for bd in bodies)}
    for a in m['abilities']:
        wait = elixir_wait(a['tick'], a.get('elixir'), HERO_IW_ABILITY_COST)
        tick = round(a['tick']+delay+wait)
        if any(e['kind'] == 'ability' and e['side'] == m['side'] and abs(e['tick'] - tick) <= 30 for e in seen):
            continue
        k = bisect_left(ticks, tick + 1) - 1
        if k < 0 or ticks[k] not in own_hero:
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
            # H-PRESPELL (W8 round 4; default 'spawn' since 10-20, PARITY_PRESPELL=off|all): a seen spell still in flight / its area running at
            # the start frame (fights.py flags it spell_in_flight_at_start, an unclean fight) is not set up; start before its
            # cast instead, so it is replayed. 'spawn': the spawning spells only (a Goblin Barrel's goblins, a Graveyard's
            # skeletons: in the J6 round-2 dumps 15 of 24 unclean failures had a live enemy from one that the SIM lacked).
            inflight = [e['tick'] for e in events if PRESPELL and e.get('source') == 'spell_seen' and i >= 0
                        and e['tick'] < ticks[i] <= e.get('end', e['tick']) and (PRESPELL == 'all' or e['name'] in PRESPELL_SPAWN)]
            if not (born or dead or inflight) or i < 0:
                break
            i = min(([bisect_left(ticks, min(born)) - 1] if born else []) + ([bisect_left(ticks, min(dead))] if dead else [])
                    + ([bisect_left(ticks, min(inflight)) - 1] if inflight else []))
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
    def __init__(self, table=None):
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
        self.b = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides={'cards.CARD_TABLE': json.dumps(table or CARD_TABLE), **extra})
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
            units = d.get('units') or {}
            self._stats |= {n: units[n] for n in TOWER_TROOPS if isinstance(units, dict) and n in units}
        except (AttributeError, KeyError, ValueError):
            self._stats = {}

    def stats(self, name):
        return self._stats.get(name, {})

    # The crown tower troop each side fields in the match being replayed (run_match sets it; None = the Princess).
    troops = (None, None)

    def tower_name(self, side, king):
        """The card-table row of `side`'s king or princess-slot tower: KingTower, the side's tower troop, or PrincessTower."""
        return 'KingTower' if king else (self.troops[side] or 'PrincessTower')

    def troop_level(self, name, princess_max_hp):
        """The tower level at which tower troop `name`'s princess-slot record has exactly this max_hp; None if none, or if
        the SIM cannot field tower troops (Battle.set_tower_troops: the ClashBot RoyaleSim fork). Resets the battle."""
        if not hasattr(self.b, 'set_tower_troops'):
            return None
        for lv in range(16, 0, -1):
            key = ('troop', name, lv)
            if key not in self._tower:
                try:
                    self.b.set_tower_troops(name, None)
                    self.b.reset(1, [[0], [0]], 0, 200, None, None, [], tower_levels=[lv, lv])
                    self._tower[key] = json.loads(self.b.state_json())['players'][0]['tower_max_hp'][1]
                except ValueError:
                    self._tower[key] = None
                finally:
                    self.b.set_tower_troops(None, None)
            if self._tower[key] == princess_max_hp:
                return lv
        return None

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
            # H-FORM-ELIXIR (diag_night/r6c): the probe's elixir topped up, as child_entity's: a 7-elixir card (Evo Mega
            # Knight, Evo P.E.K.K.A., Evo Electro Giant, Evo Royal Recruits) was refused at the reset's start elixir, so
            # every set-up body of those forms flagged setup_form_not_set (345 fights with a set-up Evo Mega Knight, 0 strict)
            after['players'][1]['mana'] = after['calib']['max_mana']*after['mana_unit']
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

    def child_proxy(self, parent, max_hp, rider=True):
        """(card, level) whose own unit is the unit `parent` makes with this max_hp (Witch's Skeleton -> Skeletons).
        rider=False skips the second-summon rows: a Goblin Giant's Spear Goblin whose Giant is dead is the rider's death
        spawn (the ground SpearGoblin, same hp), not the flying rider (H-DISMOUNT, diag_night/r5a)."""
        key = (parent, max_hp) if rider else (parent, max_hp, 'dismounted')
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
            hit = next(((role, u) for role, u, hp in rows[1:] if hp == max_hp and (rider or role != 'second_summon')), None)
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
            # the caster's own half (the Log is territory-bound), 9.7 tiles from its princess towers: out of their reach,
            # so a slow spell (Rocket, Fireball) lands before any arrow (diag_night/r3a; at 12000 / 20000 a Rocket read 158)
            b, y = self.b, (17500 if side == 1 else 14500)
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

    def snare_id(self):
        """SIM buff id of the Ram Rider's BolaSnare (SNARE_BUFF; ids are interned per table): the first buff a Ram Rider's
        bola hangs on a Knight, probed once (diag_night/r3c: id 27, 2000 ms on the 160402017 table). None if the probe
        sees none. Resets the battle: call before a fight's setup (cached)."""
        if 'snare' not in self._form:
            b, K, out = self.b, 18, None
            try:
                b.reset(1, [[self.ids['Knight']], [self.ids['RamRider']]], 0, 200, None, None,
                        [(0, self.ids['Knight'], 9000*K, 14000*K, -1), (1, self.ids['RamRider'], 9000*K, 19000*K, -1)],
                        levels=[[11], [11]], tower_levels=[11, 11])
                E = json.loads(b.save())['ents']
                kn = next(i for i in range(len(E['alive'])) if E['alive'][i] and E['team'][i] == 'Blue' and E['kind'][i] == 'Troop')
                for _ in range(120):
                    b.step([], 1)
                    E = json.loads(b.save())['ents']; slots = len(E['buffs']) // len(E['alive'])
                    out = next((s['id'] for s in E['buffs'][kn*slots:(kn+1)*slots] if s['id']), None)
                    if out or not E['alive'][kn]:
                        break
            except (ValueError, KeyError, StopIteration):
                out = None
            self._form['snare'] = out
        return self._form['snare']

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

    def first_cycle(self, name, probe=True):
        """{age: (spawn_ms, spawn_wave_left)} the record of a PLAYED spawner card holds `age` ticks after its creation tick,
        up to its first wave (H-SPAWN-BORN, diag_night/r5c firstwave.py: first child at creation + 38 for Witch, Fire Spirit
        Hut, Dark Witch and + 19 for Tombstone, the same in the SIM's played path and live, 77 / 77 Witches); None for a card
        that spawns no timed waves. probe=False reads the cache only (a probe resets the battle)."""
        key = ('first', name)
        if key not in self._form and probe:
            out = None
            if self.spawn_table(name) is not None:
                b = self.b
                b.reset(1, [[self.ids['Knight']], [self.ids[name]]], 0, 200, [10000, 10000], [[4824, 0, 0], [4824, 0, 0]], [],
                        levels=[[15], [15]], tower_levels=[15, 15])
                b.step([(1, 0, 9000*18, 24000*18)], 0)
                E = json.loads(b.save())['ents']
                seen = {j for j in range(len(E['alive'])) if E['alive'][j]}
                i, born, rec = None, None, {}
                for t in range(1, 400):
                    b.step([], 1)
                    E = json.loads(b.save())['ents']
                    new = [j for j in range(len(E['alive'])) if E['alive'][j] and j not in seen]
                    if i is None:
                        i = next((j for j in new if E['spawned_by'][j] is None), None)
                        born = t
                    if i is None:
                        continue
                    if any(E['spawned_by'][j] is not None for j in new) or not E['alive'][i]:
                        out = rec; break
                    rec[t - born] = (E['spawn_ms'][i], E['spawn_wave_left'][i])
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
                    if form and hasattr(b, 'set_tower_troops'):      # a tower troop's own shot (Blue's princess slots)
                        b.set_tower_troops(form, None)
                    try:
                        b.reset(1, [[self.ids['Knight']], [self.ids['Knight']]], 0, 200, None, None,
                                [(1, self.ids['Golem'], 9000*K, (9500 if name == 'KingTower' else 11000)*K, 10**6)],
                                levels=[[11], [11]], tower_levels=[level, level])
                    finally:
                        if form and hasattr(b, 'set_tower_troops'):
                            b.set_tower_troops(None, None)
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

    def bomb_template(self, name, side, level):
        """The death-bomb spell record (save()['spells'] row: SpellMotion::Flight with the bomb row's DeployTime as its delay,
        state.rs `phase_reap`) a `side` `name` at `level` leaves when it dies, killed at 1 hp by the enemy princess tower;
        None if its death leaves none. Resets the battle: call before a fight's setup (cached)."""
        key = ('bomb', name, side, level)
        if key not in self._form:
            b, K, out = self.b, 18, None
            y = 10000 if side == 1 else 22000
            try:
                b.reset(1, [[self.ids[name]], [self.ids[name]]], 0, 200, None, None, [(side, self.ids[name], 14500*K, y*K, 1)],
                        levels=[[level], [level]], tower_levels=[11, 11])
                for _ in range(150):
                    b.step([], 1)
                    sp = [s for s in json.loads(b.save())['spells'] if 'Flight' in s.get('motion', {})
                          and s.get('team') == ('Blue', 'Red')[side]]
                    if sp:
                        out = sp[0]; break
            except (ValueError, KeyError):
                out = None
            self._form[key] = out
        return self._form[key]

    def throw_template(self, name, level):
        """A real in-flight throw record (save()['throws'] row, state.rs `ThrowRun`) of a Red hero `name` at `level` pressed in a
        scratch battle (its card / level are what a landing reads); None if no throw starts. Resets the battle: call before a
        fight's setup (cached)."""
        key = ('throw', name, level)
        if key not in self._form:
            from scratchpad.gauntlet.L74.parity.mechanics import load_edited
            b, K, out = self.b, 18, None
            try:
                b.reset(1, [[self.ids['Knight']], [self.ids[name]]], 0, 200, None, None, [(0, self.ids['Knight'], 9000*K, 20000*K, -1)],
                        forms=[[0], [2]], levels=[[11], [level]], tower_levels=[11, 11])
                def full():          # Red's elixir topped up (the play, then the press)
                    sv = json.loads(b.save()); after = json.loads(json.dumps(sv))
                    after['players'][1]['mana'] = after['calib']['max_mana']*after['mana_unit']
                    load_edited(b, sv, after)
                full()
                b.step([(1, 0, 9000*K, 23000*K)], 0)
                b.step([], 40)
                full()
                b.step([(1, self.sim.HAND_SIZE, 0, 0)], 0)
                for _ in range(40):
                    b.step([], 1)
                    th = json.loads(b.save()).get('throws') or []
                    if th:
                        out = th[0]; break
            except (ValueError, KeyError):
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
        # A copy the Clone made reports its original's card in the SIM; the live reader shows it under the Clone card
        # (1 hp): name it 'Clone' so it pairs with the live copy and is not one of the original card's bodies
        # (diag_night/r4e H-CLONE: 235516@451 scored 4 SIM-only Minion Horde copies as misses).
        try:
            cloned = {u for u, c, _ in self.b.clone_states() if c}
        except AttributeError:
            cloned = set()
        for row in st['entities']:
            e = dict(zip(self.F, row))
            if e['card_id'] == -1:
                x = e['x']//18
                out.append(dict(id=f"T{e['team']}" + ('K' if abs(x-9000) < 1000 else 'L' if x < 9000 else 'R'),
                                side=e['team'], x=x, y=e['y']//18, hp=e['hp'], max_hp=e['max_hp'], tower=True))
                continue
            name = 'Clone' if e['uid'] in cloned else self.cat[e['card_id']]['name']
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
        eng.snare_id()
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
    # H-TIMEOUT: nothing after the match time-out is a fight outcome: the live units decay to 0 over t6000-6017 and the SIM's go
    # on t6002-6004, so a body alive at the time-out would 'die' 12-16 ticks apart (diag_night/r4c endtick.py: the 9 overtime
    # matches of the 218-log cohort all end on t6000). ponytail: a fixed ladder time-out (3 + 2 min); other modes need theirs.
    frames = [fr for fr in frames if fr[0] < TIME_OUT_TICK] or frames
    start = frames[0][1]
    for bd in start:               # spawner cycles on the t0 board: probed before this fight's reset (it resets the battle)
        c = catalog.get(bd['card_id'])
        if not bd['tower'] and c and c['display_name'] in eng.ids:
            eng.spawn_table(c['display_name']); eng.first_cycle(c['display_name'])
    flags = Counter()
    shots = inflight_shots(m, fight, start, catalog, levels, tower_levels) if m['ext'] else []
    for s_ in shots:               # templates probed before this fight's reset (a probe resets the battle); cached
        s_['tpl'] = eng.shot_template(*s_['key'])
    gm = gm_signals(m, fight, start, catalog) if m['ext'] else {}     # GM rocket template: probed before the reset too
    gm_tpl = {s_: eng.shot_template('GoblinMachine', 0, levels.get((s_, 'GoblinMachine')) or levels.get((s_, '*')) or 15)
              for s_, g in gm.items() if g['flying']}
    # A death bomb on its fuse at t0 (a Giant Skeleton / Balloon / Bomb Tower whose death leaves one: card table death_spawn
    # character *Bomb, no hitpoints, DeployTime 3000) is no body: the reader shows only its blast (the card's fx row, 60 ticks
    # after the parent's first missing frame on 10 of 12 captured deaths), so a parent gone before t0 left nothing on the setup
    # board (diag_night/r3c 004922@3452: a Giant Skeleton gone 3392, its bomb kills our full-hp Hero IW on 3453-3454 live,
    # never in the SIM). SIM law (probed): the bomb spell is made on the death tick d with the row's DeployTime as delay,
    # -50 a tick, lands on d + 61; the live death is put on the parent's first missing frame G (the fixture's IW alive on
    # G + 60, gone on G + 62).
    bombs = []
    tr0 = tracks(m['frames'][max(0, fight['frame0'] - 40):fight['frame0'] + 1])
    ticks0 = [t for t, _ in m['frames']]
    for r in tr0.values():
        c = catalog.get(r['card_id']) or {}
        name = c.get('display_name')
        if r['last'] >= t0 or name not in eng.ids or r['max_hp'] < .45*top[r['side'], r['card_id']]:
            continue
        if not str(((eng.stats(name).get('death_spawn') or {}).get('character') or '')).endswith('Bomb'):
            continue
        G = ticks0[bisect_left(ticks0, r['last']) + 1]
        tpl = eng.bomb_template(name, r['side'], levels.get((r['side'], name)) or levels.get((r['side'], '*')) or 15)
        fuse = tpl and tpl['motion']['Flight']['delay_ms']
        if tpl and G <= t0 and t0 - G <= fuse//50:
            bombs.append((r, tpl, fuse - 50*(t0 - G)))
    throw_tpl = {}
    for j in fight['events']:
        e = events[j]
        if e['kind'] == 'throw' and e['side'] not in throw_tpl:
            throw_tpl[e['side']] = eng.throw_template(e['name'], levels.get((e['side'], e['name'])) or levels.get((e['side'], '*')) or 15)
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
                          worn=bd['hp'] < bd['max_hp'], as_card=name, **({'live_xy': (bd['x'], bd['y'])} if (x, y) != (bd['x'], bd['y']) else {})))
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
            if proxy and proxy[0] == '__parent__' and not any(
                    o['side'] == bd['side'] and o['card_id'] == bd['card_id'] and not o['tower'] and
                    eng.level(c['display_name'], o['max_hp']) is not None and math.hypot(o['x']-bd['x'], o['y']-bd['y']) <= 1500
                    for o in start):
                # H-DISMOUNT (diag_night/r5a): no mount of its card within 1.5 tiles -> the rider came down when its mount
                # died; set it up as the rider's death spawn (ground), if the card has one at this hp. A clone of the rider
                # stayed flying: 141825@1113, our Skeletons walked under two dismounted Spear Goblins they attack live.
                proxy = eng.child_proxy(c['display_name'], bd['max_hp'], rider=False) or proxy
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
                                                                   eng.cat[eng.ids[c['display_name']]].get('champion') if c['display_name'] in eng.ids else False)                     and not (CHAMP_CASTS and m['ext'] and c['display_name'] in CHAMP_STATE10):
                heroes.add(c['display_name'])
    for h in heroes:
        flags['opp_ability_unobserved:'+h] += 1
    # A body of a real card id the catalog does not map, played inside the window (core.py leaves the hero Electro Wizard
    # 203000042 unmapped: the engine refuses its form, 'surge is not simulated'), is no event (deployments() drops it), so
    # the SIM fights without it while the fight stayed strict (diag_night/r3b 004922@4012: its 350 zap on our Tesla, the
    # live Tesla dies 4228, the SIM one lives). Card-less rows (-1: reader artefacts) are left alone.
    for cid in {bd['card_id'] for _, bodies in frames for bd in bodies if not bd['tower'] and bd['card_id'] >= 0} - set(catalog):
        flags[f'event_card_missing:unmapped_{cid}'] += 1
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
            need(e['side'], e['name'], 0 if CHAMP_CASTS and e['name'] in CHAMP_STATE10 else 2)
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
    # A side's crown tower troop (run_match: Engine.troops) makes its princess slots at this reset; cleared after it, so
    # the probes that reset the battle between fights keep the Princess.
    if any(eng.troops):
        b.set_tower_troops(*eng.troops); flags['setup_tower_troop'] += 1
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
    finally:
        if any(eng.troops):
            b.set_tower_troops(None, None)
    from scratchpad.gauntlet.L74.parity.mechanics import load_edited
    sv = json.loads(b.save()); pub = json.loads(b.state_json())
    # Catalogue id -> the engine's internal card id, per side. The public `deck` lists the cards in setup order, NOT the
    # save's hand + queue (cycle) order: zipping the two played the wrong card whenever the reset put another card in
    # hand slot 0 (diag_night/r4e H-DECKMAP: 034530@2567 played an Elixir Collector for the Angry Barbarians, deck
    # [100, 20, 103, 31, 43, ...] vs hand [43, 20, 112, 31] + queue [109, ...]). The public hand and next card are in the
    # save's order (exact); the internal ids grow with the catalogue ids, so the sorted lists pair the rest.
    internal = {}
    for t in (0, 1):
        pp, sp = pub['players'][t], sv['players'][t]
        mono = dict(zip(sorted(pp['deck']), sorted(sp['hand'] + sp['queue'])))
        exact = dict(zip(pp['hand'] + ([pp['next_card']] if pp.get('next_card') is not None else []), sp['hand'] + sp['queue'][:1]))
        if any(mono.get(c) != v for c, v in exact.items()):
            flags['setup_deckmap_inexact'] += 1
            mono.update(exact)
        if mono != dict(zip(pp['deck'], sp['hand'] + sp['queue'])):
            flags['setup_deckmap_fixed'] += 1
        internal[t] = mono
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
        if ref[0] == 'none':
            return None
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
    # H-SHIELD-3C (diag_night/r6b): a capture with the reader's phase-3c rows shows every body's shield hp: the setup body
    # gets exactly that (and the ceiling does not redraw it, perturb). 201510@3062: Royal Recruits at full hp whose shields
    # were gone took the Log's and our Ice Wizard's damage on their hp live; the set-up ones carried full shields. A body
    # with no row keeps the rule above.
    stick = max((t for t in m.get('shields') or {} if t0 - 2 <= t <= t0), default=None)
    sh_now = m['shields'][stick] if stick is not None else {}
    gen0 = {x['id']: x.get('gen') for x in start}
    shield_seen = {bd['id'] for bd in setup if gen0.get(bd['id']) in sh_now}
    worn = [bd for bd in setup if bd.get('worn') or bd['id'] in shield_seen]
    if worn:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        team = ('Blue', 'Red')
        for bd in worn:
            i = next((i for i in range(len(E['card'])) if E['alive'][i] and E['team'][i] == team[bd['side']]
                      and E['pos'][i] == {'x': round(bd['x']*18), 'y': round(bd['y']*18)} and E['kind'][i] in ('Troop', 'Building')), None)
            if i is None:
                continue
            if bd['id'] in shield_seen and E['shield'][i] > 0:
                # a native shield only (the SIM's setup gives one): an ability shield (the Hero Knight's) is not a setup column
                v = min(E['shield'][i], max(0, sh_now[gen0[bd['id']]]))
                if v != E['shield'][i]:
                    flags['setup_shield_seen_set'] += 1
                E['shield'][i] = v; flags['setup_shield_seen'] += 1
            elif bd.get('worn') and bd['id'] not in shield_seen and E['shield'][i] > 0:
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
            elif k == 'fired_at':
                j = ent(E, v) if 'fired_at' in E else None
                if j is None:
                    flags['setup_fired_at_not_set'] += 1
                else:
                    E['fired_at'][i] = {'index': j, 'generation': E['generation'][j]}
            elif k.startswith('dash_') and k not in E:
                flags['setup_dash_no_field'] += 1     # a runtime without the dash columns
            else:
                E[k][i] = v
        if 'hide' in kv:
            seen_hide[ref[1]['id']] = kv['hide']
    for ref, kv in edits:
        i = ent(E, ref) if 'dash_state' in kv and 'dash_state' in E else None
        if i is not None:
            E['dash_target'][i] = E['target'][i]      # the stand's target = the t0 target (phase3_state, applied above)
            if E['target'][i] is None:
                E['dash_state'][i], E['dash_mark'][i] = 'None', 0; flags['setup_dash_stand_no_target'] += 1
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
        back_frames = {t: bodies for t, bodies in m['frames'] if t0 - 40 <= t < t0}
        for s_ in shots:
            if s_['tgt'] is None:
                # A target-less straight shot (inflight_shots): the shooter's real straight record at its live point, flying to
                # its live end point; an Executioner's axe (a pingpong throw) gets its throw clock from its distance out and
                # holds its thrower; the enemies its live path already passed (centre within ProjectileRadius + radius on a
                # frame of this leg up to t0) go in its hit set, so they are not hit twice.
                i = ent(E, ref(s_['src'])) if ref(s_['src']) else None
                st = json.loads(json.dumps((s_['tpl'] or {}).get('straight'))) if (s_['tpl'] or {}).get('straight') else None
                if st is None or i is None:
                    flags['setup_shot_skipped:targetless_' + ('not_straight' if st is None else 'source')] += 1
                    continue
                p = json.loads(json.dumps(s_['tpl']))
                ox, oy = E['pos'][i]['x']/18, E['pos'][i]['y']/18
                ax, ay = s_['aim']
                leg = s_['track']
                if st['period'] > 0:
                    rng, s0 = max(1., math.hypot(ax-ox, ay-oy)), st['start']/18
                    d = math.hypot(s_['x']-ox, s_['y']-oy)
                    a = math.asin(min(1., max(0., (d-s0)/max(1., rng-s0))))*st['period']/math.pi
                    back = bool(leg) and math.hypot(leg[-1][1]-ox, leg[-1][2]-oy) > d
                    st['t'] = max(1, min(st['period'], round(st['period']-a if back else a)))
                    st['thrower'] = {'index': i, 'generation': E['generation'][i]}
                    st['carry'] = 0
                    leg = [q for q in leg if (2*(st['t']-(t0-q[0])) > st['period']) == (2*st['t'] > st['period'])]
                st['origin'] = dict(E['pos'][i]); st['hold'] = 0
                side = by_setup[s_['src']]['side']
                hit = set()
                for t, x, y in leg + [(t0, s_['x'], s_['y'])]:
                    for bd in (back_frames.get(t) or start):
                        if bd['tower'] or bd['side'] == side or bd['id'] not in by_setup:
                            continue
                        j = ent(E, ('body', by_setup[bd['id']]))
                        if j is not None and math.hypot(bd['x']-x, bd['y']-y) <= (st['reach'] + E['radius'][j])/18:
                            hit.add(j)
                st['hit'] = [{'index': j, 'generation': E['generation'][j]} for j in sorted(hit)]
                p.update(team=E['team'][i], pos={'x': round(s_['x']*18), 'y': round(s_['y']*18)}, aim={'x': round(ax*18), 'y': round(ay*18)},
                         target={'index': i, 'generation': E['generation'][i]}, firer={'index': i, 'generation': E['generation'][i]},
                         firer_card=E['card'][i], frac={'x': 0, 'y': 0}, straight=st)
                after['projectiles'].append(p); flags['setup_shot_targetless'] += 1
                continue
            i, j = (ent(E, ref(s_['src'])) if ref(s_['src']) else None), (ent(E, ref(s_['tgt'])) if ref(s_['tgt']) else None)
            if s_['tpl'] is None or i is None or j is None:
                flags['setup_shot_skipped:' + ('no_template' if s_['tpl'] is None else 'source' if i is None else 'target')] += 1
                continue
            p = json.loads(json.dumps(s_['tpl']))
            p.update(team=E['team'][i], pos={'x': round(s_['x']*18), 'y': round(s_['y']*18)}, aim=dict(E['pos'][j]),
                     target={'index': j, 'generation': E['generation'][j]}, firer={'index': i, 'generation': E['generation'][i]},
                     firer_card=E['card'][i], frac={'x': 0, 'y': 0})
            after['projectiles'].append(p); flags['setup_shot_in_flight'] += 1
            if s_.get('volley'):
                flags['setup_shot_volley'] += 1         # H-VOLLEY: the central arrow of a multi-row volley, the rest dropped
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_shot_not_set'] += 1

    # The Goblin Machine's rocket (fork combat.GOBLIN_MACHINE_ROCKET; save()['evo']['rockets'], absent on PyPI): a setup GM
    # starts with no cooldown and no mark, so it marked on t0 + 1 where the live one was on its 5000 ms cooldown, or had a
    # mark pending (diag_night/r2 162405@3238: a mark on our King tower made on t0; 5 of the 14 strict fights with a
    # signal on the t0 board were imperfect). Its last live signal (the GM card's area, life 9999, counting 50 a tick
    # from its creation) gives the mark tick M: cooldown 5000 - 50 (t0 - M), and a mark still pending (rocket on M + 20)
    # at the signal point, 1000 - 50 (t0 - M) left. A rocket already flying at t0 (a target-less GM projectile row) is
    # injected at its live point aimed at that signal. ponytail: 50 ms a tick (an Ice Wizard slow runs the clock at 35),
    # one GM per side (two GMs of a side: left as set up).
    if gm:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        runs = (after.get('evo') or {}).get('rockets')
        for bd in (setup if runs is not None else ()):
            if bd.get('proxy') or catalog[bd['card_id']]['display_name'] != 'GoblinMachine' or bd['side'] not in gm:
                continue
            if sum(x['side'] == bd['side'] and catalog[x['card_id']]['display_name'] == 'GoblinMachine' for x in setup) != 1:
                flags['setup_gm_ambiguous'] += 1; continue
            i = ent(E, ('body', bd))
            sig = gm[bd['side']]
            if i is None or t0 - sig['M'] >= GM_COOLDOWN_MS//50:
                continue
            aim = {'x': round(sig['x']*18), 'y': round(sig['y']*18)}
            foes = [j for j in range(len(E['alive'])) if E['alive'][j] and E['team'][j] != E['team'][i]
                    and E['kind'][j] in ('Troop', 'Building', 'PrincessTower', 'KingTower') and not E['flying'][j]]
            j = min(foes, key=lambda j: math.hypot(E['pos'][j]['x']-aim['x'], E['pos'][j]['y']-aim['y']), default=None)
            left = GM_SIGNAL_MS - 50*(t0 - sig['M'])
            mark = [aim, {'index': j, 'generation': E['generation'][j]}, left] if left > 0 and j is not None else None
            runs.append({'id': {'index': i, 'generation': E['generation'][i]}, 'cooldown_ms': GM_COOLDOWN_MS - 50*(t0 - sig['M']),
                         'mark': mark})
            flags['setup_gm_mark' if mark else 'setup_gm_cooldown'] += 1
            for x, y in sig['flying']:
                tpl = gm_tpl.get(bd['side'])
                if tpl is None or j is None or not tpl.get('fixed'):
                    flags['setup_gm_rocket_skipped'] += 1; continue
                p = json.loads(json.dumps(tpl))
                p.update(team=E['team'][i], pos={'x': round(x*18), 'y': round(y*18)}, aim=aim,
                         target={'index': j, 'generation': E['generation'][j]}, firer={'index': i, 'generation': E['generation'][i]},
                         firer_card=E['card'][i], frac={'x': 0, 'y': 0})
                after['projectiles'].append(p); flags['setup_gm_rocket_in_flight'] += 1
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_gm_not_set'] += 1

    # An Evo Tesla's ring (the area it makes as it surfaces: life 1500 ms, growing from Radius to MaxRadius; state.rs
    # `ring_pass`, save()['evo']['rings']) still under way at t0 is not on a setup board, so the enemies it had yet to
    # reach were never hit or stopped (diag_night/r2, skel 214908@2843: 350 ms left at t0, the Prince takes 237 and the
    # stop live at t0 + 1, never in the SIM; 3 of the 5 strict fights with a ring on the t0 board imperfect). The ring is
    # made `made` = t0 - (1500 - its row's remaining ms) / 50 on its Tesla's point; the enemies the reader shows carrying
    # its stop (phase-2 Tesla_EV1_WithDamage) are taken already.
    rings = [(bd, mk) for bd, mk in tesla_rings(m, fight, setup, start, catalog)] if m['ext'] else []
    if rings:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        rr = (after.get('evo') or {}).get('rings')
        buffs = (m.get('buffs') or {}).get(max((t for t in m.get('buffs') or {} if t0 - 6 <= t <= t0), default=None), {})
        hit = {g for g, v in buffs.items() if any(n == 'Tesla_EV1_WithDamage' for n, _ in v)}
        by = {bd['id']: bd for bd in setup}
        for bd, made in (rings if rr is not None else ()):
            i = ent(E, ('body', bd))
            if i is None:
                flags['setup_ring_not_found'] += 1; continue
            taken = []
            for x in start:
                if x.get('gen') in hit and x['side'] != bd['side']:
                    j = ent(E, ('tower', x['side'], x['x'], x['y']) if x['tower'] else ('body', by[x['id']]) if x['id'] in by else ('none',))
                    if j is not None:
                        taken.append({'index': j, 'generation': E['generation'][j]})
            rr.append({'id': {'index': i, 'generation': E['generation'][i]}, 'team': E['team'][i], 'card': E['card'][i],
                       'level': E['level'][i], 'at': dict(E['pos'][i]), 'made': made, 'taken': taken})
            flags['setup_ring'] += 1
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_ring_not_set'] += 1

    # An Evo Musketeer's snipes (state.rs `evo_created`, save()['evo']['snipers']: [unit, snipes left, aimed target]) start
    # only on her creation from a play; a set-up one "starts none of these", so the SIM never snipes where the live one
    # still held some (diag_night/r3a 012807@3463: live snipes at t0 + 138 (Skeleton) and t0 + 212 (our Hero IW, 12
    # tiles), the SIM none; AmmoCount 3 in the card table). Left = 3 - her live shots before t0 from beyond
    # SNIPE_FROM_MT (live: 3 per Musketeer, 7.9-28.9 tiles out; her ordinary shots <= 7.1).
    if m['ext']:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        sn = (after.get('evo') or {}).get('snipers')
        at = None
        for bd in (setup if sn is not None else ()):
            c = catalog.get(bd['card_id']) or {}
            if bd.get('proxy') or c.get('display_name') != 'Musketeer' or form_of(bd['card_id'], c) != 1:
                continue
            at = at or dict(m['frames'])
            i = ent(E, ('body', bd))
            if i is None:
                flags['setup_snipe_not_found'] += 1; continue
            used, last = 0, None
            for t in sorted(k for k in m['proj'] if k < t0):
                lf = {x['id']: x for x in at.get(t, ())}
                for q in m['proj'][t]:
                    if q[7] != bd['id'] or not q[8] or q[8] not in lf or bd['id'] not in lf:
                        continue
                    if last and last[0] == q[8] and t - last[1] <= 4:
                        last = (q[8], t); continue
                    last = (q[8], t)
                    a, v = lf[bd['id']], lf[q[8]]
                    used += math.hypot(a['x'] - v['x'], a['y'] - v['y']) > SNIPE_FROM_MT
            left = max(0, SNIPE_AMMO - used)
            sn[:] = [s for s in sn if s[0]['index'] != i] + [[{'index': i, 'generation': E['generation'][i]}, left, None]]
            flags['setup_snipes:%d' % left] += 1
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_snipe_not_set'] += 1

    # H-MK-SEQ (diag_night/r6c): an Evo Mega Knight's uppercut is the swing his phase-3 attack row shows at sequence 0
    # (seq_idx flips 0 -> 1 -> 0 at each swing, a jump leaves it; mkseq.py: 59 / 59 first swings at 0, 66 / 66 jumps
    # unchanged, all 32 throws on a sequence-0 swing). A set-up one starts with no count in the SIM (save()['evo']
    # ['uppercut_counts']: [unit, count]; his next swing's count is (count + 1) % 2, an uppercut on 0), so his next swing
    # is set from his t0 row: seq 0 -> count 1; seq 1 -> 0 (or 2, below). ponytail: every = 2 (the only Evo Mega Knight).
    att = m.get('attacks') or {}
    if att:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        uc = (after.get('evo') or {}).get('uppercut_counts')
        live0 = {x['id']: x for x in start}
        for bd in (setup if uc is not None else ()):
            c = catalog.get(bd['card_id']) or {}
            if bd.get('proxy') or c.get('display_name') != 'MegaKnight' or form_of(bd['card_id'], c) != 1:
                continue
            g = (live0.get(bd['id']) or {}).get('gen')
            row = next((att[t][g] for t in range(t0, t0 - 7, -1) if g is not None and g in att.get(t, {})), None)
            i = ent(E, ('body', bd))
            if row is None or row[5] not in (0, 1) or i is None:
                flags['setup_mk_seq_unseen'] += 1; continue
            # seq 1: his last swing was the uppercut; the fork's combat.UPPERCUT_STAND = client16402_after_throw holds him in
            # its stand on a count of 0 and not on 2 (a killing uppercut, the same parity): 0 only while he stands (state 0)
            n = 1 if row[5] == 0 else 0 if (live0.get(bd['id']) or {}).get('state') == 0 else 2
            uc[:] = [u for u in uc if u[0]['index'] != i] + [[{'index': i, 'generation': E['generation'][i]}, n]]
            flags['setup_mk_seq:%d' % row[5]] += 1
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_mk_seq_not_set'] += 1

    # An invisible-when-idle unit (the Royal Ghost: card table idle_invisibility; target.rs `invisible_at`) is visible from
    # the tick after its last hit (state.rs: reveal_from = hit + 1) for its idle time + 5 ticks; a set-up one has
    # reveal_from 0, "hidden from its first frame to its first hit", so no enemy could target a Ghost the live game showed
    # revealed (diag_night/r3c). Its last live hit before t0 is read off its phase-3 progress rows (the count-up attack
    # clock: a hit where progress crosses a multiple of HitSpeed, ATTACK_PHASE_1016; a row with no row of its own in the 6
    # ticks before counts from 0). A Ghost the phase-2 rows show carrying its invisibility buff at t0 is hidden and left as set
    # up (220623: the 'Invisibility' row is there exactly while it is hidden). ponytail: 50 ms a tick (an Ice Wizard slow
    # runs the clock at 35: hit estimated early).
    att = m.get('attacks') or {}
    if att:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        live0 = {x['id']: x for x in start}
        bnow = (m.get('buffs') or {}).get(max((t for t in m.get('buffs') or {} if t0 - 6 <= t <= t0), default=None), {})
        for bd in (setup if 'reveal_from' in E else ()):
            c = catalog.get(bd['card_id']) or {}
            st = eng.stats(c.get('display_name'))
            g, hs = (live0.get(bd['id']) or {}).get('gen'), st.get('hit_speed_ms') or 0
            if bd.get('proxy') or not ((st.get('idle_invisibility') or {}).get('time_ms') or 0) > 0 or g is None or hs <= 0:
                continue
            i = ent(E, ('body', bd))
            if i is None:
                flags['setup_ghost_not_found'] += 1; continue
            if any(n == st['idle_invisibility'].get('buff') for n, _ in bnow.get(g, ())):
                flags['setup_ghost_hidden_seen'] += 1; continue
            hit, prev = None, None
            for t in sorted(t for t in att if t0 - 100 <= t <= t0):
                row = att[t].get(g)
                if row is None:
                    continue
                pb = row[2] or 0
                pa = prev[1] if prev and t - prev[0] <= 6 and prev[1] <= pb else 0
                if pb // hs > pa // hs:
                    hit = t - (pb % hs)//50
                prev = (t, pb)
            if hit is not None:
                E['reveal_from'][i] = hit + 1
                flags['setup_ghost_revealed' if t0 < hit + 1 + st['idle_invisibility']['time_ms']//50 + 5 else 'setup_ghost_rehidden'] += 1
            else:
                flags['setup_ghost_hidden'] += 1
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_ghost_not_set'] += 1

    # H-EKSEED: an Evo Knight's own reduction (Knight_Fortify_EV1) is off from its hit while it keeps attacking; a set-up one
    # has idle_back 0 (on), so the SIM reduced hits the live Knight took whole (diag_night/r4c, 20261017_072528@2556: 63 vs
    # 158). A set-up Evo Knight the t0 buff rows show WITHOUT its fortify (a tick with rows lists every unit carrying a buff)
    # starts off: idle_back = tick + 2, which the SIM's idle_buff_pass extends while it attacks.
    btick = max((t for t in m.get('buffs') or {} if t0 - 6 <= t <= t0), default=None)
    if btick is not None:
        bnow = m['buffs'][btick]
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        live0 = {x['id']: x for x in start}
        now = json.loads(b.state_json())['tick']
        for bd in (setup if 'idle_back' in E else ()):
            c = catalog.get(bd['card_id']) or {}
            g = (live0.get(bd['id']) or {}).get('gen')
            if bd.get('proxy') or c.get('display_name') != 'Knight' or form_of(bd['card_id'], c) != 1 or g is None:
                continue
            if any(n == 'Knight_Fortify_EV1' for n, _ in bnow.get(g, ())):
                flags['setup_fortify_on'] += 1; continue
            i = ent(E, ('body', bd))
            if i is None:
                flags['setup_fortify_not_found'] += 1; continue
            E['idle_back'][i] = now + 2
            flags['setup_fortify_off'] += 1
        if after != before:
            try:
                load_edited(b, before, after)
            except Exception:
                flags['setup_fortify_not_set'] += 1

    if bombs:
        before = json.loads(b.save()); after = json.loads(json.dumps(before))
        for r, tpl, left in bombs:
            p = json.loads(json.dumps(tpl)); x, y = r['traj'][-1][1:]
            p['team'] = ('Blue', 'Red')[r['side']]
            # left <= 0: the fuse ran out on t0 (the SIM marks that tick with i32::MIN and lands the blast on the next)
            p['motion']['Flight'].update(pos={'x': round(x*18), 'y': round(y*18)}, aim={'x': round(x*18), 'y': round(y*18)},
                                         frac={'x': 0, 'y': 0}, delay_ms=left if left > 0 else -2**31)
            after['spells'].append(p); flags['setup_death_bomb'] += 1
        try:
            load_edited(b, before, after)
        except Exception:
            flags['setup_death_bomb_not_set'] += 1

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
            st = eng.stats(eng.tower_name(bd['side'], k.endswith('K')) if bd['tower'] else catalog[bd['card_id']]['display_name'])
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

    # H-ORDER (diag_night/r6a): set-up bodies take the live creation order (live_creation_order).
    gen0 = {x['id']: x.get('gen') for x in start}
    before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
    got = {}
    for bd in setup:
        i = ent(E, ('body', bd))
        if i is not None and gen0.get(bd['id']) is not None and i not in got:
            got[i] = gen0[bd['id']]
    live_creation_order(E, got)
    if after != before:
        try:
            load_edited(b, before, after); flags['setup_order_live'] += 1
        except Exception:
            flags['setup_order_not_set'] += 1

    # H-SNAP-BACK (diag_night/r7a): Battle.reset refuses a spawn on a water cell, so a live ground body inside the SIM's
    # impassable half-cells is set up on the nearest passable point (add(), median 165 mt away for Skeletons); live, the
    # body stands there and walks on (the river band at a bridge edge: 4,000+ live rows in 30 upgraded logs, and the SIM's
    # own walkers enter those cells too, only a spawn may not). The save takes any point: after setup each snapped body is
    # put back on its live point (pairing and the ceiling's history follow it).
    back = [(j, bd) for j, bd in enumerate(setup) if bd.get('live_xy')]
    if back:
        before = json.loads(b.save()); after = json.loads(json.dumps(before)); E = after['ents']
        moved = []
        for j, bd in back:
            i = ent(E, ('body', bd))
            if i is not None:
                E['pos'][i] = {'x': round(bd['live_xy'][0]*18), 'y': round(bd['live_xy'][1]*18)}; moved.append((j, bd))
        try:
            if moved:
                load_edited(b, before, after)
            for j, bd in moved:
                bd['x'], bd['y'] = bd['live_xy']
                if j < len(spawns):
                    spawns[j] = spawns[j][:2] + (round(bd['x']*18), round(bd['y']*18)) + spawns[j][4:]
                flags['setup_snap_back'] += 1
        except Exception:
            flags['setup_snap_back_not_set'] += 1

    def play(e):
        before = json.loads(b.save()); after = json.loads(json.dumps(before))
        if e['kind'] == 'throw':
            # the unseen throw lands on the next throw pass: in flight, its aim reached (state.rs `throw_pass`)
            tpl = throw_tpl.get(e['side'])
            if tpl is None:
                return 'NO_THROW_TEMPLATE'
            p = json.loads(json.dumps(tpl)); pt = {'x': round(e['x']*18), 'y': round(e['y']*18)}
            p.update(team=('Blue', 'Red')[e['side']], flying=True, pos=pt, aim=dict(pt), frac={'x': 0, 'y': 0}, target=None)
            after['throws'] = (after.get('throws') or []) + [p]
            load_edited(b, before, after)
            return 'OK'
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
        pts = form_live.get(id(e)) if (FORM_ORACLE or FORM_SYM) else None
        if pts:
            pre = set(i for i, a_ in enumerate(json.loads(b.save())['ents']['alive']) if a_)
        r = b.step([(e['side'], slot, round(e['x']*18) if 'x' in e else 0, round(e['y']*18) if 'y' in e else 0)], 0)[0]
        if pts and sim.DEPLOY_REASONS[r[1]] == 'OK':
            # W19 FORMATION ORACLE (diagnostic, never a landed law): once its members exist (the tick after the command),
            # they are put on the points the live members were first seen on (nearest one-to-one), to measure what an exact
            # formation law would be worth
            pending.append([pts, e['side'], pre, 0])
        return sim.DEPLOY_REASONS[r[1]]

    form_live, pending = {}, []

    def apply_pending():
        import itertools
        for item in list(pending):
            pts, side, pre, tries = item
            bf = json.loads(b.save()); af = json.loads(json.dumps(bf)); E = af['ents']
            new = [i for i, a_ in enumerate(E['alive']) if a_ and i not in pre and E['team'][i] == ('Blue', 'Red')[side]
                   and E['kind'][i] == 'Troop']
            item[3] += 1
            if len(new) == len(pts):
                best = min(itertools.permutations(range(len(pts))), key=lambda pm: sum(
                    math.hypot(E['pos'][i]['x']/18 - pts[j][0], E['pos'][i]['y']/18 - pts[j][1]) for i, j in zip(new, pm)))
                for i, j in zip(new, best):
                    E['pos'][i] = {'x': round(pts[j][0]*18), 'y': round(pts[j][1]*18)}
                try:
                    load_edited(b, bf, af); flags['form_oracle'] += 1
                except Exception:
                    flags['form_oracle_not_set'] += 1
                pending.remove(item)
            elif item[3] >= 3:
                flags['form_oracle_unmatched'] += 1
                pending.remove(item)
    if FORM_SYM:
        # W19 round 2 probe (harness emulation of an engine law, opt-in): the 10-19 live client lays three Skeletons on a
        # symmetric ring, r 580 at 90 / 210 / 330 degrees in the owner's frame (live after 10-19 ~10:00: (-500, -287),
        # (0, +580), (+500, -287) in 60 % of mid-field deploys; before: the fork's lane-shifted ring in 91 %)
        for e in evs:
            if e['kind'] == 'play' and e['name'] in FORM_SYM and e['side'] == m['side'] and 'x' in e and FORM_SYM_FROM <= m['match'][10:23]:
                fy = 1 if e['side'] == 0 else -1
                own_y = e['y'] if e['side'] == 0 else 32000 - e['y']
                if 3000 <= own_y < 13000 and 1000 <= e['x'] <= 17000:   # off the clamps: own rows 13500+, back wall, edge columns keep the fork's
                    form_live[id(e)] = [(e['x'] + dx, e['y'] + dy * fy) for dx, dy in ((-500, -287), (0, 580), (500, -287))]
    if FORM_ORACLE:
        trw = tracks([f for f in m['frames'] if t0 - 4 <= f[0] <= t1])
        for e in evs:
            if e['kind'] == 'play' and e['name'] in FORM_ORACLE and e['side'] == m['side'] and 'x' in e:
                cand = [q for q in trw.values() if q['side'] == e['side'] and (catalog.get(q['card_id']) or {}).get('display_name') == e['name']
                        and e['tick'] - 2 <= q['first'] <= e['tick'] + 80]
                if cand:
                    f1 = min(q['first'] for q in cand)
                    form_live[id(e)] = [(q['x'], q['y']) for q in cand if q['first'] <= f1 + 2]

    def simulate(rng=None):
        """(rows, refused, game over). rng None: the replay as built. Else: the setup state reloaded, hidden state redrawn
        (perturb) and each play's tick redrawn from its frame gap / the match's tap residuals (noise ceiling)."""
        ticked = sorted(((e['tick'] if rng is None else jitter_tick(e, rng)), i) for i, e in enumerate(evs))
        if rng is not None:
            b.load(base.encode() if isinstance(base, str) else base)
            perturbed.update(perturb(eng, rng, hist, who, towers0, seen_hide, inferred, observed, shield_seen))
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
                if pending:
                    b.step([], 1); apply_pending()
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
    twins = swarm_twins(m, fight) if spell else None
    view = lambda rows_, k: card_view(rows_, k, initial_pairs(rows_, setup, catalog), anchor, until, spell, eng.reach, catalog,
                                      roster=roster, twins=twins)
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
            return eng.stats(eng.tower_name(bd['side'], bd['id'].endswith('K'))), False, True
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


def perturb(eng, rng, hist, who, towers0, seen=None, inferred=None, observed=(), shield_seen=()):
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
            c = eng.stats(eng.tower_name(side, kind == 'KingTower'))
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
        if E['shield'][i] > 0 and near and lid not in shield_seen:
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


def card_view(rows, which, pairs, anchor, until, spell, reach, catalog, window=SPELL_WINDOW, roster=None, twins=None):
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
        if twins:
            out['twins'] = {k: g for k, g in twins.items() if k in enemy or k in life}
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


def swarm_twins(m, fight, back=100):
    """{live id: group} of indistinguishable swarm siblings around a fight: bodies of one side, card id and max_hp first seen
    on the same frame near the same parent (a same-card body with more max_hp, born before, alive or gone at most 15 ticks
    before, within 3 tiles: deployments()' near-parent rule), e.g. a Skeleton Balloon's 7 skeletons. Their spawn ring's
    order is not public (diag_night/r3c 004922@1682: live and SIM Tornado kills on the same ticks, on swapped skeletons).
    Only groups of 2+; a body first seen on the scan's first frame (birth unknown) is never grouped."""
    fr = [f for f in m['frames'][max(0, fight['frame0'] - back):] if f[0] <= fight['t1']]
    tr = tracks(fr)
    at = lambda q, t: max((p for p in q['traj'] if p[0] <= t), default=q['traj'][0])
    groups = defaultdict(list)
    for r in tr.values():
        if r['first'] == fr[0][0]:
            continue
        par = [(math.hypot(at(q, r['first'])[1] - r['x'], at(q, r['first'])[2] - r['y']), q['id']) for q in tr.values()
               if q['side'] == r['side'] and q['card_id'] == r['card_id'] and q['max_hp'] > r['max_hp']
               and q['first'] < r['first'] <= q['last'] + 15]
        par = [p for p in par if p[0] < 3000]
        if par:
            groups[r['side'], r['card_id'], r['max_hp'], r['first'], min(par)[1]].append(r['id'])
    return {k: n for n, ids in enumerate(v for v in groups.values() if len(v) > 1) for k in ids}


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
        pairs, keys = [], sorted(set(a['passed']) | set(b['passed']))
        for k in keys:
            h = min(v['passed'][k] for v in (a, b) if k in v['passed']) + 4
            pairs.append((fate(a, k, h), fate(b, k, h)))
    elif a['spell']:
        keys = sorted(set(a['hit']) | set(b['hit']))
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
    order = lambda v: (v == 'missing', v is None, v if isinstance(v, int) else 0)

    def unmatched(xs, ys):
        # The most of xs that can be matched one-to-one to ys by `same` (ascending, each to the earliest unused one it
        # matches: a maximum matching for this tolerance); returns how many of xs are left unmatched.
        free, left = sorted(ys, key=order), 0
        for x in sorted(xs, key=order):
            j = next((j for j, y in enumerate(free) if same(x, y)), None)
            if j is None:
                left += 1
            else:
                free.pop(j)
        return left
    mis = sum(not same(x, y) for x, y in pairs)
    if not a['spell']:
        # A troop card's bodies have no public identity, so their death lists are compared as multisets (H-SWARM-MATCH,
        # diag_night/r4b): zipping the two sorted lists counts ONE body that dies early or late as a mismatch of every
        # body after it (live [1183, 1205, 1239, ...] vs SIM [1205, 1227, 1243, ...] = 8 of 15), so a 15-body Skeleton
        # Army failed its floor(0.1 x 15) = 1 allowed miss on one displaced death. With fewer than 10 bodies no miss is
        # allowed and the verdict cannot change (a perfect matching of sorted lists is the sorted zip).
        mis = unmatched([x for x, _ in pairs], [y for _, y in pairs])
    tw = {**(a.get('twins') or {}), **(b.get('twins') or {})} if a['spell'] else {}
    if tw:
        # Indistinguishable swarm siblings (swarm_twins: one parent, one frame, one card / max_hp; views since r3c) are
        # compared as a multiset: the most of a group's live fates that can be matched one-to-one to its SIM fates by
        # `same` (ascending, each to the earliest unused one it matches: a maximum matching for this tolerance) agree, the
        # rest count as mismatches. A kill of a swapped sibling on the same tick agrees; a fate that differs still counts.
        grp = defaultdict(lambda: ([], []))
        mis = 0
        for k, (x, y) in zip(keys, pairs):
            if k in tw:
                grp[tw[k]][0].append(x); grp[tw[k]][1].append(y)
            else:
                mis += not same(x, y)
        mis += sum(unmatched(xs, ys) for xs, ys in grp.values())
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


def gm_signals(m, fight, start, catalog, look=110):
    """Ext logs: {side: dict(M, x, y, flying)} -- each side's latest Goblin Machine signal (an fx row of the GM's card) in
    the `look` ticks up to t0: its creation tick M (the row counts 50 a tick down from 9999), its point, and the live points
    of that side's target-less GM projectiles (rockets) in flight at t0."""
    t0, i0 = fight['t0'], fight['frame0']
    name = lambda cid: (catalog.get(cid) or {}).get('display_name')
    out = {}
    for t, _ in m['frames'][max(0, i0-look):i0+1]:
        if t < t0 - look:
            continue
        for e in m['fx'].get(t, ()):
            if name(e[3]) == 'GoblinMachine':
                M = t - round((9999 - e[4])/50)
                if e[0] not in out or M >= out[e[0]]['M']:
                    out[e[0]] = dict(M=M, x=e[1], y=e[2], flying=[])
    for p in m['proj'].get(t0, ()):
        if name(p[3]) == 'GoblinMachine' and not p[8] and p[0] in out:
            out[p[0]]['flying'].append((p[1], p[2]))
    return out


def tesla_rings(m, fight, setup, start, catalog):
    """Ext logs: [(setup Evo Tesla body, ring creation tick)] for each Evo Tesla area row (the Tesla card's fx row) on the
    t0 frame within 1000 of a same-side setup Evo Tesla: made = t0 - (EVO_RING_MS - remaining ms) / 50."""
    t0 = fight['t0']
    live = {bd['id']: bd for bd in start}
    out = []
    for e in m['fx'].get(t0, ()):
        if (catalog.get(e[3]) or {}).get('display_name') != 'Tesla' or not 0 < e[4] <= EVO_RING_MS:
            continue
        for bd in setup:
            a = live.get(bd['id'])
            c = catalog.get(bd['card_id']) or {}
            if (a and not bd.get('proxy') and bd['side'] == e[0] and c.get('display_name') == 'Tesla' and form_of(bd['card_id'], c) == 1
                    and math.hypot(a['x'] - e[1], a['y'] - e[2]) <= 1000):
                out.append((bd, t0 - round((EVO_RING_MS - e[4])/50)))
                break
    return out


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
        # A dasher (card table 'dash': Bandit, Mega Knight) standing before its dash at t0: its stand clock runs from the
        # first tick it did not step (T) to dash_mark = T + DashCooldown / 50 - 1 (state.rs `phase_path16402`), kept through
        # a target switch (combat.DASH_STAND_RETARGET); a setup body starts with no stand and walks (diag_night/r3b
        # 001415@341: the live Bandit stands 331-346 on our Skeletons, switches to the Tesla put down at 343 and dashes it on
        # 347; the SIM Bandit walks to it). Stand = state 1, not moved since the previous frame, last step within the window;
        # T from the last moving gap's step count. Its dash_target is the t0 target (phase3_state), set after the edits.
        dash = c.get('dash')
        if dash and st == 1 and len(hist[bd['id']]) >= 3:
            h = hist[bd['id']]
            j = next((j for j in range(len(h) - 1, 0, -1) if (h[j][1], h[j][2]) != (h[j-1][1], h[j-1][2])), None)
            if j is not None and j < len(h) - 1 and all(q[3] == 1 for q in h[j-1:]):
                gap = h[j][0] - h[j-1][0]
                steps = min(gap, max(1, round(math.hypot(h[j][1]-h[j-1][1], h[j][2]-h[j-1][2]) / (c.get('speed') or 60))))
                trig = h[j-1][0] + steps + 1
                mark = trig + dash['cooldown_ms']//50 - 1
                # fork combat.DASH_STAND_SLOW: a stand under an Ice Wizard slow at t0 (phase-2 rows) is taken slowed since
                # its trigger: lag = (t0 - trigger) x (50 - 35) ms, due ceil(lag / 50) ticks after the mark.
                # ponytail: the slow is read at t0 only (one buff row), not per elapsed tick.
                b2 = (m.get('buffs') or {}).get(max((t for t in (m.get('buffs') or {}) if t0 - 6 <= t <= t0), default=None), {})
                lag = (t0 - trig) * 15 if any(n in SLOW_BUFFS for n, _ in b2.get(a.get('gen'), ())) and t0 > trig else 0
                if mark + -(-lag // 50) >= t0:
                    out.append((('body', bd), dict(dash_state='Standing', dash_mark=mark, dash_blocked=False, dash_lag_ms=lag)))
                    flags['setup_dash_stand' + ('_slowed' if lag else '')] += 1
                else:
                    flags['setup_dash_stand_overdue'] += 1
    # Spawner timers: a setup spawn starts its cycle fresh (Fire Spirit Hut 1950 ms, Tombstone at once), the live one is
    # mid-cycle. Its last wave is seen: children of the same side and card, smaller max_hp, first seen within 3.5 tiles
    # of it. The SIM record is set to what it holds that many ticks after the same child of a wave (spawn_table).
    tick_of = [t for t, _ in m['frames']]
    tr = None
    # H-SPAWN-SLOW (W19 round 1): a spawner's cycle runs at 35 / 50 under an Ice Wizard slow, live as in the SIM (live Witch
    # waves 140 ticks apart unslowed, 140 / (1 - 0.3 x slowed share) slowed: 155 at 32 %, 177 at 70 %; SIM probe 140 -> 200
    # fully slowed). Its elapsed cycle since the last wave (or its creation) is counted at that rate over the ticks the live
    # buff rows show it slowed; before, every tick counted whole and the SIM wave came early (20261017_195826@3135: 14 ticks).
    btick = sorted(m.get('buffs') or {}) if SPAWN_SLOW else []

    def slowed(g, lo, hi):
        if g is None or not btick:
            return 0
        n, i = 0, max(0, bisect_left(btick, lo) - 1)
        while i < len(btick) and btick[i] < hi:
            t = btick[i]; nxt = btick[i + 1] if i + 1 < len(btick) else hi
            if min(nxt, hi) > max(t, lo) and any(nm in SLOW_BUFFS for nm, _ in m['buffs'][t].get(g, ())):
                n += min(nxt, hi) - max(t, lo)
            i += 1
        return n
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
                # its creation tick from the phase-3b fields (m['births']) when the capture has them, else mid-gap
                kids.append((m.get('births') or {}).get(r['gen'], ((prev + 1 + r['first'])//2,))[0])
        if not kids:
            # H-SPAWN-BORN (diag_night/r5c): no wave yet, but the capture timed its creation (phase-3b births): the record is
            # what a played one holds that many ticks after its creation (Engine.first_cycle), not a fresh cycle from t0 --
            # 162943@5518 a Witch made 32 ticks before t0 spawned on 5524 live, on 5538 in the SIM (first wave = creation + 38).
            born = (m.get('births') or {}).get(a.get('gen'), (None,))[0]
            first = eng.first_cycle(catalog[a['card_id']]['display_name'], probe=False) if born is not None else None
            age = None if born is None else t0 - born - round(.3 * slowed(a.get('gen'), born, t0))
            if first and age in first:
                ms, wl = first[age]
                out.append((('body', bd), dict(spawn_ms=ms, spawn_wave_left=wl))); flags['setup_spawner_born'] += 1; continue
            flags['setup_spawner_unseen'] += 1; continue
        kids.sort()
        last, k = kids[-1], 1
        for t in kids[-2::-1]:
            if last - t > 13:
                break
            k += 1
        ms, wl = tab[min(tab, key=lambda q: abs(q - k))]
        left = ms - 50*(t0 - last) + 15*slowed(a.get('gen'), last, t0)
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
                elif name == SNARE_BUFF and eng.snare_id():
                    # the Ram Rider's bola snare (-70 % speed, 2000 ms; the rider ranks its carriers last): a set-up target
                    # had none, so it walked on at full speed (diag_night/r3c 001415@990: our Knight snared 1400 ms at t0
                    # walked 17 mt a tick live; the set-up one was 0.5 tile ahead by t0 + 15 and took other targets)
                    out.append((r, dict(buff=(eng.snare_id(), rem)))); flags['setup_snare_buff'] += 1
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
    of every t0-board body (setup bodies, proxies included, and towers) as the reader shows it at t0, or at t0 - 1 advanced one
    tick by the measured rule (ATTACK_PHASE_1016: progress += step, 50 / 35 under an Ice Wizard slow / 0 frozen,
    carried across hits; the load timer re-armed to LoadTime on the crossing tick, else -50, held while frozen):
      * attack_ms = progress (the SIM's count-up counter, same rule), attack_load_ms = load;
      * attack_phase: Idle at progress 0, Cooldown on the fire tick (progress mod HitSpeed < step), else Windup;
      * target = the body / tower with the target's generation id (None when the reader shows none); target_locked as
        the SIM sets it after a step (projectile attackers in Windup; probed on 0.1.35: Musketeer / X-Bow 1, Knight /
        Tesla 0).
    Not set (no SIM field): the previous target, the pre-attack countdown, the attack-sequence index (flagged when
    non-zero). The live ids returned are observed: the ceiling does not redraw their attack state (perturb).
    H-PROXY-P3 (diag_night/r6b): a child set up as the card whose own unit it is (a Witch's / Tombstone's / Graveyard's
    Skeleton as a Skeletons body) is seeded too, with that card's HitSpeed / LoadTime (the unit the SIM runs), and can be
    a target: before, its row was skipped, so it walked from t0 with no target while live it was on our Knight
    (200646@3233: 4 Witch skeletons), and every body on it lost its target (setup_p3_target_unresolved).
    H-FIRED-AT (diag_night/r6b): fired_at = the target, for a projectile attacker (a body whose card fires one, a crown
    tower) the reader shows launching at it since it took it (a proj row from it at that target since the rows last
    named another): the SIM's record of a launch at its target, which keeps a doomed target (targeting.DOOMED_TARGET_DROP:
    a projectile attacker drops a unit the shots in flight will kill unless it has shot at it). A setup body had none, so
    the in-flight shot injected at t0 doomed its own target and the attacker let go of it: 180704@2074, our X-Bow's bolt at
    a 32 hp Skeleton -> the SIM X-Bow took the princess tower on t0 + 2, live it kept the Skeleton and then shot the
    Hero Knight deploying 8 tiles away."""
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
    fmap = {}

    def post_kill_wait(g, tg, prog, late=False):
        """H-POSTKILL (diag_night/r5a): the SIM retarget_wait at t0 of a unit serving combat.POST_KILL_RETARGET_WAIT, or 0.
        Live: its target died on frame L (the first row without it; the victim is off the board there), it has held its
        progress with no target since, and it takes its next target on L + 6. The engine counts the wait from the tick
        after the loss (5 on L + 1, the decision on 0), so a unit set up at t0 in L + 1 .. L + 5 holds L + 6 - t0; a setup
        unit with none scanned on t0 + 1 (112814@1051: a Prince and a Blowdart Goblin whose tower died on 1049 took our
        Knight on t0 + 2, live they waited and took the nearer new Skeleton on 1055). Only a loss 2 or more ticks before
        t0 is seeded: one tick with no target and the progress held is also what a unit exempt from the wait shows (it
        takes its next target on L + 1; v1 seeded our X-Bow and a princess tower so, 113130@1660, 144040@2953,
        141107@819).
        H-POSTKILL-T0 (diag_night/r6d): `late` (a unit with no projectile, no attack-finish override, no load-first-hit:
        what the SIM's wait never exempts) also seeds a loss on t0 - 1 or t0 itself (rw 5, 6). Live, those units took their
        next target on exactly L + 6 in 140 of 162 such cases on the strict t0 boards of the 359 FIN9 logs (melee 94 / 109,
        projectile-less buildings 46 / 53; upgraded only 52 / 62; pkcensus.py); the projectile units and towers, which show
        the exemption, took theirs on L + 2 in 60 of 79 losses on t0 and stay unseeded."""
        if tg is not None or prog <= 0:
            return 0
        rows = [(t, att[t][g]) for t in sorted(att) if t0 - 7 <= t <= tb and g in att[t]]
        had = [k for k, (_, a) in enumerate(rows) if a[0] is not None]
        if not had or had[-1] == len(rows) - 1 or any(a[2] != prog for _, a in rows[had[-1]+1:]):
            return 0
        victim, L = rows[had[-1]][1][0], rows[had[-1]+1][0]
        if not fmap:
            fmap.update((t, bodies) for t, bodies in m['frames'] if t0 - 8 <= t <= t0)
        if any(o.get('gen') == victim and o['hp'] > 0 for o in fmap.get(L, ())):
            return 0          # the target is still on the board: a switch or a walk out of reach, no kill
        rw = L + 6 - t0
        return rw if 1 <= rw <= (6 if late else 4) else 0
    for g, (tg, _prev, prog, load, pre, seq) in att[tb].items():
        bd = gens.get(g)
        r = ref_of(bd) if bd else None
        if r is None or (bd['tower'] and bd['hp'] <= 0):
            continue
        st = eng.stats(eng.tower_name(bd['side'], bd['id'].endswith('K')) if bd['tower'] else
                       by[bd['id']].get('as_card') or catalog[bd['card_id']]['display_name'])
        hs, lt = st.get('hit_speed_ms') or 0, max(0, st.get('load_time_ms') or 0)
        if hs <= 0:
            flags['setup_p3_no_hit_speed'] += 1; continue
        flags['setup_p3_proxy'] += bool(not bd['tower'] and by[bd['id']].get('proxy'))
        names = [n for n, _ in buffs.get(g, ())]
        # ponytail: Freeze / Rage-type buffs other than these names step 50; add their multipliers if a capture shows one
        step = 0 if any('Freeze' in n or n in STUN_BUFFS for n in names) else 35 if any(n in SLOW_BUFFS for n in names) else 50
        wait = post_kill_wait(g, tg, prog, late=not bd['tower'] and not st.get('projectile') and not st.get('override_attack_finish')
                              and not st.get('load_first_hit'))
        if tb < t0:
            if prog > 0 and not wait:         # the wait holds the progress (its load runs down: 112814 Prince 900, 800, 700)
                load = lt if (prog + step)//hs > prog//hs else load if step == 0 else max(0, load - 50)
                prog += step
            else:
                load = max(0, load - 50)
        tref = None
        if tg is not None:
            tbd = gens.get(tg)
            tref = ref_of(tbd) if tbd else None
            if tref is None:
                flags['setup_p3_target_unresolved'] += 1
        phase = 'Idle' if prog <= 0 else 'Cooldown' if prog % hs < step else 'Windup'
        fired = None
        if tref is not None and (bd['tower'] or st.get('projectile')):
            since = tb          # the first row of the run of rows naming tg that ends at tb (100 ticks at most)
            for t in range(tb - 1, t0 - 101, -1):
                if g in att.get(t, ()):
                    if att[t][g][0] != tg:
                        break
                    since = t
            if any(q[7] == bd['id'] and q[8] == tbd['id'] for t in range(since - 2, t0 + 1) for q in (m.get('proj') or {}).get(t, ())):
                fired = tref; flags['setup_p3_fired_at'] += 1
        out.append((r, dict(attack_ms=prog, attack_load_ms=load, attack_phase=phase, target=tref,
                            target_locked=bool(st.get('projectile')) and phase == 'Windup' and tref is not None,
                            **({'retarget_wait': wait} if wait else {}), **({'fired_at': fired} if fired else {}))))
        flags['setup_p3_postkill_wait'] += bool(wait)
        seen.add(bd['id']); flags['setup_p3_attack'] += 1
        flags['setup_p3_pre_unset'] += pre != 0
        flags['setup_p3_seq_unset'] += seq != 0
    flags['setup_p3_from_previous_tick'] += tb < t0 and bool(out)
    return out, seen, +flags


def live_creation_order(E, gens):
    """H-ORDER (diag_night/r6a): deal the creation_seq values of the save's entities `gens` ({index: live generation id})
    out again in generation order (the same values: the counter stays consistent; team_seq is left alone, since
    state.rs rider_arc_offset reads a rider's rank as team_seq[rider] - team_seq[mount] - 1). The SIM runs a tick's move updates in creation_seq order (a unit meets those made before it already
    moved; state.rs phase_path16402_for) and breaks avoidance, targeting and spawn ties by creation_seq / team_seq, but
    Battle.reset makes its spawns in a canonical order of its own (r6a seqprobe.py). The reader's generation id is the live
    creation counter (r6a genmono.py: first sightings follow it on every consecutive pair). Returns E."""
    for col, part in (('creation_seq', lambda i: 0),):
        groups = defaultdict(list)
        for i, g in gens.items():
            groups[part(i)].append((g, i))
        for lst in groups.values():
            for (g, i), v in zip(sorted(lst), sorted(E[col][i] for _, i in lst)):
                E[col][i] = v
    return E


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
    are left out (seen casts; spell_in_flight_at_start), and so are shots without a source (kamikaze Fire / Ice Spirits).
    A TARGET-LESS shot of a t0-board troop (a Bowler's rolling boulder, an Executioner's axe, a pellet whose target died) comes
    with aim (its live end point), track ([(tick, x, y)] of the same projectile serial before t0) and tgt None; run_fight
    injects it only when the shooter's template is a straight shot (diag_night/r4a: 57 strict fights hold a rolling Bowler
    boulder at t0, 32 an Executioner axe; 081712@3319 the boulder kills our Skeletons on t0 + 2 and takes 383 off the Tesla)."""
    by = {bd['id']: bd for bd in start}
    out = []
    for p in m['proj'].get(fight['t0'], ()):
        if (catalog.get(p[3]) or {}).get('type') == 'spell':
            continue
        src, tgt = by.get(p[7]), by.get(p[8])
        if src and not src['tower'] and p[8] is None and p[3] != -1:
            c = catalog.get(src['card_id'])
            if c is None:
                continue
            name = c['display_name']
            track = [(t, q[1], q[2]) for t in sorted(k for k in m['proj'] if fight['t0'] - 40 <= k < fight['t0'])
                     for q in m['proj'][t] if q[6] == p[6]]
            out.append(dict(src=src['id'], tgt=None, x=p[1], y=p[2], aim=(p[4], p[5]), track=track,
                            key=(name, form_of(src['card_id'], c), levels.get((src['side'], name)) or levels.get((src['side'], '*')) or 15)))
            continue
        if not src or not tgt or (tgt['tower'] and tgt['hp'] <= 0):
            continue
        if src['tower']:
            king = src['id'].endswith('K')
            key = ('KingTower' if king else 'PrincessTower', 0 if king else ((m.get('tower_troops') or (None, None))[src['side']] or 0),
                   tower_levels[src['side']])
        else:
            c = catalog.get(src['card_id'])
            if c is None:
                continue
            name = c['display_name']
            key = (name, form_of(src['card_id'], c), levels.get((src['side'], name)) or levels.get((src['side'], '*')) or 15)
        out.append(dict(src=src['id'], tgt=tgt['id'], x=p[1], y=p[2], key=key))
    # H-VOLLEY (diag_night/r7d): the reader shows a volley as one projectile row per arrow -- the Princess's 5 arrows all
    # name her target (volley.py: 602 of 845 Princess frames in 60 logs hold 5 rows at one target, no other firer ever more
    # than 1) -- while the SIM fires the central one alone, on the firer -> target line (its native shot matches live row 1
    # to the mt). Each row was injected as a homing shot with full damage: 20261017_210407@3264, 5 arrows at our Tesla took
    # 1122 at t0 + 6 in the SIM, 231 live. Of one firer's rows at one target, only the one nearest that line is kept.
    grp = defaultdict(list)
    for s in out:
        if s['tgt'] is not None:
            grp[s['src'], s['tgt']].append(s)
    drop = set()
    for (a, b), ss in grp.items():
        if len(ss) > 1:
            A, B = by[a], by[b]
            dx, dy = B['x'] - A['x'], B['y'] - A['y']
            keep = min(ss, key=lambda s: abs((s['x'] - A['x'])*dy - (s['y'] - A['y'])*dx))
            keep['volley'] = len(ss)
            drop |= {id(s) for s in ss if s is not keep}
    return [s for s in out if id(s) not in drop]


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
    # H-CHILDFORM (diag_night/r5d) + H-EVO-CHILD (r5b 130511@5790): a unit an evolved / hero body made (Evo Witch and Hero
    # Tombstone Skeletons, Evo Skeleton Balloon's, Evo Goblin Giant's Spear Goblins) carries its maker's evo / hero card id
    # live, while the SIM spawns it plain (form 0) -> never paired, so a spell that killed it scored misses (1,942 of 2,185
    # Evo Witch bodies unpaired on FIN7). Paired across forms on exactly the same max_hp, after every same-form candidate.
    for a in live:
        if a['tower'] or pairs.get(a['id']) is not None:
            continue
        c = catalog.get(a['card_id'])
        if c is None:
            continue
        for s_ in simb:
            if s_['tower'] or s_['id'] in taken or s_['side'] != a['side'] or s_.get('name') != c['display_name']:
                continue
            f = form_of(a['card_id'], c)
            # a Hero Balloon's thrown Skeletrooper: the hero's card id live (form 2), no hero flag in the SIM (form 0); paired
            # across forms on exactly the same max_hp (diag_night/r3c 234407@3888)
            trooper = f == 2 and s_['form'] == 0 and c['display_name'] in HERO_THROWERS and s_['max_hp'] == a['max_hp']
            child = f != 0 and s_['form'] == 0 and s_['max_hp'] == a['max_hp'] and not trooper
            if (s_['form'] != f and not trooper and not child) or not .6 <= s_['max_hp']/max(1, a['max_hp']) <= 1.67:
                continue
            d = math.hypot(a['x']-s_['x'], a['y']-s_['y'])
            if d < 2500:
                cand.append((d + 2500*child, a['id'], s_['id']))
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
    eng = Engine(table_for(m['match']))
    m['births'] = phase3_births(path) if m['ext'] else {}
    events, delay = deployments(m, catalog, eng.effect_life, own_unit=lambda n, hp: eng.level(n, hp) is not None, stats=eng.stats)
    fights = cut(m, events, window)
    m['buffs'] = phase2_buffs(path) if m['ext'] else {}
    m['attacks'] = phase3_attacks(path) if m['ext'] else {}
    m['shields'] = phase3_shields(path) if m['ext'] else {}
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
    # CROWN TOWER TROOPS: a side whose princess-slot max_hp is no Princess level's but exactly one tower troop's at one
    # level fields that troop at that level (diag_night/tesla tower_hp.py: each princess-slot max_hp on the 10-16 logs
    # matches exactly one (tower, level); 3 of the 27 fully captured matches field a troop, each confirmed by its phase-3
    # load timer: Cannoneer 1400, Chef 200, Duchess 0 as the Princess). Needs a SIM with Battle.set_tower_troops (the
    # fork); a PyPI wheel keeps the Princess, as before.
    troops = [None, None]
    for s_ in (0, 1):
        p = next((b['max_hp'] for b in t0b if b['tower'] and b['side'] == s_ and not b['id'].endswith('K')), None)
        if p is None or any(v and v[1] == p for k_, v in eng._tower.items() if isinstance(k_, int)):
            continue
        for name in TOWER_TROOPS:
            lv = eng.troop_level(name, p)
            if lv:
                troops[s_] = name; tw[s_] = lv
                break
    eng.troops = tuple(troops)
    m['tower_troops'] = eng.troops
    # the phase-3 load timers of the princess slots, as a check (a troop's LoadTime is its own)
    loads = [0, 0]
    gens = {}
    for t, bodies in m['frames']:
        for b in bodies:
            if b['tower'] and not b['id'].endswith('K') and b.get('gen') is not None:
                gens[b['gen']] = b['side']
    for rows in (m.get('attacks') or {}).values():
        for g, v in rows.items():
            if g in gens:
                loads[gens[g]] = max(loads[gens[g]], v[3] or 0)
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
                   tower_troops=list(eng.troops), princess_slot_load_ms=loads if m.get('attacks') else None,
                   ground_samples=dict(ground), ground_in_impassable=dict(blocked),
                   spell_delay_ticks=delay, levels={f'{s}:{n}': v for (s, n), v in levels.items()}, tower_levels=tw,
                   seconds=round(time.monotonic()-t_start, 1), stamp=eng.stamp, ceiling_k=ceiling)
    if m['ext']:
        summary.update(ext=True, phase2=bool(m['buffs']),
                       seen=dict(Counter(f"{e['kind']}:{'own' if e['side'] == m['side'] else 'opp'}:{e['name']}"
                                         for e in events if e['source'] in ('spell_seen', 'cast_seen'))))
        if m['attacks']:
            summary['phase3'] = True
        if m['births']:
            summary['phase3b_births'] = len(m['births'])
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


# Owner goal 10-17: RAW agreement (live vs the perturbed SIMs) lower 95% CI >= .95 per card (n >= 30) and >= .975 overall, with
# the normalised score's lower CI as a floor (>= .88 per card where possible, >= .92 overall). normalised = raw / ceiling and the
# ceiling is <= 1, so a row that meets the raw goal always clears its floor: the floor only binds while raw is below goal.
GOAL_CARD, GOAL_ALL, GOAL_N = .95, .975, 30
FLOOR_CARD, FLOOR_ALL = .88, .92


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
    def row(label, xs, goal, floor):
        ceil = [x['ceil'] for x in xs if x['ceil'] is not None]
        items = [(x['match'], x) for x in xs]
        nm = norm(xs); nlo, nhi = boot_ci(items, norm)
        aci = boot_ci(items, agree)
        floor_ok = nlo is not None and nlo >= floor
        flag = ('insufficient n' if len(xs) < GOAL_N else 'no ceiling' if nm is None else
                'MEETS' if aci[0] is not None and aci[0] >= goal and floor_ok else
                'below (floor met)' if floor_ok else 'below (floor missed)')
        bn, bnc = sum(x['bn'] for x in xs), sum(x['bn_c'] or 0 for x in xs)
        return dict(card=label, n=len(xs), matches=len({x['match'] for x in xs}),
                    agree_unperturbed=round(sum(x['a0'] for x in xs)/len(xs), 3),
                    agree=round(agree(xs), 3), agree_ci=aci,
                    ceiling=round(sum(ceil)/len(ceil), 3) if ceil else None,
                    normalised=round(nm, 3) if nm is not None else None, normalised_ci=(nlo, nhi), goal=goal, floor=floor, flag=flag,
                    whole_fight_outcome=round(sum(x['outcome'] for x in xs)/len(xs), 3),
                    body_miss=round(sum(x['bmis'] for x in xs)/bn, 3) if bn else None,
                    body_miss_ceiling=round(sum(x['bmis_c'] or 0 for x in xs)/bnc, 3) if bnc else None,
                    tower_fail=round(sum(x['tfail'] for x in xs)/len(xs), 3),
                    tower_fail_ceiling=round(sum(x['tfail_c'] for x in xs if x['tfail_c'] is not None)/len(ceil), 3) if ceil else None)
    rows = sorted((row(k, v, GOAL_CARD, FLOOR_CARD) for k, v in groups.items()), key=lambda r: -r['n'])
    every = [x for v in groups.values() for x in v]
    overall = row('OVERALL', every, GOAL_ALL, FLOOR_ALL) if every else None
    out = dict(mode=mode, cohort='stamped' if os.environ.get('PARITY_STAMPED') else 'all', definitions=dict(DEATH_TOL=DEATH_TOL, SWARM_SLACK=SWARM_SLACK, TOWER_FLOOR=TOWER_FLOOR,
                                           TOWER_REL=TOWER_REL, SPELL_WINDOW=SPELL_WINDOW, GOAL_CARD=GOAL_CARD,
                                           GOAL_ALL=GOAL_ALL, GOAL_N=GOAL_N, FLOOR_CARD=FLOOR_CARD, FLOOR_ALL=FLOOR_ALL),
               k=max((len(r['card']['sim'])-1 for r in clean if r.get('card')), default=0), overall=overall, cards=rows)
    Path(out_dir, f'ceiling_{mode}.json').write_text(json.dumps(out, indent=1))
    f = lambda r: (f"{r['card']} | {r['n']} | {r['matches']} | {r['agree_unperturbed']} | {r['agree']} {list(r['agree_ci'])} | "
                   f"{r['ceiling']} | {r['normalised']} {list(r['normalised_ci'])} | {r['flag']} | {r['whole_fight_outcome']} | "
                   f"{r['body_miss']}/{r['body_miss_ceiling']} | {r['tower_fail']}/{r['tower_fail_ceiling']}")
    L = [f"CEILING [{mode}] K={out['k']} perturbed replays per fight; tolerant card agreement (CEILING.md); goal: raw agreement "
         f"(live vs perturbed) lower 95% CI >= {GOAL_CARD} per card (n >= {GOAL_N}), >= {GOAL_ALL} overall; floor: normalised lower "
         f"95% CI >= {FLOOR_CARD} per card, >= {FLOOR_ALL} overall", '',
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
        if os.environ.get('PARITY_STAMPED') and not d['summary'].get('phase3b_births'):
            # --stamped (owner 10-17): grade only matches whose capture times every new body exactly (reader 3b); older
            # captures keep a frame-gap placement noise no fix can remove
            skipped['not_stamped'] += 1; continue
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
    ap.add_argument('--stamped', action='store_true', help='score: only matches with phase-3b creation ticks (the step-d trigger cohort)')
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
        # phase-3b creation ticks per generation id (phase3_births), for the logs whose capture has them
        out['_births'] = {n: b for n in sorted(filter(None, logs)) for b in [phase3_births(n)] if b}
        # phase-3c shield hp per generation id (phase3_shields), for the logs whose capture has them
        out['_shields'] = {n: s for n in sorted(filter(None, logs)) for s in [phase3_shields(n)] if s}
        a.out.write_text(json.dumps(out, separators=(',', ':')))
        print({n: len(v) for n, v in out.items()}); return 0
    if a.mode == 'score':
        if a.stamped:
            os.environ['PARITY_STAMPED'] = '1'
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
