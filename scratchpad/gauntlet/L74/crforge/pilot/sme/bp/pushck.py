"""Every gk_dash cast: the knight's burst displacement and the enemy rollers near it (laptop, live_frames)."""
import json, sys
sys.path.insert(1, 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme')
import live_frames
LIVE = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
for l in open('inputs_v5.jsonl'):
    r = json.loads(l)
    cs = [p for p in r['plays'] if p.get('source') == 'gk_dash']
    if not cs:
        continue
    fr = {f['t']: f for f in live_frames.convert(LIVE + r['match'] + '.jsonl')}
    for p in cs:
        a, b = p['run_ticks'][0] + 1, p['run_ticks'][1] + 2
        ga = [e for e in fr[a]['E'] if e[0] == p['side'] and e[3] == 26000074]
        gb = [e for e in fr[b]['E'] if e[0] == p['side'] and e[3] == 26000074]
        if not ga or not gb:
            continue
        e0 = ga[0]
        e1 = min(gb, key=lambda e: abs(e[1] - e0[1]) + abs(e[2] - e0[2]))
        rol = [(t, q[1], q[2], q[3]) for t in (a, b) for q in fr[t]['P'] if q[0] != p['side'] and q[3] in (28000011, 28000015, 28000000, 28000017)]
        print(r['match'][10:], p['tick'], 'gk', (e0[1], e0[2]), 'move', (e1[1] - e0[1], e1[2] - e0[2]), 'rollers', rol)
