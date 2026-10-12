"""Prepare or run LIVECAL. Default SIM = requested S2/CAL bundle, fast per log.

Era settings are retained as audit strata, not passed blindly to the SIM. Identical
checkpoint/fast arms share one SIM run; all era counts remain in the frozen truth.
No network, live scripts, forced-spend rules, training or deployment.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import numpy as np
from live_truth import HERE, ROOT, digest, wilson

BACKUP = Path('C:/Users/benpe/pod_backup_weekend/pod3/x_ADAPT/wk_adapt')
GEN = 'icebow/data/pipeline/gen_v1_s0/gen_s0.pt'
E4 = 'icebow/data/bench/rl_royale/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt'
CENSUS = dict(evo='scratchpad/gauntlet/L70/pool_forms/loadable_decks.json',
              lad='scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json')
RUNTIME_FILES = ['pipeline/'+name+'.py' for name in (
    'search_s0', 'e1_eval', 'royale_env', 'rl_royale', 'decision_options', 'obs_contract',
    'public_observation', 'extrapolate', 'model_gen', 'dataset_gen')]
RUNTIME_FILES += ['scratchpad/gauntlet/L70/abilities/ability_policy.py',
                  'scratchpad/gauntlet/L70/abilities/ability_models_v2.json']
LIVE = dict(xbow_class='class_sample', xbow_class_floor=.3, tau_phase=[.35, .45, .55],
            spell_aim='rocket_area', gate_decode='hazard_below_tau', gate_hazard_min_elixir=9,
            log_aim='log_barrel', lethal_rocket='ot_behind', xbow_dead_lane='block',
            gate_hazard_threatened=2, rocket_dead_target='block', tau_threatened=.2, lethal_log='on')
LV = [arg for k, v in LIVE.items() for arg in ['--'+k.replace('_', '-'), *map(str, v if isinstance(v, list) else [v])]]


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf8')


def collapse_groups(truth):
    """One vote per checkpoint+fast arm, not one vote for each configuration-era split."""
    groups = {}
    for g in truth['groups']:
        if not g['checkpoint_verified']:
            raise ValueError(f"missing or changed live checkpoint: {g['checkpoint']}")
        key = (g['checkpoint'], g['checkpoint_sha256'], g['fast'])
        if key not in groups:
            groups[key] = dict(id=f"g{len(groups):02d}", checkpoint=g['checkpoint'],
                               checkpoint_sha256=g['checkpoint_sha256'], family=g['family'], fast=g['fast'],
                               n=0, wins=0, losses=0, draws=0, eras=[])
        out = groups[key]
        for field in ('n', 'wins', 'losses', 'draws'):
            out[field] += g[field]
        recorded = g['settings'].get('decision_options') or {}
        mismatches = {k: {'live': recorded.get(k, 'not recorded'), 'sim': v}
                      for k, v in LIVE.items() if recorded.get(k) != v}
        extra = {k: v for k, v in recorded.items() if k not in LIVE}
        out['eras'].append(dict(id=g['id'], era=g['era'], n=g['n'], wins=g['wins'], losses=g['losses'], draws=g['draws'], mismatches=mismatches,
                                 other_live_decision_options=extra, live_settings=g['settings']))
    for g in groups.values():
        g['win_rate'] = g['wins']/g['n']
        g['ci95'] = wilson(g['wins'], g['n'])
        g['reportable'] = g['n'] >= truth['min_n']
    return list(groups.values())


def prepare(truth_path, out, backup=BACKUP, root=ROOT):
    from census import weighted
    out.mkdir(parents=True, exist_ok=True)
    truth = json.loads(truth_path.read_text(encoding='utf8'))
    groups = collapse_groups(truth)
    files = {}
    def need(rel, source=None):
        source = Path(source or root/rel)
        if not source.is_file():
            raise FileNotFoundError(source)
        files[rel] = dict(path=rel, source=str(source), bytes=source.stat().st_size, sha256=digest(source))
        return rel
    for f in truth['files']:
        if f['exists']:
            rel = need(f['path'])
            if files[rel]['sha256'] != f['sha256']:
                raise ValueError(f'checkpoint changed since truth scan: {rel}')
    need(GEN)
    pools = [dict(id='P1', members=[dict(path=E4, temperature=.1)]),
             dict(id='P2', members=[dict(path=GEN, temperature=.3)]),
             dict(id='P3', members=[dict(path=GEN, temperature=1.)])]
    league = []
    for role in ('main', 'exp1', 'exp2', 'exp3'):
        rel = f'icebow/data/bench/rl_royale/wk_adapt_{role}/wk_adapt_{role}_latest.pt'
        source = backup/rel
        if source.is_file():
            league.append(dict(path=need(rel, source), temperature=.3))
    if league and len(league) != 4:
        raise ValueError('partial ADAPT pool: require main and all three exploiters')
    if league:
        pools.append(dict(id='P4', members=league))
    pools.append(dict(id='P5', members=[dict(path=GEN, temperature=.3), dict(path=E4, temperature=.1)]))
    census_files = {}
    for name, rel in CENSUS.items():
        dest = out/f'census_{name}.json'
        dump(dest, weighted(json.loads((root/rel).read_text())))
        census_files[name] = dict(path=dest.name, sha256=digest(dest), source=rel, source_sha256=digest(root/rel))
    manifest = dict(schema=1, truth_sha256=digest(truth_path), groups=groups, pools=pools,
                    files=list(files.values()), censuses=census_files,
                    runtime_files=[dict(path=rel, bytes=(root/rel).stat().st_size, sha256=digest(root/rel))
                                   for rel in RUNTIME_FILES],
                    p4_note='uniform main + three final exploiters, T=.3 (temperature fixed by experiment)' if league else 'unavailable; P4 omitted',
                    protocol='S2/CAL bundle + recorded pipeline_decisions. Distinct eras audited; pooled per checkpoint/fast for scoring.',
                    assumptions=['S2/CAL tau .35, own effects, forms deck, hero abilities v2; no anti-stall.',
                                 'SIM fixed 26-tick action delay and extrapolation; device timing/identity/emotes not modeled.',
                                 'Later live Rocket/Tornado, Log-air, card-level and follow-up options are outside S2/CAL.',
                                 'Earlier era decision differences and historical anti-leak are standardized to S2/CAL, not reproduced.',
                                 'No claim of exact live execution parity. Era-specific truth is in truth.json.'])
    dump(out/'manifest.json', manifest)
    lines = ['Source -> pod repo-relative destination | bytes | SHA256']
    lines += [f"{f['source']} -> {f['path']} | {f['bytes']} | {f['sha256']}" for f in files.values()]
    lines.append(f"Total checkpoint bytes: {sum(f['bytes'] for f in files.values())}")
    lines += ['', 'Also copy the new livecal directory and use the existing full repo + installed Royale runtime.',
              'Pinned runtime support files (repo-relative path | bytes | SHA256):']
    lines += [f"{f['path']} | {f['bytes']} | {f['sha256']}" for f in manifest['runtime_files']]
    (out/'NEEDED_FILES.txt').write_text('\n'.join(lines)+'\n', encoding='utf8')
    return manifest


def schedule(manifest, k=480, seed_start=740000, pools=None):
    if k < 4 or k % 4:
        raise ValueError('K must be a positive multiple of four (two censuses, two sides)')
    plan = {**manifest, 'k': k, 'seed_start': seed_start, 'jobs': []}
    for pool in manifest['pools']:
        for census in ('evo', 'lad'):
            rng = np.random.default_rng([74012, int(pool['id'][1:]), census == 'lad'])
            count = k//2
            if pool['id'] == 'P5':
                # Exact 50/50 overall, balanced within side to within one game; randomized, shared across checkpoints.
                pick = np.zeros(count, dtype=int)
                for parity in (0, 1):
                    ix = np.arange(parity, count, 2)
                    values = np.array([(i+parity) % 2 for i in range(len(ix))])
                    rng.shuffle(values)
                    pick[ix] = values
            else:
                pick = rng.integers(len(pool['members']), size=count)
            for g in manifest['groups']:
                for mi, member in enumerate(pool['members']):
                    seeds = [seed_start+i for i in range(count) if pick[i] == mi]
                    for start in range(0, len(seeds), 12):
                        plan['jobs'].append(dict(group=g['id'], checkpoint=g['checkpoint'], fast=g['fast'],
                                                 pool=pool['id'], census=census, opponent=member,
                                                 seeds=seeds[start:start+12]))
    plan['games'] = len(manifest['groups'])*len(manifest['pools'])*k
    plan['eta_hours_28_procs'] = plan['games']/47/60
    if pools is not None:
        selected = [p.strip() for p in pools.split(',')] if isinstance(pools, str) else list(pools)
        available = {p['id'] for p in manifest['pools']}
        if not selected or len(set(selected)) != len(selected) or set(selected) - available:
            raise ValueError(f'pools must be distinct available IDs: {", ".join(sorted(available))}')
        # Filter only after the full schedule is built. Never renumber groups or redraw assignments.
        plan['all_pools'] = manifest['pools']
        plan['pools'] = [p for p in manifest['pools'] if p['id'] in selected]
        plan['jobs'] = [j for j in plan['jobs'] if j['pool'] in selected]
        plan['games'] = sum(len(j['seeds']) for j in plan['jobs'])
        plan['eta_hours_28_procs'] = plan['games']/47/60
    return plan


def command(job, census, out, python=sys.executable):
    cmd = [python, str(HERE/'livecal.py'), '--worker', '--out', str(out), '--seeds', ','.join(map(str, job['seeds'])),
           '--opps', 'gen', '--arms', 'plain', '--gen', job['checkpoint'], '--opp-gen', job['opponent']['path'],
           '--s1', GEN,  # search_s0 hashes this unused argument even with --opps gen; no S1 file needed.
           '--forms-mode', 'deck', '--device', 'cpu', '--workers', '1', '--threads', '1', '--tail-cap', '7200',
           '--tau-plain', '.35', '--census', str(census), '--hero-abilities', '--ability-policy', 'v2',
           '--opp-policy', 'sample', '--opp-T', str(job['opponent']['temperature']), '--own-effects', *LV]
    if job['fast']:
        cmd += ['--pipeline-decisions', '--pipeline-tau-delta', '0']
    return cmd


def validate_files(manifest, root, directory):
    for f in manifest['files'] + manifest.get('runtime_files', []):
        p = root/f['path']
        if not p.is_file() or p.stat().st_size != f['bytes'] or digest(p) != f['sha256']:
            raise ValueError(f"missing or hash-mismatched input: {p}")
    for c in manifest['censuses'].values():
        if digest(directory/c['path']) != c['sha256']:
            raise ValueError('weighted census changed')


def run(plan, directory, out, workers, root=ROOT):
    if not 1 <= workers <= 28:
        raise ValueError('workers must be between 1 and 28')
    validate_files(plan, root, directory)
    (out/'chunks').mkdir()
    file_hashes = {f['path']: f['sha256'] for f in plan['files']}
    env = dict(os.environ, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    def one(item):
        i, job = item
        dest = out/'chunks'/f'{i:05d}'
        cmd = command(job, directory/plan['censuses'][job['census']]['path'], dest)
        with dest.with_suffix('.log').open('w', encoding='utf8') as log:
            subprocess.run(cmd, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        receipt = json.loads((dest/'run.json').read_text())
        if (receipt['gen_sha256'] != file_hashes[job['checkpoint']] or
                receipt['opp_gen_sha256'] != file_hashes[job['opponent']['path']] or
                bool(receipt.get('pipeline_decisions')) != job['fast']):
            raise ValueError(f'checkpoint/fast receipt mismatch in {dest}')
        rows = [json.loads(s) for s in (dest/'matches.jsonl').read_text().splitlines()]
        if sorted(r['seed'] for r in rows) != sorted(job['seeds']):
            raise ValueError(f'wrong seeds in {dest}')
        for r in rows:
            if r['arm'] != 'plain' or r.get('searched') != 0:
                raise ValueError('search/hidden-state rollout is forbidden')
            if r['opp_gen_sha256'] != file_hashes[job['opponent']['path']]:
                raise ValueError('opponent receipt mismatch')
            r.update(group=job['group'], pool=job['pool'], census=job['census'])
        return rows
    paired = {}
    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        with (out/'matches.jsonl').open('w', encoding='utf8') as f:
            for i, rows in enumerate(executor.map(one, enumerate(plan['jobs']))):
                for r in rows:
                    key = r['pool'], r['census'], r['seed']
                    design = (r['opp_gen_sha256'], r['opp_deck'], r['learner_side'])
                    if key in paired and paired[key] != design:
                        raise ValueError(f'common random number design mismatch at {key}')
                    paired[key] = design
                    f.write(json.dumps(r)+'\n')
                f.flush()
                if i % 20 == 0:
                    print(f"completed {i+1}/{len(plan['jobs'])} chunks", flush=True)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def worker():
    sys.path.insert(0, str(ROOT))
    from pipeline import search_s0 as S
    original = S.live_cfg
    def no_stall(*args, **kwargs):
        cfg = original(*args, **kwargs)
        cfg['stall_elixir'] = None
        assert cfg['opp_elixir'] == 'counter'
        return cfg
    S.live_cfg = no_stall
    args = sys.argv[2:]
    if args[args.index('--arms')+1] != 'plain' or args[args.index('--workers')+1] != '1':
        raise ValueError('only a single plain-policy worker is permitted')
    return S.main(args)


def merge(directories):
    """Read copied plans/results, with no checkpoint files or SIM runtime required.

    A failed/interrupted part can contribute finished arms from its flushed matches.
    Identical overlap is a set union; contradictory observations fail closed.
    """
    from score import indexed_results
    combined, reference, full = {}, None, None
    derived = {'k', 'seed_start', 'jobs', 'games', 'eta_hours_28_procs', 'all_pools'}
    for directory in directories:
        directory = Path(directory)
        part = json.loads((directory/'plan.json').read_text(encoding='utf8'))
        manifest = {k: v for k, v in part.items() if k not in derived}
        manifest['pools'] = part.get('all_pools', part['pools'])
        contract = (manifest, part['k'], part['seed_start'])
        if reference is not None and contract != reference:
            raise ValueError(f'incompatible experiment plans: {directory}')
        reference = contract
        full = schedule(manifest, part['k'], part['seed_start'])
        selected = [p['id'] for p in part['pools']] if 'all_pools' in part else None
        if part != schedule(manifest, part['k'], part['seed_start'], pools=selected):
            raise ValueError(f'changed or invalid schedule: {directory}')
        path = directory/'matches.jsonl'
        rows = [json.loads(s) for s in path.read_text(encoding='utf8').splitlines() if s.strip()] if path.exists() else []
        indexed_results(part, rows)  # Reject duplicates, unexpected seeds, and invalid outcomes within a part.
        hashes = {f['path']: f['sha256'] for f in part['files']}
        expected = {(j['pool'], j['group'], j['census'], s): j for j in part['jobs'] for s in j['seeds']}
        for row in rows:
            key = row['pool'], row['group'], row['census'], row['seed']
            job = expected[key]
            if (row.get('arm') != 'plain' or row.get('searched') != 0 or
                    row.get('opp_gen_sha256') != hashes[job['opponent']['path']]):
                raise ValueError(f'policy/opponent receipt mismatch: {key}')
            if key in combined and combined[key] != row:
                raise ValueError(f'conflicting result: {key}')
            combined[key] = row
    if full is None:
        raise ValueError('merge requires at least one result directory')
    paired = {}
    for key, row in combined.items():
        pair = row['pool'], row['census'], row['seed']
        design = row['opp_gen_sha256'], row['opp_deck'], row['learner_side']
        if pair in paired and paired[pair] != design:
            raise ValueError(f'common random number design mismatch at {key}')
        paired[pair] = design
    return full, [combined[key] for key in sorted(combined)]


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        return worker()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--truth', type=Path, default=HERE/'truth.json')
    ap.add_argument('--manifest', type=Path, default=HERE/'manifest.json')
    ap.add_argument('--backup', type=Path, default=BACKUP)
    ap.add_argument('--out', type=Path, default=Path('/workspace/results/LIVECAL'))
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--k', type=int)
    ap.add_argument('--workers', type=int, default=28)
    ap.add_argument('--bootstrap', type=int, default=2000)
    ap.add_argument('--plan-only', action='store_true')
    ap.add_argument('--pools', help='comma-separated pool IDs; default: every available pool')
    ap.add_argument('--merge', nargs='+', type=Path, help='score the union of copied result directories, without SIM')
    a = ap.parse_args()
    if a.merge and (a.prepare or a.pools is not None or a.quick or a.k is not None or a.plan_only):
        ap.error('--merge uses the saved plans; cannot combine with --prepare, --pools, --quick, --k or --plan-only')
    if a.prepare and a.pools is not None:
        ap.error('--pools selects run jobs, not preparation inputs')
    if a.prepare:
        m = prepare(a.truth, a.manifest.parent, a.backup)
        print(f"prepared {len(m['groups'])} arms, {len(m['pools'])} pools; {m['p4_note']}")
        return 0
    a.out.mkdir(parents=True, exist_ok=True)
    # Refuse reuse, so a failed/reconfigured run cannot inherit old success or append duplicates.
    if any((a.out/name).exists() for name in ('DONE', 'plan.json', 'chunks')):
        raise ValueError('output already used; choose a fresh --out directory')
    rc = 1
    try:
        if not 1 <= a.workers <= 28:
            raise ValueError('workers must be between 1 and 28')
        if a.merge:
            plan, rows = merge(a.merge)
        else:
            manifest = json.loads(a.manifest.read_text(encoding='utf8'))
            plan = schedule(manifest, a.k if a.k is not None else 120 if a.quick else 480, pools=a.pools)
        dump(a.out/'plan.json', plan)
        if a.plan_only:
            rate = 47*a.workers/28
            (a.out/'SUMMARY.txt').write_text(f"PLAN ONLY: no pool ranked; {plan['games']} games, about {plan['games']/rate/60:.2f} hours at {rate:.2f} games/min ({a.workers} workers).\n", encoding='utf8')
        else:
            from score import evaluate, evaluate_finished, summary
            if a.merge:
                with (a.out/'matches.jsonl').open('w', encoding='utf8') as f:
                    for row in rows:
                        f.write(json.dumps(row)+'\n')
                report = evaluate_finished(plan, rows, a.bootstrap)
            else:
                run(plan, a.manifest.parent.resolve(), a.out.resolve(), a.workers)
                rows = [json.loads(s) for s in (a.out/'matches.jsonl').read_text().splitlines()]
                report = evaluate(plan, rows, a.bootstrap)
            dump(a.out/'score.json', report)
            note = ''
            if 'all_pools' in plan and len(plan['pools']) < len(plan['all_pools']):
                note = '\nPART ONLY: ranked selected pools; merge all parts for the full experiment.\n'
            (a.out/'SUMMARY.txt').write_text(summary(report)+note, encoding='utf8')
            if report.get('missing_arms'):
                return 1  # finally writes DONE with the initial nonzero rc.
        rc = 0
    except Exception as exc:
        (a.out/'SUMMARY.txt').write_text(f"FAILED: no pool can be named. {type(exc).__name__}: {exc}\nSee driver.log and chunks/*.log. No deployment.\n", encoding='utf8')
        traceback.print_exc()
    finally:
        (a.out/'DONE').write_text(f'exit_code={rc}\n', encoding='utf8')
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
