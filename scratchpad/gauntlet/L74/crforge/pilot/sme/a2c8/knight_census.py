"""own Knight plays (A2c round 8, 171753): per play, drop pair (last frame before the 3-elixir drop, frame of it), first
visible frame, first moved frame. python -I knight_census.py INPUTS.jsonl"""
import json, sys, collections
sys.path.insert(0, r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\crforge\pilot\sme')
import live_frames
KN = 26000000
out = collections.Counter()
for l in open(sys.argv[1]):
    r = json.loads(l)
    me = r['my_side']
    ps = [p for p in r['plays'] if p['side'] == me and p['card'] == 'Knight' and p['kind'] == 'play']
    if not ps:
        continue
    fr = live_frames.convert(r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\%s.jsonl' % r['match'])
    for p in ps:
        win = [f for f in fr if p['tick'] - 10 <= f['t'] <= p['tick'] + 40]
        at = lambda f: [(e[1], e[2]) for e in f['E'] if e[0] == me and e[3] == KN and abs(e[1] - p['x']) + abs(e[2] - p['y']) <= 300]
        vis = next((f['t'] for f in win if (p['x'], p['y']) in at(f) or at(f)), None)
        mv = next((f['t'] for f in win if vis and f['t'] > vis and at(f) and (p['x'], p['y']) not in at(f)), None)
        drop = next((b['t'] for a, b in zip(win, win[1:]) if a['el'] - b['el'] > 20000), None)
        k = (vis - drop if vis and drop else None, mv - drop if mv and drop else None)
        out[k] += 1
        if k[1] is not None and k[1] < 16:
            print(r['match'], p['tick'], p['run_ticks'], 'drop', drop, 'vis', vis, 'move', mv)
print(sorted(out.items(), key=lambda x: -x[1])[:15])
