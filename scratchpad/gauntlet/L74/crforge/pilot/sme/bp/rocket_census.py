"""Rocket launch dating census (A2c-BP2): for every Rocket play of the inputs, the reader's first Rocket projectile of
that side after the play's run tick R, its distance from that side's king centre in Rocket steps (k = d / 349.7,
crforge's first line R+1 shows k = 1, 094126@4575 probe), so the game's run tick is f - k. Prints the offset
(game R - extracted R) per play and a summary by dating source.
    python3 rocket_census.py INPUTS.jsonl FRAMES_DIR"""
import collections, json, math, os, sys
ROCKET, STEP = 28000003, 349.7
KING = {0: (9000, 3000), 1: (9000, 29000)}
inp, fdir = sys.argv[1:3]
cnt = collections.Counter()
for l in open(inp):
    r = json.loads(l)
    fp = os.path.join(fdir, r['match'] + '.jsonl')
    if not os.path.exists(fp):
        continue
    fr = {f['t']: f for f in map(json.loads, open(fp))}
    ts = sorted(fr)
    for p in r['plays']:
        if p['kind'] != 'play' or p['card'] != 'Rocket':
            continue
        R, s = p['tick'], p['side']
        old = {(q[1], q[2]) for t in ts if R - 4 <= t <= R for q in fr[t]['P'] if q[0] == s and q[3] == ROCKET}
        hit = next(((t, q) for t in ts if R < t <= R + 8 for q in fr[t]['P']
                    if q[0] == s and q[3] == ROCKET and (q[1], q[2]) not in old), None)
        if hit is None:
            cnt[(p.get('source'), 'unseen')] += 1
            continue
        t, q = hit
        k = math.hypot(q[1] - KING[s][0], q[2] - KING[s][1]) / STEP
        if abs(k - round(k)) > 0.05:
            cnt[(p.get('source'), 'not_from_king')] += 1
            continue
        off = (t - round(k)) - R
        cnt[(p.get('source'), 'me' if s == r['my_side'] else 'opp', off)] += 1
        print(r['match'], s, R, p['run_ticks'], p.get('source'), 'first', t, 'k', round(k), 'offset', off)
for k, v in sorted(cnt.items(), key=str):
    print('SUM', k, v)
