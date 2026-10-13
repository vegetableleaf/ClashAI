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
from scratchpad.gauntlet.L74.parity.core import SwarmPairing, Tracks, compare, mean, ps, rank, select
from scratchpad.gauntlet.L74.parity.planning import hydrate, plan, planning_report, OLD_HERO_REASON

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


def drive(source, runtime, mechanics_replay=False, fix_artefacts=False, own_timing='tap', pair_swarms=False):
    if fix_artefacts and not mechanics_replay:
        raise ValueError('artefact_fixes_require_mechanics_replay')
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
    if not mechanics_replay:
        from research.sandbox_tools.replay_drive import infer_deals
    catalog, native = ps.load_catalog()
    opts = {} if runtime == 'old' else {'calibration_overrides': {'cards.CARD_TABLE': json.dumps('client160402017_20261006')}}
    battle = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], **opts)
    cat = json.loads(battle.catalogue_json())
    names = [dict(zip(sim.CATALOGUE_FIELDS, row))['name'] for row in cat]
    ids = {name: i for i, name in enumerate(names)}
    replay_plan = plan(source, True, fix_artefacts, own_timing) if mechanics_replay else None
    if replay_plan and replay_plan['blocks']:
        raise ValueError(';'.join(replay_plan['blocks']))
    if runtime == 'old' and replay_plan and replay_plan['old_unsupported']:
        # Probe the known form limitation before resolving any opponent card.
        # An unrelated newer enemy card must not hide old's expected hero refusal.
        try:
            battle.reset(424242, [[ids['IceWizard']], []], 0, 0, None, None, [],
                         forms=[[2], []], levels=[[source['tower_levels'][0]], []],
                         tower_levels=source['tower_levels'])
        except ValueError as e:
            if 'IceWizard has no loadable hero form:' in str(e):
                return dict(match=source['match'], runtime=runtime, status='UNSUPPORTED_EXPECTED',
                            skip_reason=OLD_HERO_REASON, detail=str(e), stamp=stamp, versions=versions)
            raise
    decks, forms, levels, choices = [], [], [], []
    for side in (0, 1):
        items = (replay_plan['own_deck'] if side == source['observer_side'] else replay_plan['opponent_roster']) if replay_plan else source['decks'][str(side)]
        byid = {ids[c['name']]: c for c in items}
        if replay_plan:
            order = ([ids[n] for n in replay_plan['decisions'][0]['order']] if side == source['observer_side'] else list(byid))
            choices.append(None)
        else:
            sequence = [ids[p['name']] for p in source['plays'] if p['side'] == side]
            deals = infer_deals(sequence, list(byid))
            if not deals:
                raise ValueError('no_public_sequence_consistent_deal_side_'+str(side))
            order = list(deals[0][0] + deals[0][1]); choices.append(len(deals))
        decks.append(order)
        forms.append([byid[i]['form'] for i in order]); levels.append([byid[i]['level'] for i in order])
    # Same requested levels in every arm; never silently downgrade an unsupported form.
    try:
        battle.reset(424242, decks, 0, 0, None, None, [], forms=forms,
                     levels=levels, tower_levels=source['tower_levels'])
    except ValueError as e:
        if runtime == 'old' and 'IceWizard has no loadable hero form:' in str(e):
            return dict(match=source['match'], runtime=runtime, status='UNSUPPORTED_EXPECTED',
                        skip_reason=OLD_HERO_REASON, detail=str(e))
        raise
    adapter = None
    if replay_plan:
        from scratchpad.gauntlet.L74.parity.mechanics import SnapshotReplay
        adapter = SnapshotReplay(battle, sim, opts, replay_plan, ids, source['tower_levels'][0])
    decisions = replay_plan['decisions'] if replay_plan else []
    decision_cursor = 0
    def advance(target):
        nonlocal decision_cursor
        while decision_cursor < len(decisions) and decisions[decision_cursor]['tick'] <= target:
            dec = decisions[decision_cursor]; decision_cursor += 1
            now = json.loads(battle.state_json())['tick']
            if now < dec['tick']:
                battle.step([], dec['tick']-now)
            if json.loads(battle.state_json())['tick'] == dec['tick']:
                adapter.sync(source['observer_side'], dec['hand'], dec['queue'])
        now = json.loads(battle.state_json())['tick']
        if now < target:
            battle.step([], target-now)
    limits = None
    if fix_artefacts:
        from scratchpad.gauntlet.L74.parity.inference import role_limits
        limits = role_limits(source, catalog)
    live_tracks, sim_tracks = Tracks(limits), Tracks(limits)
    pairing = SwarmPairing() if pair_swarms else None
    plays = replay_plan['actions'] if replay_plan else source['plays']
    cursor = 0; commands = []; samples = []; divergence = None
    last_sample_commands = 0
    for frame in source['frames']:
        tick = frame['tick']
        while cursor < len(plays) and plays[cursor]['tick'] <= tick:
            p = plays[cursor]; cursor += 1
            advance(p['tick'])
            raw = json.loads(battle.state_json())
            if raw['tick'] != p['tick']:
                commands.append(dict(p, accepted=False, reason='terminal_before_play')); continue
            if adapter:
                slot = adapter.action(p)
            else:
                player = next(q for q in raw['players'] if q['team'] == p['side'])
                cid = ids[p['name']]
                if cid not in player['hand']:
                    commands.append(dict(p, accepted=False, reason='not_in_hand')); continue
                slot = player['hand'].index(cid)
            result = battle.step([(p['side'], slot, round(p['x']*18), round(p['y']*18))], 0)[0]
            reason = sim.DEPLOY_REASONS[result[1]]
            commands.append(dict(p, accepted=reason == 'OK', reason=reason, engine_tick=result[2],
                                 resolved_xy=[result[3]/18, result[4]/18]))
        advance(tick)
        state, bodies, own_elixir = snapshot(sim, battle, native, names, source['observer_side'])
        if state['tick'] != tick:
            samples.append(dict(match=source['match'], tick=tick, rows=[], unavailable='sim_terminated',
                                sim_tick=state['tick']))
            if divergence is None: divergence = tick
            continue
        live = live_tracks.assign(tick, frame['bodies']); predicted = sim_tracks.assign(tick, bodies)
        if pairing:
            predicted = pairing.apply(live, predicted, live_tracks.births, sim_tracks.births)
        rows = compare(live, predicted)
        if fix_artefacts:
            # Preserve paired raw public values for the next triage. V2 stored
            # only absolute errors, losing damage signs and subtype evidence.
            for row in rows:
                for label, lookup in [('live', live), ('sim', predicted)]:
                    b = lookup.get(row['identity'])
                    row[label] = ({k: b[k] for k in ('x','y','hp','max_hp','card_id','side')}
                                  if b is not None else None)
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
                status='EXPLORATORY_MECHANICS' if adapter else 'EXPLORATORY_RECONSTRUCTION',
                replay_mode='mechanics' if adapter else 'strict_deal',
                artefact_fixes=fix_artefacts, own_timing=own_timing, pair_swarms=pair_swarms,
                inference_receipts=replay_plan.get('inference_receipts', []) if replay_plan else [],
                planning_counts=replay_plan['counts'] if replay_plan else None,
                planning_skips=replay_plan['skips'] if replay_plan else [], source_sha256=source['sha256'])


