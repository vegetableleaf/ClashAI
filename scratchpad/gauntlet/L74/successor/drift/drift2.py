"""Follow-up on drift.json: (1) same-method trophy drift (frames-era 12.1-12.7k u250 window vs 13k), (2) win rate by the
opponent's king-tower level and tower troop since 10-15 (first frame only: cheap), (3) per-card drift x cost ranking.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/successor/drift/drift2.py   -> drift2.txt
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import drift as D                                                          # noqa: E402

d = json.loads((HERE / 'drift.json').read_text())
rows = d['live']
P = d['pools']
A = D.A
bs = D.base_set
W = dict(u250=[r for r in rows if r['mark'] == 'CXXIV'],
         cue=[r for r in rows if r['mark'] == 'CXXXVIII'],
         cue_hi=[r for r in rows if r['mark'] == 'CXXXVIII' and (r['before'] or 0) >= 12800])
rec = [r for r in rows if r['log'] >= 'live_play_20261015']
T = []
w = T.append


def first_frame_towers(path):
    with open(path, 'rb') as f:
        for raw in f:
            if b'"frame"' in raw[:40]:
                e = json.loads(raw); me = e['my_side']
                ks = [a[5] for a in e['ents'] if a[3] == -1 and a[0] != me and abs(a[1] - 9000) < 1000]
                ps = {a[5] for a in e['ents'] if a[3] == -1 and a[0] != me
                      and any(abs(a[1] - x) < 600 and abs(a[2] - y) < 600 for x, y in D.SLOTS)}
                king = next((int(l) for l, r in D.TOWERS.items() for k in ks if abs(r['king'] - k) <= 1), None)
                hits = [n for l, r in D.TOWERS.items() for n, v in r.items() if n != 'king' for p in ps if abs(v - p) <= 1]
                return king, (hits[0] if len(ps) == 1 and len(hits) == 1 else None)
    return None, None


# 1. same-method drift: frames-era u250 window (12.1-12.7k) vs CXXXVIII 13k
w("== same-method opponent drift (all three windows = frame logs): u250 window vs CXXXVIII windows; train / d3 for reference")
L = {k: D.live_stats(v) for k, v in W.items()}
for k, v in W.items():
    tb = sorted(r['before'] for r in v if r['before'])
    w(f"  {k}: n {len(v)}, trophies-before median {tb[len(tb)//2]}, win {100*sum(r['win'] for r in v)/len(v):.1f}%")
w(f"{'arch':17s} {'train':>6s} {'d3':>6s} {'u250win':>7s} {'cue':>6s} {'cue_hi':>6s}")
for a in list(A.ORDER) + ['other']:
    w(f"{a:17s} {100*P['train']['arch'].get(a,0):6.1f} {100*P['d3']['arch'].get(a,0):6.1f} {100*L['u250']['arch'].get(a,0):7.1f} "
      f"{100*L['cue']['arch'].get(a,0):6.1f} {100*L['cue_hi']['arch'].get(a,0):6.1f}")
SPELLS = {'fireball', 'log', 'arrows', 'zap', 'tornado', 'rage', 'poison', 'earthquake', 'freeze', 'lightning', 'rocket', 'goblincurse',
          'giantsnowball', 'snowball', 'barblog', 'royaldelivery', 'clone', 'mirror', 'heal', 'darkmagic', 'vines', 'void', 'goblinbarrel',
          'graveyard'}
w(f"\n{'card (troops/buildings)':24s} {'train':>6s} {'d3':>6s} {'u250win':>7s} {'cue':>6s} {'cue_hi':>6s} {'cue/u250':>8s} {'cue/train':>9s} {'cue/d3':>6s}")
cards = sorted({c for c in L['cue']['card']} | {c for c in L['u250']['card']}, key=lambda c: -(L['cue']['card'].get(c, 0)))
for c in cards[:60]:
    if c in SPELLS:
        continue
    cu, uw, tr, d3 = L['cue']['card'].get(c, 0), L['u250']['card'].get(c, 0), P['train']['card'].get(c, 0), P['d3']['card'].get(c, 0)
    if cu < 0.04 and uw < 0.04:
        continue
    f = lambda a, b: f"{a/b:.1f}" if b else 'inf'                                   # noqa: E731
    w(f"{c:24s} {100*tr:6.1f} {100*d3:6.1f} {100*uw:7.1f} {100*cu:6.1f} {100*L['cue_hi']['card'].get(c,0):6.1f} {f(cu,uw):>8s} "
      f"{f(cu,tr):>9s} {f(cu,d3):>6s}")

# 2. win rate by opponent king level / tower troop since 10-15 (first frame)
w("\n== win rate by the opponent's KING TOWER LEVEL and tower troop (first frame; all matches since 10-15 with frames)")
g, gt, gm = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(collections.Counter)
for r in rec:
    k, p = first_frame_towers(D.LOGS / (r['log'] + '.jsonl'))
    if k is None:
        continue
    r['king'], r['troop'] = k, p
    g[k].append(r['win'])
    gt['troop' if p and p != 'PrincessTower' else 'princess'].append(r['win'])
    band = 'lt12500' if (r['before'] or 0) < 12500 else '12500-12799' if r['before'] < 12800 else 'ge12800'
    gm[band][k] += 1
for k in sorted(g):
    x = g[k]; ci = D.wilson(sum(x), len(x))
    w(f"  opp king level {k}: n {len(x):4d} win {100*sum(x)/len(x):5.1f}% [{ci[0]:.1f}, {ci[1]:.1f}]")
for k, x in gt.items():
    ci = D.wilson(sum(x), len(x))
    w(f"  opp {k:8s}: n {len(x):4d} win {100*sum(x)/len(x):5.1f}% [{ci[0]:.1f}, {ci[1]:.1f}]")
for b in ('lt12500', '12500-12799', 'ge12800'):
    c = gm[b]; n = sum(c.values())
    w(f"  trophies {b:11s}: n {n:4d} opp king level " + ", ".join(f"L{k} {100*v/n:.1f}%" for k, v in sorted(c.items())))
for m in ('CXXIV', 'CXXXVIII'):
    for k in (15, 16):
        x = [r['win'] for r in rec if r['mark'] == m and r.get('king') == k]
        if x:
            ci = D.wilson(sum(x), len(x))
            w(f"  {m:8s} vs opp king L{k}: n {len(x):4d} win {100*sum(x)/len(x):5.1f}% [{ci[0]:.1f}, {ci[1]:.1f}]")

# 3. card drift x cost: live 13k presence minus training presence, times (overall win - win when present), since 10-15
w("\n== per-card drift x cost (troops/buildings): u = cue-window presence - train presence; cost = win-rate gap when present "
  "(both Marks since 10-15); product = matches lost per 100 that the card's under-representation touches")
base = sum(r['win'] for r in rec) / len(rec)
wr = D.winrate(rec, bs)
out = []
for c, x in wr.items():
    if c in SPELLS or len(x) < 25:
        continue
    pw = sum(x) / len(x)
    u = L['cue']['card'].get(c, 0) - P['train']['card'].get(c, 0)
    out.append((u * (base - pw) * 100, c, u, len(x), pw, D.wilson(sum(x), len(x))))
for prod, c, u, n, pw, ci in sorted(out, reverse=True)[:15]:
    w(f"  {c:17s} under-rep {100*u:+5.1f} pp | n {n:4d} win {100*pw:5.1f}% [{ci[0]:.1f}, {ci[1]:.1f}] | product {prod:+5.2f}")
w(f"  (overall win since 10-15 {100*base:.1f}%, n {len(rec)})")
(HERE / 'drift2.txt').write_text('\n'.join(T) + '\n', encoding='utf-8')
print('\n'.join(T))
