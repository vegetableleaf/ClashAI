"""SIM-side per-unit visual cues: the same fields the live reader captures, from a RoyaleSim Battle.

    from pipeline.sim_unit_state import extract
    cues = extract(battle, memo)      # memo: a dict you keep between calls (optional, see "frac")

Reads only `battle.save()` and `battle.state_json()` (the way the parity harness does) and the card table that ships
inside the royalesim module (activate the runtime first: `pipeline.royale_runtime.activate()` or sys.path). It never
steps or edits the battle. Output is plain dicts/lists, key order and list order deterministic (units by uid, shots
and areas in the engine's list order). Positions are tiles (engine subtiles / 18000), time is ms, fractions 0..1.

Schema (None = not applicable / unknown):
  {'tick': int,
   'units': [{
      'uid': int, 'team': 0|1 (0 = Blue, the engine's first player), 'kind': 'troop'|'building'|'princess_tower'|'king_tower',
      'name': unit type name, 'x','y': tiles, 'hp','max_hp': int,
      'state': 'idle'|'moving'|'engaged'|'deploying'|'jumping'|'tunnelling'|'casting',
         # deploying = deploy timer > 0; tunnelling = underground (Miner/Drill); jumping = river jump or dash in the
         # air; casting = hero ability wind-up; engaged = has a target and the attack cycle runs; moving = a troop with
         # walk speed and nothing above; idle = the rest (buildings, towers, a hidden Tesla). Status effects do NOT
         # change `state` (a frozen walker still reads 'moving'); read `status`.
      'charging': bool, 'charge_frac': 0..1,          # Prince / Dark Prince / Battle Ram: charged = speed doubled
      'hide': 'up'|'hidden'|'rising'|None,            # Tesla-type only; None while it is deploying (live: state 4)
      'attack': {'target': uid|None,   # the ACQUIRED target (inside sight range); the live reader's target also holds a far
                 # default/path target (a tower 19 tiles away): drop it live when farther than sight + 1.5 tiles (S6_CUES_1016.md)
                 'phase': 'idle'|'windup'|'hit', 'frac': 0..1|None,
                 'progress_ms': int, 'hit_speed_ms': int|None, 'load_ms': int},
         # progress_ms is the engine's count-up attack counter (carries across hits, 35/tick under a -30 slow, held
         # frozen); frac = (progress mod hit_speed) / hit_speed; 'hit' = the hit landed this tick (progress mod
         # hit_speed < hit_window_ms, progress > 0; default 50 = one tick, 100 for the live 2-tick sampling); 'idle' = no target or progress 0.
      'status': {'stunned','frozen','slowed','raged','taunted','invisible','shielded': bool,
                 # frozen = speed and hit speed -100 from any source (Freeze, Zap, Tesla evo, stun: the engine has one stun
                 # flag); stunned = only a buff whose own name says stun (rare); taunted: the SIM has no taunt buff (always
                 # False, live shows Knight_hero_IsTauntedBuff); shielded: shield hp, Fortify (idle buff) or a shield buff
                 'slow_frac': remaining/total of the longest slow, or None},
      'buffs': [{'name': alias string "A|B" (names sharing one engine id), 'ms': remaining, 'frac': ms/total|None}]},
      # frac needs `memo`: total = the card table's full duration of the buff where it names one (projectile
      # buff_time_ms: the Ice Wizard slows 2500 ms), else the largest ms this memo saw for (uid, buff); None without
      # memo or for the 999999 "lives as long as the owner" sentinel. An 'A|B' alias takes the longest table duration of
      # its names, so the frac of a merged stun/freeze group is a lower bound only; read `slow_frac` for slows.
   'projectiles': [{'type': projectile table name, 'team', 'x','y','aim_x','aim_y': tiles,
                    'source': uid|None (firer gone), 'target': uid|None (homing target; None for ground-aimed),
                    'effect': {'buff': name, 'ms': int}|None, 'damage': int}],
   'areas': [{'name': spell card, 'team', 'motion': 'Pulsing'|'Airborne'|'Rolling'|..., 'x','y': tiles,
              'remaining_ms': int|None, 'frac': remaining/area life|None}]}   # Tornado/Freeze/Rage... and Log/Rocket in flight
"""
from __future__ import annotations

import json
import sys

K = 18000                 # engine subtiles per tile
HIT_WINDOW_MS = 50        # 'hit' bucket: the tick the attack counter crosses a hit-speed multiple (one 50 ms tick)
SENTINEL_MS = 900_000     # buff "lives as long as the owner" (999999 / 999949 in the table)
_KINDS = {'Troop': 'troop', 'Building': 'building', 'PrincessTower': 'princess_tower', 'KingTower': 'king_tower'}
_tables, _unit_types = {}, {}