def metrics(rows, matches, common_ticks, catalog):
    paired_rows = [r for r in rows if r['match'] in matches]
    samples = [s for r in paired_rows for s in r['samples'] if s['tick'] in common_ticks[r['match']]]
    bodies = [b for s in samples for b in s['rows']]
    return dict(completed=len(rows), paired=len(paired_rows), ticks=len(samples),
        rows_used=len(bodies), matches_used=len(paired_rows),
        unavailable_ticks=sum('unavailable' in s for r in paired_rows for s in r['samples']),
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
        ranking=rank(samples, catalog))


def summarize(cohort, results, runtimes):
    catalog, _ = ps.load_catalog()
    reports = {rt: [] for rt in runtimes}; failures = []; skips = []
    by_key = {(r['runtime'], r['match']): r for r in results}
    for result in results:
        if result.get('error'):
            failures.append(result)
            skips.append(dict(match=result['match'], runtime=result['runtime'], kind='match', reason=result['error']))
        elif result.get('skip_reason'):
            for reason in result.get('skip_reasons', [result['skip_reason']]):
                skips.append(dict(match=result['match'], runtime=result['runtime'], kind='match',
                                  reason=reason, expected=result.get('status')=='UNSUPPORTED_EXPECTED'))
        else:
            reports[result['runtime']].append(result)
            skips.extend(dict(s, match=result['match'], runtime=result['runtime']) for s in result.get('planning_skips', []))
            for p in result.get('commands', []):
                if not p['accepted']:
                    skips.append(dict(match=result['match'], runtime=result['runtime'], kind='command',
                                      tick=p['tick'], reason=p['reason']))
            for p in result.get('undriven_after_last_snapshot', []):
                skips.append(dict(match=result['match'], runtime=result['runtime'], kind='command',
                                  tick=p['tick'], reason='after_last_snapshot'))
    groups = {'all_requested': (runtimes, None)}
    if set(('old', 'new', 'fork')) <= set(runtimes):
        fallback = {r['match'] for r in results if r['runtime']=='old' and
                    r.get('status')=='UNSUPPORTED_EXPECTED' and r.get('skip_reason')==OLD_HERO_REASON}
        groups['new_fork_unsupported_old'] = (['new', 'fork'], fallback)
    group_reports = {}; all_paired = set(); aggregate_ticks = {rt: {} for rt in runtimes}
    for group, (arms, allowed) in groups.items():
        sets = [set(r['match'] for r in reports[rt]) for rt in arms]
        candidates = set.intersection(*sets) if sets else set()
        if allowed is not None:
            candidates &= allowed
        common = {}
        for match in sorted(candidates):
            ticks = [{s['tick'] for s in by_key[(rt, match)]['samples'] if not s.get('unavailable') and s['rows']} for rt in arms]
            shared = set.intersection(*ticks)
            if shared:
                common[match] = shared
            else:
                skips.append(dict(match=match, group=group, kind='pair', reason='no_common_measurement_rows'))
            for rt in arms:
                for sample in by_key[(rt, match)]['samples']:
                    if sample['tick'] not in shared:
                        skips.append(dict(match=match, runtime=rt, group=group, kind='measurement',
                                          tick=sample['tick'], reason=sample.get('unavailable') or 'not_available_in_all_group_runtimes'))
        matches = sorted(common)
        all_paired.update(matches)
        for rt in arms:
            aggregate_ticks[rt].update(common)
        group_reports[group] = dict(arms=arms, matches=matches, matches_used=len(matches),
            decision_rows_used=sum(len(t) for t in common.values()),
            runtimes={rt: metrics(reports[rt], matches, common, catalog) for rt in arms})
    for source in cohort:
        match = source.get('match')
        if match is None:
            continue
        for rt in runtimes:
            if (rt, match) not in by_key:
                skips.append(dict(match=match, runtime=rt, kind='match', reason='missing_worker_result'))
        if match not in all_paired:
            skips.append(dict(match=match, kind='pair', reason='no_successful_comparison_group'))
            for rt in runtimes:
                result = by_key.get((rt, match), {})
                if 'samples' in result:
                    skips.append(dict(match=match, runtime=rt, kind='completed_match',
                                      reason='not_in_successful_comparison_group',
                                      decision_rows_skipped=len(result['samples']),
                                      body_rows_skipped=sum(len(s['rows']) for s in result['samples'])))
    out = dict(status='EXPLORATORY_ONLY' if all_paired else 'NO_PAIRED_MEASUREMENTS', selected=len(cohort),
               paired_matches=sorted(all_paired), matches_used=len(all_paired), failures=failures,
               skips=skips, skip_reasons=dict(Counter(s['reason'] for s in skips)),
               expected_unsupported_jobs=sum(r.get('status')=='UNSUPPORTED_EXPECTED' for r in results),
               comparison_groups=group_reports,
               thresholds=dict(position_tiles=0.5, hp=1, own_elixir=0.1),
               attribution='Temporal/card association; not a causal mechanic diagnosis')
    out['runtimes'] = {rt: metrics(rows, sorted(aggregate_ticks[rt]), aggregate_ticks[rt], catalog)
                       for rt, rows in reports.items()}
    return out


