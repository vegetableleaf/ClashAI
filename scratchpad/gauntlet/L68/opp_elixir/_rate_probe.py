"""Exploratory: per-200-tick bins of clean regen rate (no play, uncapped), to locate phase boundaries."""
import json, glob, collections, statistics
bins = collections.defaultdict(list)
for deck in ('icebow', 'hogeq'):
    for f in sorted(glob.glob(f'scratchpad/gauntlet/ext/corpus_v6/{deck}/replay_*.json'))[:300]:
        d = json.load(open(f))
        plays = [(e['tick'], e['side']) for e in d['log'] if e.get('accepted')]
        fr = d['frames']
        for a, b in zip(fr, fr[1:]):
            t0, t1 = a['tick'], b['tick']
            if t1 <= t0: continue
            for s in (0, 1):
                e0, e1 = a['elixir'][s], b['elixir'][s]
                if e1 >= 10 or e0 >= 10: continue
                if any(t0 <= t < t1 and ps == s for t, ps in plays): continue
                bins[t0 // 200 * 200].append((e1 - e0) / (t1 - t0))
for k in sorted(bins):
    v = bins[k]
    print(k, len(v), round(statistics.median(v), 6), round(min(v), 6), round(max(v), 6),
          'ticks/elixir', round(1 / statistics.median(v), 2) if statistics.median(v) > 0 else None)
