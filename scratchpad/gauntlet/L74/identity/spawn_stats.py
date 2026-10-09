"""Game-data stats of the hero ability spawns (RoyaleSim 20261006 cards.json hero_forms[*].tables.units, extracted
from the client) next to candidate learned classes, all at level 11 (catalog HP / damage are level 1; x2.56 = L11).
  python spawn_stats.py -> spawn_stats.out"""
import json
ROOT = 'C:/Users/benpe/ClashBot/research/ext/Royale-20261006/RoyaleSim/data/derived/cards.json'
c = json.load(open(ROOT, encoding='utf-8'))
L11 = 256 / 100
F = ('source_table', 'hitpoints', 'damage', 'hit_speed_ms', 'speed', 'range_milli', 'attacks_air', 'attacks_ground',
     'target_only_buildings', 'flying_height', 'area_damage_radius_milli', 'lifetime_ms', 'shield_hitpoints', 'charge',
     'kamikaze', 'hides_when_not_attacking', 'spawner', 'death_spawn')


def row(name, r):
    out = {k: r.get(k) for k in F if r.get(k) not in (None, False, 0, '', [], {})}
    for k in ('hitpoints', 'damage', 'shield_hitpoints'):
        if isinstance(out.get(k), int):
            out[k] = f"{out[k]} (L11 {out[k] * 256 // 100})"
    if isinstance(out.get('charge'), dict):
        out['charge'] = {k: v for k, v in out['charge'].items() if v}
    print(f'{name:32s}', out)


SPAWNS = {'Balloon_hero': ['SkeletonTrooper', 'BalloonHero'], 'DarkPrince_hero': ['DarkPrinceHero_Mount', 'DarkPrinceHero_Walking'],
          'Musketeer_hero': ['MusketeerTurret'], 'Tombstone_hero': ['TombstoneHero_Monster_Passive', 'TombstoneHero_Monster_Active'],
          'Goblins_hero': ['GoblinHero_Flag_Building', 'Goblin_dummy'], 'EliteArcher_hero': ['EliteArcherHero_Dummy', 'EliteArcherHero']}
print('== spawns (hero_forms tables)')
for h in c['hero_forms']:
    for n in SPAWNS.get(h['name'], []):
        row(h['name'] + ':' + n, h['tables']['units'][n])
    if h['name'] in SPAWNS:
        e = (h.get('ability') or {}).get('effect') or {}
        print(f"{'  ability ' + h['name']:32s}", {k: v for k, v in e.items() if k not in ('speeds',) and not isinstance(v, dict)})
print('== candidate learned classes (cards)')
CARDS = {r['name']: r for r in c['cards']}
for n in ('RamRider', 'HogRider', 'BattleRam', 'Tesla', 'Cannon', 'InfernoTower', 'BombTower', 'Lumberjack' if 'Lumberjack' in CARDS else 'RageBarbarian',
          'Bandit' if 'Bandit' in CARDS else 'Assassin', 'MiniPekka', 'Valkyrie', 'Knight', 'Pekka', 'GiantSkeleton', 'Golem', 'MegaKnight',
          'GoblinHut', 'Tombstone', 'ElixirCollector', 'EliteArcher', 'Archer', 'Goblins', 'Barbarians', 'AngryBarbarians',
          'IceGolemite', 'Skeletons', 'Giant', 'RoyalGhost' if 'RoyalGhost' in CARDS else 'Ghost', 'Fisherman', 'Prince', 'DarkPrince'):
    if n in CARDS:
        row(n, CARDS[n])
