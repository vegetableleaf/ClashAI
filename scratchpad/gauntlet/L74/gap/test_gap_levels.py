"""Opt-in level-16 evaluation routing; no engine match or checkpoint load required."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gap  # noqa: E402
from pipeline import rl_royale as R, search_s0 as S  # noqa: E402


ALL_ARMS = (*gap.ARMS, *gap.HEAD_ARMS, *gap.SWEEP)
JOB = dict(checkpoint='learner.pt', opponent=dict(path='opponent.pt', temperature=.1), seeds=[741200, 741201], fast=False)


@pytest.mark.parametrize('arm', ALL_ARMS)
def test_command_default_and_none_unchanged_and_all16_routes_every_arm(arm, tmp_path):
    args = (arm, JOB, tmp_path/'census.json', tmp_path/'out', 'python')
    default = gap.command(*args)
    assert gap.command(*args, levels='none') == default
    assert default[1:3] == [str(gap.LIVE/'livecal.py'), '--worker']
    assert '--levels' not in default
    assert '--live-levels' not in default
    all16 = gap.command(*args, levels='all16')
    assert all16[1:3] == [str(gap.HERE/'gap.py'), '--worker-all16']
    assert all16[:1] + all16[3:] == default[:1] + default[3:]


@pytest.mark.parametrize('level_args,expected', [([], 'none'), (['--levels', 'none'], 'none'),
                                               (['--levels', 'all16'], 'all16')])
def test_main_forwards_levels_to_every_requested_arm(monkeypatch, tmp_path, level_args, expected):
    monkeypatch.setattr(sys, 'argv', ['gap.py', '--out', str(tmp_path), '--arms', ','.join(ALL_ARMS), *level_args])
    monkeypatch.setattr(gap, 'prepare', lambda *args: {'jobs': []})
    monkeypatch.setattr(gap, 'summarize', lambda *args: None)
    runs = []
    monkeypatch.setattr(gap, 'run_arm', lambda *args: runs.append(args))
    gap.main()
    assert [args[0] for args in runs] == list(ALL_ARMS)
    assert [args[-1] for args in runs] == [expected] * len(ALL_ARMS)


def test_all16_preserves_existing_live_level_extra_flags(tmp_path):
    args = ('D3', JOB, tmp_path/'census.json', tmp_path/'out', 'python')
    extra = ('--live-levels', '--ability-stats')
    default = gap.command(*args, extra=extra)
    assert default[-len(extra):] == list(extra)
    assert gap.command(*args, extra=extra, levels='none') == default
    all16 = gap.command(*args, extra=extra, levels='all16')
    assert all16[:1] + all16[3:] == default[:1] + default[3:]


@pytest.mark.parametrize('measured_live_levels', [False, True])
def test_worker_uses_real_draw_for_every_spec_before_match_creation(monkeypatch, measured_live_levels):
    captured = []
    draws = []
    real_draw = R.draw_live_levels
    def draw(*args):
        draws.append(args)
        return real_draw(*args)
    monkeypatch.setattr(R, 'draw_live_levels', draw)
    monkeypatch.setattr(S.E, 'SelfPlayMatch', lambda env, spec, *args: captured.append(spec) or spec)
    monkeypatch.setattr(S, '_W', {})
    monkeypatch.setattr(S, 'live_cfg', lambda *args, **kwargs: {'opp_elixir': 'counter'})
    def init_worker(args):
        S._W['runner'] = SimpleNamespace(make_env=lambda: None, lcfg={}, learner=None, opps={'gen': (None, {})})
        if args.get('live_levels'):
            S._W['runner'].live_levels = {'measured_table': 'must be overridden by all16'}
    monkeypatch.setattr(S, '_init_worker', init_worker)
    decks = [list(S.E.ICEBOW_ENGINE_DECK),
             ['HogRider', 'Earthquake', 'Log', 'Cannon', 'Musketeer', 'IceSpirits', 'Skeletons', 'Valkyrie']]
    worker_args = ['--arms', 'plain', '--workers', '1'] + (['--live-levels'] if measured_live_levels else [])
    def run(args):
        assert args == worker_args
        assert S.live_cfg()['stall_elixir'] is None
        S._init_worker({'live_levels': '--live-levels' in args})
        for seed in (741200, 741201):
            for deck in decks:
                S.Runner.setup(S._W['runner'], 'gen', seed, deck)
        return 0
    monkeypatch.setattr(S, 'main', run)
    monkeypatch.setattr(sys, 'argv', ['gap.py', '--worker-all16', *worker_args])
    assert gap.main() == 0
    assert S._init_worker is init_worker
    assert len(captured) == len(draws) == 4
    assert {spec['learner_side'] for spec in captured} == {0, 1}
    for spec, draw_args in zip(captured, draws):
        assert draw_args[0] == R._live_level_table('all16')
        assert draw_args[1:3] == (spec['learner_deck'], spec['opp_deck'])
        assert spec['levels'] == {'learner': {'cards': [16] * 8, 'tower': 16},
                                  'opp': {'cards': [16] * 8, 'tower': 16, 'profile': 0}}


def test_unconfigured_runner_spec_has_no_levels(monkeypatch):
    monkeypatch.setattr(S.E, 'SelfPlayMatch', lambda env, spec, *args: spec)
    run = SimpleNamespace(make_env=lambda: None, lcfg={}, learner=None, opps={'gen': (None, {})})
    deck = list(S.E.ICEBOW_ENGINE_DECK)
    assert S.Runner.setup(run, 'gen', 741200, deck) == {
        'tag': 's0:gen:741200', 'opp': {'id': 'gen'}, 'learner_deck': deck,
        'opp_deck': deck, 'learner_side': 0, 'seed': 741200}