def text_report(report):
    lines = [report['status'], f"Selected: {report['selected']}; paired completed: {len(report['paired_matches'])}",
             'Compare within comparison_groups: each group uses identical matches AND available decision ticks.',
             'runtime | completed | unit tiles MAE | unit HP MAE | tower HP MAE | unmatched units | divergence s']
    for name, group in report['comparison_groups'].items():
        lines.append(f"Group {name}: {group['arms']}; matches={group['matches_used']}; decision rows={group['decision_rows_used']}")
        for rt, values in group['runtimes'].items():
            lines.append(f"  {rt}: body rows={values['rows_used']}; tower HP MAE={values['tower_hp_mae']}")
    for rt, r in report['runtimes'].items():
        lines.append(f"{rt}: matches used={r['matches_used']}; decision rows={r['ticks']}; body rows={r['rows_used']}")
        lines.append(' | '.join(str(v) for v in (rt, r['completed'], r['unit_position_mae_tiles'], r['unit_hp_mae'],
                     r['tower_hp_mae'], r['unmatched_bodies'], r['mean_divergence_seconds'])))
        for item in r['ranking'][:15]:
            lines.append(f"  {item['group']}: impact={item['impact']:.2f}; frequency={item['frequency']}/{item['exposures']}; "
                         f"unit HP={item['mean_unit_hp_error']}; associated tower HP={item['mean_tower_hp_error']}")
    lines += [f"Expected unsupported jobs: {report['expected_unsupported_jobs']}; skip counts: {report['skip_reasons']}",
              f"Failed jobs: {len(report['failures'])}",
              'Not causal attribution: target switches, pulls, knockback and damage sources are not recorded.',
              'Levels may be assumed; enemy spells, opening state, hidden deal and unplayed deck slots are incomplete.',
              'See selection.json, summary.json and per-match results for coverage, assumptions and rejection receipts.']
    return '\n'.join(lines)+'\n'


