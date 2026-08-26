# -*- coding: utf-8 -*-
"""Validate ledger/r2_champions.jsonl and count MATCHING fields against the snapshot.

A "match" = a field the KB row carries whose value the wiki independently confirms.
Every expected value below is transcribed from the archived wikitext (revids in REV),
never from memory.
"""
import json, os

LED = r'C:/Users/benpe/ClashBot/research/sim_parity/ledger'
SNAP = json.load(open(os.path.join(LED, 'current_db_snapshot.json')))['cards']

# ---- schema check -------------------------------------------------------------
REQ = {'key', 'field', 'current_db', 'p1_vardefine', 'p2_table', 'p3_history',
       'sources', 'vote', 'cross_checks', 'verdict', 'notes'}
VOTES = {'2of3', '3of3', 'split'}
VERDICTS = {'match', 'update', 'pin', 'escalate'}
GROUP = ['archer_queen', 'boss_bandit', 'goblinstein', 'golden_knight',
         'little_prince', 'mighty_miner', 'monk', 'skeleton_king']

rows = [json.loads(l) for l in open(os.path.join(LED, 'r2_champions.jsonl'), encoding='utf-8')]
bad = []
for i, r in enumerate(rows):
    if set(r) != REQ:
        bad.append((i, 'keys', set(r) ^ REQ))
    if r['vote'] not in VOTES:
        bad.append((i, 'vote', r['vote']))
    if r['verdict'] not in VERDICTS:
        bad.append((i, 'verdict', r['verdict']))
    if r['key'] not in GROUP:
        bad.append((i, 'key', r['key']))
    if r['cross_checks'].get('edit_war') not in ('pass', 'CHANGED'):
        bad.append((i, 'edit_war', r['cross_checks']))
    if not r['sources'] or not all(set(s) == {'url', 'revid', 'fetched', 'raw'} for s in r['sources']):
        bad.append((i, 'sources', r['field']))
print('SCHEMA:', 'OK' if not bad else bad)
print('rows=%d  keys=%d' % (len(rows), len(set(r['key'] for r in rows))))

