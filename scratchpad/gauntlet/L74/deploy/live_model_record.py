"""Owner 10-11: is the E4 graft really worse than the old model LIVE? Per icebow live match (own hand contains Xbow), the result
is inferred from the last decision's crown towers (destroyed counts; equal counts = draw). Groups by checkpoint, 10-08 onward."""
import glob, json, math
from collections import defaultdict
D = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
rec = defaultdict(lambda: [0, 0, 0])
for f in sorted(glob.glob(D + 'live_play_2026100[89]_*.jsonl') + glob.glob(D + 'live_play_2026101*_*.jsonl')):
    head = open(f, encoding='utf-8', errors='replace').readline()
    ck = 'E4' if 'rdef_e4' in head else ('OLD' if 'towerref_w2' in head else None)
    if ck is None: continue
    last, xbow = None, False
    for l in open(f, encoding='utf-8', errors='replace'):
        if l.startswith('{"event": "decision"'):
            last = l
            if not xbow and '"Xbow"' in l: xbow = True
    if last is None or not xbow: continue
    p = json.loads(last)['public']; me = p['observer_side']
    t = [b for b in p['raw_bodies'] if b['card_id'] == -1]
    if len(t) < 2 or json.loads(last).get('tick', 0) < 2400: continue      # too short / not a full match record
    mine = sum(1 for b in t if b['side'] == me and b['hp'] > 0); theirs = sum(1 for b in t if b['side'] != me and b['hp'] > 0)
    lost, took = 3 - mine, 3 - theirs
    rec[ck][0 if took > lost else (1 if took < lost else 2)] += 1
for ck, (w, l, d) in rec.items():
    n = w + l; p = w / max(n, 1); se = math.sqrt(p * (1 - p) / max(n, 1))
    print(f'{ck}: W {w} L {l} D {d} | win rate (W/(W+L)) {p:.1%} +- {1.96 * se:.1%}')
