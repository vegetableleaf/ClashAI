import copy
import json
import subprocess
import sys

import pytest
import livecal as L
from score import evaluate, summary
from test_livecal import manifest
from test_score import fixture


@pytest.mark.parametrize('k', [4, 120, 480])
def test_split_preserves_every_job_seed_and_arm(k):
    m = manifest()
    full = L.schedule(m, k)
    a = L.schedule(m, k, pools='P3,P1,P2')
    c = L.schedule(m, k, pools='P4,P5')
    assert a['jobs'] + c['jobs'] == full['jobs']
    assert a['groups'] == c['groups'] == full['groups']
    assert a['games'] + c['games'] == full['games']
    assert L.schedule(m, k, pools='P1,P3')['jobs'] == [j for j in full['jobs'] if j['pool'] in ('P1', 'P3')]
    assert 'all_pools' not in full
    assert L.schedule(m, k) == full


@pytest.mark.parametrize('pools', ['', 'P0', 'P1,P1', 'P1,', 'P1,P9'])
def test_bad_pool_selection(pools):
    with pytest.raises(ValueError, match='distinct available IDs'):
        L.schedule(manifest(), pools=pools)


def synthetic():
    score_plan, score_rows = fixture()
    m = manifest()
    m['groups'] = [dict(g, checkpoint=g['id']+'.pt', checkpoint_sha256=g['id']) for g in score_plan['groups']]
    paths = [g['checkpoint'] for g in m['groups']] + [member['path'] for p in m['pools'] for member in p['members']]
    m['files'] = [dict(path=p, sha256=p) for p in paths]
    m['truth_sha256'] = 'frozen truth'
    plan = L.schedule(m, 8)
    outcomes = {(r['pool'], r['group'], r['census'], r['seed']-10): r['outcome'] for r in score_rows}
    rows = [dict(pool=j['pool'], group=j['group'], census=j['census'], seed=s,
                 outcome=outcomes['P1' if j['pool'] in ('P1', 'P4') else 'P2', j['group'], j['census'], s-plan['seed_start']],
                 arm='plain', searched=0, opp_gen_sha256=j['opponent']['path'],
                 opp_deck=['HogRider'], learner_side=s % 2)
            for j in plan['jobs'] for s in j['seeds']]
    return m, plan, rows


