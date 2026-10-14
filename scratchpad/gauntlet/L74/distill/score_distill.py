"""Step 4 scoring (DISTILL_PLAN.md): paired 960-game comparisons of gap.py runs, validate.paired_drift as in FINDING.md.

    python scratchpad/gauntlet/L74/distill/score_distill.py EVAL_DIR [--ref-teacher 'DIR_{seed}']

EVAL_DIR holds gap.py outputs named <run>_<seed>/<arm>/matches.jsonl, run in RUNS, seed in SEEDS. --ref-teacher: a
path pattern of earlier teacher D3 gap.py outputs, e.g. '/workspace/ref/D3_full_{seed}' (pod1014_refit), checked game for game.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'heroiw'))
from validate import paired_drift  # noqa: E402

SEEDS = (741200, 742000)
RUNS = {'student_D1': 'D1', 'teacher_D3': 'D3', 'plain_D1': 'D1', 'student_D3': 'D3'}
PAIRS = [('student_D1', 'teacher_D3', 'PRIMARY: distilled model, greedy, no add-ons - deployed teacher stack'),
         ('student_D1', 'plain_D1', 'distillation gain over the start (both greedy, no add-ons)'),
         ('teacher_D3', 'plain_D1', 'add-on value to transfer (FINDING.md r1: +2.19 [-1.88, +6.15])'),
         ('student_D3', 'student_D1', 'the rule stack (no refine heads) on top of the distilled model')]


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('eval_dir', type=Path)
    ap.add_argument('--ref-teacher', help="pattern with {seed}")
    a = ap.parse_args()
    text = report(runs(a.eval_dir), a.ref_teacher)
    (a.eval_dir/'SUMMARY.txt').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
