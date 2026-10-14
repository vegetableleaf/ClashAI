"""Step 4 data (DISTILL_PLAN.md): SIM games, every learner decision recorded with a label.

Same code path as gap.py (gap.prepare -> gap.run_arm -> livecal worker -> search_s0.Runner), one difference: each worker
process is THIS file, which wraps two methods in its own process and then hands over to livecal.worker(). No repo file
changes. Per learner decision: the generalist row the model saw (SelfPlaySide._gen_row, i.e. GenPolicy.row + v3/v3.1
features) and a decision (play, slot, cell, why) + gate p. Per game: <chunk dir>/distill_<seed>.npz = arrays
[n_decisions, ...] + `accepted` + a `meta` json string.

  iteration 1  the learner plays gap's D3 (teacher checkpoint + live rules); its FINAL decision is the label.
  DAgger       (--teacher, iteration 2) the learner plays gap's D1 (the STUDENT checkpoint, greedy, no rules); on every
               learner decision the teacher's D3 decision (teacher checkpoint + D3's decision flags, gap's D3 code:
               forward -> pre -> live_decide_batch + match_kwargs) is computed on the SAME prepared state and the SAME
               input row and recorded as the label; with probability --p-teacher the teacher's action is the one
               executed (beta-mixture rollout), else the student's. D3's --own-effects look-ahead changes the model INPUT,
               so it cannot act on the student's row: it is not applied (meta own_effects_not_applied).

    python scratchpad/gauntlet/L74/distill/gen_distill.py --ckpt TEACHER --out DIR [--blocks 5] [--workers 13]
    python scratchpad/gauntlet/L74/distill/gen_distill.py --ckpt STUDENT --teacher TEACHER --p-teacher 0.5 --out DIR \
        --blocks 3 --seed-start 760000

Block i = gap.prepare(seed_start = --seed-start + i * 1000): 480 games (CAL c, E4 T .1, evo + lad censuses), seeds
disjoint from the 960 evaluation pairs (741200.., 742000..), which the driver refuses to reuse.
"""
from __future__ import annotations

import argparse
from functools import partial
import json
from pathlib import Path
import sys
import zlib

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT), str(HERE.parent/'gap'), str(HERE.parent/'livecal'), str(HERE.parent/'heroiw')]
import gap  # noqa: E402
import livecal  # noqa: E402

EVAL_SEEDS = (741200, 742000)        # gap.py's 960 pairs; generation must never touch them
GAMES_PER_SEED_SET = 240             # gap.prepare k=480 -> 240 seeds per census


def row_keys():
    from pipeline import e1_eval as E
    return E.GEN_ROW_KEYS + E.GEN_V3_KEYS + E.GEN_V31_KEYS


def snapshot(side, p, d):
    """One decision: copies of the model's input row + the decision. Fails closed on second plays."""
    if d.get('follow_ups'):
        raise ValueError('follow-up second plays have no decision row; this stack cannot be distilled as is')
    row = side._gen_row
    if row is None:
        raise ValueError('distill recording needs a GenPolicy learner (no gen row)')
    out = {k: np.array(row[k], copy=True) for k in row_keys() if k in row}
    out.update(tick=int(side._cur[0]), play=bool(d['play']), slot=int(d['slot']), cell=int(d['cell']),
               why=str(d['why']), p=float(p))
    return out


def game_arrays(rows, plays):
    """Decision rows + the side's landing records -> stacked arrays. `accepted` = the label's play counts as a PLAY row:
    iteration 1, the play landed and the engine took it; DAgger, every teacher play (it was mostly not executed, so
    there is no landing to check; `exec_accepted` = the executed action landed)."""
    if not rows:
        raise ValueError('a game with no learner decision')
    acc = {int(q['tick']): bool(q['accepted']) for q in plays}
    out = {k: np.stack([r[k] for r in rows]) for k in rows[0] if k != 'why'}
    out['why'] = np.array([r['why'] for r in rows])
    landed = np.array([acc.get(r['tick'], False) for r in rows], dtype=bool)
    if 'teacher_exec' in out:
        out['exec_accepted'] = np.where(out['teacher_exec'], out['play'], out['s_play']) & landed
        out['accepted'] = out['play'].copy()
    else:
        out['accepted'] = out['play'] & landed
    return out


