"""Planted check for stats.estimate: confounded synthetic episodes (treatment rate AND base win rate both rise with the cell)
with a known +0.10 effect on the treated. The naive difference is biased; the cell-matched lift must recover 0.10 inside its
CI, and a planted null must give a CI covering 0.   python -B test_stats.py"""
import random

import stats

OUT0 = {o: 0.0 for o in stats.OUTS[1:]}


def synth(effect, n=6000, seed=3):
    rng, rows = random.Random(seed), []
    for i in range(n):
        ph = rng.choice(('1x', '2x', 'OT'))
        k = ('1x', '2x', 'OT').index(ph)
        tr = rng.random() < 0.2 + 0.3 * k                 # treated more often in later phases
        p = 0.3 + 0.2 * k + (effect if tr else 0.0)        # later phases win more anyway
        rows.append(dict(cid='m%d' % (i // 3), ph=ph, cr=0, hm='0', el='mid', oa='X', wa='Y', tr=int(tr), well=None,
                         win=float(rng.random() < p), **OUT0))
    return rows


if __name__ == '__main__':
    r = stats.estimate(synth(0.10), B=300)
    naive = r['win_tr_raw'] - r['win_ctl_raw']
    lo, hi = r['lift_win']['ci']
    print('planted +0.10: matched %.3f [%.3f, %.3f], naive %.3f' % (r['lift_win']['est'], lo, hi, naive))
    assert lo <= 0.10 <= hi and naive > hi, 'matched lift must cover the planted effect; the naive gap must be biased above it'
    r0 = stats.estimate(synth(0.0, seed=4), B=300)
    lo, hi = r0['lift_win']['ci']
    print('planted 0: matched %.3f [%.3f, %.3f]' % (r0['lift_win']['est'], lo, hi))
    assert lo <= 0 <= hi
    print('ok')
