"""Default-off identity in SIM: the base arm on this branch (~/threat/sim/base_*) vs the same arm on main 808f4f4
(~/threat/sim_main/base_*), every match by (census, tag): outcome, end tick, crowns, tower HP, plays, decisions and
the full behaviour telemetry must be equal.   python parity_vs_main.py ~/threat/sim ~/threat/sim_main"""
import json, sys

KEYS = ('outcome', 'end_tick', 'crowns_for', 'crowns_against', 'tower_hp_for', 'tower_hp_against', 'plays_accepted',
        'opp_plays_accepted', 'decisions', 'behaviour')


def load(d):
    out = {}
    for s in ('evo', 'lad'):
        for line in open(f'{d}/base_{s}/matches.jsonl'):
            r = json.loads(line)
            out[(s, r['tag'])] = r
    return out


new, main = load(sys.argv[1]), load(sys.argv[2])
same = [k for k in main if k in new and all(new[k][x] == main[k][x] for x in KEYS)]
diff = [k for k in main if k in new and k not in same]
print(f'matches new {len(new)} main {len(main)} common {len(set(new) & set(main))} identical {len(same)} differ {len(diff)}')
for k in diff[:10]:
    print('  differ', k, {x: (new[k][x], main[k][x]) for x in KEYS if x != 'behaviour' and new[k][x] != main[k][x]})
