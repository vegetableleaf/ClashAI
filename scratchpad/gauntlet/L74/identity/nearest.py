"""Nearest learned class for an ability spawn, from client-extracted game data (RoyaleSim 20261006 cards.json).
Hard match: transport (air/ground), targets (air&ground / ground / buildings), melee (range <= 1.6 tiles) vs ranged,
single vs splash, troop vs building. Distance among the matches: |log HP ratio| + |log DPS ratio| + |log speed ratio|
(per body, level 11). Only classes in the model's vocab (pipeline.vocab) count.  python nearest.py -> nearest.out"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '../../../..')))
from pipeline import vocab
c = json.load(open('C:/Users/benpe/ClashBot/research/ext/Royale-20261006/RoyaleSim/data/derived/cards.json', encoding='utf-8'))
H = {h['name']: h for h in c['hero_forms']}


def sig(r, building):
    tgt = 'buildings' if r.get('target_only_buildings') else ('air&ground' if r.get('attacks_air') else 'ground')
    return ('air' if r.get('flying_height') else 'ground', tgt, (r.get('range_milli') or 0) <= 1600,
            not (r.get('area_damage_radius_milli') or 0), building)


def num(r):
    hp, dmg, hs = r.get('hitpoints') or 0, r.get('damage') or 0, r.get('hit_speed_ms') or 0
    return hp, (dmg / hs * 1000 if hs and dmg else 0.0), r.get('speed') or 0


def dist(a, b):
    return sum(abs(math.log(max(x, 1e-3) / max(y, 1e-3))) for x, y in zip(a, b) if x or y)


cands = []
for r in c['cards']:
    k = vocab.engine_key(r['name'])
    if r.get('kind') in ('troop', 'building') and k in vocab.UNIT_VOCAB and r.get('hitpoints'):
        cands.append((k, sig(r, r['kind'] == 'building'), num(r)))
for hero, unit, building in (('Balloon_hero', 'SkeletonTrooper', False), ('Tombstone_hero', 'TombstoneHero_Monster_Active', False),
                             ('DarkPrince_hero', 'DarkPrinceHero_Mount', False), ('Musketeer_hero', 'MusketeerTurret', True),
                             ('Goblins_hero', 'GoblinHero_Flag_Building', False), ('EliteArcher_hero', 'EliteArcherHero_Dummy', False)):
    r = H[hero]['tables']['units'][unit]
    s, n = sig(r, building), num(r)
    best = sorted((dist(n, cn), k, cn) for k, cs, cn in cands if cs == s)[:4]
    print(f'{unit}: sig {s} hp/dps/speed L1 {tuple(round(x) for x in n)}')
    for d, k, cn in best:
        print(f'   {k:18s} dist {d:.2f}  hp/dps/speed L1 {tuple(round(x) for x in cn)}')
    if not best:
        print('   no learned class with the same transport / targets / reach / splash / kind')
