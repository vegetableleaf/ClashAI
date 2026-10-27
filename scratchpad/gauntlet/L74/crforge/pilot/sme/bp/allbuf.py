"""All buff rows (name, remaining, duration) and ability fields of every unit in a tick range. python -I allbuf.py LOG LO HI [SUBSTR]"""
import json, sys
lo, hi = int(sys.argv[2]), int(sys.argv[3])
sub = sys.argv[4] if len(sys.argv) > 4 else ''
seen = set()
for line in open(sys.argv[1], 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    t = d['tick']
    if t is None or not lo <= t <= hi or t in seen:
        continue
    seen.add(t)
    for u in (d.get('phase2') or {}).get('units', []):
        bs = [(b['name'], b['remaining_ms_raw'], b['duration_ms_raw']) for b in u.get('buffs') or [] if sub in b['name']]
        ab = u.get('ability')
        if bs or (ab and (ab.get('pending_on_body') or ab.get('cast_timer_ms_raw') or ab.get('own_action'))):
            print(t, u['generation'], u['side'], u['name'], bs, ab)
