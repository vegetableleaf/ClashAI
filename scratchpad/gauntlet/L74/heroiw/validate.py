"""Pod orchestration and offline paired scoring. No deployment or remote commands."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LIVE = HERE.parent/'livecal'
sys.path.insert(0, str(LIVE))
sys.path.insert(0, str(ROOT))


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment():
    from pipeline.royale_runtime import activate
    # Full file inventory catches installs/uninstalls or writes in the original venv.
    root = Path(sys.prefix).resolve()
    files = {p.relative_to(root).as_posix(): [p.stat().st_size, p.stat().st_mtime_ns]
             for p in root.rglob('*') if p.is_file()}
    return dict(prefix=str(root), runtime=activate(), files=files)


def link_deps(venv):
    import sysconfig
    old = Path(sysconfig.get_paths()['purelib']).resolve()
    new = Path(subprocess.check_output([str(venv/'bin/python'), '-c',
                    'import sysconfig; print(sysconfig.get_paths()["purelib"])'], text=True).strip())
    assert new.resolve().is_relative_to(venv.resolve()) and not old.is_relative_to(venv.resolve())
    (new/'heroiw_dependencies.pth').write_text(str(old)+'\n')


def prepare(out):
    import livecal
    original = read(LIVE/'manifest.json')
    # Check checkpoint and census evidence against the frozen LIVECAL manifest.
    livecal.validate_files({**original, 'runtime_files': []}, ROOT, LIVE)
    manifest = copy.deepcopy(original)
    support = set(livecal.RUNTIME_FILES) | {
        'pipeline/royale_runtime.py', 'pipeline/royale_heroiw.py', 'pipeline/reader_identity_aliases.py',
        'pipeline/own_ability.py', 'scratchpad/gauntlet/L74/heroiw/build_manifest.json'}
    manifest['runtime_files'] = [dict(path=p, bytes=(ROOT/p).stat().st_size, sha256=digest(ROOT/p)) for p in sorted(support)]
    manifest['heroiw_source_manifest_sha256'] = digest(LIVE/'manifest.json')
    out.mkdir()
    for c in manifest['censuses'].values():
        (out/c['path']).write_bytes((LIVE/c['path']).read_bytes())
    dump(out/'manifest.json', manifest)
    drift = copy.deepcopy(manifest)
    drift['groups'] = [g for g in drift['groups'] if g['family'] == 'old' and not g['fast']]
    assert len(drift['groups']) == 1
    assert Path(drift['groups'][0]['checkpoint']).name == 'rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt'
    drift['pools'] = [p for p in drift['pools'] if p['id'] == 'P1']
    assert drift['pools'] == [dict(id='P1', members=[dict(path=livecal.E4, temperature=.1)])]
    # CAL set c uses the original census decks. LIVECAL keeps its own frozen weighted censuses.
    for name, rel in livecal.CENSUS.items():
        path = out/f'cal_{name}.json'
        path.write_bytes((ROOT/rel).read_bytes())
        drift['censuses'][name] = dict(path=path.name, sha256=digest(path), source=rel, source_sha256=digest(path))
    dump(out/'drift.json', drift)
    return manifest


def suite(manifest, out, workers, pools, drift=False):
    import livecal
    from pipeline.royale_runtime import activate
    if any((out/n).exists() for n in ('plan.json', 'DONE', 'chunks')):
        raise ValueError(f'output already used: {out}')
    out.mkdir(parents=True, exist_ok=True)
    rc = 1
    try:
        stamp = activate()
        dump(out/'runtime.json', stamp)
        plan = livecal.schedule(read(manifest), k=480, seed_start=741200 if drift else 740000, pools=pools)
        dump(out/'plan.json', plan)
        livecal.run(plan, manifest.parent, out, workers)
        if not drift:
            from score import evaluate, summary
            report = evaluate(plan, rows(out/'matches.jsonl'))
            dump(out/'score.json', report)
            (out/'SUMMARY.txt').write_text(summary(report), encoding='utf8')
        else:
            (out/'SUMMARY.txt').write_text('Drift arm complete; requires paired scoring. No deployment.\n')
        rc = 0
    finally:
        if rc:
            (out/'SUMMARY.txt').write_text('FAILED: incomplete validation arm. See job log. No deployment.\n')
        (out/'DONE').write_text(f'exit_code={rc}\n')


def paired_drift(old, new, expected=480):
    import numpy as np
    def indexed(rs):
        out = {}
        for r in rs:
            key = r['census'], r['seed']
            if key in out or r['outcome'] not in ('win', 'loss', 'draw') or r.get('searched') != 0:
                raise ValueError('duplicate/invalid/non-public drift row')
            out[key] = r
        return out
    a, b = indexed(old), indexed(new)
    if a.keys() != b.keys() or len(a) != expected:
        raise ValueError('incomplete drift pairs')
    strata = {}
    for k in sorted(a):
        for field in ('opp_deck', 'learner_side', 'opp_gen_sha256'):
            if a[k][field] != b[k][field]:
                raise ValueError(f'drift pairing mismatch: {k}/{field}')
        # Keep side/census proportions fixed; resample matched outcomes, not two independent WRs.
        strata.setdefault((k[0], a[k]['learner_side']), []).append(int(b[k]['outcome'] == 'win')-int(a[k]['outcome'] == 'win'))
    rng = np.random.default_rng(20261012)
    boot = np.zeros(10000)
    for values in strata.values():
        values = np.asarray(values)
        boot += values[rng.integers(len(values), size=(len(boot), len(values)))].sum(axis=1)
    return dict(pairs=len(a), old_win_rate=sum(r['outcome'] == 'win' for r in a.values())/len(a),
                new_win_rate=sum(r['outcome'] == 'win' for r in b.values())/len(b),
                delta_pp=100*sum(map(sum, strata.values()))/len(a),
                ci95_pp=(100*np.quantile(boot/len(a), [.025, .975])).tolist(),
                method='10000 paired bootstrap draws within census and learner side; draws count as non-wins')


def compatible_baseline(directory, manifest, pools):
    import livecal
    from score import evaluate
    plan = read(directory/'plan.json')
    expected = livecal.schedule(read(manifest), k=480, seed_start=740000, pools=pools)
    # Code stamps may differ for archived old runs; all experiment inputs and actual assignments must match.
    for key in ('groups', 'truth_sha256', 'files', 'censuses', 'k', 'seed_start', 'protocol', 'assumptions'):
        if plan[key] != expected[key]:
            raise ValueError(f'baseline differs in {key}')
    wanted = {p['id'] for p in expected['pools']}
    jobs = [j for j in plan['jobs'] if j['pool'] in wanted]
    if jobs != expected['jobs']:
        raise ValueError('baseline assignments differ')
    # Legacy LIVECAL did not record a runtime: it cannot establish OLD vs NEW provenance.
    if read(directory/'runtime.json')['runtime_id'] != '20261006-linux':
        raise ValueError('baseline does not prove the old runtime')
    return evaluate(expected, [r for r in rows(directory/'matches.jsonl') if r['pool'] in wanted])


def run(a):
    from importlib.metadata import requires, version
    from packaging.requirements import Requirement
    for raw in requires('royalegym'):
        req = Requirement(raw)
        if req.marker is None or req.marker.evaluate({'extra': ''}):
            if version(req.name) not in req.specifier:
                raise RuntimeError(f'Reused dependency does not satisfy {req}; old venv was not modified')
    pools = 'P1,P2,P5' + (',P3' if a.include_p3 else '')
    if not 1 <= a.workers <= 25:
        raise ValueError('workers must be 1..25')
    manifest = a.out/'inputs'/'manifest.json'
    m = prepare(manifest.parent)
    games = len(m['groups'])*len(pools.split(','))*480
    print(f'LIVECAL {games} games/runtime; estimate {(2*games+960)/(47*a.workers/28)/60:.1f} hours including fresh old baseline', flush=True)
    subprocess.run([sys.executable, str(HERE/'smoke.py'), '--out', str(a.out/'smoke.json')], check=True, cwd=ROOT)
    def launch(python, runtime, source, out, selected, drift=False):
        cmd = [str(python), str(__file__), 'suite', '--manifest', str(source), '--out', str(out),
               '--workers', str(a.workers), '--pools', selected]
        if drift:
            cmd += ['--drift']
        with (a.out/f'{out.name}.log').open('w') as log:
            subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, ROYALE_RUNTIME=runtime), check=True,
                           stdout=log, stderr=subprocess.STDOUT)
    drift_manifest = manifest.with_name('drift.json')
    launch(a.old_python, '20261006-linux', drift_manifest, a.out/'DRIFT_OLD', 'P1', True)
    launch(sys.executable, '20261012-linux', drift_manifest, a.out/'DRIFT_NEW', 'P1', True)
    report = paired_drift(rows(a.out/'DRIFT_OLD/matches.jsonl'), rows(a.out/'DRIFT_NEW/matches.jsonl'))
    dump(a.out/'drift.json', report)
    new_out = Path('/workspace/results/LIVECAL_NEW')
    launch(sys.executable, '20261012-linux', manifest, new_out, pools)
    baseline = Path(os.environ.get('LIVECAL_OLD', '/workspace/results/LIVECAL'))
    try:
        old = compatible_baseline(baseline, manifest, pools)
    except (OSError, ValueError, KeyError) as exc:
        print(f'Archived baseline not reusable ({exc}); measuring a fresh OLD baseline.', flush=True)
        baseline = a.out/'LIVECAL_OLD'
        launch(a.old_python, '20261006-linux', manifest, baseline, pools)
        old = compatible_baseline(baseline, manifest, pools)
    new = read(new_out/'score.json')
    comparisons = {}
    for p in pools.split(','):
        comparisons[p] = dict(old=old['pools'][p], new=new['pools'][p])
    dump(a.out/'comparison.json', dict(old_directory=str(baseline), pools=comparisons))
    gain = sum(v['new']['agreements']-v['old']['agreements'] for v in comparisons.values())
    verdict = 'more' if gain > 0 else 'fewer' if gain < 0 else 'the same number of'
    lines = [f'VALIDATED: new runtime reproduces {verdict} live ordering signs across the selected pools. No deployment.',
             'Eight smoke games verified hero deploy, 3 elixir deploy cost, 2 elixir button cost, single charge and public cube identity.',
             f"480 paired CAL-c games: old {100*report['old_win_rate']:.2f}%, new {100*report['new_win_rate']:.2f}%; "
             f"change {report['delta_pp']:+.2f} pp, paired 95% CI {report['ci95_pp']}.", report['method']]
    for p, r in comparisons.items():
        lines.append(f"{p}: ordering signs old {r['old']['agreements']}/2 -> new {r['new']['agreements']}/2.")
        for q in r['new']['pairs']:
            if q['primary']:
                prior = next(t for t in r['old']['pairs'] if t['name'] == q['name'])
                lines.append(f"  {q['name']}: old {100*prior['sim_delta']:+.2f} pp {prior['sim_ci95']} -> "
                             f"new {100*q['sim_delta']:+.2f} pp {q['sim_ci95']} (CI endpoints in win-rate units).")
    lines += ['This tests the combined engine, card-table and Hero IW change. It cannot attribute drift to Hero IW alone.',
              'Ordering signs are descriptive; intervals that span zero do not establish an ordering. Live truth is observational.',
              'LIVECAL retains its frozen S2/CAL surrogate; the live iw_press_pstar policy is not ported or retrained.',
              f'Old comparison: {baseline}. Full new report: {new_out}/SUMMARY.txt.']
    (a.out/'SUMMARY.txt').write_text('\n'.join(lines)+'\n', encoding='utf8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['preflight', 'unchanged', 'link-deps', 'run', 'suite'])
    ap.add_argument('--out', type=Path)
    ap.add_argument('--venv', type=Path)
    ap.add_argument('--manifest', type=Path)
    ap.add_argument('--old-python', type=Path)
    ap.add_argument('--workers', type=int, default=25)
    ap.add_argument('--pools', default='P1,P2,P5')
    ap.add_argument('--include-p3', action='store_true')
    ap.add_argument('--drift', action='store_true')
    a = ap.parse_args()
    if not 1 <= a.workers <= 25:
        raise ValueError('workers must be 1..25')
    if a.mode == 'preflight':
        snapshot = environment()
        assert snapshot['runtime']['runtime_id'] == '20261006-linux'
        dump(a.out/'old_environment.json', snapshot)
    elif a.mode == 'unchanged':
        assert environment() == read(a.out/'old_environment.json'), 'original venv changed'
        print('Original venv inventory and runtime stamp unchanged.')
    elif a.mode == 'link-deps':
        link_deps(a.venv)
    elif a.mode == 'suite':
        suite(a.manifest, a.out, a.workers, a.pools, a.drift)
    else:
        run(a)


if __name__ == '__main__':
    main()
