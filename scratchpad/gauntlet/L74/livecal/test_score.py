import copy
import numpy as np
import pytest
from score import sign_agreement, spearman, offset_mae, matrices, evaluate


def fixture():
    groups = [dict(id='old', family='old', fast=False, n=100, win_rate=.75, reportable=True),
              dict(id='fast', family='old', fast=True, n=100, win_rate=.5, reportable=True),
              dict(id='e4', family='E4', fast=False, n=100, win_rate=.25, reportable=True),
              dict(id='adapt', family='adapt_alone', fast=True, n=8, win_rate=.5, reportable=False)]
    plan = dict(groups=groups, pools=[dict(id='P1'), dict(id='P2')], k=8, seed_start=10)
    rows = []
    for pool in ('P1', 'P2'):
        for g, wins in zip(groups, [3, 2, 1, 2] if pool == 'P1' else [1, 2, 3, 2]):
            for c in ('evo', 'lad'):
                for s in range(4):
                    rows.append(dict(pool=pool, group=g['id'], census=c, seed=10+s,
                                     outcome='win' if s < wins else 'draw' if s == 3 else 'loss'))
    return plan, rows


def test_math_and_tied_rank():
    assert sign_agreement(.1, .2) and sign_agreement(-.1, -.2)
    assert not sign_agreement(0, .1) and not sign_agreement(.1, -.1)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1)
    assert spearman([1, 1, 2], [1, 2, 3]) == pytest.approx(np.sqrt(.75))
    assert spearman([1, 1], [1, 2]) is None
    assert offset_mae([.2, .4, .6], [.3, .5, .7]) == pytest.approx((.1, 0))
    # L1 constant is the median, not the mean residual.
    assert offset_mae([0, 0, 0], [0, .1, 1]) == pytest.approx((.1, 1/3))


def test_pool_verdict_bootstrap_and_report_only():
    plan, rows = fixture()
    result = evaluate(plan, rows, boots=80)
    assert result['verdict'] == 'pool P1 reproduces 2 of 2 live orderings'
    assert result['pools']['P2']['agreements'] == 0
    assert result['pools']['P1']['offset_mae'] == 0
    assert result == evaluate(plan, rows, boots=80)
    pair = result['pools']['P1']['pairs'][0]
    assert pair['sim_ci95'][0] >= 0
    assert not result['pools']['P1']['pairs'][-1]['primary']
    assert result['pools']['P1']['ci95']['spearman'] is not None


def test_paired_identical_arms_have_zero_delta_ci():
    plan, rows = fixture()
    for r in rows:
        if r['group'] == 'fast':
            r['outcome'] = next(x['outcome'] for x in rows if x['pool'] == r['pool'] and
                                x['group'] == 'old' and x['census'] == r['census'] and x['seed'] == r['seed'])
    result = evaluate(plan, rows, boots=30)
    assert result['pools']['P1']['pairs'][1]['sim_ci95'] == [0, 0]


@pytest.mark.parametrize('bad', ['missing', 'duplicate', 'extra', 'truncated', 'skipped', 'outcome'])
def test_incomplete_results_fail(bad):
    plan, rows = fixture()
    if bad == 'missing': rows.pop()
    if bad == 'duplicate': rows.append(copy.deepcopy(rows[0]))
    if bad == 'extra': rows[0]['seed'] = -1
    if bad == 'truncated': rows[0]['wall_truncated'] = True
    if bad == 'skipped': rows[0]['skipped'] = 'no deck'
    if bad == 'outcome': rows[0]['outcome'] = 'unknown'
    with pytest.raises(ValueError):
        matrices(plan, rows)
