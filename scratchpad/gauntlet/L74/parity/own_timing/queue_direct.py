"""Decisive elixir-queue test: forward-walking own troops, motion-onset gap (sim - live) split by elixir at the tap."""
import bisect, glob, json, os, sys, statistics as st
from collections import defaultdict
TILE, TICK = 1000.0, 0.05
COST = {'Knight': 3, 'Skeletons': 1, 'IceWizard': 3}
new_dir, src_dir = sys.argv[1], sys.argv[2]
out = defaultdict(lambda: defaultdict(list))
for path in sorted(glob.glob(new_dir + '/*.json')):
    sp = os.path.join(src_dir, os.path.basename(path))
    if not os.path.exists(sp): continue
    d, s = json.load(open(path)), json.load(open(sp))
    fr = sorted((f['tick'], f['own_elixir']) for f in s['frames'] if f.get('own_elixir') is not None)
    ticks = [t for t, _ in fr]
    taps = [c for c in d.get('commands', []) if c.get('source') == 'confirmed_own_tap']
    if not taps or not fr: continue
    own = taps[0]['side']; f = 1.0 if own == 0 else -1.0
    names = {c['card_id']: c['name'] for c in taps}
    seen = defaultdict(list)
    for smp in d['samples']:
        for r in smp.get('rows', []):
            if r.get('tower') or r.get('side') != own or not r.get('live') or not r.get('sim'): continue
            seen[r['identity']].append((smp['tick'], r['card_id'], r['live'], r['sim']))
    for rows in seen.values():
        rows.sort(key=lambda t: t[0]); t0, cid = rows[0][0], rows[0][1]
        card = names.get(cid)
        if card not in COST: continue
        prior = [c for c in taps if c['card_id'] == cid and c['tick'] <= t0]
        if not prior: continue
        tap = max(prior, key=lambda c: c['tick'])
        if t0 - tap['tick'] > 60: continue
        i = bisect.bisect_right(ticks, tap['tick']) - 1
        if i < 0 or tap['tick'] - ticks[i] > 20: continue      # need an elixir reading within 1 s before the tap
        short = COST[card] - fr[i][1]
        pts = [((t - tap['tick']) * TICK, f * lv['y'] / TILE, f * sm['y'] / TILE) for t, _, lv, sm in rows if (t - tap['tick']) * TICK <= 4.0]
        if len(pts) < 4 or pts[-1][1] - pts[0][1] < 1.0: continue
        on = lambda k: next((a for a, *v in pts if v[k] - pts[0][k + 1] > 0.2), None)
        ol, os_ = on(0), on(1)
        if ol is None or os_ is None: continue
        b = 'full (elixir >= cost)' if short <= 0 else 'queued (short <= 0.5)' if short <= 0.5 else 'queued (short > 0.5)'
        out[card][b].append(os_ - ol)
for card, bs in out.items():
    print(f'== {card} (cost {COST[card]})')
    for b in ('full (elixir >= cost)', 'queued (short <= 0.5)', 'queued (short > 0.5)'):
        v = bs.get(b)
        if v: print(f'   {b:24s} n {len(v):4d}  sim-minus-live onset median {st.median(v):+.2f}s  mean {sum(v)/len(v):+.2f}s')
