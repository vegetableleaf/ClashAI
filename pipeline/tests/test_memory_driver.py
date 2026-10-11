from pipeline.tests.memory_fixtures import tmp_path
import copy
import json
from pathlib import Path
import subprocess
import torch
import pytest

from scratchpad.gauntlet.L74.memory import driver as D


def test_three_memory_exploiters_and_plain_training():
    base = dict(stall_elixir=None)
    p = D.plans()
    assert len(p) == 3
    assert [x['main_target'] for x in p] == [20, 40, 60]
    for plan in p:
        assert plan['exploiter_init'] == plan['frozen']
        c = D.config(base, 'main', plan, 'decks', [], 'memory.pt', 'data.npz', 256)
        assert c['history_events'] and c['hero_abilities']
        assert c['league_pfsp'] == 'hard' and c['opp_style'] == 'on'
        assert c['stall_elixir'] is None and not c['branch_gate']
        assert c['init'] == 'memory.pt'
        exp = D.config(base, 'exploiter', plan, 'decks', [], 'memory.pt', 'data.npz', 256)
        assert exp['init'] == plan['frozen'] == exp['league_frozen_opponent']


def test_yardstick_command_pinned():
    cmd = D.A.eval_command('memory.pt', 'out', D.A.EVO, 30000)
    assert cmd[cmd.index('--seeds')+1] == '30000:30480'
    assert cmd[cmd.index('--opp-gen')+1] == str(D.A.CAL_C)
    assert cmd[cmd.index('--opp-T')+1] == '0.1'
    assert all(flag in cmd for flag in D.A.LIVE_FLAGS)


def test_ablation_keeps_all_weights(tmp_path):
    src, out = tmp_path/'src.pt', tmp_path/'out.pt'
    ck = dict(model={'history.cfg': torch.tensor([8, 16, 1, 4]), 'history.gate': torch.ones(32)}, args={'history_events': True})
    torch.save(ck, src)
    D.ablate(src, out)
    actual = torch.load(out, weights_only=True)
    assert actual['args']['history_zero']
    assert all(torch.equal(v, actual['model'][k]) for k, v in ck['model'].items())


def populate(root, games=3):
    for arm in ('old', 'memory', 'zero'):
        for census in ('evo', 'lad'):
            path = root/f'{arm}_{census}'
            path.mkdir(parents=True)
            rows = [dict(tag=str(i), outcome='win' if arm == 'memory' else 'loss', opp_deck=['Knight', 'Rocket']) for i in range(games)]
            (path/'matches.jsonl').write_text('\n'.join(map(json.dumps, rows)))


def test_report_requires_every_pair_and_reports_ablation(tmp_path):
    populate(tmp_path)
    text = D.report(tmp_path, 3)
    assert '6 paired games' in text and 'Memory benefit: shown' in text and 'by opponent archetype' in text
    path = tmp_path/'zero_evo/matches.jsonl'
    path.write_text(path.read_text().splitlines()[0])
    with pytest.raises(ValueError, match='incomplete'):
        D.report(tmp_path, 3)


def test_report_rejects_changed_decks(tmp_path):
    populate(tmp_path)
    path = tmp_path/'zero_evo/matches.jsonl'
    path.write_text(path.read_text().replace('Knight', 'Giant'))
    with pytest.raises(ValueError, match='decks differ'):
        D.report(tmp_path, 3)


def test_shell_lock_order_gate_and_phase_completion():
    script = D.REPO/'scratchpad/gauntlet/L74/memory/run_memory.sh'
    source = script.read_text()
    assert source.index('WAIT_FOR') < source.index('flock ')
    assert 'flock /workspace/gpu.lock flock /workspace/cpu.lock' in source
    assert 'for phase in P1 P2 P3 P4' in source
    assert 'touch "$out/DONE"' in source and 'SUMMARY.txt' in source


def test_phase_three_orchestration_and_resume_without_sim(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import yaml
    monkeypatch.setattr(D, 'REPO', tmp_path)
    monkeypatch.setattr(D, 'recipe', lambda a: {'fixed': 'recipe'})
    (tmp_path/'pipeline').mkdir()
    (tmp_path/'pipeline/rl_royale.yaml').write_text(yaml.safe_dump({}))
    results = tmp_path/'results'
    (results/'MEMP2').mkdir(parents=True)
    (results/'MEMP2/SUCCESS').touch()
    calls = []

    def fake_train(c, name, out):
        path = tmp_path/D.A.checkpoint(name)
        if path.exists():
            ck = torch.load(path, weights_only=True)
        else:
            ck = dict(model={'history.cfg': torch.tensor([8,16,1,4]), 'w': torch.zeros(1)},
                      rl=dict(league={'snapshots': [], 'ratings': {}}, update=0))
        if 'league_frozen_opponent' in c:
            snapshot = torch.load(tmp_path/c['league_frozen_opponent'], weights_only=True)
            assert 'rl' not in snapshot and 'history.cfg' in snapshot['model']
            assert c['init'] == c['league_frozen_opponent']
        ck['rl']['update'] = c['max_updates']
        ck['model']['w'] = torch.tensor([float(c['max_updates'])])
        D.A.save_checkpoint(path, ck)
        D.A.save_checkpoint(path.with_name(f"{name}_u{c['max_updates']:04d}.pt"), ck)
        calls.append((name, c))
        return ck

    def fake_run(cmd, log):
        assert 'mk_weighted_decks.py' in str(cmd[1])
        Path(cmd[3]).write_text(json.dumps({'decks': [dict(engine=['Golem'], sides=10), dict(engine=['HogRider'], sides=90)]}))

    monkeypatch.setattr(D.A, 'train', fake_train)
    monkeypatch.setattr(D.A, 'run', fake_run)
    a = SimpleNamespace(results=results, phase='P3', prefix='test_memory', cap=8)
    D.execute(a)
    assert len(calls) == 7
    assert len(calls[-1][1]['league_external']) == 3
    assert calls[-1][1]['max_updates'] == 80
    state = json.loads((results/'MEMP3/cycles.json').read_text())
    assert state['completed'] == [1, 2, 3]
    D.execute(a)
    assert len(calls) == 7  # receipt verifies, no duplicate training
    monkeypatch.setattr(D, 'recipe', lambda a: {'fixed': 'changed'})
    with pytest.raises(ValueError, match='recipe changed'):
        D.execute(a)
