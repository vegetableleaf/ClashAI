"""One NEWSIM arm: smoke -> fresh-runtime adaptive cycles -> graft -> paired eval.

Invoked under gpu.lock then cpu.lock. Never resumes ADAPT's old-runtime RL state,
never deploys, never downloads. Individual training stages resume only their
new-runtime main checkpoint between cycles. Results hold checkpoint and logs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.weekend.adaptive import driver as D
from scratchpad.gauntlet.L74.newsim import census, metrics
from scratchpad.gauntlet.L74.newsim.evaluate import GEN

INIT = D.checkpoint('wk_adapt_main')
EXTRA = [D.CKROOT/f'wk_adapt_exp{i}'/f'wk_adapt_exp{i}_u0015.pt' for i in range(1, 4)]
CSV = Path('scratchpad/gauntlet/L74/pro2/output/battles.csv')


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--arm', choices=('base', 'fast'), required=True)
    p.add_argument('--workers', type=int, default=24)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--plan-only', action='store_true', help='Print commands/configuration; no SIM or files written')
    a = p.parse_args(argv)
    if not 1 <= a.workers <= 24:
        p.error('workers must be 1..24 (plus shell, driver, trainer and tracker <=28)')
    return a


def plan(a):
    prefix = f'newsim_{a.arm}'
    cycles = D.cycle_plan(prefix)
    return dict(arm=a.arm, tag=prefix, learner_pipeline_frac=.3 if a.arm == 'fast' else 0.,
                workers=a.workers, max_processes=a.workers+4, init=str(INIT),
                extra_exploiters=list(map(str, EXTRA)), runtime='20261012-linux', cycles=cycles,
                fresh_runtime_state=True, evaluations=[dict(pool=p, pipeline=f, pairs=960)
                    for p in ('CAL', 'P2') for f in (False, True)])


def training_config(base, phase, cycle, deck_path, external, a):
    c = D.config_for(base, phase, cycle, deck_path, external, init=INIT)
    c.update(n_actors=a.workers, learner_pipeline_frac=.3 if a.arm == 'fast' else 0.)
    return c


def inputs(base):
    return [INIT, *EXTRA, D.FAST, D.OLD, D.CAL_C, Path(GEN), D.EVO, D.LAD, D.DATA, CSV,
            Path(base['pool']), Path(base['pool']).with_name('pool_env_v1_split.json'),
            Path(base['league_specialist']),
            Path('research/ext/Royale/RoyaleSim/data/derived/cards.json'),
            Path('research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json'),
            Path('scratchpad/gauntlet/L70/abilities/ability_models_v2.json')]


def input_receipt(base, out):
    rows = []
    for relative in dict.fromkeys(inputs(base)):
        path = ROOT/relative
        if not path.is_file():
            raise FileNotFoundError(f'required pod input: {relative}')
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
        rows.append(dict(path=str(relative), bytes=path.stat().st_size, sha256=h.hexdigest()))
    D.atomic_json(out/'inputs.json', rows)


def read_evaluation(ev, model):
    records = {}
    for name in ('evo', 'lad'):
        path = ev/f'{model}_{name}'
        if not (path/'COMPLETE').is_file():
            raise ValueError(f'missing completion: {path}')
        rows = [json.loads(s) for s in (path/'matches.jsonl').read_text().splitlines()]
        if len(rows) != 480:
            raise ValueError(f'expected 480 games: {path}')
        for r in rows:
            key = (name, r['tag'])
            if key in records or r.get('skipped') or r.get('wall_truncated') or r.get('outcome') not in ('win', 'loss', 'draw'):
                raise ValueError(f'invalid or duplicate eval game: {key}')
            records[key] = r
    return records


def compare(a, b):
    import math
    if set(a) != set(b) or len(a) != 960:
        raise ValueError('expected 960 paired games')
    if any(a[k]['opp_deck'] != b[k]['opp_deck'] or a[k]['seed'] != b[k]['seed']
           or a[k]['learner_side'] != b[k]['learner_side'] for k in a):
        raise ValueError('paired decks, seeds or seats differ')
    score = {'win': 1., 'draw': .5, 'loss': 0.}
    delta = [score[b[k]['outcome']]-score[a[k]['outcome']] for k in sorted(a)]
    n, mu = len(delta), sum(delta)/len(delta)
    half = 1.96*math.sqrt(sum((d-mu)**2 for d in delta)/(n-1)/n)
    return dict(pairs=n, old_pct=100*sum(score[r['outcome']] for r in a.values())/n,
                new_pct=100*sum(score[r['outcome']] for r in b.values())/n,
                delta_pp=100*mu, lo_pp=100*(mu-half), hi_pp=100*(mu+half))


def report(out, census_report):
    from scratchpad.gauntlet.L74.weekend import wk_compare as W
    readings, lines, all_records = {}, [], {}
    for pool in ('CAL', 'P2'):
        for mode in ('off', 'on'):
            ev = out/'eval'/f'{pool}_{mode}'
            old, new = (read_evaluation(ev, m) for m in ('old', 'new'))
            result = compare(old, new)
            readings[f'{pool}_{mode}'] = result
            all_records[pool, mode, 'old'], all_records[pool, mode, 'new'] = old, new
            lines += [f'{pool}, pipeline {mode}: {json.dumps(result)}', W.arch_table(str(ev), 'old', 'new')]
            for name, rs in (('old', old), ('new', new)):
                lines += [f'{pool}/{mode}/{name}:', metrics.table(list(rs.values()))]
        for model in ('old', 'new'):
            cost = compare(all_records[pool, 'off', model], all_records[pool, 'on', model])
            lines.append(f'{pool}/{model} fast-play change ON minus OFF: {json.dumps(cost)}')
            readings[f'{pool}_{model}_fast_change'] = cost
    off = [readings[f'{p}_off'] for p in ('CAL', 'P2')]
    verdict = ('Improvement shown on both opponent pools' if all(r['lo_pp'] > 0 for r in off) else
               'Worse on at least one opponent pool' if any(r['hi_pp'] < 0 for r in off) else
               'Improvement not established')
    # No unstated non-inferiority margin. Positive/negative/uncertain use the
    # same paired normal 95% interval as ADAPT; phase/archetype rows descriptive.
    D.atomic_json(out/'scores.json', readings)
    (out/'SUMMARY.txt').write_text('VERDICT: '+verdict+'. Nothing deployed.\n'+
        '\n'.join(lines)+'\nCensus counts and dropped cards:\n'+json.dumps(census_report, indent=2)+'\n', encoding='utf8')


def execute(a):
    import torch
    import yaml
    from pipeline.royale_runtime import activate
    from pipeline.rl_royale import RUN_ROOT
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    recipe = plan(a)
    D.atomic_json(out/'plan.json', recipe)
    stamp = activate()
    if stamp.get('runtime_id') != recipe['runtime']:
        raise ValueError('NEWSIM requires ROYALE_RUNTIME=20261012-linux')
    D.atomic_json(out/'runtime.json', stamp)
    # Gate always precedes census reset checks and all training.
    D.run([sys.executable, HERE.parent/'heroiw/smoke.py', '--out', out/'smoke.json'], out/'smoke.log')
    base = yaml.safe_load((ROOT/'pipeline/rl_royale.yaml').read_text())
    input_receipt(base, out)
    census_report = census.prepare(out, ROOT/CSV, [ROOT/p for p in [INIT, *EXTRA, D.FAST, D.OLD, D.CAL_C, Path(GEN)]])
    external = list(map(str, EXTRA))
    runs = []
    try:
        for c in recipe['cycles']:
            for name in (c['main_run'], c['exploiter_run']):
                if name not in runs and (ROOT/D.checkpoint(name)).exists():
                    raise FileExistsError(f'NEWSIM run already exists: {name}')
            main_cfg = training_config(base, 'main', c, out/'decks_rl.json', external, a)
            if c['main_run'] not in runs:
                runs.append(c['main_run'])
            main = D.train(main_cfg, c['main_run'], out)
            frozen = ROOT/c['frozen']
            if frozen.exists():
                raise FileExistsError(frozen)
            D.save_checkpoint(frozen, {k: v for k, v in main.items() if k != 'rl'})
            digest = hashlib.sha256(frozen.read_bytes()).hexdigest()
            exp_cfg = training_config(base, 'exploiter', c, out/'decks_rl.json', [], a)
            runs.append(c['exploiter_run'])
            D.train(exp_cfg, c['exploiter_run'], out)
            if hashlib.sha256(frozen.read_bytes()).hexdigest() != digest:
                raise RuntimeError('frozen main changed')
            exp = D.CKROOT/c['exploiter_run']/f"{c['exploiter_run']}_u0015.pt"
            if not (ROOT/exp).is_file():
                raise FileNotFoundError(exp)
            main = D.enroll(main, str(exp))
            D.save_checkpoint(ROOT/D.checkpoint(c['main_run']), main)
            external = list(main['rl']['league']['external'])
            D.atomic_json(out/f"cycle_{c['cycle']}.json", dict(c, frozen_sha256=digest, external=external))
        final = out/f"newsim_{a.arm}_final_grafted.pt"
        D.run([sys.executable, D.WEEKEND/'graft_generic.py', D.checkpoint(recipe['cycles'][-1]['main_run']),
               D.OLD, final], out/'graft.log')
        graft = torch.load(final, map_location='cpu', weights_only=True)
        donor = torch.load(ROOT/D.OLD, map_location='cpu', weights_only=True)
        heads = [k for k in donor['model'] if k.startswith(('cell_refine.', 'tower_refine.', 'projectile_target_'))]
        if not heads or any(not torch.equal(graft['model'][k], donor['model'][k]) for k in heads):
            raise ValueError('graft verification failed')
        D.atomic_json(out/'graft_receipt.json', dict(tensors=len(heads), sha256=hashlib.sha256(final.read_bytes()).hexdigest()))
        for pool in ('CAL', 'P2'):
            for mode in ('off', 'on'):
                ev = out/'eval'/f'{pool}_{mode}'
                ev.mkdir(parents=True)
                for model, checkpoint in (('old', ROOT/D.OLD), ('new', final)):
                    for family, start in (('evo', 30000), ('lad', 30480)):
                        command = [sys.executable, HERE/'evaluate.py', '--checkpoint', checkpoint, '--census',
                            out/f'decks_{family}.json', '--pool', pool, '--out', ev/f'{model}_{family}',
                            '--workers', a.workers, '--start', start]
                        if mode == 'on':
                            command.append('--fast')
                        D.run(command, ev/f'{model}_{family}.log')
        report(out, census_report)
    finally:
        for run in runs:
            source = RUN_ROOT/run
            if source.is_dir():
                shutil.copytree(source, out/'training_logs'/run, dirs_exist_ok=True)


def main(argv=None):
    a = parse_args(argv)
    if a.plan_only:
        print(json.dumps(plan(a), indent=2))
        return
    if (a.out/'DONE').exists():
        raise FileExistsError(f'output already completed: {a.out}')
    # Shell owns DONE for install/gate/signals; direct invocation also reports failures.
    try:
        execute(a)
    except BaseException as exc:
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out/'SUMMARY.txt').write_text(f'VERDICT: Failed; no result established. Nothing deployed.\n{type(exc).__name__}: {exc}\n')
        (a.out/'DONE').write_text('exit_code=1\n')
        raise
    (a.out/'DONE').write_text('exit_code=0\n')


if __name__ == '__main__':
    main()
