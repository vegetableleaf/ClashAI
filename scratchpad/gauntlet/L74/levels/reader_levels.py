"""Cross-check of live_levels.py's table: the memory reader's own per-entity level field (frame ents_state[2], 10-16+ logs;
fights.py: [behavior_state_raw, evo, level, generation id]) vs the harness's max_hp inference. Reads frame JSON only.

    python reader_levels.py LIVE_LEVELS.json LOG [LOG ...]     -> per own card: reader level counts; opp tower / card levels
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[4])]
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402

catalog, _ = load_catalog()
table = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
kept = {p[0] for p in table['opp_profiles']}
own, opp_card, opp_tower, n = defaultdict(Counter), Counter(), Counter(), 0
for log in sys.argv[2:]:
    if Path(log).stem not in kept:
        continue
    seen = set()
    with open(log, encoding='utf-8') as f:
        for line in f:
            if '"ents_state"' not in line:
                continue
            e = json.loads(line)
            if e.get('event') != 'frame':
                continue
            me = e['my_side']
            for a, st in zip(e['ents'], e['ents_state']):
                key = (a[0], a[3], st[3])               # side, card id, generation: one reading per body
                if key in seen:
                    continue
                seen.add(key)
                if a[3] == -1:                          # crown tower (kind 12 king / 13 princess)
                    if a[0] != me and a[6] == 12:
                        opp_tower[st[2]] += 1
                    continue
                c = catalog.get(a[3])
                name = c['display_name'] if c else str(a[3])
                (own[name] if a[0] == me else opp_card)[st[2]] += 1
    n += 1
print(f'{n} logs of the table read')
for k, v in sorted(own.items()):
    print('own', k, dict(sorted(v.items())))
print('opp king tower level (reader):', dict(sorted(opp_tower.items())))
print('opp body level (reader, every body):', dict(sorted(opp_card.items())))
