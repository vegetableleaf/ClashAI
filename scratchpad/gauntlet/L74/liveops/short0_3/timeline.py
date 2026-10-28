"""Timeline of a short live match: every STEP ticks the units (side, name, hp, xy in my frame), tower hp, my elixir, + play/confirmed events."""
import json, sys
f, STEP = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40
names = {}
my_side = None
rows = []
for l in open(f, 'rb'):
    if l.startswith(b'{"event": "start"'):
        st = json.loads(l); print('start keys sample:', {k: st[k] for k in ('screen','ckpt_sha256','decision_seed') if k in st}); continue
    if l.startswith(b'{"event": "frame"'):
        d = json.loads(l); my_side = d.get('my_side', my_side)
        for u in ((d.get('phase2') or {}).get('units') or []):
            names[u['address']] = (u.get('name'), u.get('side'), u.get('definition_id'))
        rows.append(d)
    elif l[:30].startswith((b'{"event": "play"', b'{"event": "confirmed"', b'{"event": "stop"', b'{"event": "unconfirmed"')):
        e = json.loads(l); rows.append(e)
print('my_side', my_side, 'frames', sum(1 for r in rows if r.get('event') == 'frame'))
last = -999
for r in rows:
    if r['event'] == 'frame':
        t = r['tick']
        if t - last < STEP and t != 0: continue
        last = t
        us = []
        for e in r.get('ents') or []:
            side, x, y, card, hp, mx, kind, addr = e[:8]
            nm = names.get(addr, (None,))[0] or str(card)
            if nm in ('KingTower', 'PrincessTower'): 
                us.append(f"{'ME' if side == my_side else 'OP'}:{nm[:3]}{hp}"); continue
            us.append(f"{'me' if side == my_side else 'OP'}:{nm}@{round(x/18000,2)},{round(y/32000,2)}/{hp}")
        print(f"t{t} el{r.get('elixir')} | " + ' '.join(us))
    elif r['event'] == 'play':
        print(f"   >>> PLAY t{r['tick']} {r['name']} xy={r['xy']} p={r['p_play']} el={r['elixir']}")
    elif r['event'] == 'confirmed':
        print(f"   <<< CONF t{r['tick']} {r['name']} intended={[round(v,3) for v in r['intended']]} spawn={r.get('spawn')} err={r.get('err_tiles')} lat={r.get('latency_s')}")
    else:
        print('   ', r['event'], {k: v for k, v in r.items() if k != 'event'})