class Teacher:
    """DAgger labels: gap's D3 decision (this policy + D3's decision flags) on the learner's prepared state and row.
    Mirrors search_s0.Runner.round for one side: forward -> pre(hand) -> live_decide_batch(**match_kwargs) with the
    D3 cfg. The per-match rule state (threat / dead-tower / lethal history, rng_decision_options) lives on the side, so
    it evolves along the student's trajectory exactly as D3's would along its own."""

    def __init__(self, policy, p, d3_args, meta=None):
        from pipeline.decision_options import add_arguments, config_from_args
        ap = argparse.ArgumentParser()
        add_arguments(ap)
        ap.add_argument('--own-effects', action='store_true')
        a = ap.parse_args(list(d3_args))
        self.policy, self.p, self.cfg = policy, float(p), config_from_args(a)
        if not 0.0 <= self.p <= 1.0:
            raise ValueError('--p-teacher must be in [0, 1]')
        self.meta = dict(meta or {}, mode='dagger', p_teacher=self.p, d3_args=list(d3_args),
                         own_effects_not_applied=bool(a.own_effects))

    def decide(self, side):
        from pipeline.decision_options import match_kwargs
        from pipeline.e1_eval import live_decide_batch, policy_feature_version as fv
        if side._gen_row is None:
            raise ValueError('DAgger labels need a GenPolicy learner (no gen row)')
        if side.model.gid != self.policy.gid or fv(side.model) != fv(self.policy):
            raise ValueError('teacher and student must share the card vocab and feature version (one input row)')
        enc, heads, p, hand = self.policy.forward_batch([side._gen_row], side.cfg['device'])
        _, allowed, stalled = side.pre(hand[0])
        cfg = side.cfg
        side.cfg = {**cfg, **self.cfg}                  # the D3 learner cfg (search_s0._init_worker: cfg.update(options))
        try:
            kw = match_kwargs([side])
            tau, dev = side.cfg['tau'], side.cfg['device']
        finally:
            side.cfg = cfg
        d = live_decide_batch(self.policy, enc, heads, [p[0]], allowed[None], np.array([stalled]), tau=tau, device=dev,
                              **kw)[0]
        return p[0], d

    def executes(self, side):
        """Beta mixture: the teacher's action is executed with probability p (own per-match stream; p 0 never draws)."""
        if self.p <= 0:
            return False
        if not hasattr(side, '_dagger_rng'):
            side._dagger_rng = np.random.default_rng(zlib.crc32(f'{side.tag}:dagger_mix'.encode()))
        return bool(side._dagger_rng.random() < self.p)


def install(S, E, out, census, teacher=None):
    """Wrap SelfPlaySide.apply (record the learner's decisions) and Runner.play (mark the learner, save the game).
    teacher None: the learner's own decision is the label (iteration 1). A Teacher: DAgger (module docstring)."""
    apply0, play0 = E.SelfPlaySide.apply, S.Runner.play

    def apply(self, p, d):
        rows = getattr(self, '_distill', None)
        if rows is None or teacher is None:
            if rows is not None:
                rows.append(snapshot(self, p, d))
            return apply0(self, p, d)
        pt, dt = teacher.decide(self)
        use = teacher.executes(self)
        rows.append(dict(snapshot(self, pt, dt), s_play=bool(d['play']), s_slot=int(d['slot']), s_cell=int(d['cell']),
                         s_p=float(p), teacher_exec=use))
        return apply0(self, pt, dt) if use else apply0(self, p, d)

    def play(self, arm, m, deadline=None):
        m.learner._distill = []
        r = play0(self, arm, m, deadline)
        side = m.learner
        gid = side.model.gid
        meta = dict(seed=r['seed'], census=census, tag=r['tag'], learner_side=r['learner_side'], outcome=r['outcome'],
                    crowns_for=r['crowns_for'], crowns_against=r['crowns_against'], opp_deck=r['opp_deck'],
                    feature_version=int(getattr(side.model.model, 'feature_version', 1)),
                    card_vocab=sorted(gid, key=gid.get), **(teacher.meta if teacher else {}))
        np.savez_compressed(out/f"distill_{r['seed']}.npz", meta=json.dumps(meta), **game_arrays(side._distill, side.plays))
        return r

    E.SelfPlaySide.apply, S.Runner.play = apply, play


