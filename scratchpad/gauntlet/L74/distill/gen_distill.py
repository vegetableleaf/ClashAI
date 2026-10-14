"""Step 4 data (DISTILL_PLAN.md): SIM games with the learner played by gap.py's D3 stack, every learner decision recorded.

Same code path as `gap.py --arms D3` (gap.prepare -> gap.run_arm -> livecal worker -> search_s0.Runner), one difference:
each worker process is THIS file, which wraps two methods in its own process and then hands over to livecal.worker().
No repo file changes. The wrappers copy, never modify: the decision dict and gen row reach the original code as the
same objects (test_distill.py). Per learner decision: the generalist row the model saw (SelfPlaySide._gen_row, i.e.
GenPolicy.row + v3/v3.1 features) and the FINAL decision after decision_options (play, slot, cell, why) + gate p.
Per game: <chunk dir>/distill_<seed>.npz = arrays [n_decisions, ...] + `accepted` + a `meta` json string.

    python scratchpad/gauntlet/L74/distill/gen_distill.py --ckpt TEACHER --out DIR [--blocks 5] [--workers 13]

Block i = gap.prepare(seed_start = --seed-start + i * 1000): 480 games (CAL c, E4 T .1, evo + lad censuses), seeds
disjoint from the 960 evaluation pairs (741200.., 742000..), which the driver refuses to reuse.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

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
    """One decision: copies of the model's input row + the final decision. Fails closed on second plays."""
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
    """Decision rows + the side's landing records -> stacked arrays; `accepted` = the play landed and the engine took it."""
    if not rows:
        raise ValueError('a game with no learner decision')
    acc = {int(q['tick']): bool(q['accepted']) for q in plays}
    out = {k: np.stack([r[k] for r in rows]) for k in rows[0] if k != 'why'}
    out['why'] = np.array([r['why'] for r in rows])
    out['accepted'] = np.array([r['play'] and acc.get(r['tick'], False) for r in rows])
    return out


def install(S, E, out, census):
    """Wrap SelfPlaySide.apply (record the learner's decisions) and Runner.play (mark the learner, save the game)."""
    apply0, play0 = E.SelfPlaySide.apply, S.Runner.play

    def apply(self, p, d):
        rows = getattr(self, '_distill', None)
        if rows is not None:
            rows.append(snapshot(self, p, d))
        return apply0(self, p, d)

    def play(self, arm, m, deadline=None):
        m.learner._distill = []
        r = play0(self, arm, m, deadline)
        side = m.learner
        gid = side.model.gid
        meta = dict(seed=r['seed'], census=census, tag=r['tag'], learner_side=r['learner_side'], outcome=r['outcome'],
                    crowns_for=r['crowns_for'], crowns_against=r['crowns_against'], opp_deck=r['opp_deck'],
                    feature_version=int(getattr(side.model.model, 'feature_version', 1)),
                    card_vocab=sorted(gid, key=gid.get))
        np.savez_compressed(out/f"distill_{r['seed']}.npz", meta=json.dumps(meta), **game_arrays(side._distill, side.plays))
        return r

    E.SelfPlaySide.apply, S.Runner.play = apply, play


def worker():
    argv = sys.argv
    out, census = Path(argv[argv.index('--out')+1]), Path(argv[argv.index('--census')+1]).stem
    from pipeline import e1_eval as E, search_s0 as S
    install(S, E, out, census)
    return livecal.worker()          # reads sys.argv[2:], exactly as `livecal.py --worker`


def distill_command(arm, job, census, dest, python, _orig=gap.command):
    cmd = _orig(arm, job, census, dest, python)
    i = cmd.index('--worker')
    if not cmd[i-1].endswith('livecal.py'):
        raise ValueError('gap/livecal command layout changed')
    return [cmd[0], str(HERE/'gen_distill.py'), *cmd[i:]]


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
    ap.add_argument('--ckpt', default='icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--python', default='/workspace/venv33/bin/python')
    ap.add_argument('--workers', type=int, default=13)
    ap.add_argument('--blocks', type=int, default=5, help='480 games each')
    ap.add_argument('--seed-start', type=int, default=750000)
    ap.add_argument('--smoke', action='store_true', help='pod check: the first job of block 0 cut to 2 games')
    a = ap.parse_args()
    gap.command = distill_command     # gap.run_arm looks `command` up at call time
    for s in block_starts(a.seed_start, 1 if a.smoke else a.blocks):
        d = a.out/f'b{s}'
        plan = gap.prepare(d/'inputs', a.ckpt, s)
        if a.smoke:
            plan['jobs'] = [dict(plan['jobs'][0], seeds=plan['jobs'][0]['seeds'][:2])]
        gap.run_arm('D3', plan, d/'inputs', d/'D3', a.python, a.workers)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
