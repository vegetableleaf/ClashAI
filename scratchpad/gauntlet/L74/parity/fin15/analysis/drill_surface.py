"""Goblin Drill (base + evo): the tapped point (the confirmed play's unrounded 'intended', own frame) against the point the drill
building first appears (frame ents, card name from the phase-2 unit rows), per play.  python drill_surface.py LOG [LOG ...]"""
import json, math, sys
for p in sys.argv[1:]:
    plays, surf, side = [], [], None
    with open(p, 'rb') as f:
        for raw in f:
            h = raw[:40]
            if b'"confirmed"' in h:
                j = json.loads(raw)
                if j['name'] == 'GoblinDrill':
                    plays.append((j['tick'], j['intended']))
            elif b'"frame"' in h:
                j = json.loads(raw); side = j['my_side']
                names = {u['address']: u['name'] for u in (j.get('phase2') or {}).get('units', [])}
                for e in j['ents']:
                    if e[0] == side and names.get(e[7]) in ('GoblinDrill', 'GoblinDrill_EV1') and e[7] not in [s[3] for s in surf]:
                        surf.append((j['tick'], e[1], e[2], e[7], names[e[7]]))
    for t, (nx, ny) in plays:
        # own frame -> arena: x = nx * 18 tiles; y = (1 - ny) * 32 for the bottom seat (side 0), ny * 32 for the top seat
        ax, ay = nx * 18000, ((1 - ny) * 32000 if side == 0 else ny * 32000)
        if side == 1:
            ax = 18000 - ax
        s = next((x for x in surf if 0 < x[0] - t < 200), None)
        if s:
            print(p[-22:-6], 'side', side, 'tap', t, (round(ax), round(ay)), '-> surfaced', s[0], (s[1], s[2]), s[4],
                  'off', round(math.hypot(s[1] - ax, s[2] - ay)))
