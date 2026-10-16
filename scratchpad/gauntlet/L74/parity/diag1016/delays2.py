"""Own troop plays: does the late-registration mode (+16..20 ticks) show in public play-side fields?"""
import json, sys, statistics
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F
from scratchpad.gauntlet.L74.parity.core import load_catalog, ps
catalog, by_name = load_catalog(); rows = []
for p in sorted(ps.LIVE.glob('live_play_2026101[5-9]_*.jsonl')):
    m, why = F.read_match(str(p))
    if not m: continue
    ev, delay = F.deployments(m, catalog)
    tt, pl = {}, {}
    for raw in open(p, 'rb'):
        if b'"tap_timing"' in raw[:40]:
            j = json.loads(raw); tt[j['tick']] = j
        elif b'"play"' in raw[:40]:
            j = json.loads(raw); pl[j['tick']] = j
    for e in ev:
        if e['source'] != 'own_tap': continue
        t = tt.get(e['tap'], {}); q = pl.get(e['tap'], {})
        cost = by_name.get(e['name'], {}).get('elixir')
        rows.append(dict(tap=e['tap'], dev=e['tick']-e['tap']-delay, tap_end=t.get('tap_end_ms'), elixir=q.get('elixir'), cost=cost, name=e['name']))
late = [r for r in rows if r['dev'] >= 12]; ok = [r for r in rows if abs(r['dev']) <= 4]
for lab, rs in (('late', late), ('normal', ok)):
    te = [r['tap_end'] for r in rs if r['tap_end'] is not None]
    short = [r['elixir'] - r['cost'] for r in rs if r['elixir'] is not None and r['cost'] is not None]
    print(lab, len(rs), 'tap_end_ms median', statistics.median(te) if te else None, 'elixir-cost median', statistics.median(short) if short else None,
          'share elixir<cost', round(sum(s < 0 for s in short)/max(1, len(short)), 3), Counter(r['name'] for r in rs).most_common(6))
# rate check: dev vs deficit, by clock phase
import math
for lo, hi in ((0, 2400), (2400, 3600), (3600, 4800), (4800, 9999)):
    rs = [r for r in rows if lo <= r['tap'] < hi and r['elixir'] is not None and r['elixir'] < r['cost']]
    ratio = [r['dev']/(r['cost']-r['elixir']) for r in rs if r['cost']-r['elixir'] > 0.15]
    res = [r['dev'] for r in rs]
    print(f'tap in [{lo},{hi}) n {len(rs)} ticks per elixir (dev/deficit) median', round(statistics.median(ratio), 1) if ratio else None,
          'q25/q75', [round(x, 1) for x in statistics.quantiles(ratio, n=4)] if len(ratio) > 3 else None)
