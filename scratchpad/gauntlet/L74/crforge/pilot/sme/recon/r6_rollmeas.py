"""RECON-6 (laptop): the live barrel roll length (visible rolling phase of the opponent's BarbLog projectile in the reader frames) by slot flag, FRESH9 + FRESH10:
  python -I recon/r6_rollmeas.py -> results/live/recon/r6/barblog_roll_lengths.txt"""
import json, sys, collections, math, statistics
S = 'C:/Users/benpe/ClashBot/.foreman/scratch/'
sets = [(S + 'recon4/f9/off/inputs_all.jsonl', S + 'recon4/f9/frames/'), (S + 'recon5/f10/off/inputs_all.jsonl', S + 'recon5/f10/frames/')]
res = collections.defaultdict(list)
for inp, fr in sets:
    for l in open(inp):
        rec = json.loads(l)
        me = rec['my_side']
        opp = 1 - me
        deck = rec['sides'][str(opp)]['deck']
        if 'BarbLog' not in deck: continue
        flag = rec['sides'][str(opp)]['slot_flags'][deck.index('BarbLog')]
        try:
            rows = [json.loads(x) for x in open(fr + rec['match'] + '.jsonl')]
        except Exception:
            continue
        pts = []
        for r in rows:
            for p in r['P']:
                if p[0] == opp and p[3] == 28000015:
                    pts.append((r['t'], p[1], p[2]))
        # clusters by time
        pts.sort()
        cl, cur = [], []
        for p in pts:
            if cur and p[0] - cur[-1][0] > 6:
                cl.append(cur); cur = []
            cur.append(p)
        if cur: cl.append(cur)
        for c in cl:
            if len(c) < 8: continue
            steps = [(math.hypot(b[1] - a[1], b[2] - a[2]), b[0] - a[0]) for a, b in zip(c, c[1:])]
            per_tick = [d / dt for d, dt in steps if dt > 0]
            # rolling phase: per tick ~200 (150..250)
            idx = [i for i, v in enumerate(per_tick) if 150 <= v <= 250]
            if not idx: continue
            a = idx[0]; b = idx[-1] + 1
            roll = math.hypot(c[b][1] - c[a][1], c[b][2] - c[a][2])
            res[flag].append((round(roll), rec['match'][-13:], c[a][0], c[b][0] - c[a][0]))
for flag, v in sorted(res.items()):
    rolls = [x[0] for x in v]
    print('flag', flag, 'barrels', len(v), 'roll median', statistics.median(rolls), 'min', min(rolls), 'max', max(rolls))
    print('  ', collections.Counter(rolls).most_common(8))
