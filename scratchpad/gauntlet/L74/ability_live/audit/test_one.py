"""Smoke: run audit.scan + analyse_press on one match (180311) and print the rows."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit
inv = json.loads((audit.HERE / 'inventory.json').read_text())
m = next(x for x in inv if x['log'] == (sys.argv[1] if len(sys.argv) > 1 else 'live_play_20261017_180311.jsonl'))
presses, frames, decs, rows = audit.scan(m)
evs = {e['tick']: e for e in m['events'] if e['event'] == 'ability'}
for P in presses:
    r = audit.analyse_press(m, P, evs[P]['why'], evs[P].get('elixir'), frames, decs, rows)
    print(json.dumps(r, default=str, indent=0)[:3000])
print(audit.button_audit(m, rows, presses))
