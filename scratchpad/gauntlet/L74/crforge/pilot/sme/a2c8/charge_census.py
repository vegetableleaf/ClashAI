"""Census (A2c round 8, 225213@3588): our own hero's ability charge drops (phase-2 unit ability.own_action.charges_raw,
own side only) vs our extracted ability presses. python -I charge_census.py INPUTS.jsonl LIVE_DIR
Per drop: match, tick (first frame with the lower count), previous frame, hero, nearest own press (tick, distance)."""
import json, os, sys, collections
inputs, live = sys.argv[1:3]
tot = collections.Counter()
for l in open(inputs):
    r = json.loads(l)
    me = r['my_side']
    presses = [p['tick'] for p in r['plays'] if p['kind'] == 'ability' and p['side'] == me]
    last, seen, prev_t = {}, set(), None
    for line in open(os.path.join(live, r['match'] + '.jsonl'), 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        for u in (d.get('phase2') or {}).get('units', []):
            oa = (u.get('ability') or {}).get('own_action')
            if u.get('side') != me or not oa or oa.get('charges_raw') is None:
                continue
            k = u.get('generation')
            c = oa['charges_raw']
            if k in last and c < last[k][0]:
                near = min(presses, key=lambda x: abs(x - t), default=None)
                dist = None if near is None else near - t
                ok = dist is not None and -30 <= dist <= 2
                tot[ok] += 1
                if not ok:
                    print('UNMATCHED', r['match'], 'drop at', t, 'prev', last[k][1], u.get('name'), 'nearest press', near, dist)
            last[k] = (c, t)
print('matched (press within [drop-30, drop+2]):', tot[True], 'unmatched:', tot[False])