def _all_buffs(d):
    """(rows, totals): buff rows by name -- the top-level table plus the rows nested in projectiles / hero abilities (the
    Hero Ice Wizard's IceWizardHeroSlow, ..._SlowBuff, FreezeBuff live only there; without them a slowed body read 'not
    slowed') -- and each buff's full duration in ms where a sibling field names it (projectile buff_time_ms, ability
    time_ms), so `frac` is right for a buff first seen mid-way (a fight started from a live board)."""
    rows, totals = {}, {}

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                if isinstance(v, dict) and 'speed_multiplier_raw' in v and isinstance(v.get('name'), str):
                    rows.setdefault(v['name'], v)
                    ms = o.get('buff_time_ms') or o.get('time_ms')
                    if ms and ms < SENTINEL_MS:
                        totals[v['name']] = max(totals.get(v['name'], 0), ms)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk({k: v for k, v in d.items() if k != 'buffs'})
    return rows | d['buffs'], totals


def _tbl(sim):
    """Card/buff/projectile tables of the embedded 160402017 card table, indexed once per royalesim module."""
    t = _tables.get(id(sim))
    if t is None:
        d = json.loads(sim.EMBEDDED_CARDS_160402017_JSON)
        char = {c['name']: c for c in d['towers']} | {c['name']: c for c in d['cards']}
        for c in d['cards'] + d['evolutions'] + d['hero_forms']:      # unit type name -> its card row
            char.setdefault(c.get('summon_character'), c)
        rows, totals = _all_buffs(d)
        t = _tables[id(sim)] = dict(char=char, cards={c['name']: c for c in d['cards']}, buffs=rows, totals=totals,
                                    proj=d['projectiles'])
    return t


def _unit_names(battle):
    key = battle.unit_types_digest()
    if key not in _unit_types:
        _unit_types[key] = json.loads(battle.unit_types_json())
    return _unit_types[key]


def _statuses(alias, buffs):
    """Set of effect words for one buff alias group ('A|B' = one engine id), from the table's multipliers + names."""
    low, row = alias.lower(), next((buffs[a] for a in alias.split('|') if a in buffs), {})
    spd, hsp = row.get('speed_multiplier_raw') or 0, row.get('hit_speed_multiplier_raw') or 0
    out = set()
    if spd <= -100 or hsp <= -100:
        out.add('frozen')
    elif spd < 0 or hsp < 0:
        out.add('slowed')
    if spd > 0 or hsp > 0 or 'rage' in low:
        out.add('raged')
    for word, tag in (('taunt', 'taunted'), ('invisib', 'invisible'), ('stun', 'stunned'),
                      ('shield', 'shielded'), ('fortify', 'shielded')):
        if word in low and '|' not in alias:      # an 'A|B' group is one engine id: which name is on the unit is unknown
            out.add(tag)
    return out


