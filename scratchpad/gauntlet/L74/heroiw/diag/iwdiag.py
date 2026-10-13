"""Offline-only IWDIAG orchestrator. Provisioned runtimes required; no installs."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
LIVE = HERE.parents[1]/'livecal'
sys.path[:0] = [str(ROOT), str(LIVE), str(HERE.parent)]
ARMS = dict(N0=('20261012-linux', 'hero', 'off'),
            N1=('20261012-linux', 'normal', 'off'),
            N2=('20261012-linux', 'hero', 'live'),
            O0=('20261006-linux', 'hero', 'off'),
            N3=('20261012-linux', 'hero', 'never'))
LABELS = dict(N0='0.1.33 Hero IW; existing v2 generic IW proximity fallback (no IW ability head)',
              N1='N0 with IceWizard NORMAL form only',
              N2='N0 with live IW geometry + deterministic p >= .03 rule only',
              O0='0.1.17 old-runtime reference',
              N3='N0 with the IW ability NEVER pressed (hero body only)')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def eta(workers, games=1920):
    # Prior HEROIW throughput = 47 games/min at 28 processes. Per-tick
    # telemetry has not been benchmarked; give 2-4x allowance, no precision claim.
    baseline = games/(47*workers/28)/60
    return f'{2*baseline:.1f}-{4*baseline:.1f} hours at {workers} workers, excluding cpu.lock wait (unmeasured telemetry allowance)'


def arm_env(arm):
    runtime, form, press = ARMS[arm]
    env = dict(os.environ, ROYALE_RUNTIME=runtime, ROYALE_HEROIW_FORM=form, ROYALE_HEROIW_PRESS=press,
               IWDIAG_ARM=arm, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONPATH=str(ROOT))
    return env


def source_files():
    import livecal
    support = set(livecal.RUNTIME_FILES) | {
        'pipeline/royale_runtime.py', 'pipeline/royale_heroiw.py', 'pipeline/royale_iw_policy.py',
        'pipeline/reader_identity_aliases.py', 'pipeline/own_ability.py',
        'scratchpad/gauntlet/L74/heroiw/build_manifest.json',
        'scratchpad/gauntlet/L73/royale_update_20261006/build_manifest.json',
        'scratchpad/gauntlet/L68/live_reader/ability_ice_wizard.py',
        'scratchpad/gauntlet/L68/live_reader/ability_ice_wizard_model.json',
        'scratchpad/gauntlet/L68/live_reader/hero_button.py',
        'scratchpad/gauntlet/L68/live_reader/unit_values.json'}
    support.update(p.relative_to(ROOT).as_posix() for p in HERE.glob('*') if p.suffix in ('.py', '.sh', '.json'))
    return sorted(support)


def prepare(directory):
    import livecal
    original = read(LIVE/'manifest.json')
    manifest = copy.deepcopy(original)
    manifest['groups'] = [g for g in original['groups'] if g['family'] == 'old' and not g['fast']]
    assert len(manifest['groups']) == 1
    assert Path(manifest['groups'][0]['checkpoint']).name == 'rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt'
    manifest['pools'] = [p for p in original['pools'] if p['id'] == 'P1']
    assert manifest['pools'] == [dict(id='P1', members=[dict(path=livecal.E4, temperature=.1)])]
    wanted = {manifest['groups'][0]['checkpoint'], livecal.E4, livecal.GEN}
    manifest['files'] = [f for f in original['files'] if f['path'] in wanted]
    assert {f['path'] for f in manifest['files']} == wanted
    manifest['runtime_files'] = [dict(path=p, bytes=(ROOT/p).stat().st_size, sha256=digest(ROOT/p))
                                 for p in source_files()]
    manifest['iwdiag_source_manifest_sha256'] = digest(LIVE/'manifest.json')
    directory.mkdir()
    for name, rel in livecal.CENSUS.items():
        # Same unweighted CAL-c census, seed range and P1 opponent as HEROIW DRIFT.
        dest = directory/f'cal_{name}.json'
        if digest(ROOT/rel) != original['censuses'][name]['source_sha256']:
            raise ValueError(f'original CAL census changed: {rel}')
        dest.write_bytes((ROOT/rel).read_bytes())
        manifest['censuses'][name] = dict(path=dest.name, sha256=digest(dest), source=rel, source_sha256=digest(dest))
    livecal.validate_files(manifest, ROOT, directory)
    dump(directory/'manifest.json', manifest)
    plan = livecal.schedule(manifest, k=480, seed_start=741200, pools='P1')
    dump(directory/'plan.json', plan)
    return plan


def command(job, census, dest, python):
    import livecal
    cmd = livecal.command(job, census, dest, python=python)
    cmd[1] = str(__file__)  # same flags, but isolated observer instrumentation
    return cmd


def worker():
    import livecal
    from pipeline import search_s0 as S
    from pipeline.royale_runtime import activate
    from pipeline import royale_heroiw as H
    from royalegym.protocol import EntityKind
    from royalegym.rust_engine import embedded_card_table
    import royalesim
    from metrics import instrument
    stamp = activate()
    arm = os.environ['IWDIAG_ARM']
    if stamp['runtime_id'] != ARMS[arm][0]:
        raise ValueError('wrong runtime')
    data = H.selected_card_data() if H.ENABLED else json.loads(embedded_card_table())
    xbow = next(c for c in data['cards'] if c['name'] == 'Xbow')
    calibration = json.loads(royalesim.EMBEDDED_CALIBRATION_JSON)
    shot_step = xbow['projectile']['speed'] * calibration['time']['PROJECTILE_SPEED_TO_SUBTILES_PER_TICK']['value']
    iw = next((c for c in data['hero_forms'] if c['form_of'] == 'IceWizard'), None)
    original_play = S.Runner.play
    def play(self, policy_arm, match, deadline=None):
        recorder, restore = instrument(match.env, match.learner.side, shot_step,
                                       (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER))
        try:
            result = original_play(self, policy_arm, match, deadline)
            result['iwdiag'] = recorder.result()
            result['iwdiag'].update(arm=arm, runtime=stamp, form=ARMS[arm][1], press=ARMS[arm][2],
                                   loaded_forms=match.env.loaded_forms,
                                   iw_table_cost=iw['ability']['mana_cost'] if iw else None,
                                   xbow_shot_step=shot_step)
            return result
        finally:
            restore()
    S.Runner.play = play
    return livecal.worker()


def run_arm(arm, python, plan, inputs, out, workers):
    import livecal
    livecal.validate_files(plan, ROOT, inputs)
    out.mkdir()
    (out/'chunks').mkdir()
    dump(out/'plan.json', plan)
    hashes = {f['path']: f['sha256'] for f in plan['files']}
    def one(item):
        index, job = item
        dest = out/'chunks'/f'{index:05d}'
        cmd = command(job, inputs/plan['censuses'][job['census']]['path'], dest, python)
        with dest.with_suffix('.log').open('w', encoding='utf8') as log:
            subprocess.run(cmd, cwd=ROOT, env=arm_env(arm), stdout=log, stderr=subprocess.STDOUT, check=True)
        receipt = read(dest/'run.json')
        if receipt['gen_sha256'] != hashes[job['checkpoint']] or receipt['opp_gen_sha256'] != hashes[job['opponent']['path']]:
            raise ValueError('checkpoint receipt mismatch')
        if bool(receipt.get('pipeline_decisions')) != job['fast']:
            raise ValueError('fast setting mismatch')
        result = rows(dest/'matches.jsonl')
        if sorted(r['seed'] for r in result) != sorted(job['seeds']):
            raise ValueError('missing, duplicate or wrong seeds')
        for r in result:
            if (r['arm'] != 'plain' or r['searched'] != 0 or r['wall_truncated'] or
                    r['opp_gen_sha256'] != hashes[job['opponent']['path']] or r['iwdiag']['arm'] != arm):
                raise ValueError('invalid diagnostic receipt')
            r.update(group=job['group'], pool=job['pool'], census=job['census'])
        return result
    with ThreadPoolExecutor(max_workers=workers) as executor, (out/'matches.jsonl').open('w', encoding='utf8') as stream:
        for i, result in enumerate(executor.map(one, enumerate(plan['jobs']))):
            for r in result:
                stream.write(json.dumps(r, allow_nan=False)+'\n')
            stream.flush()
            print(f'{arm}: {i+1}/{len(plan["jobs"])} chunks', flush=True)
    livecal.validate_files(plan, ROOT, inputs)
    (out/'DONE').write_text('exit_code=0\n')


def summarize(all_rows, workers, expected=480):
    from validate import paired_drift
    if 'N0' not in all_rows or not set(all_rows) <= set(ARMS):
        raise ValueError('require N0 (the paired reference) and known arms')
    reports = {}
    lines = [f'COMPLETE: IWDIAG | ETA budget: {eta(workers)}',
             f'{expected} paired games per arm; old live checkpoint; CAL set c; seeds 741200..741439 in evo and lad.',
             'Draws count as non-wins. Deltas are ARM minus N0; 10,000 paired bootstrap draws within census/side.',
             'N0 preserves HEROIW: IW uses the generic proximity fallback under v2, NOT a learned ability head.']
    for arm in all_rows:
        rr = all_rows[arm]
        paired = paired_drift(all_rows['N0'], rr, expected=expected)
        expected_keys = {(c, s) for c in ('evo', 'lad') for s in range(741200, 741200+expected//2)}
        if {(r['census'], r['seed']) for r in rr} != expected_keys:
            raise ValueError('wrong seed/census coverage')
        for r in rr:
            d = r['iwdiag']
            if (d['arm'] != arm or d['runtime']['runtime_id'] != ARMS[arm][0] or
                    (d['form'], d['press']) != ARMS[arm][1:] or r['wall_truncated']):
                raise ValueError('arm provenance mismatch')
            if r['learner_side'] != r['seed'] % 2:
                raise ValueError('wrong learner side')
            own_forms = d['loaded_forms'].get(str(r['learner_side']), d['loaded_forms'].get(r['learner_side']))
            if own_forms[2] != (2 if arm in ('N0', 'N2', 'N3') else 0):
                raise ValueError('wrong learner IW form')
            for field in ('iw_scheduled', 'iw_attempts', 'iw_accepted', 'iw_elixir', 'xbow_placements',
                          'xbow_impact_hp_loss', 'xbow_contested_hp_loss', 'xbow_impact_windows'):
                if not math.isfinite(d[field]) or d[field] < 0:
                    raise ValueError(f'invalid metric {field}')
            if not 0 <= d['iw_accepted'] <= d['iw_attempts'] <= d['iw_scheduled']:
                raise ValueError('invalid per-game press denominators')
            if arm in ('N1', 'O0', 'N3') and (d['iw_scheduled'] or d['iw_elixir']):
                raise ValueError('normal IW unexpectedly pressed or spent ability elixir')
            press_counter = r['ability_presses'].get(str(r['learner_side']), r['ability_presses'].get(r['learner_side'], {}))
            if d['iw_accepted'] != press_counter.get('IceWizard', 0):
                raise ValueError('recorder differs from adapter press counter')
            if len(d['press_receipts']) != d['iw_attempts'] or sum(q['accepted'] for q in d['press_receipts']) != d['iw_accepted']:
                raise ValueError('incomplete press receipts')
            if abs(sum(q['spent'] for q in d['press_receipts'])-d['iw_elixir']) > 1e-9:
                raise ValueError('elixir receipt mismatch')
        totals = {k: sum(r['iwdiag'][k] for r in rr) for k in
                  ('iw_scheduled', 'iw_attempts', 'iw_accepted', 'iw_elixir', 'xbow_placements',
                   'xbow_impact_hp_loss', 'xbow_contested_hp_loss', 'xbow_impact_windows')}
        if not 0 <= totals['iw_accepted'] <= totals['iw_attempts'] <= totals['iw_scheduled']:
            raise ValueError('invalid press denominators')
        rate = totals['iw_accepted']/totals['iw_attempts'] if totals['iw_attempts'] else None
        table_costs = sorted({r['iwdiag']['iw_table_cost'] for r in rr if r['iwdiag']['iw_table_cost'] is not None})
        paid_costs = sorted({q['spent'] for r in rr for q in r['iwdiag']['press_receipts'] if q['accepted']})
        reports[arm] = dict(paired=paired, totals=totals, per_game={k: v/expected for k, v in totals.items()},
                            press_success_rate=rate, table_costs=table_costs, observed_press_debits=paid_costs)
        ci = paired['ci95_pp']
        lines += ['', f'{arm}: {LABELS[arm]}',
                  f"win {100*paired['new_win_rate']:.2f}%; delta vs N0 {paired['delta_pp']:+.2f} pp; 95% CI [{ci[0]:+.2f}, {ci[1]:+.2f}]",
                  f"Hero IW accepted presses/game {totals['iw_accepted']/expected:.4f}; elixir spent/game {totals['iw_elixir']/expected:.4f}; "
                  + ('press success n/a (0 attempts)' if rate is None else f'press success {100*rate:.2f}%')
                  + f" ({totals['iw_accepted']}/{totals['iw_attempts']} submitted; {totals['iw_scheduled']} scheduled).",
                  f"X-Bow placements/game {totals['xbow_placements']/expected:.4f}; X-Bow impact-associated tower HP loss/game "
                  f"{totals['xbow_impact_hp_loss']/expected:.2f}; possibly mixed portion/game {totals['xbow_contested_hp_loss']/expected:.2f}.",
                  f'Wheel IW ability table cost(s): {table_costs or "absent"}; actual accepted press debit(s): {paid_costs or "no presses"}.']
    cost = read(HERE/'device_cost.json')
    for arm, report in reports.items():
        if any(c != cost['ability_cost'] for c in report['table_costs']):
            lines.append(f'{arm}: SIM/device cost mismatch originates in royalesim selected table; adapter does not set the debit.')
        if any(c not in report['table_costs'] for c in report['observed_press_debits']):
            lines.append(f'{arm}: observed debit differs from exported table: engine charge behavior requires investigation; adapter only submits DeployCommand.')
    lines += ['', f"Device ability cost: {cost['ability_cost']} elixir; deploy: {cost['deploy_cost']}. "
              'Ability TOML is device_update; deploy CSV is APK fallback. See device_cost.json hashes/rows.',
              'Compare each arm iw_table_cost and press_receipts.spent: _Core.act submits a button command; the engine charges elixir.',
              'Source 0.1.33 and prior HEROIW smoke both say 2. The live own_ability SUPPLEMENT says 1; it is not used to charge SIM presses.',
              'X-Bow damage is a public attribution estimate, NOT exact source damage. Coincident damage, unseen same-tick bolts,',
              'damage modifiers and public observation limits can confound it. Exact X-Bow damage is unavailable from this public API.',
              'Press success = engine-accepted / submitted; it does not measure freeze effectiveness. Scheduled includes failed landing rechecks.',
              'N2 ports geometry and p>=.03 at whole seconds since deploy, using public opponent estimates and own history.',
              'SIM retains its existing 26-tick queue/readiness checks; device button sampling, taps and UI scheduling are not reproduced.',
              'All arms have identical observer instrumentation. No search, hidden-state rollouts, live script edits, or network.',
              'Interpret N1-N0 as the form ablation, N2-N0 as the press-rule ablation; O0-N0 is the combined runtime reference.',
              'These arms do not independently ablate X-Bow mechanics or the ability cost; neither can be named causal from telemetry alone.']
    return reports, '\n'.join(lines)+'\n'


def run(args):
    if not 1 <= args.workers <= 25:
        raise ValueError('workers must be 1..25')
    plan = prepare(args.out/'inputs')
    dump(args.out/'device_cost.json', read(HERE/'device_cost.json'))
    print(f'IWDIAG {480*len(args.arms)} games ({",".join(args.arms)}) | ETA {eta(args.workers, 480*len(args.arms))}', flush=True)
    for arm in args.arms:
        python = args.old_python if arm == 'O0' else args.new_python
        run_arm(arm, str(python), plan, args.out/'inputs', args.out/arm, args.workers)
    report, summary = summarize({arm: rows(args.out/arm/'matches.jsonl') for arm in args.arms}, args.workers)
    dump(args.out/'score.json', report)
    (args.out/'SUMMARY.txt').write_text(summary, encoding='utf8')


def main():
    if sys.argv[1:2] == ['--worker']:
        return worker()
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=Path('/workspace/results/IWDIAG'))
    ap.add_argument('--old-python', type=Path, default=Path('/workspace/venv/bin/python'))
    ap.add_argument('--new-python', type=Path, default=Path('/workspace/venv33/bin/python'))
    ap.add_argument('--workers', type=int, default=25)
    ap.add_argument('--arms', type=lambda v: v.split(','), default=['N0', 'N1', 'N2', 'O0'],
                    help='comma list; N0 (the paired reference) first; N3 = never press (10-13)')
    args = ap.parse_args()
    if args.arms[0] != 'N0' or not set(args.arms) <= set(ARMS):
        ap.error('--arms must start with N0 and name known arms')
    run(args)


if __name__ == '__main__':
    main()
