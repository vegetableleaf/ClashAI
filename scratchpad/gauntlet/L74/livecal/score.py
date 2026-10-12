"""Score complete paired SIM outcomes against frozen live truth; never deploys.

Unweighted across reportable checkpoint/fast/era groups. Offset = median(live-SIM),
the L1-optimal constant. Bootstrap resamples SIM seeds jointly across arms within
each census, and live matches independently within groups (binomial wins).
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np


def ranks(values):
    a = np.asarray(values)
    return np.array([1 + np.sum(a < v) + (np.sum(a == v)-1)/2 for v in a], dtype=float)


def spearman(x, y):
    a, b = ranks(x), ranks(y)
    if len(a) < 2 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def offset_mae(sim, live):
    residual = np.asarray(live) - np.asarray(sim)
    offset = float(np.median(residual))
    return offset, float(np.mean(np.abs(residual-offset)))


def sign_agreement(a, b):
    # A tie is not evidence of a strict live ordering.
    return bool(a*b > 0)


def interval(values):
    v = [x for x in values if x is not None and np.isfinite(x)]
    return np.quantile(v, [.025, .975]).tolist() if v else None


def contrasts(groups):
    def indices(fam, fast=None):
        return [i for i, g in enumerate(groups) if g['family'] == fam and (fast is None or g['fast'] == fast)]
    out = []
    for name, left, right, primary in [
        ('old > E4', indices('old', False), indices('E4', False), True),
        ('fast-off > fast-on (old)', indices('old', False), indices('old', True), True),
        ('adapt_fixed vs old (fast-on)', indices('adapt_fixed', True), indices('old', True), False),
        ('adapt_alone vs old (fast-on)', indices('adapt_alone', True), indices('old', True), False),
        ('adapt_alone vs old (fast-off)', indices('adapt_alone', False), indices('old', False), False),
    ]:
        if left and right:
            out.append((name, left, right, primary))
    return out


def delta(values, left, right, n):
    return float(np.average(values[left], weights=n[left])-np.average(values[right], weights=n[right]))


def metrics(sim, live, groups):
    mask = [i for i, g in enumerate(groups) if g['reportable']]
    if len(mask) < 2:
        raise ValueError('need at least two reportable groups for calibration')
    n = np.array([g['n'] for g in groups])
    pairs = []
    for name, left, right, primary in contrasts(groups):
        sd, ld = delta(sim, left, right, n), delta(live, left, right, n)
        pairs.append(dict(name=name, primary=primary, sim_delta=sd, live_delta=ld,
                          agreement=sign_agreement(sd, ld), live_n=[int(sum(n[left])), int(sum(n[right]))]))
    offset, mae = offset_mae(sim[mask], live[mask])
    return dict(spearman=spearman(sim[mask], live[mask]), offset=offset, offset_mae=mae,
                agreements=sum(p['agreement'] for p in pairs if p['primary']),
                orderings=sum(p['primary'] for p in pairs), pairs=pairs)


def matrices(plan, rows):
    """Reject missing/duplicate/extra/truncated observations rather than score biased survivors."""
    ids = [g['id'] for g in plan['groups']]
    pools = [p['id'] for p in plan['pools']]
    keys = [(c, s) for c in ('evo', 'lad') for s in range(plan['seed_start'], plan['seed_start']+plan['k']//2)]
    expected = {(p, g, c, s) for p in pools for g in ids for c, s in keys}
    got = {}
    for r in rows:
        key = (r['pool'], r['group'], r['census'], r['seed'])
        if key not in expected or key in got:
            raise ValueError(f'extra or duplicate result: {key}')
        if r.get('skipped') or r.get('wall_truncated') or r.get('outcome') not in ('win', 'loss', 'draw'):
            raise ValueError(f'invalid or truncated result: {key}')
        got[key] = float(r['outcome'] == 'win')
    if set(got) != expected:
        raise ValueError(f'incomplete results: {len(got)}/{len(expected)}')
    return {p: np.array([[got[p, g, c, s] for c, s in keys] for g in ids]) for p in pools}


def evaluate(plan, rows, boots=2000, seed=74012):
    if boots < 1:
        raise ValueError('bootstrap count must be positive')
    mats = matrices(plan, rows)
    groups = plan['groups']
    live = np.array([g['win_rate'] for g in groups])
    n = np.array([g['n'] for g in groups])
    results = {p: metrics(m.mean(axis=1), live, groups) for p, m in mats.items()}
    draws = {p: [] for p in mats}
    rng = np.random.default_rng(seed)
    half = plan['k']//2
    for _ in range(boots):
        ix = np.r_[rng.integers(0, half, half), half+rng.integers(0, half, half)]
        lb = rng.binomial(n, live)/n
        for p, m in mats.items():
            draws[p].append(metrics(m[:, ix].mean(axis=1), lb, groups))
    for p, result in results.items():
        result['ci95'] = {k: interval([b[k] for b in draws[p]]) for k in
                          ('spearman', 'offset', 'offset_mae', 'agreements')}
        result['spearman_defined_bootstraps'] = sum(b['spearman'] is not None for b in draws[p])
        for j, pair in enumerate(result['pairs']):
            pair['sim_ci95'] = interval([b['pairs'][j]['sim_delta'] for b in draws[p]])
            pair['live_ci95'] = interval([b['pairs'][j]['live_delta'] for b in draws[p]])
            pair['bootstrap_agreement'] = float(np.mean([b['pairs'][j]['agreement'] for b in draws[p]]))
        result['rates'] = {g['id']: dict(sim=float(mats[p][i].mean()), live=float(live[i]))
                           for i, g in enumerate(groups)}
    # Primary signs first, then rank correlation, then offset-adjusted error; stable pool id tie break.
    def key(p):
        r = results[p]
        return (-r['agreements'], -(r['spearman'] if r['spearman'] is not None else -2), r['offset_mae'], p)
    best = min(results, key=key)
    r = results[best]
    if r['orderings'] != 2:
        raise ValueError('both required old/E4 and old fast contrasts must be present')
    verdict = f"pool {best} reproduces {r['agreements']} of {r['orderings']} live orderings"
    return dict(verdict=verdict, best_pool=best, pools=results, bootstrap_replicates=boots,
                limitations=['In-sample pool selection and offset fitting; validate on future live checkpoints.',
                             'Live comparisons are observational and mixed-era, not randomized causal effects.',
                             'SIM uses the S2/CAL bundle; see plan flag mismatches and fixed runtime assumptions.',
                             'Live bootstrap assumes independent matches within groups; no session-cluster correction.'])


def summary(report):
    lines = [report['verdict'], 'Best pool by sign agreement, then Spearman, then offset MAE. No deployment.']
    for p, r in report['pools'].items():
        lines.append(f"{p}: {r['agreements']}/{r['orderings']} orderings; Spearman={r['spearman']}; "
                     f"offset={100*r['offset']:.2f} pp; offset MAE={100*r['offset_mae']:.2f} pp; CI95={r['ci95']}")
        for q in r['pairs']:
            lines.append(f"  {q['name']}{' (report only)' if not q['primary'] else ''}: "
                         f"live {100*q['live_delta']:+.2f} pp {q['live_ci95']}, "
                         f"SIM {100*q['sim_delta']:+.2f} pp {q['sim_ci95']}; agreement bootstrap={q['bootstrap_agreement']:.3f}")
    return '\n'.join(lines + report['limitations'])+'\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--matches', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--bootstrap', type=int, default=2000)
    a = ap.parse_args()
    report = evaluate(json.loads(a.plan.read_text()), [json.loads(s) for s in a.matches.read_text().splitlines()], a.bootstrap)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out/'score.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf8')
    (a.out/'SUMMARY.txt').write_text(summary(report), encoding='utf8')


if __name__ == '__main__':
    main()
