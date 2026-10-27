"""Self-check of j7.py's grading path: python -I test_j7.py (laptop; imports replay_metrics -> fights)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import j7

MAX = dict(T0L=4858, T0R=4858, T0K=7728, T1L=4858, T1R=4858, T1K=7728)


def truth(fall_t):
    rows = []
    for t in range(150, 4000, 2):
        r1l = 4858 if t < fall_t else 0
        rows.append([t, 4858, 4858, 7728, r1l, 4858, 7728, 0, int(t >= fall_t + 71)])
    return dict(match='m', my_side=1, maxhp=MAX, rows=rows)


def run_from(tr):
    """The engine format: one row per change, from tick 1; a dead tower is hp 0."""
    rows, prev = [], None
    for r in [[1] + tr['rows'][0][1:]] + tr['rows']:
        if prev is None or r[1:] != prev[1:]:
            rows.append(r)
        prev = r
    return dict(rows=rows)


tr = truth(2000)
g = j7.grade(tr, run_from(tr), run_from(tr))
assert g['seq_same'] and g['seq_timing'] and g['result_live'] == g['result_sim'] == [1, 0], g
assert g['traj_ok'] == g['traj_n'] > 0 and g['king_live'] == g['king_sim'], g
assert g['ceiling'][0]['seq_same']
g = j7.grade(tr, run_from(truth(2500)), None)          # same fall, 500 ticks late: sequence yes, timing no
assert g['seq_same'] and not g['seq_timing'], g
g = j7.grade(tr, run_from(truth(99999)), None)         # no fall in the engine
assert not g['seq_same'] and g['result_sim'] == [0, 0], g
assert j7.at([[1, 0], [10, 1]], 9)[1] == 0 and j7.at([[1, 0], [10, 1]], 10)[1] == 1
d, n = j7.best_deal([0, 1, 2, 3, 4, 0])
assert n == 6 and j7.cycle_fail(d, [0, 1, 2, 3, 4, 0]) is None
print('test_j7 OK')
