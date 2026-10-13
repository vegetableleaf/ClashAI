"""Train/deploy gap (owner step 1, 2026-10-13): ONE checkpoint under four decision setups, one change per step.

  D0  rl_royale rollout sampler (T .5, tau .27), no rules     = how RL trains it
  D1  greedy, tau .35, no rules                               = decoding change only
  D2  D1 + timing rules (tau_phase, hazard gate, threatened)  = + when-to-play rules
  D3  D2 + card/cell overrides + own_effects                  = the SIM gate's live stack (LIVECAL LIVE flags)

Same paired design as IWDIAG/LIVECAL: CAL set c (E4 at T .1), evo + lad censuses, seeds 741200.., 480 games per arm,
runtime 0.1.33 with Hero IW and the live press rule in EVERY arm (live condition; not a factor here). Rules stay out of
training (owner: the model must learn them); this only measures how much each layer changes results.

    python scratchpad/gauntlet/L74/gap/gap.py --ckpt <path> --out /workspace/results/GAP_r1 --workers 25
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LIVE = HERE.parent/'livecal'
sys.path[:0] = [str(ROOT), str(LIVE), str(HERE.parent/'heroiw')]
import livecal  # noqa: E402

TIMING = {'tau_phase', 'gate_decode', 'gate_hazard_min_elixir', 'gate_hazard_threatened', 'tau_threatened'}
ARMS = ('D0', 'D1', 'D2', 'D3')
STEPS = [('D1', 'D0', 'decoding: greedy vs RL sampler'), ('D2', 'D1', '+ timing rules'),
         ('D3', 'D2', '+ card/cell overrides'), ('D3', 'D0', 'whole gap: live stack vs RL sampler')]


def flags(keys):
    out = []
    for k, v in livecal.LIVE.items():
        if k in keys:
            out += ['--'+k.replace('_', '-'), *map(str, v if isinstance(v, list) else [v])]
    return out


def command(arm, job, census, dest, python):
    cmd = livecal.command(job, census, dest, python=python)
    tail = ['--own-effects', *livecal.LV]
    if cmd[-len(tail):] != tail:
        raise ValueError('livecal.command layout changed; refusing to guess the rule flags')
    cmd = cmd[:-len(tail)]
    if arm == 'D0':
        cmd[cmd.index('--tau-plain')+1] = '0.27'
        return cmd + ['--learner-policy', 'sample', '--learner-T', '0.5']
    if arm == 'D2':
        return cmd + flags(TIMING)
    if arm == 'D3':
        return cmd + tail
    return cmd


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prepare(directory, ckpt):
    original = json.loads((LIVE/'manifest.json').read_text(encoding='utf8'))
    files = [ckpt, livecal.E4, livecal.GEN]
    manifest = dict(schema=1, groups=[dict(id='g00', checkpoint=ckpt, fast=False)],
                    pools=[dict(id='P1', members=[dict(path=livecal.E4, temperature=.1)])],
                    files=[dict(path=f, bytes=(ROOT/f).stat().st_size, sha256=digest(ROOT/f)) for f in files],
                    censuses={})
    directory.mkdir(parents=True)
    for name, rel in livecal.CENSUS.items():
        if digest(ROOT/rel) != original['censuses'][name]['source_sha256']:
            raise ValueError(f'CAL census changed: {rel}')
        dest = directory/f'cal_{name}.json'
        dest.write_bytes((ROOT/rel).read_bytes())
        manifest['censuses'][name] = dict(path=dest.name, sha256=digest(dest), source=rel)
    plan = livecal.schedule(manifest, k=480, seed_start=741200, pools='P1')
    (directory/'plan.json').write_text(json.dumps(plan, indent=1))
    return plan


def run_arm(arm, plan, inputs, out, python, workers):
    out.mkdir()
    env = dict(os.environ, ROYALE_RUNTIME='20261012-linux', ROYALE_HEROIW_FORM='hero', ROYALE_HEROIW_PRESS='live',
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=str(ROOT))
    def one(item):
        i, job = item
        dest = out/f'{i:05d}'
        cmd = command(arm, job, inputs/plan['censuses'][job['census']]['path'], dest, python)
        with dest.with_suffix('.log').open('w', encoding='utf8') as log:
            subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        rows = [json.loads(s) for s in (dest/'matches.jsonl').read_text().splitlines() if s.strip()]
        if sorted(r['seed'] for r in rows) != sorted(job['seeds']):
            raise ValueError(f'{dest}: missing/duplicate seeds')
        for r in rows:
            r['census'] = job['census']
        return rows
    with ThreadPoolExecutor(max_workers=workers) as ex, (out/'matches.jsonl').open('w', encoding='utf8') as f:
        for k, rows in enumerate(ex.map(one, enumerate(plan['jobs'])), 1):
            for r in rows:
                f.write(json.dumps(r)+'\n')
            print(f'{arm}: {k}/{len(plan["jobs"])} chunks', flush=True)


def summarize(out):
    from validate import paired_drift
    rows = {a: [json.loads(s) for s in (out/a/'matches.jsonl').read_text().splitlines() if s.strip()] for a in ARMS}
    lines = ['GAP: one checkpoint, four decision setups; 480 paired games each (CAL c, E4 T .1; Hero IW + live press).',
             'Draws count as non-wins. Paired deltas, 10,000 bootstrap draws within census/side.']
    for a in ARMS:
        r = rows[a]
        w = sum(x['outcome'] == 'win' for x in r)
        lines.append(f"{a}: win {100*w/len(r):.2f}% ({w}/{len(r)}); plays/game {sum(x['plays_accepted'] for x in r)/len(r):.1f}; "
                     f"tower HP diff/game {sum(x['tower_hp_diff'] for x in r)/len(r):+.0f}")
    report = {}
    for new, old, label in STEPS:
        d = paired_drift(rows[old], rows[new], expected=480)
        report[f'{new}-{old}'] = d
        lines.append(f"{new} - {old} ({label}): {d['delta_pp']:+.2f} pp [{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}]")
    (out/'score.json').write_text(json.dumps(report, indent=1))
    (out/'SUMMARY.txt').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt', default='icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--python', default='/workspace/venv33/bin/python')
    ap.add_argument('--workers', type=int, default=25)
    ap.add_argument('--arms', default=','.join(ARMS))
    ap.add_argument('--summarize-only', action='store_true')
    a = ap.parse_args()
    if not a.summarize_only:
        plan = prepare(a.out/'inputs', a.ckpt)
        for arm in a.arms.split(','):
            run_arm(arm, plan, a.out/'inputs', a.out/arm, a.python, a.workers)
    summarize(a.out)


if __name__ == '__main__':
    main()
