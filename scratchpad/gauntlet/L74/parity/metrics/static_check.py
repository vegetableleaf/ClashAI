"""J-ALL-CARDS static stat check (W1, 10-20): the SIM's card table, as the runtime loads it, against
  (1) DEVICE  the game's own tables pulled from the device on 10-12 (apktables device build; private, gitignored), every card;
  (2) LIVE    every (card, level, max_hp) the reader saw on ext frame logs (census_metrics.py levels) -> exact hp at that level;
  (3) WIKI    icebow/config/cards_stats.json (fandom level-11 vardefines, fetched 2026-08-26; may predate later balance changes).
Fields: hp, damage, hit speed, first hit (load time), range, min range, sight, mass, speed, deploy time, collision radius, count,
shield, plus the spell / projectile hop stats apktables already compares. Level 16 = floor(base x ladder[15] / 100) per side.

  python static_check.py OUT.json [--census census.json] [--device cards.json]
Engine: PARITY_SIM_PATH (laptop wheel) or ROYALE_RUNTIME, as fights.py. The table sha is printed (0.1.36 == fork clashbot36).
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scratchpad/gauntlet/L74/apktables'))
import compare as AC  # noqa: E402  apktables projection / diff (exact, unit-preserving)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from pipeline.vocab import engine_key  # noqa: E402

DEVICE = ROOT/'scratchpad/gauntlet/L74/apktables/out/device_builds/20261012T221627332682Z-50188/cards.json'
WIKI = ROOT/'icebow/config/cards_stats.json'
AC.STAT |= {'hitpoints', 'damage', 'load_time_ms', 'load_first_hit', 'minimum_range_milli', 'sight_range_milli', 'mass',
            'collision_radius_milli', 'count', 'speed', 'hit_speed_ms', 'range_milli', 'deploy_time_ms'}
GROUP = {'hitpoints': 'hp', 'shield_hitpoints': 'hp', 'damage': 'damage', 'damage_per_second': 'damage',
         'crown_tower_damage_percent': 'damage', 'hit_speed_ms': 'hit_speed', 'hit_frequency_ms': 'hit_speed',
         'load_time_ms': 'first_hit', 'load_first_hit': 'first_hit', 'range_milli': 'range', 'minimum_range_milli': 'range',
         'sight_range_milli': 'sight', 'mass': 'mass', 'speed': 'speed', 'deploy_time_ms': 'deploy',
         'spawn_character_deploy_time_ms': 'deploy', 'collision_radius_milli': 'radius', 'count': 'count'}
COLUMN = {'Hitpoints': 'hitpoints', 'ProjectileDamage': 'damage', 'CrownTowerDamagePercent': 'crown_tower_damage_percent',
          'AreaBuffTime': 'buff_time_ms'}
EVENT = ('Super', 'Chess', 'TriWizards', 'PrinceBuff', 'GoblinParty', 'GoblinRocketSilo', 'BarbarianLauncher', 'WarmSpell',
         'GlobalClone', 'GlobalLightning', 'RoyalDelivery')     # event / mode-only rows (not ladder cards)


def ladder16(card):
    ls = card.get('level_scaling') or {}
    m = ls.get('multiplier_percent_by_level') or []
    return m[15] if len(m) >= 16 else None


def at16(card, key):
    v, m = card.get(key), ladder16(card)
    return v * m // 100 if isinstance(v, int) and m else None


def resolved(card_name, sim_card, field, dev_value, overrides):
    """An override in the runtime calibration sets exactly the device value on this card (or a unit it names)."""
    leaf = field.rsplit('.', 1)[-1]
    blob = json.dumps(sim_card)
    for ov in overrides:
        v = ov['value']
        if ov['column'] == 'CrownTowerDamagePercent' and v < 0:
            v = 100 + v          # raw encoding: -77 -> 23 (device Fireball 23)
        if COLUMN.get(ov['column']) == leaf and v == dev_value and (ov['card'] == card_name or f'"{ov["card"]}"' in blob):
            return ov
    return None


def device_vs_sim(sim_doc, dev_doc, overrides):
    a, b = AC.cards_by_name(dev_doc), AC.cards_by_name(sim_doc)
    rows = []
    for n in sorted(a.keys() | b.keys()):
        if n not in a or n not in b:
            rows.append(dict(card=n, status='missing_in_' + ('sim' if n not in b else 'device'), diffs=[]))
            continue
        diffs = []
        for d in AC.diff_values(AC.projection(b[n]), AC.projection(a[n])):
            if d['field'].startswith('related_') and d['before'] == AC.MISSING:
                continue     # structural: the SIM table keeps related characters in `units` (compared by units_vs_sim)
            leaf = d['field'].rsplit('.', 1)[-1]
            ov = resolved(n, b[n], d['field'], d['after'], overrides)
            diffs.append(dict(field=d['field'], group=GROUP.get(leaf, 'level' if 'level_scaling' in d['field'] else 'other'),
                              sim=d['before'], device=d['after'], override=bool(ov)))
        left = [d for d in diffs if not d['override']]
        rows.append(dict(card=n, status='mismatch' if left else ('override_resolved' if diffs else 'equal'), diffs=diffs,
                         hp16=(at16(b[n], 'hitpoints'), at16(a[n], 'hitpoints')),
                         dmg16=(at16(b[n], 'damage'), at16(a[n], 'damage')), event=any(e in n for e in EVENT)))
    return rows


def live_vs_sim(census, eng, sim_doc):
    """(label, level, max_hp) seen live -> does the SIM have a unit of that card with that hp at that level?"""
    by = AC.cards_by_name(sim_doc)
    units = sim_doc.get('units') or {}
    seen = Counter()
    for r in census['matches']:
        for lab, lv, hp, n in r.get('levels') or []:
            seen[lab.split(' ', 1)[1] if not lab.startswith('tower') else lab, lv, hp] += n
    tower = {}
    out = []
    for (lab, lv, hp), n in sorted(seen.items(), key=lambda kv: -kv[1]):
        if lab.startswith('tower'):
            if lv not in tower:
                try:
                    eng.b.reset(1, [[0], [0]], 0, 200, None, None, [], tower_levels=[lv, lv])
                    tower[lv] = json.loads(eng.b.state_json())['players'][0]['tower_max_hp']
                except ValueError:
                    tower[lv] = None
            want = tower[lv] and (tower[lv][0] if lab.endswith('king') else tower[lv][1])
            note = None
            if want and want != hp and not lab.endswith('king'):
                # a crown tower troop in the princess slot: its table hp on the princess's ladder (exact probe: the fork's
                # Battle.set_tower_troops, fights.Engine.troop_level; the PyPI wheel has none). ponytail: ratio, +-3 hp
                note = next((t for t in F.TOWER_TROOPS if abs((units.get(t) or {}).get('hitpoints', 0) * want / 1400 - hp) <= 3),
                            'princess slot: no tower troop fits')
            out.append(dict(card=lab.replace('tower own ', 'tower ').replace('tower opp ', 'tower '), side=lab.split()[1], level=lv,
                            live_hp=hp, frames=n, sim_hp=[want], ok=want == hp or (note in F.TOWER_TROOPS), note=note))
            continue
        name, form = (lab[:-4], 1) if lab.endswith(' evo') else (lab[:-5], 2) if lab.endswith(' hero') else (lab, 0)
        cand = set()
        if name in eng.ids:
            try:
                cand |= {h for _, _, h in eng.b.unit_hitpoints(eng.ids[name], lv)}
            except ValueError:
                pass
        rec = by.get(name)
        recs = [rec] if rec else []
        for sec in ('evolutions', 'hero_forms'):
            recs += [c for c in sim_doc.get(sec, []) if (c.get('form_of') or c.get('base') or '') == name or
                     c['name'] in (name + '_EV1', name + '_hero')]
        for c in recs:   # table-derived hp of the form record, every nested hp row (a hero's ability cube) and the units it names
            m = (c.get('level_scaling') or {}).get('multiplier_percent_by_level') or []
            rows = [c] + [u for k, u in units.items() if f'"{k}"' in json.dumps(c)]
            while rows:
                u = rows.pop()
                if isinstance(u, dict):
                    um = (u.get('level_scaling') or {}).get('multiplier_percent_by_level') or m
                    if isinstance(u.get('hitpoints'), int) and len(um) >= lv:
                        cand.add(u['hitpoints'] * um[lv-1] // 100)
                    rows += [v for v in u.values() if isinstance(v, (dict, list))]
                elif isinstance(u, list):
                    rows += u
        out.append(dict(card=name + ('', ' evo', ' hero')[form], level=lv, live_hp=hp, frames=n, sim_hp=sorted(cand)[:12],
                        ok=hp in cand, near=min((abs(hp-c) for c in cand), default=None)))
    return out


def wiki_vs_sim(sim_doc):
    w = json.loads(WIKI.read_text())['cards']
    out = []
    for sec, suf in (('cards', ''), ('evolutions', '_evo'), ('hero_forms', '_hero')):
        for c in sim_doc.get(sec, []):
            base = c['name'].replace('_EV1', '').replace('_hero', '')
            k = (engine_key(base) or '') + suf
            if k not in w or any(e in c['name'] for e in EVENT):
                continue
            ww = w[k]
            m = (c.get('level_scaling') or {}).get('multiplier_percent_by_level') or []
            l11 = lambda v: v * m[10] // 100 if isinstance(v, int) and len(m) > 10 else None
            pairs = dict(hp=(l11(c.get('hitpoints')), ww.get('hitpoints')),
                         damage=(l11(c.get('damage')), ww.get('damage')),
                         hit_speed=(c.get('hit_speed_ms'), round(ww['hit_speed']*1000) if ww.get('hit_speed') else None),
                         speed=(c.get('speed'), round(ww['speed_tiles']*60) if ww.get('speed_tiles') else None),
                         range=(c.get('range_milli'), round(ww['range_tiles']*1000) if ww.get('range_tiles') and c.get('kind') != 'spell' else None),
                         deploy=(c.get('deploy_time_ms'), round(ww['deploy_time']*1000) if ww.get('deploy_time') else None),
                         count=(c.get('count'), ww.get('count') if c.get('kind') == 'troop' else None))
            for f, (s, v) in pairs.items():
                if s is None or v is None:
                    continue
                tol = 1 if f in ('hp', 'damage') else 0      # the wiki rounds its level-11 anchor
                if abs(s - v) > tol:
                    out.append(dict(card=c['name'], field=f, sim_l11=s, wiki_l11=v, wiki_fetched=(ww.get('_src') or {}).get('fetched')))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--census', type=Path)
    ap.add_argument('--device', type=Path, default=DEVICE)
    a = ap.parse_args()
    eng = F.Engine()
    raw = eng.sim.EMBEDDED_CARDS_160402017_JSON
    sim_doc = json.loads(raw)
    eng.b.reset(1, [[0], [0]], 0, 0, None, None, [], tower_levels=[16, 16])
    overrides = json.loads(eng.b.save())['calib']['card_value_overrides']
    dev_doc = json.loads(a.device.read_text())
    dv = device_vs_sim(sim_doc, dev_doc, overrides)
    dv += device_vs_sim(dict(cards=[dict(u, name='unit:' + k) for k, u in (sim_doc.get('units') or {}).items()]),
                        dict(cards=[dict(u, name='unit:' + k) for k, u in (dev_doc.get('units') or {}).items()]), overrides)
    lv = live_vs_sim(json.loads(a.census.read_text()), eng, sim_doc) if a.census else []
    wk = wiki_vs_sim(sim_doc)
    res = dict(stamp=eng.stamp, sim_table_sha256=hashlib.sha256(raw.encode()).hexdigest(), overrides=overrides,
               device=str(a.device.name), device_vs_sim=dv, live_vs_sim=lv, wiki_vs_sim=wk)
    a.out.write_text(json.dumps(res, indent=1))
    st = Counter(r['status'] for r in dv)
    grp = Counter(d['group'] for r in dv if r['status'] == 'mismatch' for d in r['diffs'] if not d['override'])
    print('sim table sha', res['sim_table_sha256'][:16], 'overrides', len(overrides))
    print('DEVICE vs SIM:', dict(st), 'unresolved field diffs by group', dict(grp))
    for r in dv:
        if r['status'] == 'mismatch' and not r['event']:
            print(' ', r['card'], 'hp16 sim/dev', r['hp16'], 'dmg16', r['dmg16'], '|',
                  '; '.join(f"{d['field']}: {d['sim']} -> {d['device']}" for d in r['diffs'] if not d['override'])[:400])
    if lv:
        bad = [r for r in lv if not r['ok']]
        print(f'LIVE vs SIM: {len(lv)} (card, level, max_hp) triples, {sum(r["frames"] for r in lv)} body-frames; '
              f'{len(bad)} without a SIM unit of that hp ({sum(r["frames"] for r in bad)} body-frames)')
        for r in bad[:40]:
            print('  ', r)
    print(f'WIKI vs SIM: {len(wk)} field mismatches beyond rounding')
    for r in wk:
        print('  ', r)


if __name__ == '__main__':
    main()
