"""Print, per p3 frame in a tick window: own IceWizardHero bodies (ability state), IceCubes, frozen enemies.
usage: probe_p3.py <log stem> <tick0> <tick1>"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
stem, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
TICK = re.compile(rb'"game_tick":(\d+)')
d = ROOT / 'icebow/data/p3_captures' / stem
own = json.loads((d / 'run.json').read_text())['observer_side']
with open(d / 'frames.jsonl', 'rb') as f:
    for raw in f:
        t = TICK.search(raw)
        if not t or not t0 <= int(t.group(1)) <= t1:
            continue
        j = json.loads(raw)
        ent = {e['category']: e for e in j['entities']}
        p2 = j.get('phase2') or {}
        p3b = {b['generation']: b for b in (j.get('phase3') or {}).get('bodies', [])}
        row = []
        for u in p2.get('units', []):
            e = ent.get(u['generation'], {})
            if u['name'].startswith('IceWizardHero'):
                ab = (u.get('ability') or {})
                oa = ab.get('own_action') or {}
                tg = (p3b.get(u['generation'], {}).get('attack') or {}).get('target_gen')
                row.append(f"{u['name'][13:] or 'IW'}[{u['side']}]@({e.get('x')},{e.get('y')}) hp={e.get('hp')} "
                           f"bs={e.get('behavior_state_raw')} st={oa.get('state_raw')} ch={oa.get('charges_raw')} "
                           f"pend={ab.get('pending_on_body')} tgt={tg}")
            fb = [b['name'] for b in u['buffs'] if b['name'].startswith('IceWizardHero')]
            if fb and u['side'] != own:
                row.append(f"  {u['name']}#{u['generation']}@({e.get('x')},{e.get('y')}) {fb}")
        print(j['game_tick'], ' | '.join(row))