def worker_job(python, runtime, source, dest, mechanics_replay=False, fix_artefacts=False, own_timing='tap', pair_swarms=False):
    env = dict(os.environ, ROYALE_RUNTIME=RUNTIMES[runtime][0], PYTHONDONTWRITEBYTECODE='1',
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', PYTHONNOUSERSITE='1')
    cmd = [str(python), str(HERE/'driver.py'), 'worker', '--runtime', runtime, '--source', str(source), '--out', str(dest)]
    if mechanics_replay:
        cmd.append('--mechanics-replay')
    if fix_artefacts:
        cmd.append('--fix-artefacts')
    cmd += ['--own-timing', own_timing] + (['--pair-swarms-by-position'] if pair_swarms else [])
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
    ap.add_argument('mode', choices=['select', 'plan', 'run', 'worker'])
    ap.add_argument('--runtime', nargs='+', choices=list(RUNTIMES), default=list(RUNTIMES))
    ap.add_argument('--source', type=Path)
    ap.add_argument('--mechanics-replay', action='store_true', help='PARITY ONLY: logged own hands and synthetic public opponent injection; default off')
    ap.add_argument('--fix-artefacts', action='store_true', help='Offline public-body inference and ambiguous-injection exclusion; requires --mechanics-replay; default off')
    ap.add_argument('--own-timing', choices=['tap', 'spawn', 'spawn_mid'], default='tap', help='Own-play injection tick (planning.own_spawn_tick); non-tap requires --mechanics-replay; default tap')
    ap.add_argument('--pair-swarms-by-position', action='store_true', help='Re-pair same-batch swarm members by position (core.SwarmPairing); default off')
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
    if (a.fix_artefacts or a.own_timing != 'tap') and not a.mechanics_replay:
        ap.error('--fix-artefacts and --own-timing spawn* require --mechanics-replay')
    if not 1 <= a.workers <= 24 or a.matches < 1:
        ap.error('workers must be 1..24; matches must be positive')
    if a.mode == 'worker':
        if len(a.runtime) != 1 or not a.source:
            ap.error('worker needs one runtime and --source')
        try:
            result = drive(json.loads(a.source.read_text(encoding='utf8')), a.runtime[0], a.mechanics_replay, a.fix_artefacts, a.own_timing, a.pair_swarms_by_position)
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
    if a.mechanics_replay:
        cohort = [hydrate(row, a.live) for row in cohort]
    sources = a.out/'sources'; sources.mkdir()
    for row in cohort: write(sources/(row['match']+'.json'), row)
    selection = dict(selected=len(cohort), requested=a.matches if not a.cohort else len(cohort), since=a.since,
                     frozen_cohort=str(a.cohort) if a.cohort else None,
                     source_hashes={r['match']:hashlib.sha256((sources/(r['match']+'.json')).read_bytes()).hexdigest() for r in cohort},
                     artefact_fixes=a.fix_artefacts,
                     harness_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'core.py', HERE/'driver.py', HERE/'planning.py', HERE/'mechanics.py', HERE/'inference.py')},
                     exclusions=exclusions, matches=[{k:r[k] for k in ('match', 'sha256', 'quality', 'blocks')} for r in cohort])
    write(a.out/'selection.json', selection)
    if not cohort: raise RuntimeError('No eligible phase_stats matches')
    planned = planning_report(cohort, a.mechanics_replay, a.fix_artefacts)
    write(a.out/'planning.json', planned)
    if a.mode == 'plan':
        print(f"PARITY_PLANNED {planned['usable_matches']}/{len(cohort)}; NO_SIM; counts={planned['counts']}")
        return 0
    if a.mode == 'select':
        print(f"PARITY_SELECTED {len(cohort)}; reconstructable={sum(not r['blocks'] for r in cohort)}")
        return 0
    results = []; jobs = []; started = time.monotonic()
    for rt in a.runtime:
        folder = a.out/rt; folder.mkdir()
        for row in cohort:
            blocks = plan(row, a.mechanics_replay, a.fix_artefacts)['blocks']
            if blocks:
                result = dict(match=row['match'], runtime=rt, status='SKIPPED_INPUT',
                              skip_reason=';'.join(blocks), skip_reasons=blocks)
                write(folder/(row['match']+'.json'), result); results.append(result)
            else:
                jobs.append((getattr(a,rt+'_python'), rt, sources/(row['match']+'.json'), folder/(row['match']+'.json'), a.mechanics_replay, a.fix_artefacts, a.own_timing, a.pair_swarms_by_position))
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
