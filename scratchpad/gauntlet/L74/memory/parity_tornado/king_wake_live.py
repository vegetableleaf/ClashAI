"""Q2 (live only): how does OUR king wake on live, and is there any wake without damage or a princess fall (a Tornado
pull-into-king rule would show up as one)? Reads the W1 census (parity/output/metrics/census.json: 1,207 frame-logged
matches 10-05..10-19; king kind 12 -> 13 = awake; trigger = awake - 70; cause princess / damage within +-4 ticks, else other).
Read-only.   python king_wake_live.py CENSUS.json"""
import json
import sys
from collections import Counter

d = json.load(open(sys.argv[1]))
ms = [m for m in d['matches'] if 'king' in m]
BUILD = {'HogRider', 'RoyalHogs', 'BattleRam', 'Giant', 'RoyalGiant', 'Golem', 'ElixirGolem', 'GoblinGiant', 'ElectroGiant',
         'Balloon', 'LavaHound', 'Ram', 'RamRider', 'GiantSkeleton', 'SkeletonBalloon', 'Goblins', 'GoblinBarrel'}
c = Counter()
other, dmg_rows = [], []
for m in ms:
    for k in m['king']:
        if k['side'] != 'own':
            continue
        c['own sides'] += 1
        if k['awake'] is None:
            c['never awake'] += 1
            continue
        if k['cause'] == 'at_start':
            c['awake at first frame'] += 1
            continue
        both = k['down'] is None or k['down'] > k['trigger'] + 4
        c[f"cause={k['cause']} both_princesses_up={both}"] += 1
        if k['cause'] == 'damage' and both:
            dmg_rows.append((m, k))
        if k['cause'] == 'other':
            other.append((m, k))
print('own-king sides', dict(c))
n = len(dmg_rows)
torn = [(m, k) for m, k in dmg_rows if k['tornado_before'] is not None]
pre = [(m, k) for m, k in dmg_rows if k['trigger'] < 3600]
print(f'\nown king DAMAGE-woken with both princesses up: {n} sides in {len(ms)} matches ({n/len(ms):.3f} per match); '
      f'regulation (trigger < 3600): {len(pre)}')
print(f'  own Tornado in the 80 ticks before the trigger: {len(torn)} ({len(torn)/max(n,1):.2f})')
act = Counter(a.split(' ', 1)[1] for _, k in dmg_rows for a in k['activators'])
act_t = Counter(a.split(' ', 1)[1] for _, k in torn for a in k['activators'])
print('  activators (enemy in king reach at the trigger), all:', act.most_common(12))
print('  activators, after own Tornado:', act_t.most_common(12))
lag = Counter(min((k['trigger'] - k['tornado_before']) // 10 * 10, 80) for _, k in torn)
print('  trigger - Tornado cast (ticks, 10-bins):', sorted(lag.items()))
win = lambda rows: sum(m['end'].get('won') is True for m, _ in rows) / max(1, sum(m['end'].get('won') is not None for m, _ in rows))
woke = {m['match'] for m, _ in dmg_rows}
rest = [(m, None) for m in ms if m['match'] not in woke]
print(f'  win rate (association): woken-with-both-up {win(dmg_rows):.3f} (n {n}) vs other matches {win(rest):.3f} (n {len(rest)}); '
      f'after own Tornado {win(torn):.3f} (n {len(torn)})')
print(f'\nOTHER wakes (no princess fall and no first king damage within +-4 ticks of awake-70): {len(other)}')
pre_o = [(m, k) for m, k in other if k['trigger'] < 5900]
print(f'  of which trigger < 5900 (before the tiebreak drain): {len(pre_o)}')
for m, k in pre_o:
    print('   ', m['match'], 'awake', k['awake'], 'trigger', k['trigger'], 'hurt', k['hurt'], 'down', k['down'],
          'own Tornado', k['tornado_before'], 'activators', k['activators'])