def part(directory, m, rows, pools=None):
    directory.mkdir()
    plan = L.schedule(m, 8, pools=pools)
    L.dump(directory/'plan.json', plan)
    selected = {p['id'] for p in plan['pools']}
    (directory/'matches.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows if r['pool'] in selected), encoding='utf8')
    return directory


def cli(out, *args):
    return subprocess.run([sys.executable, '-B', str(L.HERE/'livecal.py'), '--out', str(out),
                           '--bootstrap', '30', *map(str, args)], capture_output=True, text=True)


def test_merge_equals_full_scoring_and_summary(tmp_path):
    m, full, rows = synthetic()
    a = part(tmp_path/'A', m, rows, 'P1,P2,P3')
    c = part(tmp_path/'C', m, rows, 'P4,P5')
    out = tmp_path/'merged'
    # Reverse input order and include an identical overlapping part: union, not double counting.
    result = cli(out, '--merge', c, a, c, '--manifest', tmp_path/'not_needed.json')
    assert result.returncode == 0, result.stderr
    expected = evaluate(full, rows, boots=30)
    assert json.loads((out/'score.json').read_text()) == expected
    assert (out/'SUMMARY.txt').read_text() == summary(expected)
    assert (out/'DONE').read_text() == 'exit_code=0\n'
    assert json.loads((out/'plan.json').read_text()) == full
    assert len((out/'matches.jsonl').read_text().splitlines()) == len(rows)
    assert not (out/'chunks').exists()
    # Legacy unsplit result directories remain valid merge inputs.
    legacy = part(tmp_path/'full', m, rows)
    assert L.merge([legacy])[0] == full


@pytest.mark.parametrize('remaining', [0, 7])
def test_missing_arm_reported_without_imputation(tmp_path, remaining):
    m, full, rows = synthetic()
    missing = [r for r in rows if (r['pool'], r['group']) == ('P4', 'old')]
    rows = [r for r in rows if (r['pool'], r['group']) != ('P4', 'old')] + missing[:remaining]
    a = part(tmp_path/'A', m, rows, 'P1,P2,P3')
    c = part(tmp_path/'C', m, rows, 'P4,P5')
    (c/'DONE').write_text('exit_code=1\n')  # Finished arms from a failed part still count.
    out = tmp_path/'merged'
    result = cli(out, '--merge', a, c)
    assert result.returncode == 1
    report = json.loads((out/'score.json').read_text())
    assert report['missing_arms'] == [dict(pool='P4', group='old', games=remaining, expected_games=8)]
    assert report['best_pool'] is None
    assert 'P4' not in report['pools']
    assert len(report['finished_arms']) == 19
    expected = evaluate({**full, 'pools': [p for p in full['pools'] if p['id'] != 'P4']},
                        [r for r in rows if r['pool'] != 'P4'], boots=30)
    assert report['pools'] == expected['pools']
    assert f'MISSING ARM P4/old: {remaining}/8 games' in (out/'SUMMARY.txt').read_text()
    assert (out/'DONE').read_text() == 'exit_code=1\n'
    assert len((out/'matches.jsonl').read_text().splitlines()) == len(rows)


def test_absent_part_and_no_results(tmp_path):
    m, _, rows = synthetic()
    a = part(tmp_path/'A', m, rows, 'P1,P2,P3')
    out = tmp_path/'merged'
    assert cli(out, '--merge', a).returncode == 1
    report = json.loads((out/'score.json').read_text())
    assert {r['pool'] for r in report['missing_arms']} == {'P4', 'P5'}
    assert len(report['missing_arms']) == 8
    (a/'matches.jsonl').unlink()
    out = tmp_path/'empty'
    assert cli(out, '--merge', a).returncode == 1
    report = json.loads((out/'score.json').read_text())
    assert len(report['missing_arms']) == 20
    assert report['pools'] == {} and report['finished_arms'] == []


@pytest.mark.parametrize('bad', ['truth', 'group', 'schedule', 'conflict', 'duplicate', 'opponent', 'pairing', 'truncated'])
def test_merge_rejects_incompatible_or_invalid_results(tmp_path, bad):
    m, _, rows = synthetic()
    a = part(tmp_path/'A', m, rows, 'P1,P2,P3')
    changed = copy.deepcopy(m)
    changed_rows = copy.deepcopy(rows)
    if bad == 'truth': changed['truth_sha256'] = 'changed'
    if bad == 'group': changed['groups'][0]['fast'] = True
    if bad == 'conflict': changed_rows[0]['outcome'] = 'loss' if rows[0]['outcome'] == 'win' else 'win'
    if bad == 'duplicate': changed_rows.append(changed_rows[0])
    if bad == 'opponent': changed_rows[0]['opp_gen_sha256'] = 'wrong'
    if bad == 'pairing': changed_rows[0]['opp_deck'] = ['Golem']
    if bad == 'truncated': changed_rows[0]['wall_truncated'] = True
    b = part(tmp_path/'B', changed, changed_rows, 'P1,P2,P3')
    if bad == 'schedule':
        p = json.loads((b/'plan.json').read_text())
        p['jobs'][0]['seeds'][0] += 100
        L.dump(b/'plan.json', p)
    inputs = [b] if bad == 'pairing' else [a, b]
    out = tmp_path/'merged'
    result = cli(out, '--merge', *inputs)
    assert result.returncode == 1
    assert (out/'SUMMARY.txt').read_text().startswith('FAILED:')
    assert (out/'DONE').read_text() == 'exit_code=1\n'


def test_split_cli_and_optional_p4(tmp_path):
    m = manifest()
    m['pools'] = [p for p in m['pools'] if p['id'] != 'P4']
    path = tmp_path/'manifest.json'
    L.dump(path, m)
    out = tmp_path/'plan'
    result = cli(out, '--manifest', path, '--pools', 'P1,P3', '--quick', '--plan-only', '--workers', '25')
    assert result.returncode == 0, result.stderr
    plan = json.loads((out/'plan.json').read_text())
    assert plan == L.schedule(m, 120, pools='P1,P3')
    assert '25 workers' in (out/'SUMMARY.txt').read_text()
    assert cli(tmp_path/'bad', '--manifest', path, '--pools', 'P4', '--plan-only').returncode == 1


def test_merge_refuses_used_output(tmp_path):
    m, _, rows = synthetic()
    a = part(tmp_path/'A', m, rows)
    out = tmp_path/'merged'
    assert cli(out, '--merge', a).returncode == 0
    saved = (out/'SUMMARY.txt').read_bytes()
    assert cli(out, '--merge', a).returncode != 0
    assert (out/'SUMMARY.txt').read_bytes() == saved


def test_split_execution_scores_only_selected_pools(tmp_path, monkeypatch):
    m, _, rows = synthetic()
    path = tmp_path/'manifest.json'
    L.dump(path, m)
    out = tmp_path/'part'
    def fake_run(plan, directory, dest, workers):
        assert plan == L.schedule(m, 8, pools='P4,P5')
        assert workers == 25
        (dest/'matches.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows if r['pool'] in ('P4', 'P5')))
    monkeypatch.setattr(L, 'run', fake_run)
    monkeypatch.setattr(sys, 'argv', ['livecal.py', '--manifest', str(path), '--out', str(out),
                                    '--k', '8', '--pools', 'P4,P5', '--workers', '25', '--bootstrap', '30'])
    assert L.main() == 0
    report = json.loads((out/'score.json').read_text())
    assert set(report['pools']) == {'P4', 'P5'}
    assert 'PART ONLY' in (out/'SUMMARY.txt').read_text()
    assert (out/'DONE').read_text() == 'exit_code=0\n'


def test_empty_merge_rejects_invalid_bootstrap(tmp_path):
    m, _, _ = synthetic()
    a = part(tmp_path/'A', m, [], 'P1')
    out = tmp_path/'merged'
    assert cli(out, '--merge', a, '--bootstrap', '0').returncode == 1
    assert 'bootstrap count must be positive' in (out/'SUMMARY.txt').read_text()