def split_argv(argv):
    """Worker argv -> (argv for livecal.worker, teacher path or None, p, D3 decision flags): DAgger appends
    `--distill TEACHER P <D3 flags...>` after search_s0's own arguments."""
    if '--distill' not in argv:
        return list(argv), None, 0.0, []
    i = argv.index('--distill')
    return list(argv[:i]), argv[i+1], float(argv[i+2]), list(argv[i+3:])


def worker():
    argv, teacher_path, p, d3 = split_argv(sys.argv)
    sys.argv[:] = argv                       # livecal.worker reads sys.argv[2:] = search_s0's arguments only
    out, census = Path(argv[argv.index('--out')+1]), Path(argv[argv.index('--census')+1]).stem
    from pipeline import e1_eval as E, search_s0 as S
    teacher = None
    if teacher_path is not None:
        policy, _ = E.load_policy(ROOT/teacher_path, argv[argv.index('--device')+1])
        teacher = Teacher(policy, p, d3, meta=dict(teacher=teacher_path, teacher_sha256=gap.digest(ROOT/teacher_path)))
    install(S, E, out, census, teacher)
    return livecal.worker()          # reads sys.argv[2:], exactly as `livecal.py --worker`


def distill_command(arm, job, census, dest, python, extra=(), drop=(), *, _orig=gap.command, teacher=None, p_teacher=0.0):
    """gap's worker command for `arm`, run by this file (gap.run_arm passes `extra` and `drop` positionally). DAgger (teacher):
    the student plays D1, and D3's command must be D1's + decision flags; those flags go to the worker's Teacher."""
    cmd = _orig(arm, job, census, dest, python, extra, drop)
    i = cmd.index('--worker')
    if not cmd[i-1].endswith('livecal.py'):
        raise ValueError('gap/livecal command layout changed')
    out = [cmd[0], str(HERE/'gen_distill.py'), *cmd[i:]]
    if teacher is None:
        return out
    d3 = _orig('D3', job, census, dest, python, extra)
    if arm != 'D1' or d3[:len(cmd)] != cmd:
        raise ValueError('DAgger: the student plays D1, and D3 must be D1 + decision flags')
    return out + ['--distill', str(teacher), repr(float(p_teacher)), *d3[len(cmd):]]


def block_starts(seed_start, blocks, stride=1000):
    starts = [seed_start + i*stride for i in range(blocks)]
    for s in starts:
        for e in EVAL_SEEDS:
            if s < e + GAMES_PER_SEED_SET and e < s + GAMES_PER_SEED_SET:
                raise ValueError(f'generation block {s} overlaps the evaluation seeds {e}..')
    if stride < GAMES_PER_SEED_SET:
        raise ValueError('blocks would share seeds')
    return starts


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        return worker()
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt', default='icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt',
                    help='the learner: the teacher (iteration 1) or the acting student (with --teacher)')
    ap.add_argument('--teacher', default=None, help='DAgger: the D3 teacher checkpoint that labels the student\'s states')
    ap.add_argument('--p-teacher', type=float, default=0.0, help='DAgger: P(the teacher\'s action is executed)')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--python', default='/workspace/venv33/bin/python')
    ap.add_argument('--workers', type=int, default=13)
    ap.add_argument('--blocks', type=int, default=5, help='480 games each')
    ap.add_argument('--seed-start', type=int, default=750000)
    ap.add_argument('--smoke', action='store_true', help='pod check: the first job of block 0 cut to 2 games')
    a = ap.parse_args()
    arm = 'D1' if a.teacher else 'D3'
    gap.command = partial(distill_command, teacher=a.teacher, p_teacher=a.p_teacher)   # run_arm looks it up at call time
    for s in block_starts(a.seed_start, 1 if a.smoke else a.blocks):
        d = a.out/f'b{s}'
        plan = gap.prepare(d/'inputs', a.ckpt, s)
        if a.smoke:
            plan['jobs'] = [dict(plan['jobs'][0], seeds=plan['jobs'][0]['seeds'][:2])]
        gap.run_arm(arm, plan, d/'inputs', d/arm, a.python, a.workers)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
