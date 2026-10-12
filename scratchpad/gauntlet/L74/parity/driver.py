"""Isolated SIM worker + offline cohort/report CLI. No network or live control."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity.core import Tracks, compare, mean, ps, rank, select

RUNTIMES = {'old': ('20261006-linux', '0.1.17'), 'new': ('20261012-linux', '0.1.33'), 'fork': ('fork', None)}


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n', encoding='utf8')


def snapshot(sim, battle, native, names, side):
    state = json.loads(battle.state_json())
    fields = list(sim.ENTITY_FIELDS)
    required = {'uid', 'team', 'card_id', 'x', 'y', 'hp', 'max_hp', 'status_flags'}
    if not required <= set(fields):
        raise ValueError('unsupported_entity_layout')
    bodies = []
    for row in state['entities']:
        if len(row) != len(fields):
            raise ValueError('entity_layout_length_mismatch')
        e = dict(zip(fields, row))
        cid = e['card_id']
        # Direct PyO3 JSON uses -1; RoyaleGym's typed decoder remaps to EMPTY_CARD.
        tower = cid == -1
        public = -1
        if not tower:
            if not 0 <= cid < len(names):
                raise ValueError('unmapped_sim_card_id:' + str(cid))
            c = native.get(names[cid])
            if c is None:
                raise ValueError('unmapped_sim_entity:' + names[cid])
            form = 2 if e['status_flags'] & 16 else 1 if e['status_flags'] & 8 else 0
            public = c.get(('card_id', 'evolution_form_id', 'hero_form_id')[form])
            if c['display_name'] == 'IceWizard' and form == 2:
                public = 203000023  # same public alias phase_stats.load_catalog uses
            if public is None:
                raise ValueError('unmapped_sim_form:' + names[cid]+':'+str(form))
        b = dict(key=str(e['uid']), card_id=public, side=e['team'], x=e['x']/18, y=e['y']/18,
                 hp=e['hp'], max_hp=e['max_hp'], tower=tower)
        if tower and not ps.is_tower(b):
            raise ValueError('unmapped_sim_tower_geometry')
        bodies.append(b)
    own = next(p for p in state['players'] if p['team'] == side)
    return state, bodies, own['elixir_milli']/1000


def drive(source, runtime):
    # Environment set BEFORE importing any engine; process never switches runtimes.
    os.environ['ROYALE_RUNTIME'] = RUNTIMES[runtime][0]
    from pipeline.royale_runtime import activate, RUNTIME
    stamp = activate()
    from importlib.metadata import distributions
    versions = {d.metadata['Name'].lower(): d.version for d in distributions(path=[str(RUNTIME)])
                if d.metadata['Name'].lower() in ('royalesim', 'royalegym')}
    if RUNTIMES[runtime][1] and versions.get('royalesim') != RUNTIMES[runtime][1]:
        raise ValueError('wrong_runtime_version:' + str(versions))
    import royalesim as sim
    # This is the actual public corpus deal solver, not copied cycle inference.
    from research.sandbox_tools.replay_drive import infer_deals
    catalog, native = ps.load_catalog()
    opts = {} if runtime == 'old' else {'calibration_overrides': {'cards.CARD_TABLE': json.dumps('client160402017_20261006')}}
    battle = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], **opts)
    cat = json.loads(battle.catalogue_json())
    names = [dict(zip(sim.CATALOGUE_FIELDS, row))['name'] for row in cat]
    ids = {name: i for i, name in enumerate(names)}
    decks, forms, levels, choices = [], [], [], []
    for side in (0, 1):
        items = source['decks'][str(side)]
        byid = {ids[c['name']]: c for c in items}
        sequence = [ids[p['name']] for p in source['plays'] if p['side'] == side]
        deals = infer_deals(sequence, list(byid))
        if not deals:
            raise ValueError('no_public_sequence_consistent_deal_side_'+str(side))
        order = list(deals[0][0] + deals[0][1])
        choices.append(len(deals)); decks.append(order)
        forms.append([byid[i]['form'] for i in order]); levels.append([byid[i]['level'] for i in order])
    # Same requested levels in every arm; never silently downgrade an unsupported form.
    battle.reset(424242, decks, 0, 0, None, None, [], forms=forms,
                 levels=levels, tower_levels=source['tower_levels'])
    live_tracks, sim_tracks = Tracks(), Tracks()
    plays = source['plays']; cursor = 0; commands = []; samples = []; divergence = None
    last_sample_commands = 0
    for frame in source['frames']:
        tick = frame['tick']
        while cursor < len(plays) and plays[cursor]['tick'] <= tick:
            p = plays[cursor]; cursor += 1
            raw = json.loads(battle.state_json())
            if raw['tick'] < p['tick']:
                battle.step([], p['tick']-raw['tick'])
            raw = json.loads(battle.state_json())
            if raw['tick'] != p['tick']:
                commands.append(dict(p, accepted=False, reason='terminal_before_play')); continue
            player = next(q for q in raw['players'] if q['team'] == p['side'])
            cid = ids[p['name']]
            if cid not in player['hand']:
                commands.append(dict(p, accepted=False, reason='not_in_hand')); continue
            result = battle.step([(p['side'], player['hand'].index(cid), round(p['x']*18), round(p['y']*18))], 0)[0]
            reason = sim.DEPLOY_REASONS[result[1]]
            commands.append(dict(p, accepted=reason == 'OK', reason=reason, engine_tick=result[2],
                                 resolved_xy=[result[3]/18, result[4]/18]))
        raw = json.loads(battle.state_json())
        if raw['tick'] < tick:
            battle.step([], tick-raw['tick'])
        state, bodies, own_elixir = snapshot(sim, battle, native, names, source['observer_side'])
        if state['tick'] != tick:
            samples.append(dict(match=source['match'], tick=tick, rows=[], unavailable='sim_terminated',
                                sim_tick=state['tick']))
            if divergence is None: divergence = tick
            continue
        live = live_tracks.assign(tick, frame['bodies']); predicted = sim_tracks.assign(tick, bodies)
        rows = compare(live, predicted)
        recent = [p for p in plays if tick-100 <= p['tick'] <= tick]
        rejected = sum(not p['accepted'] for p in commands[last_sample_commands:])
        last_sample_commands = len(commands)
        elixir = abs(own_elixir-frame['own_elixir']) if frame['own_elixir'] is not None else None
        if divergence is None and (any(r['mismatch'] for r in rows) or rejected):
            divergence = tick
        samples.append(dict(match=source['match'], tick=tick, rows=rows, recent_plays=recent,
                            own_elixir_error=elixir, command_rejections=rejected))
    return dict(match=source['match'], runtime=runtime, stamp=stamp, versions=versions,
                quality=source['quality'], deal_candidates=choices, commands=commands, samples=samples,
                undriven_after_last_snapshot=plays[cursor:],
                divergence_tick=divergence, divergence_seconds=divergence/20 if divergence is not None else None,
                divergence_since_first_observation_seconds=(divergence-source['frames'][0]['tick'])/20 if divergence is not None else None,
                first_rejected_command_tick=min((p['tick'] for p in commands if not p['accepted']), default=None),
                status='EXPLORATORY_RECONSTRUCTION', source_sha256=source['sha256'])


def summarize(cohort, results, runtimes):
    catalog, _ = ps.load_catalog()
    reports = {r: [] for r in runtimes}; failures = []
    for result in results:
        if result.get('error'):
            failures.append(result)
        else:
            reports[result['runtime']].append(result)
    sets = [set(r['match'] for r in reports[rt]) for rt in runtimes]
    paired = sorted(set.intersection(*sets)) if sets else []
    out = dict(status='EXPLORATORY_ONLY' if paired else 'NO_PAIRED_MEASUREMENTS', selected=len(cohort),
               runtimes={}, paired_matches=paired, failures=failures,
               thresholds=dict(position_tiles=0.5, hp=1, own_elixir=0.1),
               attribution='Temporal/card association; not a causal mechanic diagnosis')
    for rt, rows in reports.items():
        samples = [s for r in rows if r['match'] in paired for s in r['samples']]
        bodies = [b for s in samples for b in s['rows']]
        paired_rows = [r for r in rows if r['match'] in paired]
        out['runtimes'][rt] = dict(completed=len(rows), paired=len(paired_rows), ticks=len(samples),
            unavailable_ticks=sum('unavailable' in s for s in samples),
            unit_position_mae_tiles=mean(b['position_error_tiles'] for b in bodies if not b['tower']),
            unit_hp_mae=mean(b['hp_error'] for b in bodies if not b['tower']),
            tower_hp_mae=mean(b['hp_error'] for b in bodies if b['tower']),
            unmatched_bodies=sum(b['missing'] is not None for b in bodies if not b['tower']),
            matched_unit_observations=sum(b['missing'] is None for b in bodies if not b['tower']),
            unmatched_towers=sum(b['missing'] is not None for b in bodies if b['tower']),
            mean_divergence_seconds=mean(r['divergence_seconds'] for r in paired_rows),
            undiverged_matches=sum(r['divergence_tick'] is None for r in paired_rows),
            own_elixir_mae=mean(s.get('own_elixir_error') for s in samples),
            command_rejections=sum(not p['accepted'] for r in paired_rows for p in r['commands']),
            ranking=rank([s for s in samples if 'unavailable' not in s], catalog))
    return out


def text_report(report):
    lines = [report['status'], f"Selected: {report['selected']}; paired completed: {len(report['paired_matches'])}",
             'All metrics use the SAME completed matches across requested runtimes.',
             'runtime | completed | unit tiles MAE | unit HP MAE | tower HP MAE | unmatched units | divergence s']
    for rt, r in report['runtimes'].items():
        lines.append(' | '.join(str(v) for v in (rt, r['completed'], r['unit_position_mae_tiles'], r['unit_hp_mae'],
                     r['tower_hp_mae'], r['unmatched_bodies'], r['mean_divergence_seconds'])))
        for item in r['ranking'][:15]:
            lines.append(f"  {item['group']}: impact={item['impact']:.2f}; frequency={item['frequency']}/{item['exposures']}; "
                         f"unit HP={item['mean_unit_hp_error']}; associated tower HP={item['mean_tower_hp_error']}")
    lines += [f"Failed/blocked jobs: {len(report['failures'])}",
              'Not causal attribution: target switches, pulls, knockback and damage sources are not recorded.',
              'Levels may be assumed; enemy spells, opening state, hidden deal and unplayed deck slots are incomplete.',
              'See selection.json, summary.json and per-match results for coverage, assumptions and rejection receipts.']
    return '\n'.join(lines)+'\n'


def worker_job(python, runtime, source, dest):
    env = dict(os.environ, ROYALE_RUNTIME=RUNTIMES[runtime][0], PYTHONDONTWRITEBYTECODE='1',
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', PYTHONNOUSERSITE='1')
    cmd = [str(python), str(HERE/'driver.py'), 'worker', '--runtime', runtime, '--source', str(source), '--out', str(dest)]
    try:
        with dest.with_suffix('.log').open('w', encoding='utf8') as log:
            done = subprocess.run(cmd, env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        if dest.is_file():
            result = json.loads(dest.read_text(encoding='utf8'))
            if done.returncode and not result.get('error'):
                raise RuntimeError(f'worker_exit_{done.returncode}')
            return result
        raise RuntimeError(f'worker_exit_{done.returncode}')
    except (subprocess.TimeoutExpired, RuntimeError) as e:
        return dict(match=source.stem, runtime=runtime, error=str(e))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['select', 'run', 'worker'])
    ap.add_argument('--runtime', nargs='+', choices=list(RUNTIMES), default=list(RUNTIMES))
    ap.add_argument('--source', type=Path)
    ap.add_argument('--cohort', type=Path, help='Reuse a prior sanitized sources directory exactly; no live re-selection')
    ap.add_argument('--live', type=Path, default=ps.LIVE)
    ap.add_argument('--since', default='20261008')
    ap.add_argument('--matches', type=int, default=100)
    ap.add_argument('--workers', type=int, default=24)
    ap.add_argument('--assume-level', type=int, choices=range(1, 17), help='Explicit exploratory uniform card/tower level; never measured from logs')
    ap.add_argument('--old-python', type=Path, default=Path('/workspace/venv/bin/python'))
    ap.add_argument('--new-python', type=Path, default=Path('/workspace/venv33/bin/python'))
    ap.add_argument('--fork-python', type=Path, default=Path('/workspace/venv33/bin/python'))
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if not 1 <= a.workers <= 24 or a.matches < 1:
        ap.error('workers must be 1..24; matches must be positive')
    if a.mode == 'worker':
        if len(a.runtime) != 1 or not a.source:
            ap.error('worker needs one runtime and --source')
        try:
            result = drive(json.loads(a.source.read_text(encoding='utf8')), a.runtime[0])
        except Exception as e:
            result = dict(match=a.source.stem, runtime=a.runtime[0], error=type(e).__name__+':'+str(e))
        write(a.out, result)
        return int(bool(result.get('error')))
    a.out.mkdir(parents=True, exist_ok=True)
    if (a.out/'selection.json').exists():
        ap.error('output already contains selection.json; choose a fresh directory')
    if a.cohort:
        cohort = [json.loads(p.read_text(encoding='utf8')) for p in sorted(a.cohort.glob('*.json'))]
        exclusions = []
        if a.assume_level is not None:
            ap.error('--cohort preserves its saved levels; do not also set --assume-level')
        if any(r['schema'] != 1 or Path(r['match']).name != r['match'] for r in cohort):
            ap.error('invalid saved cohort')
    else:
        cohort, exclusions = select(a.live, a.since, a.matches, a.assume_level)
    sources = a.out/'sources'; sources.mkdir()
    for row in cohort: write(sources/(row['match']+'.json'), row)
    selection = dict(selected=len(cohort), requested=a.matches if not a.cohort else len(cohort), since=a.since,
                     frozen_cohort=str(a.cohort) if a.cohort else None,
                     source_hashes={r['match']:hashlib.sha256((sources/(r['match']+'.json')).read_bytes()).hexdigest() for r in cohort},
                     harness_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'core.py', HERE/'driver.py')},
                     exclusions=exclusions, matches=[{k:r[k] for k in ('match', 'sha256', 'quality', 'blocks')} for r in cohort])
    write(a.out/'selection.json', selection)
    if not cohort: raise RuntimeError('No eligible phase_stats matches')
    if a.mode == 'select':
        print(f"PARITY_SELECTED {len(cohort)}; reconstructable={sum(not r['blocks'] for r in cohort)}")
        return 0
    results = []; jobs = []; started = time.monotonic()
    for rt in a.runtime:
        folder = a.out/rt; folder.mkdir()
        for row in cohort:
            if row['blocks']:
                result = dict(match=row['match'], runtime=rt, error=';'.join(row['blocks']))
                write(folder/(row['match']+'.json'), result); results.append(result)
            else:
                jobs.append((getattr(a,rt+'_python'), rt, sources/(row['match']+'.json'), folder/(row['match']+'.json')))
    print(f'Jobs={len(jobs)}, workers={a.workers}; unbenchmarked estimate 5-30 min for 300 jobs, excluding build/lock wait.', flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = [pool.submit(worker_job, *job) for job in jobs]
        for n, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if n % a.workers == 0 or n == len(jobs):
                elapsed = time.monotonic()-started
                print(f'{n}/{len(jobs)} completed; elapsed {elapsed:.1f}s; observed ETA {elapsed/n*(len(jobs)-n):.1f}s', flush=True)
    report = summarize(cohort, results, a.runtime)
    report['seconds'] = time.monotonic()-started
    write(a.out/'summary.json', report)
    (a.out/'SUMMARY.txt').write_text(text_report(report), encoding='utf8')
    return 0 if report['paired_matches'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
