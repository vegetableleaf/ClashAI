import copy
import json
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path
import pytest
import livecal as L
from census import weighted


def manifest():
    return dict(groups=[dict(id='a', checkpoint='a.pt', fast=False), dict(id='b', checkpoint='b.pt', fast=True)],
                pools=[dict(id=p, members=[dict(path=f'{p}_{i}.pt', temperature=.3) for i in range(n)])
                       for p, n in [('P1', 1), ('P2', 1), ('P3', 1), ('P4', 4), ('P5', 2)]])


@pytest.mark.parametrize('k', [120, 480])
def test_schedule_pairing_and_pool_mixture(k):
    plan = L.schedule(manifest(), k)
    assert plan['games'] == k*10
    assignment = {}
    for j in plan['jobs']:
        for s in j['seeds']:
            key = j['pool'], j['census'], s
            if key in assignment:
                assert assignment[key] == j['opponent']
            assignment[key] = j['opponent']
    for g in ('a', 'b'):
        count = Counter(j['pool'] for j in plan['jobs'] for _ in j['seeds'] if j['group'] == g)
        assert set(count.values()) == {k}
    mixture = Counter(v['path'] for (p, c, s), v in assignment.items() if p == 'P5')
    assert sorted(mixture.values()) == [k//2, k//2]
    for c in ('evo', 'lad'):
        for parity in (0, 1):
            values = Counter(v['path'] for (p, cc, s), v in assignment.items() if p == 'P5' and cc == c and s % 2 == parity)
            assert max(values.values())-min(values.values()) <= 1
    assert len({v['path'] for (p, c, s), v in assignment.items() if p == 'P4'}) == 4
    assert plan == L.schedule(manifest(), k)


def test_optional_pool_and_command_contract(tmp_path):
    m = manifest()
    m['pools'] = [p for p in m['pools'] if p['id'] != 'P4']
    plan = L.schedule(m, 120)
    assert len({j['pool'] for j in plan['jobs']}) == 4
    a = L.command(plan['jobs'][0], 'census.json', tmp_path)
    b = L.command(next(j for j in plan['jobs'] if j['fast']), 'census.json', tmp_path)
    assert '--pipeline-decisions' not in a and '--pipeline-decisions' in b
    assert a[a.index('--workers')+1] == '1' and a[a.index('--threads')+1] == '1'
    assert a[a.index('--arms')+1] == 'plain'
    assert all(x in a for x in ('--own-effects', '--tau-phase', '--lethal-log', '--hero-abilities'))
    with pytest.raises(ValueError): L.schedule(m, 121)


def test_archetype_weighting_matches_target():
    data = dict(decks=[dict(engine=['Golem'], sides=1), dict(engine=['HogRider'], sides=100)])
    before = copy.deepcopy(data)
    result = weighted(data)
    assert data == before
    assert result['weighted_archetypes']['achieved'] == pytest.approx(.6, abs=.002)
    with pytest.raises(ValueError): weighted(result)


@pytest.mark.parametrize('args', [['--workers', '29'], ['--manifest', 'does_not_exist.json'], ['--k', '3']])
def test_driver_failure_writes_summary_done(tmp_path, args):
    result = subprocess.run([sys.executable, str(L.HERE/'livecal.py'), '--out', str(tmp_path), *args], capture_output=True, text=True)
    assert result.returncode != 0
    assert (tmp_path/'SUMMARY.txt').read_text().startswith('FAILED:')
    assert 'exit_code=1' in (tmp_path/'DONE').read_text()


def test_plan_only_no_sim(tmp_path):
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest()))
    out = tmp_path/'out'
    result = subprocess.run([sys.executable, str(L.HERE/'livecal.py'), '--manifest', str(path),
                             '--out', str(out), '--quick', '--plan-only'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads((out/'plan.json').read_text())['games'] == 1200
    assert (out/'SUMMARY.txt').read_text().startswith('PLAN ONLY')
    assert not (out/'matches.jsonl').exists()
    assert (out/'DONE').read_text().strip() == 'exit_code=0'


def test_worker_forces_public_counter_no_stall_and_rejects_search(monkeypatch):
    fake = types.SimpleNamespace(live_cfg=lambda: {'stall_elixir': 9, 'opp_elixir': 'counter'})
    def main(args):
        cfg = fake.live_cfg()
        assert cfg == {'stall_elixir': None, 'opp_elixir': 'counter'}
        return 0
    fake.main = main
    monkeypatch.setitem(sys.modules, 'pipeline', types.SimpleNamespace(search_s0=fake))
    monkeypatch.setattr(sys, 'argv', ['livecal.py', '--worker', '--arms', 'plain', '--workers', '1'])
    assert L.worker() == 0
    # Restore fake before second call: worker wraps live_cfg once in a fresh real process.
    fake.live_cfg = lambda: {'stall_elixir': 9, 'opp_elixir': 'counter'}
    monkeypatch.setattr(sys, 'argv', ['livecal.py', '--worker', '--arms', 'search', '--workers', '1'])
    with pytest.raises(ValueError): L.worker()


def test_runner_receipts_and_pairing_without_sim(tmp_path, monkeypatch):
    m = manifest()
    m['pools'] = m['pools'][:1]
    m['files'] = [dict(path=x, sha256=x) for x in ('a.pt', 'b.pt', 'P1_0.pt')]
    m['censuses'] = {c: dict(path=c+'.json') for c in ('evo', 'lad')}
    p = L.schedule(m, 4)
    monkeypatch.setattr(L, 'validate_files', lambda *a: None)
    def fake_run(cmd, **kwargs):
        dest = Path(cmd[cmd.index('--out')+1])
        dest.mkdir()
        learner = cmd[cmd.index('--gen')+1]
        opponent = cmd[cmd.index('--opp-gen')+1]
        L.dump(dest/'run.json', dict(gen_sha256=learner, opp_gen_sha256=opponent,
                                   pipeline_decisions='--pipeline-decisions' in cmd))
        rows = [dict(seed=int(s), arm='plain', searched=0, opp_gen_sha256=opponent,
                     opp_deck=['HogRider'], learner_side=int(s)%2, outcome='win')
                for s in cmd[cmd.index('--seeds')+1].split(',')]
        (dest/'matches.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    monkeypatch.setattr(L.subprocess, 'run', fake_run)
    L.run(p, tmp_path, tmp_path, 2)
    rows = [json.loads(s) for s in (tmp_path/'matches.jsonl').read_text().splitlines()]
    from score import matrices
    assert matrices(p, rows)['P1'].shape == (2, 4)
    assert len(rows) == 8


def test_hash_preflight_rejects_changed_checkpoint(tmp_path):
    p = tmp_path/'model.pt'
    p.write_bytes(b'original')
    m = dict(files=[dict(path=p.name, bytes=p.stat().st_size, sha256=L.digest(p))], censuses={})
    L.validate_files(m, tmp_path, tmp_path)
    p.write_bytes(b'modified')
    with pytest.raises(ValueError, match='hash-mismatched'):
        L.validate_files(m, tmp_path, tmp_path)


def test_mixed_eras_collapse_without_extra_rank_votes():
    truth = dict(min_n=30, groups=[])
    for i, n, w, fast in [(0, 20, 10, False), (1, 40, 30, False), (2, 10, 1, True)]:
        truth['groups'].append(dict(id=str(i), era=str(i), checkpoint='old.pt', checkpoint_sha256='sha',
             checkpoint_verified=True, family='old', fast=fast, n=n, wins=w, losses=n-w, draws=0, settings={}))
    groups = L.collapse_groups(truth)
    assert len(groups) == 2
    assert groups[0]['win_rate'] == pytest.approx(40/60)
    assert groups[0]['n'] == 60 and len(groups[0]['eras']) == 2
    assert groups[0]['reportable'] and not groups[1]['reportable']
