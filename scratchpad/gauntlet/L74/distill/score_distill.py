"""Step 4 scoring (DISTILL_PLAN.md): paired 960-game comparisons of gap.py runs, validate.paired_drift as in FINDING.md.

    python scratchpad/gauntlet/L74/distill/score_distill.py EVAL_DIR [--ref-teacher 'DIR_{seed}']

EVAL_DIR holds gap.py outputs named <run>_<seed>/<arm>/matches.jsonl, run in RUNS, seed in SEEDS. --ref-teacher: a
path pattern of earlier teacher D3 gap.py outputs, e.g. '/workspace/ref/D3_full_{seed}' (pod1014_refit), checked game for game.
Iteration 2: dagger_D1 / daggerkl_D1 (the DAgger students), iter1_D1 (iteration 1's student; run_distill.sh links it and
iteration 1's plain_D1 / teacher_D3); --pro NAME=eval_gen.json (first = the reference) adds the pro VAL check.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'heroiw'))
from validate import paired_drift  # noqa: E402

SEEDS = (741200, 742000)
RUNS = {'student_D1': 'D1', 'teacher_D3': 'D3', 'plain_D1': 'D1', 'student_D3': 'D3', 'iter1_D1': 'D1',
        'dagger_D1': 'D1', 'daggerkl_D1': 'D1'}
PAIRS = [('student_D1', 'teacher_D3', 'PRIMARY: distilled model, greedy, no add-ons - deployed teacher stack'),
         ('student_D1', 'plain_D1', 'distillation gain over the start (both greedy, no add-ons)'),
         ('teacher_D3', 'plain_D1', 'add-on value to transfer (FINDING.md r1: +2.19 [-1.88, +6.15])'),
         ('student_D3', 'student_D1', 'the rule stack (no refine heads) on top of the distilled model'),
         ('dagger_D1', 'plain_D1', 'ITERATION 2: DAgger student vs the plain start (iteration 1: -8.33 [-12.19, -4.48])'),
         ('dagger_D1', 'iter1_D1', 'DAgger rows added vs teacher-state rows only'),
         ('dagger_D1', 'teacher_D3', 'DAgger student - deployed teacher stack'),
         ('daggerkl_D1', 'dagger_D1', '+ cell KL to the plain model (same rows)'),
         ('daggerkl_D1', 'plain_D1', 'DAgger + cell KL student vs the plain start')]
PRO_BAR = 0.3                        # owner 10-14: pro VAL cell NLL may not rise more than this over the plain model


def load(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def runs(directory):
    got = {}
    for name, arm in RUNS.items():
        paths = [Path(directory)/f'{name}_{s}'/arm/'matches.jsonl' for s in SEEDS]
        if all(p.is_file() for p in paths):
            got[name] = {s: load(p) for s, p in zip(SEEDS, paths)}
    return got


def report(got, ref=None):
    lines = ['DISTILL scoring: 960 paired games (seeds 741200 + 742000), CAL c, E4 T .1, Hero IW + live press.',
             'Draws count as non-wins. Paired deltas: 10,000 bootstrap draws within census/side (validate.paired_drift).']
    for name, by_seed in got.items():
        rows = by_seed[SEEDS[0]] + by_seed[SEEDS[1]]
        w = sum(r['outcome'] == 'win' for r in rows)
        lines.append(f"{name}: win {100*w/len(rows):.2f}% ({w}/{len(rows)}); plays/game "
                     f"{sum(r['plays_accepted'] for r in rows)/len(rows):.1f}")
    for new, old, label in PAIRS:
        if new in got and old in got:
            d = paired_drift(got[old][SEEDS[0]] + got[old][SEEDS[1]], got[new][SEEDS[0]] + got[new][SEEDS[1]], expected=960)
            lines.append(f"{new} - {old}: {d['delta_pp']:+.2f} pp [{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}]  {label}")
    if ref is not None and 'teacher_D3' in got:
        for s in SEEDS:
            a = {(r['census'], r['seed']): r['outcome'] for r in load(Path(ref.format(seed=s))/'D3'/'matches.jsonl')}
            b = {(r['census'], r['seed']): r['outcome'] for r in got['teacher_D3'][s]}
            lines.append(f"environment check, teacher D3 seeds {s}: {sum(a[k] == b.get(k) for k in a)}/{len(a)} identical outcomes")
    return '\n'.join(lines)+'\n'


def pro_report(named):
    """[(name, eval_gen json path)], the first = the reference (plain): v3val (12,237 pro VAL rows) cell NLL vs the bar."""
    res = [(n, json.loads(Path(p).read_text())['v3val']['model']) for n, p in named]
    ref_name, ref = res[0]
    lines = [f'Pro VAL (v3val, {ref["n"]} rows, {ref["n_play"]} plays): cell NLL bar = {ref_name} + {PRO_BAR}']
    for n, m in res:
        d = m['cell_nll'] - ref['cell_nll']
        verdict = '' if n == ref_name else ' PASS' if d <= PRO_BAR else ' FAIL'
        lines.append(f"{n}: cell_nll {m['cell_nll']:.3f} ({d:+.3f}{verdict}); cell_half {m['cell_half_top1']:.3f} "
                     f"card {m['card_top1']:.3f} gate_bal {m['gate_bal_acc']:.3f}")
    return '\n'.join(lines)+'\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('eval_dir', type=Path)
    ap.add_argument('--ref-teacher', help="pattern with {seed}")
    ap.add_argument('--pro', action='append', default=[], help='NAME=eval_gen json; the first is the reference')
    a = ap.parse_args()
    text = report(runs(a.eval_dir), a.ref_teacher)
    if a.pro:
        text += pro_report([x.split('=', 1) for x in a.pro])
    (a.eval_dir/'SUMMARY.txt').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