def extract(battle, memo=None, hit_window_ms=HIT_WINDOW_MS):
    """All visual cues of the battle's current tick (schema in the module docstring). hit_window_ms: width of the
    'hit' bucket; pass 100 to mimic the live reader's 2-tick sampling (a hit is then 'just landed' for 2 ticks)."""
    sim = sys.modules['royalesim']
    T, names = _tbl(sim), _unit_names(battle)
    sv, st = json.loads(battle.save()), json.loads(battle.state_json())
    E, F = sv['ents'], sim.ENTITY_FIELDS
    slots = [i for i, a in enumerate(E['alive']) if a]
    if len(slots) != len(st['entities']):
        raise ValueError('save/state_json entity lists disagree')
    uid = {}
    units = []
    for i, row in zip(slots, st['entities']):
        e = dict(zip(F, row))
        if (e['x'], e['y']) != (E['pos'][i]['x'], E['pos'][i]['y']):
            raise ValueError('save/state_json entity order disagree')
        uid[i] = e['uid']
        name = names[e['unit_type']]
        ct = T['char'].get(name, {})
        hs = ct.get('hit_speed_ms')
        flags = {n for b, n in enumerate(sim.STATUS_BITS) if e['status_flags'] >> b & 1}
        tgt = e['target_uid'] if e['target_uid'] >= 0 else None
        prog, load = E['attack_ms'][i], E['attack_load_ms'][i]
        if tgt is None or prog <= 0:
            phase = 'idle'
        else:
            phase = 'hit' if hs and prog % hs < hit_window_ms else 'windup'
        jumping = E['jumping'][i] or E['dash_state'][i] not in ('None', 'Standing')
        if 'underground' in flags:
            state = 'tunnelling'
        elif e['deploy_ticks'] > 0:
            state = 'deploying'
        elif jumping:
            state = 'jumping'
        elif 'ability_windup' in flags:
            state = 'casting'
        elif tgt is not None and E['attack_phase'][i] != 'Idle':
            state = 'engaged'
        elif E['kind'][i] == 'Troop' and E['speed'][i] > 0:
            state = 'moving'
        else:
            state = 'idle'
        # a Tesla still deploying reads 'deploying' live (state 4), not up/hidden: the hide cue starts when the deploy ends
        hide = E['hide'][i].lower() if ct.get('hides_when_not_attacking') and state != 'deploying' else None
        status = dict.fromkeys(('stunned', 'frozen', 'slowed', 'raged', 'taunted', 'invisible', 'shielded'), False)
        status['frozen'] = e['stun_ticks'] > 0     # the engine's one stun flag = speed and hit speed -100 (Freeze, Zap, Tesla evo...)
        status['invisible'] = 'invisible' in flags
        status['shielded'] = e['shield'] > 0
        slow_frac, buffs = None, []
        for alias, ms in e['buffs']:
            frac = None
            if memo is not None and ms < SENTINEL_MS:
                total = memo[uid[i], alias] = max(ms, memo.get((uid[i], alias), 0),
                                                  *(T['totals'].get(a, 0) for a in alias.split('|')))
                frac = round(ms / total, 3) if total else None
            for tag in _statuses(alias, T['buffs']):
                status[tag] = True
                if tag == 'slowed' and frac is not None:
                    slow_frac = max(slow_frac or 0, frac)
            buffs.append({'name': alias, 'ms': ms, 'frac': frac})
        ib = ct.get('idle_buff')
        if ib and state != 'engaged':
            # BuffWhenNotAttacking (Evo Knight Knight_Fortify_EV1, Super Knight shield): the engine applies the effect
            # implicitly, the live reader lists it as a buff for as long as the unit is not attacking
            for tag in _statuses(ib['buff_name'], T['buffs']):
                status[tag] = True
            buffs.append({'name': ib['buff_name'], 'ms': ib['time_ms'], 'frac': None})
        status['slow_frac'] = slow_frac
        units.append({
            'uid': e['uid'], 'team': e['team'], 'kind': _KINDS[E['kind'][i]], 'name': name,
            'x': round(e['x'] / K, 3), 'y': round(e['y'] / K, 3), 'hp': e['hp'], 'max_hp': e['max_hp'],
            'state': state, 'charging': bool(E['charged'][i]), 'charge_frac': round(e['charge'] / 1000, 3),
            'hide': hide,
            'attack': {'target': tgt, 'phase': phase, 'frac': round(prog % hs / hs, 3) if hs and phase != 'idle' else None,
                       'progress_ms': prog, 'hit_speed_ms': hs, 'load_ms': load},
            'status': status, 'buffs': buffs})
    units.sort(key=lambda u: u['uid'])

    def who(ref):          # {'index','generation'} -> uid while that body is the same one and alive
        return uid.get(ref['index']) if ref and E['generation'][ref['index']] == ref['generation'] else None

    shots = []
    for p, row in zip(sv['projectiles'], st['projectiles']):
        src = who(p['firer'])
        firer = next((u for u in units if u['uid'] == src), None)
        row_t = T['char'].get(firer['name']) if firer else None
        pj = (row_t or {}).get('projectile') or {}
        eff = p['buff'] and {'buff': (T['proj'].get(pj.get('name'), {}).get('target_buff') or {}).get('name'),
                             'ms': p['buff']['time_ms']}
        shots.append({'type': pj.get('name'), 'team': row[0], 'x': round(row[1] / K, 3), 'y': round(row[2] / K, 3),
                      'aim_x': round(row[3] / K, 3), 'aim_y': round(row[4] / K, 3), 'source': src,
                      'target': row[5] if row[5] >= 0 else None, 'effect': eff, 'damage': p['damage']})
    cat = [c[0] for c in json.loads(battle.catalogue_json())]
    areas = []
    for s, row in zip(sv['spells'], st['spells']):
        (motion, m), = s['motion'].items()
        card = cat[row[1]]
        life = ((T['cards'].get(card, {}).get('spell') or {}).get('area_effect_object') or {}).get('life_duration_ms')
        rem = m.get('life_ms')
        areas.append({'name': card, 'team': row[0], 'motion': motion, 'x': round(m['pos']['x'] / K, 3),
                      'y': round(m['pos']['y'] / K, 3), 'remaining_ms': rem,
                      'frac': round(min(1.0, rem / life), 3) if rem is not None and life else None})
    return {'tick': st['tick'], 'units': units, 'projectiles': shots, 'areas': areas}
