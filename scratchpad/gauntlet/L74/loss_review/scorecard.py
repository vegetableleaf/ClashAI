"""Owner 10-12: "no trophy gain overnight, stuck at 12,000". Live scorecard by contiguous segment of (checkpoint, fast plays, deck):
matches, W/L/D (towers at the last decision, as live_model_record.py), and the main-menu trophy reads (ladder_nav) in that window.
  python scorecard.py [since=YYYYMMDD_HHMMSS]"""
import glob, json, math, os, sys
from datetime import datetime
D = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
since = sys.argv[1] if len(sys.argv) > 1 else '20261011_000000'


def stamp(f):
    return os.path.basename(f).split('_', 2)[2][:15]


def result(f):
    last, xbow = None, False
    for l in open(f, encoding='utf-8', errors='replace'):
        if l.startswith('{"event": "decision"'):
            last = l
            xbow = xbow or '"Xbow"' in l
    if last is None:
        return None, xbow
    j = json.loads(last); p = j['public']; me = p['observer_side']
    t = [b for b in p['raw_bodies'] if b['card_id'] == -1]
    if len(t) < 2 or j.get('tick', 0) < 2400:
        return None, xbow                                           # too short / not a full match record
    took = 3 - sum(1 for b in t if b['side'] != me and b['hp'] > 0); lost = 3 - sum(1 for b in t if b['side'] == me and b['hp'] > 0)
    return ('W' if took > lost else 'L' if took < lost else 'D'), xbow


troph = []
for f in sorted(glob.glob(D + 'ladder_nav_*.jsonl')):
    if stamp(f) < since:
        continue
    for l in open(f, encoding='utf-8', errors='replace'):
        if '"event": "trophies"' in l:
            j = json.loads(l)
            if j.get('trophies_total'):
                troph.append((datetime.fromtimestamp(j['t']).strftime('%Y%m%d_%H%M%S'), j['trophies_total']))
segs = []
for f in sorted(glob.glob(D + 'live_play_*.jsonl')):
    s = stamp(f)
    if s < since:
        continue
    head = open(f, encoding='utf-8', errors='replace').readline()
    try:
        h = json.loads(head)
    except ValueError:
        continue
    ck = os.path.basename(str(h.get('ckpt', '?')).replace('\\', '/'))
    fast = 'fast' if h.get('pipeline_decisions') else 'nofast'
    r, xbow = result(f)
    key = (ck, fast, 'icebow' if xbow else 'other')
    if not segs or segs[-1]['key'] != key:
        segs.append(dict(key=key, start=s, end=s, W=0, L=0, D=0, short=0))
    sg = segs[-1]; sg['end'] = s
    if r is None:
        sg['short'] += 1
    else:
        sg[r] += 1
for i, sg in enumerate(segs):
    nxt = segs[i + 1]['start'] if i + 1 < len(segs) else '99999999_999999'
    tr = [v for t, v in troph if sg['start'] <= t < nxt]
    n = sg['W'] + sg['L']; p = sg['W'] / n if n else 0
    ci = 1.96 * math.sqrt(p * (1 - p) / n) if n else 0
    print(f"{sg['start'][4:13]}..{sg['end'][9:13]} {sg['key'][0][:44]:44s} {sg['key'][1]:6s} {sg['key'][2]:6s} "
          f"W{sg['W']:3d} L{sg['L']:3d} D{sg['D']:2d} short{sg['short']:2d} win {p:5.1%} +-{ci:4.1%} "
          f"trophies {tr[0] if tr else '-'} -> {tr[-1] if tr else '-'} ({len(tr)} reads)")
