"""W8: PARITY_ATTACKS / PARITY_BUFFS exports for the frame logs whose name matches PATTERN only (the 10-20 classic-challenge
parity battles), in the `fights.py attacks` / `fights.py buffs` layout (generation ids, counters, buff names; no addresses).
  python export20.py PATTERN OUT_ATTACKS OUT_BUFFS OUT_LIST      e.g. PATTERN = live_play_20261020_"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
os.environ.pop('PARITY_ATTACKS', None); os.environ.pop('PARITY_BUFFS', None)   # read the captures, not an export
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

pat, oa, ob, ol = sys.argv[1:5]
logs = set()
for r in F.p3_runs() + sorted(F.P2_DIR.glob('*/run.json')):
    try:
        n = json.loads(r.read_text()).get('live_log')
    except ValueError:
        continue
    if n and Path(n).name.startswith(pat):
        logs.add(Path(n).name)
logs = sorted(logs)
att = {n: F.phase3_attacks(n) for n in logs}
att['_births'] = {n: b for n in logs for b in [F.phase3_births(n)] if b}
att['_shields'] = {n: s for n in logs for s in [F.phase3_shields(n)] if s}
buf = {n: F.phase2_buffs(n) for n in logs}
Path(oa).write_text(json.dumps(att, separators=(',', ':'))); Path(ob).write_text(json.dumps(buf))
Path(ol).write_text('\n'.join(logs) + '\n')
print(len(logs), 'logs; attacks rows', sum(len(v) for k, v in att.items() if not k.startswith('_')), '; births', len(att['_births']),
      '; shields', len(att['_shields']), '; buff ticks', sum(len(v) for v in buf.values()))
