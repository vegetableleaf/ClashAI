# -*- coding: utf-8 -*-
"""Which indexing does the game's own per-level array use?

  A  absolute-level  : stat(L) = floor(arr[0] * PERCENT[L] / 100),      arr[0] treated as level 1
  B  floor-indexed   : stat(L) = floor(arr[0] * PERCENT[L-floor+1]/100), arr[0] = the rarity floor row

For Common cards (floor 1) A and B are the same function. They diverge for every other rarity.
Run over every per-level array in the cr-api-data dump.
"""
import json, sys, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:/Users/benpe/ClashBot/icebow/src')
from clashrl.levels import PERCENT

d = json.load(open(r'C:/Users/benpe/ClashBot/icebow/data/webcache/4d3032da0d552e2dd7bc.json',
                   encoding='utf-8'))
b = json.loads(d['body']) if isinstance(d['body'], str) else d['body']
FLOOR = {'Common': 1, 'Rare': 3, 'Epic': 6, 'Legendary': 9, 'Champion': 11}
ARRS = ['hitpoints_per_level', 'damage_per_level', 'dps_per_level', 'shield_hitpoints_per_level',
        'death_damage_per_level', 'crown_tower_damage_per_level', 'area_damage_per_level',
        'spawn_damage_per_level', 'life_duration_per_level']

def fl(x, p):
    return int(x * p // 100)

tally = collections.Counter()
lenmatch = collections.Counter()
bad_A, bad_B = [], []
seen = 0
for sect in ('characters', 'buildings', 'troop', 'building', 'spell', 'projectile'):
    for c in b.get(sect, []) or []:
        rar = c.get('rarity')
        if rar not in FLOOR:
            continue
        f = FLOOR[rar]
        for k in ARRS:
            arr = c.get(k)
            if not arr or len(arr) < 2:
                continue
            seen += 1
            lenmatch[(rar, len(arr), 19 - f + 1)] += 1
            okA = all(fl(arr[0], PERCENT[i + 1]) == arr[i] for i in range(len(arr)) if i + 1 <= 19)
            okB = all(fl(arr[0], PERCENT[i + 1]) == arr[i] for i in range(len(arr)) if i + 1 <= 19)
            # A: percent indexed by ABSOLUTE level (arr[i] is level f+i)
            okA = all(f + i <= 19 and fl(arr[0], PERCENT[f + i]) == arr[i] for i in range(len(arr)))
            # B: percent indexed from the array start (arr[i] is percent slot i+1)
            okB = all(i + 1 <= 19 and fl(arr[0], PERCENT[i + 1]) == arr[i] for i in range(len(arr)))
            tally[(rar, 'A_absolute', okA)] += 1
            tally[(rar, 'B_floorindexed', okB)] += 1
            if not okA:
                bad_A.append((c.get('name'), rar, k))
            if not okB:
                bad_B.append((c.get('name'), rar, k))

print('arrays examined:', seen)
print()
print('%-11s %-16s %8s %8s' % ('rarity', 'model', 'exact', 'mismatch'))
for rar in ['Common', 'Rare', 'Epic', 'Legendary', 'Champion']:
    for m in ['A_absolute', 'B_floorindexed']:
        print('%-11s %-16s %8d %8d' % (rar, m, tally[(rar, m, True)], tally[(rar, m, False)]))
print()
print('array length vs (19 - floor + 1):')
for (rar, n, exp), cnt in sorted(lenmatch.items()):
    print('   %-10s len=%-3d expected=%-3d %s  x%d' % (rar, n, exp, 'OK' if n == exp else 'DIFF', cnt))
print()
print('model B mismatches (%d):' % len(bad_B), bad_B[:20])
print('model A mismatches (%d), first 20:' % len(bad_A), bad_A[:20])
