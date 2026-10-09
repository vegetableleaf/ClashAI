"""Offline: would rocket_dead_target_cells have blocked each live Rocket's cell? The rule on the logged decision board
(public.model_towers alive flags, public.model_bodies side != 0), lattice grid, cell = the played xy.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/rocket_dead/replay_rule.py"""
import glob, json, os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))
from pipeline.decision_options import rocket_dead_target_cells  # noqa: E402

LOGS = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/live_play_202610*.jsonl"
n = blocked = 0
hits = []
for f in sorted(glob.glob(LOGS)):
    last = None
    for line in open(f, encoding='utf-8', errors='replace'):
        if not (line.startswith('{"event": "decision"') or line.startswith('{"event": "play"')):
            continue
        d = json.loads(line)
        if d['event'] == 'decision':
            last = d
            continue
        if d.get('name') != 'Rocket' or not last or 'model_towers' not in (last.get('public') or {}):
            continue
        p = last['public']
        alive = {(t['kind'], t['lane']): t['alive'] for t in p['model_towers'] if t['side'] == 1}
        enemy_alive = (alive[('king', None)], alive[('princess', 'L')], alive[('princess', 'R')])
        bodies = tuple((b['x'] * 18, b['y'] * 32) for b in p['model_bodies'] if b['side'] != 0)
        xy = d['xy'] if isinstance(d['xy'], list) else json.loads(d['xy'])
        c = int(round(xy[1] * 64)) * 36 + int(round(xy[0] * 36))
        n += 1
        if rocket_dead_target_cells(enemy_alive, bodies, 'lattice')[c]:
            blocked += 1
            hits.append((os.path.basename(f)[10:25], d['tick'], [round(xy[0] * 18, 1), round(xy[1] * 32, 1)],
                         (last.get('decision') or {}).get('why')))
print(f'Rocket plays with a decision board: {n}; cell blocked by the rule: {blocked}')
for h in hits:
    print('  ', h)
