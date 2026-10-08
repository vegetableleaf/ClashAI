"""Live Rocket timing (archive 10-05..latest): decision/tap tick -> hand-rotation confirm tick -> tower impact tick.
Impact = first logged snapshot (raw_bodies, ~10-tick cadence) where an enemy crown tower lost HP by 80-120 % of the
level's Rocket tower damage, within 150 ticks of the tap. Also: the regulation end tick (last game tick of matches that
ended at 3:00 with unequal crowns is not logged directly -- reported as the last decision tick of short matches).
  python timing.py "<glob>" """
import glob, json, sys
import numpy as np

files = sorted(glob.glob(sys.argv[1]))
conf_lat, rk = [], []
for f in files:
    ev = []
    for line in open(f):
        try:
            ev.append(json.loads(line))
        except ValueError:
            pass
    dec = [e for e in ev if e.get('event') == 'decision' and 'public' in e]
    if not dec:
        continue
    side = dec[0]['public']['observer_side']
    plays = [e for e in ev if e.get('event') == 'play']
    confs = [e for e in ev if e.get('event') == 'confirmed']
    for p in plays:
        c = next((c for c in confs if c['tick'] >= p['tick'] and c['name'] == p['name']), None)
        if c is None or c['tick'] - p['tick'] > 60:
            continue
        conf_lat.append(c['tick'] - p['tick'])
        if p['name'] != 'Rocket':
            continue
        def towers(d):
            return {(b['x'], b['y']): (b['hp'], b['max_hp']) for b in d['public']['raw_bodies']
                    if b.get('card_id') == -1 and b['side'] != side and b.get('kind') in (12, 13)}
        before = next((d for d in reversed(dec) if d['tick'] <= p['tick']), None)
        if before is None:
            continue
        t0 = towers(before)
        for d in dec:
            if not p['tick'] < d['tick'] <= p['tick'] + 150:
                continue
            t1 = towers(d)
            hit = [(k, t0[k][0] - t1.get(k, (0, 0))[0], t0[k][1]) for k in t0
                   if t0[k][0] - t1.get(k, (0, 0))[0] >= .8 * .1123 * t0[k][1]]
            if hit:
                k, dmg, mx = hit[0]
                rk.append(dict(play=p['tick'], conf=c['tick'], impact=d['tick'], dmg=dmg, max=mx,
                               dist=round(np.hypot(k[0] - 9000, k[1] - (3000 if side == 0 else 29000)) / 1000, 2)))
                break
cl = np.array(conf_lat)
print(f"tap -> confirm (all cards, n {len(cl)}): median {np.median(cl):.0f}, p90 {np.percentile(cl, 90):.0f}, "
      f"p99 {np.percentile(cl, 99):.0f}, max {cl.max()} ticks")
if rk:
    a = np.array([[r['conf'] - r['play'], r['impact'] - r['conf'], r['impact'] - r['play']] for r in rk])
    print(f"Rocket tower hits n {len(rk)}: confirm-tap median {np.median(a[:, 0]):.0f}; impact-confirm median "
          f"{np.median(a[:, 1]):.0f} (p90 {np.percentile(a[:, 1], 90):.0f}, max {a[:, 1].max()}); impact-tap median "
          f"{np.median(a[:, 2]):.0f} (p90 {np.percentile(a[:, 2], 90):.0f}, max {a[:, 2].max()}) ticks "
          f"(impact is the first ~10-tick snapshot after the hit: upper bound)")
    for j, nm in enumerate(("confirm-tap", "impact-confirm", "impact-tap")):
        print(f"  {nm}: min {a[:, j].min()} p1 {np.percentile(a[:, j], 1):.0f} p10 {np.percentile(a[:, j], 10):.0f} "
              f"median {np.median(a[:, j]):.0f} p90 {np.percentile(a[:, j], 90):.0f}")
    h = np.histogram(a[:, 1], bins=range(0, 120, 10))
    print("  impact-confirm histogram (10-tick bins from 0):", h[0].tolist())
    print("  distances king->tower (tiles):", sorted({r['dist'] for r in rk}), "dmg/max:",
          sorted({(r['dmg'], r['max']) for r in rk})[:8])