# ---- matching fields ----------------------------------------------------------
# (snapshot path, expected value, wiki evidence)  -- expected transcribed from wikitext
M = {
 'archer_queen': [
   ('elixir', 5, 'infobox Cost=5 / table Cost 5'),
   ('hitpoints', 1000, 'vardefine hp_11=1000'),
   ('damage', 225, 'vardefine dmg_11=225'),
   ('hit_speed', 1.2, 'vardefine atk_speed=1.2 / table Hit Speed 1.2 sec'),
   ('dps', 188, '225/1.2=187.5 -> 188'),
   ('speed_tiles', 1.0, 'table Speed Medium (60) -> 60/60'),
   ('deploy_time', 1.0, 'table Deploy Time 1 sec'),
   ('range_tiles', 5.0, 'table Range 5'),
   ('projectile_speed', 800.0, 'table Projectile Speed 800'),
   ('attacks', ['air', 'ground'], 'table Target Air & Ground'),
   ('count', 1, 'table Count x1'),
   ('movement', 'ground', 'table Transport Ground'),
   ('rarity', 'champion', 'table Rarity Champion'),
   ('kind', 'troop', 'table Type Troop'),
   ('champion', True, 'Rarity Champion'),
 ],
 'boss_bandit': [
   ('elixir', 6, 'table Cost 6'), ('hitpoints', 2624, 'vardefine hp_11=2624'),
   ('damage', 244, 'vardefine dmg_11=244'), ('hit_speed', 1.1, 'vardefine atk_speed=1.1'),
   ('dps', 222, '244/1.1=221.8 -> 222'), ('dash_damage', 489.0, 'vardefine dash_11=489'),
   ('dash_time_s', 0.8, 'Dash Attributes Dash Time 0.8 sec'),
   ('leap_speed_tiles', 8.33, 'Dash Attributes Dash Speed 500 -> 500/60=8.333'),
   ('leap_min_tiles', 3.5, 'Dash Range 3.5-6'), ('leap_max_tiles', 6.0, 'Dash Range 3.5-6'),
   ('speed_tiles', 1.5, 'table Speed Fast (90) -> 90/60'),
   ('deploy_time', 1.0, 'table Deploy Time 1 sec'),
   ('range_tiles', 0.8, 'table Range Melee: Short (0.8)'),
   ('attacks', ['ground'], 'table Target Ground'), ('count', 1, 'table Count x1'),
   ('movement', 'ground', 'table Transport Ground'), ('rarity', 'champion', 'table Rarity Champion'),
   ('ability_cost', 1, 'Getaway Grenade Cost 1'),
   ('ability_uses', 2, 'Getaway Grenade Ability Count 2 / History 8/7/2025 "a total of 2 times"'),
   ('ability_cooldown_s', 3.0, 'Ability Cooldown 3 sec / History 8/7/2025 "3-second cooldown"'),
   ('ability_invis_s', 1.0, 'Invisibility Duration 1 sec / prose "invisible for 1 second"'),
   ('ability_back_tiles', 6.0, 'Teleport Range 6 / prose "teleports 6 tiles behind"'),
 ],
 'goblinstein': [
   ('elixir', 5, 'Card Attributes Cost 5'),
   # deploy_time is NOT a match: the KB goblinstein row omits it entirely (see ledger row).
   ('count', 2, 'Doctor x1 + Monster x1'), ('rarity', 'champion', 'Card Attributes Rarity Champion'),
   ('stun_duration_s', 0.5, 'Doctor Attributes Stun Duration 0.5 sec'),
   ('damage', 128, 'vardefine monster_dmg_11=128 (card row carries the MONSTER)'),
   ('hit_speed', 1.5, 'vardefine monster_atk_speed=1.5'),
   ('hitpoints', 2393, 'vardefine monster_hp_11=2393'), ('dps', 85, '128/1.5=85.3 -> 85'),
   ('components.0.hitpoints', 721.0, 'vardefine hp_11=721 (Doctor)'),
   ('components.0.hit_speed', 1.8, 'vardefine atk_speed=1.8 / Doctor Hit Speed 1.8 sec'),
   ('components.0.range_tiles', 5.5, 'Doctor Attributes Range 5.5'),
   ('components.0.speed_tiles', 1.0, 'Doctor Attributes Speed Medium (60)'),
   ('components.0.attacks', ['air', 'ground'], 'Doctor Attributes Target Air & Ground'),
   ('components.0.count', 1, 'Doctor Attributes Count x1'),
   ('components.1.hitpoints', 2393.0, 'vardefine monster_hp_11=2393'),
   ('components.1.damage', 128.0, 'vardefine monster_dmg_11=128'),
   ('components.1.hit_speed', 1.5, 'vardefine monster_atk_speed=1.5'),
   ('components.1.range_tiles', 1.2, 'Monster Attributes Range Melee: Medium (1.2)'),
   ('components.1.speed_tiles', 1.0, 'Monster Attributes Speed Medium (60)'),
   ('components.1.attacks', ['buildings'], 'Monster Attributes Target Buildings'),
   ('components.1.count', 1, 'Monster Attributes Count x1'),
   ('spawn_unit_stats.hit_speed', 1.8, 'Doctor Hit Speed 1.8 sec'),
   ('spawn_unit_stats.range_tiles', 5.5, 'Doctor Range 5.5'),
   ('spawn_unit_stats.speed_tiles', 1.0, 'Doctor Speed Medium (60)'),
 ],
 'golden_knight': [
   ('elixir', 4, 'table Cost 4'), ('hitpoints', 1799, 'vardefine hp_11=1799'),
   ('damage', 161, 'vardefine dmg_11=161'), ('hit_speed', 0.9, 'vardefine atk_speed=0.9'),
   ('dps', 179, '161/0.9=178.9 -> 179'), ('dash_damage', 335.0, 'vardefine dash_11=335'),
   ('speed_tiles', 1.0, 'table Speed Medium (60)'), ('deploy_time', 1.0, 'table Deploy Time 1 sec'),
   ('range_tiles', 1.2, 'table Range Melee: Medium (1.2)'),
   ('attacks', ['ground'], 'table Target Ground'), ('count', 1, 'table Count x1'),
   ('movement', 'ground', 'table Transport Ground'), ('rarity', 'champion', 'table Rarity Champion'),
 ],
 'little_prince': [
   ('elixir', 3, 'table Cost 3'), ('hitpoints', 698, 'vardefine hp_11=698'),
   ('damage', 104, 'vardefine dmg_11=104'),
   ('hit_speed', 1.2, 'vardefine 1_atk_speed=1.2 / Hit Speed (Stage 1) 1.2 sec'),
   ('dps', 87, '104/1.2=86.7 -> 87'), ('speed_tiles', 1.0, 'table Speed Medium (60)'),
   ('deploy_time', 1.0, 'table Deploy Time 1 sec'), ('range_tiles', 5.5, 'table Range 5.5'),
   ('projectile_speed', 800.0, 'table Projectile Speed 800'),
   ('attacks', ['air', 'ground'], 'table Target Air & Ground'), ('count', 1, 'table Count x1'),
   ('movement', 'ground', 'table Transport Ground'), ('rarity', 'champion', 'table Rarity Champion'),
   ('attack_ramp.per_stage', 3, 'History 17/11/2023 "attacks required to change stages to 3 (from 2)"'),
   ('attack_ramp.mults.0', 1.0, 'stage 1 = 1.2 s = base hit speed'),
   ('attack_ramp.mults.2', 3.0, 'stage 3 = 0.4 s = 1.2/3.0'),
   ('spawn_unit_stats.hit_speed', 1.2, 'Guardienne Attributes Hit Speed 1.2 sec / guard_atk_speed=1.2'),
   ('spawn_unit_stats.range_tiles', 1.2, 'Guardienne Range Melee: Medium (1.2)'),
   ('spawn_unit_stats.speed_tiles', 1.0, 'Guardienne Speed Medium (60)'),
 ],
 'mighty_miner': [
   ('elixir', 4, 'table Cost 4'), ('hitpoints', 2250, 'vardefine hp_11=2250'),
   ('hit_speed', 0.4, 'vardefine atk_speed=0.4 / table Hit Speed 0.4 sec'),
   ('speed_tiles', 1.0, 'table Speed Medium (60)'), ('deploy_time', 1.0, 'table Deploy Time 1 sec'),
   ('range_tiles', 1.6, 'table Range Melee: Long (1.6)'),
   ('attacks', ['ground'], 'table Target Ground'), ('count', 1, 'table Count x1'),
   ('movement', 'ground', 'table Transport Ground'), ('rarity', 'champion', 'table Rarity Champion'),
   ('knockback_immune', True, 'History 8/4/2022 "gave the Mighty Miner knockback immunity"'),
   ('ability_cost', 1, 'Explosive Escape Cost 1 / History 8/4/2022 "cost to 1 Elixir (from 2)"'),
   ('ability_uses', 1, 'History 4/8/2026 "his ability will now be single use"'),
   ('ability_delay_s', 1.0, 'Explosive Escape Deploy Time 1 sec / prose "After a 1-second delay"'),
   ('ability_bomb_knockback', 1.8, 'prose "will also knock them back 1.8 tiles"'),
   ('damage_ramp.hit_speed', 0.4, 'vardefine atk_speed=0.4'),
 ],
 'monk': [
   ('elixir', 5, 'table Cost 5 / History 7/12/2022 "cost to 5 Elixir (from 4)"'),
   ('hitpoints', 2214, 'vardefine hp_11=2214'), ('damage', 140, 'vardefine dmg_11=140'),
   ('hit_speed', 0.8, 'vardefine atk_speed=0.8 / History 7/2/2023 "to 0.8 seconds (from 0.9)"'),
   ('dps', 175, '140/0.8=175'), ('speed_tiles', 1.0, 'table Speed Medium (60)'),
   ('deploy_time', 1.0, 'table Deploy Time 1 sec'),
   ('range_tiles', 1.2, 'table Range Melee: Medium (1.2)'),
   ('attacks', ['ground'], 'table Target Ground'), ('count', 1, 'table Count x1'),
   ('movement', 'ground', 'table Transport Ground'), ('rarity', 'champion', 'table Rarity Champion'),
   ('combo_every', 3, 'intro "The Monk uses a 3-hit combo: the first 2 attacks deal normal damage, while the 3rd strike..."'),
 ],
 'skeleton_king': [
   ('elixir', 4, 'table Cost 4'), ('hitpoints', 2298, 'vardefine hp_11=2298'),
   ('damage', 204, 'vardefine dmg_11=204'), ('hit_speed', 1.6, 'vardefine atk_speed=1.6'),
   ('dps', 128, '204/1.6=127.5 -> 128'), ('speed_tiles', 1.0, 'table Speed Medium (60)'),
   ('deploy_time', 1.0, 'table Deploy Time 1 sec'),
   ('range_tiles', 1.2, 'table Range Melee: Medium (1.2)'),
   ('splash_radius', 1.3, 'table Splash Radius 1.3 / History 4/11/2021 "area radius to 1.3 tiles (from 1 tile)"'),
   ('attacks', ['ground'], 'table Target Ground'), ('count', 1, 'table Count x1'),
   ('movement', 'ground', 'table Transport Ground'), ('rarity', 'champion', 'table Rarity Champion'),
   ('knockback_immune', True, 'History 4/11/2021 "gave him knockback immunity"'),
   ('spawn_unit_stats.hit_speed', 1.1, 'vardefine skel_atk_speed=1.1 / Skeleton Hit Speed 1.1 sec'),
   ('spawn_unit_stats.range_tiles', 0.5, 'Skeleton Attributes Range Melee: Short (0.5)'),
   ('spawn_unit_stats.speed_tiles', 1.5, 'Skeleton Attributes Speed Fast (90) -> 90/60'),
 ],
}


def dig(d, path):
    cur = d
    for p in path.split('.'):
        if isinstance(cur, list):
            cur = cur[int(p)]
        else:
            if p not in cur:
                return '<<MISSING>>'
            cur = cur[p]
    return cur


matches = 0
mismatch = []
for key, fields in M.items():
    row = SNAP[key]
    for path, exp, _ev in fields:
        got = dig(row, path)
        ok = (got == exp) or (isinstance(exp, float) and isinstance(got, (int, float))
                              and abs(got - exp) < 1e-6)
        if ok:
            matches += 1
        else:
            mismatch.append((key, path, got, exp))

print()
print('MATCHES (wiki-confirmed KB fields): %d' % matches)
print('claimed-match failures:', mismatch if mismatch else 'none')
print('fields_checked = matches + discrepancy/flag rows = %d + %d = %d'
      % (matches, len(rows), matches + len(rows)))
per = {k: len(v) for k, v in M.items()}
print('matches per key:', per)
