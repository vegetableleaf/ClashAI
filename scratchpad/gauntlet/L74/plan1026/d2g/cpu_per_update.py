"""Actor + learner core-s per update from cpusample.sh's file (epoch, main cpu-s, children cpu-s, n) and the run's
w16_matches_uNNNN.json mtimes (= the end of each update's rollout). Interval i = rollout end of u(i-1) .. rollout end of u(i),
i.e. one update step + one rollout; interpolated linearly between 20 s samples.
    python cpu_per_update.py SAMPLES RUN_DIR"""
import bisect
import os
import sys
from pathlib import Path

rows = [tuple(map(float, line.split()[:3])) for line in open(sys.argv[1]) if len(line.split()) >= 3]
ts = [r[0] for r in rows]


def at(t, col):
    i = min(max(bisect.bisect_left(ts, t), 1), len(ts) - 1)
    (t0, *a), (t1, *b) = rows[i - 1], rows[i]
    return a[col] + (b[col] - a[col]) * (t - t0) / (t1 - t0)


ends = sorted(os.path.getmtime(p) for p in Path(sys.argv[2]).glob('w16_matches_u*.json'))
for i in range(1, len(ends)):
    t0, t1 = ends[i - 1], ends[i]
    act, main = at(t1, 1) - at(t0, 1), at(t1, 0) - at(t0, 0)
    print(f'u{i:04d}: wall {t1 - t0:.0f} s, actors {act:.0f} core-s ({act / (t1 - t0):.1f} cores), learner {main:.0f} core-s')
