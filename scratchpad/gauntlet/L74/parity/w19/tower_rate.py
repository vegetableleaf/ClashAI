"""Live crown-tower fire rate by tower level: first sighting of every tower projectile (serial) -> shot ticks per tower ->
intervals between consecutive shots (< 40 ticks = continuous fire). Per (own / opp, princess / king, tower max_hp).
  python tower_rate.py LIVE_DIR [GLOB]"""
import glob
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

d, g = Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else 'live_play_*.jsonl'
iv = defaultdict(Counter)
for p in sorted(glob.glob(str(d / g))):
    m, why = F.read_match(p)
    if m is None or not m['ext']:
        continue
    mx = {}
    for b in m['frames'][0][1]:
        if b['tower']:
            mx[b['id']] = b['max_hp']
    seen, shots = set(), defaultdict(list)
    for t in sorted(m['proj']):
        for q in m['proj'][t]:
            src, serial = q[7], q[6]
            if src and str(src).startswith('T') and (src, serial) not in seen:
                seen.add((src, serial)); shots[src].append(t)
    for src, ts in shots.items():
        side = int(src[1]); kind = 'king' if src.endswith('K') else 'princess'
        key = ('own' if side == m['side'] else 'opp', kind, mx.get(src))
        for a, b in zip(ts, ts[1:]):
            if b - a < 40:
                iv[key][b - a] += 1
for k in sorted(iv, key=lambda k: (k[0], k[1], -(k[2] or 0))):
    c = iv[k]; n = sum(c.values())
    if n >= 30:
        print(k, n, 'top intervals', c.most_common(6), 'mean %.2f' % (sum(a * v for a, v in c.items()) / n))
