"""Adversarial geometry, decision parity and seeded integration checks; CPU only."""
import ast
import copy
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline.decision_options import (DecisionOptions, filtered_probabilities, choose_slot, choose_cells,
                                      rocket_area_scores, rocket_radius_tiles, match_kwargs)
from pipeline.live_gen_v2 import GenPilot
from pipeline.tests.test_live_gen_afford import pilot, frame

torch.set_num_threads(1)


@pytest.mark.parametrize('ratio,expected', [(0.5, [.6, .4]), (0.7, [1, 0])])
def test_confident_replacement_is_measured_not_silently_blocked(ratio, expected):
    np.testing.assert_allclose(filtered_probabilities(np.log([.6, .4]), [True, True], ratio), expected)


def test_filter_before_temperature_and_affordability():
    p = filtered_probabilities(np.log([.9, .06, .04]), [False, True, True], .7, .2)
    np.testing.assert_array_equal(p, [0, 1, 0])
    np.testing.assert_array_equal(filtered_probabilities([4, 5], [False, False]), [0, 0])
    np.testing.assert_allclose(filtered_probabilities([1, 1, 0], [True]*3, 1), [.5, .5, 0])


@pytest.mark.parametrize('kwargs', [{'card_ratio': 0}, {'card_ratio': 1.1}, {'card_T': 0},
                                    {'card_T': float('nan')}, {'spell_aim': 'tower_rule'}])
def test_invalid_options_fail(kwargs):
    with pytest.raises(ValueError):
        DecisionOptions(**kwargs)


def test_only_near_ties_draw_and_stream_is_reproducible():
    rng = np.random.default_rng(123); before = copy.deepcopy(rng.bit_generator.state)
    options = DecisionOptions(card_choice='filtered')
    assert choose_slot(torch.tensor([9., 0.]), [True, True], options, rng) == 0
    assert choose_slot(torch.tensor([0., 0.]), [True, True], options, rng, playing=False) == 0
    assert choose_slot(torch.tensor([0., 0.]), [False, False], options, rng) == -1
    assert rng.bit_generator.state == before
    def draws(seed):
        stream = np.random.default_rng(seed)
        return [choose_slot(torch.zeros(2), [True, True], options, stream) for _ in range(40)]
    assert draws(7) == draws(7)
    assert set(draws(7)) == {0, 1}
    assert draws(7) != draws(8)


def cluster_logits():
    p = torch.zeros(1, 2304)
    p[0, 50*36+28] = .2  # highest individual cell, away from the learned target cluster
    for y in range(12, 15):
        for x in range(6, 9):
            p[0, y*36+x] = .8/9
    return p.log()


def test_area_mass_selects_broad_cluster_without_tower_prior():
    logits = cluster_logits()
    default = int(choose_cells(logits, ['Rocket'], DecisionOptions())[0])
    selected = int(choose_cells(logits, ['Rocket'], DecisionOptions(spell_aim='rocket_area'))[0])
    assert default == 50*36+28
    assert np.linalg.norm(np.array([selected % 36, selected // 36])/2 - [3.5, 6.5]) <= rocket_radius_tiles()
    # Same probabilities on a different card do not enable the Rocket rule.
    assert int(choose_cells(logits, ['Log'], DecisionOptions(spell_aim='rocket_area'))[0]) == default


def test_disk_uses_physical_tiles_and_cannot_wrap_edges():
    p = torch.zeros(2, 2304); p[0, 0] = 1; p[1, 20*36+20] = 1
    mass = rocket_area_scores(p)
    assert rocket_radius_tiles() == 2  # checked-in game's catalog, not the inference implementation
    assert mass[0, 4] == 1 and mass[0, 4*36] == 1
    assert mass[0, 3*36+3] == 0  # 2.12 tiles diagonally
    assert mass[0, 35] == 0 and mass[0, -1] == 0
    assert mass[0, 0] == 1  # missing board cells do not get probability renormalised
    # Independent brute-force disk sum at every board location.
    xy = np.c_[np.tile(np.arange(36)/2, 64), np.repeat(np.arange(64)/2, 36)]
    expected = np.linalg.norm(xy-[10, 10], axis=1) <= 2
    np.testing.assert_array_equal(mass[1].numpy(), expected)


def test_equal_mass_prefers_learned_local_mode():
    logits = torch.full((1, 2304), -torch.inf); logits[0, 20*36+20] = 0
    assert int(choose_cells(logits, ['Rocket'], DecisionOptions(spell_aim='rocket_area'))[0]) == 20*36+20


class Model:
    def cell_logits(self, enc, slot):
        return cluster_logits().repeat(len(slot), 1)


@pytest.fixture(scope='module')
def legacy():
    root = Path(__file__).resolve().parents[2]
    source = subprocess.check_output(['git', 'show', '4b36ab2:pipeline/e1_eval.py'], cwd=root, text=True)
    tree = ast.parse(source)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('live_decide', 'live_decide_batch')]
    scope = dict(E.__dict__)
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<frozen legacy e1>', 'exec'), scope)
    return scope


def tensors():
    heads = {'card': torch.tensor([[1., 2., 0., -1.], [0., 0., 0., 0.], [2., 2., -1., 0.],
                                   [0., 9., 3., 2.], [1., 1., 1., 1.]])}
    allowed = np.array([[1, 1, 1, 1], [0, 0, 0, 0], [1, 1, 0, 1], [1, 0, 1, 1], [1, 1, 1, 1]], bool)
    return {'g': torch.zeros(5, 2)}, heads, np.array([.9, .9, .1, .35, .1]), allowed, np.array([0, 0, 0, 0, 1], bool)


def test_default_sim_is_exact_legacy_single_and_batch(legacy):
    enc, heads, p, allowed, stalled = tensors()
    for r in range(len(p)):
        args = (Model(), {k:v[r:r+1] for k,v in enc.items()}, {k:v[r:r+1] for k,v in heads.items()},
                p[r], allowed[r])
        expected = legacy['live_decide'](*args, tau=.35, stalled=stalled[r])
        assert E.live_decide(*args, tau=.35, stalled=stalled[r]) == expected
        assert E.live_decide(*args, tau=.35, stalled=stalled[r], decision_options=DecisionOptions()) == expected
    args = (Model(), enc, heads, p, allowed, stalled)
    assert E.live_decide_batch(*args, tau=.35) == legacy['live_decide_batch'](*args, tau=.35)


def test_option_sim_batch_and_single_are_identical_and_gate_unchanged():
    enc, heads, p, allowed, stalled = tensors()
    options = DecisionOptions(card_choice='filtered', card_ratio=.5, spell_aim='rocket_area')
    names = [['Rocket', 'Knight', 'Log', 'Tesla']]*len(p)
    seeds = [7, 19, 6, 42, 123]
    batch = E.live_decide_batch(Model(), enc, heads, p, allowed, stalled, tau=.35, decision_options=options,
                                rngs=[np.random.default_rng(s) for s in seeds], card_names=names)
    single = [E.live_decide(Model(), {k:v[r:r+1] for k,v in enc.items()}, {k:v[r:r+1] for k,v in heads.items()},
                           p[r], allowed[r], tau=.35, stalled=stalled[r], decision_options=options,
                           rng=np.random.default_rng(seeds[r]), card_names=names[r]) for r in range(len(p))]
    assert batch == single
    baseline = E.live_decide_batch(Model(), enc, heads, p, allowed, stalled, tau=.35)
    assert [d['play'] for d in batch] == [d['play'] for d in baseline]
    assert [d['why'] for d in batch] == [d['why'] for d in baseline]
    for r, d in enumerate(batch):
        assert d['slot'] == -1 or allowed[r, d['slot']]


def test_streams_follow_match_not_batch_order():
    def match(tag, seed):
        return SimpleNamespace(tag=tag, k=seed, cfg={'card_choice':'filtered'}, deck=SimpleNamespace(cards=['Rocket', 'Log']))
    a, b = match('a', 2), match('b', 3)
    streams = match_kwargs([a, b])['rngs']
    first = [s.random() for s in streams]
    a2, b2 = match('a', 2), match('b', 3)
    second = [s.random() for s in match_kwargs([b2, a2])['rngs']]
    assert first == second[::-1]
    assert match_kwargs([SimpleNamespace(cfg={})]) == {}


@pytest.mark.parametrize('elixir', [1.9, 3.5, 10])
def test_candidate_live_default_is_exact_legacy(elixir):
    original = pilot([0, 9, 1, 2])
    candidate = object.__new__(GenPilot); candidate.__dict__.update(copy.deepcopy(original.__dict__))
    candidate.decision_options = DecisionOptions()
    assert candidate.decide(frame(elixir)) == original.decide(frame(elixir))


def test_candidate_live_and_sim_share_selected_rocket_aim():
    candidate = object.__new__(GenPilot)
    candidate.decision_options = DecisionOptions(spell_aim='rocket_area', card_choice='filtered')
    candidate.rng_decisions = np.random.default_rng(7)
    candidate.dev, candidate.grid, candidate.gate_tau = torch.device('cpu'), 'lattice', .35
    info = dict(hand=[(1, 0), (2, 0)], costs=[6, 3], el_int=10, bs=None,
                names=['Rocket', 'Knight'], hand_deck_indices=[0, 1])
    candidate.row = lambda frame: ({}, info)
    class LiveModel:
        def __call__(self, b, card=None, form=None):
            return {'cell':cluster_logits()} if card is not None else {'gate':torch.tensor([2.]), 'card':torch.tensor([[9., 0.]])}
    candidate.model = LiveModel()
    d = candidate.decide({})
    expected = E.live_decide(Model(), {'g':torch.zeros(1, 2)}, {'card':torch.tensor([[9., 0.]])},
                             float(torch.sigmoid(torch.tensor(2.))), np.array([True, True]), tau=.35, stalled=False,
                             decision_options=candidate.decision_options, rng=np.random.default_rng(7),
                             card_names=info['names'])
    assert d['play'] == expected['play'] and d['hand_pos'] == expected['slot']
    assert d['xy'] == (expected['cell'] % 36 / 36, expected['cell'] // 36 / 64)


def test_diagnostic_maps_checkpoint_card_ids_by_name():
    from scratchpad.gauntlet.L71.decision_options.check_sampling_v2 import remap_validation_cards
    a = np.array([[0, 2, 3]])
    sub = {k: a for k in ('hand_card', 'next_card', 'deck_card', 'y_card', 'y_wait_card')}
    sub['past'] = np.array([[[3., 0, .1, .2, 1.]]])
    result, mapping = remap_validation_cards(sub, ['pad', 'new', 'rocket', 'log'], ['pad', 'rocket', 'log'], 1)
    np.testing.assert_array_equal(result['hand_card'], [[0, 1, 2]])
    assert result['past'][0, 0, 0] == 2
    assert sub['past'][0, 0, 0] == 3  # source rows preserved
    assert mapping['identity_mapping'] is False
    with pytest.raises(ValueError, match='lacks'):
        remap_validation_cards(sub, ['pad', 'new', 'rocket', 'log'], ['pad', 'rocket'], 1)


def test_active_options_follow_real_reactive_path_and_match_batched_engine():
    from pipeline.tests.test_search_s0 import runner, HOGEQ, RoyaleSelfPlayEnv
    if RoyaleSelfPlayEnv is None:
        pytest.skip('Royale venv required')
    run = runner(tail_cap=500)
    run.lcfg.update(card_choice='filtered', card_ratio=.5, card_T=.7,
                    spell_aim='rocket_area', decision_seed=17)
    actual_match = run.setup('gen', 3, HOGEQ)
    run.play('plain', actual_match)
    actual = dict(run.last_result); actual.pop('wall_s')
    assert hasattr(actual_match.learner, 'rng_decision_options')
    assert not hasattr(actual_match.opp, 'rng_decision_options')
    opp, opp_cfg = run.opps['gen']
    spec = dict(tag='s0:gen:3', opp={'id':'gen'}, learner_deck=list(E.ICEBOW_ENGINE_DECK),
                opp_deck=list(HOGEQ), learner_side=1, seed=3)
    outputs=[]
    E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(tail_cap=500), run.learner,
                         {'gen':(opp,opp_cfg)}, [(0,spec,0)], run.lcfg, 1, on_result=outputs.append)
    expected=dict(outputs[0]); expected.pop('wall_s')
    assert actual == expected


def test_seeded_runtime_frequencies_match_checked_distribution():
    options=DecisionOptions(card_choice='filtered',card_ratio=.5,card_T=.7)
    logits=np.log([.4,.3,.2,.1]); allowed=[True]*4
    expected=filtered_probabilities(logits,allowed,.5,.7)
    rng=np.random.default_rng(982)
    samples=[choose_slot(logits,allowed,options,rng) for _ in range(6000)]
    observed=np.bincount(samples,minlength=4)/len(samples)
    assert observed[3]==0
    np.testing.assert_allclose(observed,expected,atol=.025,rtol=0)


def test_e1_cli_rejects_invalid_options_before_loading(tmp_path):
    # Exercises main(), not only --help, with no model/game connection.
    with pytest.raises(ValueError, match='card_ratio'):
        E.main(['--port','0','--out',str(tmp_path/'unused'), '--card-ratio','0'])
    with pytest.raises(ValueError, match='policy live'):
        E.main(['--port','0','--out',str(tmp_path/'unused2'), '--policy','sample', '--spell-aim','rocket_area'])


def test_reactive_cli_forwards_telemetry_and_options_to_worker(tmp_path, monkeypatch):
    from pipeline import search_s0 as S
    seen=[]
    monkeypatch.setattr(S, '_init_worker', lambda args: seen.append(args))
    monkeypatch.setattr(S, '_run_job', lambda job: dict(arm=job[0], opp=job[1], seed=job[2], skipped='test'))
    S.main(['--out',str(tmp_path/'run'),'--seeds','0:1','--opps','gen','--arms','plain',
            '--behaviour-telemetry','--card-choice','filtered','--card-ratio','.7'])
    assert seen[0]['behaviour_telemetry'] is True
    assert seen[0]['decision_options']['card_choice']=='filtered'


# ---- tau_phase and xbow_class (L73 decode options) -------------------------------------------------------
from pipeline.decision_options import (add_arguments, config_from_args, options_from_config, phase_index,
                                      xbow_offensive_cells, xbow_class_choice, decide_batch)


def test_new_options_default_off_and_cli_defaults_are_inert():
    import argparse
    ap = argparse.ArgumentParser(); add_arguments(ap)
    cfg = config_from_args(ap.parse_args([]))
    assert options_from_config(cfg) == DecisionOptions() and not DecisionOptions().active
    assert cfg['tau_phase'] is None and cfg['xbow_class'] == 'argmax' and cfg['xbow_class_floor'] == .2
    on = options_from_config(config_from_args(ap.parse_args(['--tau-phase', '.4', '.45', '.5'])))
    assert on.active and on.tau_phase == (.4, .45, .5)
    assert options_from_config({'tau_phase': [.4, .45, .5]}) == on       # JSON lists compare equal to tuples
    assert DecisionOptions(xbow_class='class_sample').active


@pytest.mark.parametrize('kwargs', [{'tau_phase': (.4, .5)}, {'tau_phase': (.4, .5, 1.2)},
                                    {'tau_phase': (.4, float('nan'), .5)}, {'xbow_class': 'sample'},
                                    {'xbow_class_floor': .6}, {'xbow_class_floor': -.1}])
def test_invalid_new_options_fail(kwargs):
    with pytest.raises(ValueError):
        DecisionOptions(**kwargs)


def test_phase_boundaries_follow_tick_seconds():
    t = [0, 119.95, 120, 179.95, 180, 400, 2399 * 0.05, 2400 * 0.05, 3599 * 0.05, 3600 * 0.05]
    np.testing.assert_array_equal(phase_index(t), [0, 0, 1, 1, 2, 2, 0, 1, 1, 2])


def test_tau_phase_gate_uses_the_row_phase_and_keeps_anti_stall():
    enc = {'g': torch.zeros(4, 2)}
    heads = {'card': torch.tensor([[1., 0, 0, 0]] * 4)}
    allowed = np.ones((4, 4), bool)
    p = np.array([.5, .5, .5, .3])
    stalled = np.array([0, 0, 0, 1], bool)
    out = decide_batch(Model(), enc, heads, p, allowed, stalled, tau=.35, device='cpu',
                       options=DecisionOptions(tau_phase=(.45, .55, .45)), rngs=[None] * 4, card_names=None,
                       t_sec=[119.95, 120.0, 180.0, 120.0])
    assert [d['play'] for d in out] == [True, False, True, True]
    assert [d['why'] for d in out] == ['gate', 'wait', 'gate', 'stall']
    with pytest.raises(ValueError, match='decision time'):
        decide_batch(Model(), enc, heads, p, allowed, stalled, tau=.35, device='cpu',
                     options=DecisionOptions(tau_phase=(.45, .55, .45)), rngs=[None] * 4, card_names=None)


def test_uniform_tau_phase_and_confident_xbow_reproduce_default_decisions():
    enc, heads, p, allowed, stalled = tensors()
    base = E.live_decide_batch(Model(), enc, heads, p, allowed, stalled, tau=.35)
    names = [['Rocket', 'Knight', 'Log', 'x_bow']] * len(p)
    same = E.live_decide_batch(Model(), enc, heads, p, allowed, stalled, tau=.35,
                               decision_options=DecisionOptions(tau_phase=(.35, .35, .35)),
                               rngs=[np.random.default_rng(1)] * len(p), card_names=names, t_sec=[10, 130, 200, 0, 5])
    assert same == base


def test_xbow_geometry_uses_alive_towers_and_exact_reach():
    all_alive = xbow_offensive_cells((True, True, True), 'lattice')
    assert not xbow_offensive_cells((False, False, False), 'lattice').any()
    # (+1, +13) tiles from the left princess (3.5, 6.5) is the validated reach sqrt(170) = 13.03840
    edge, past = 39 * 36 + 9, 40 * 36 + 9                     # lattice (4.5, 19.5) / (4.5, 20.0)
    assert all_alive[edge] and not all_alive[past]
    assert xbow_offensive_cells((False, True, False), 'lattice')[edge]
    assert not xbow_offensive_cells((True, False, True), 'lattice')[edge]
    assert all_alive[18 * 36 + 18]                             # own half next to the river reaches the king
    assert not all_alive[63 * 36 + 18]                         # behind my king: defensive


def two_class_logits(d_mass, off_cells=(100, 101), def_cells=(2000, 2001)):
    p = torch.full((2304,), 1e-12)
    p[off_cells[0]], p[off_cells[1]] = (1 - d_mass) * .6, (1 - d_mass) * .4
    p[def_cells[0]], p[def_cells[1]] = d_mass * .3, d_mass * .7
    off = np.zeros(2304, bool); off[list(off_cells)] = True
    return p.log(), off


def test_floor_keeps_confident_class_deterministic_and_draws_only_near_balance():
    rng = np.random.default_rng(5); before = copy.deepcopy(rng.bit_generator.state)
    logits, off = two_class_logits(.25)
    assert xbow_class_choice(logits, off, .3, rng) == (100, False, False)      # minority .25 < floor .3: majority
    assert rng.bit_generator.state == before                                   # and no RNG consumed
    logits, off = two_class_logits(.9)
    assert xbow_class_choice(logits, off, .2, rng) == (2001, True, False)      # argmax INSIDE the defensive class
    assert rng.bit_generator.state == before
    logits, off = two_class_logits(.25)
    draws = [xbow_class_choice(logits, off, .2, rng) for _ in range(4000)]
    assert {c for c, _, s in draws} == {100, 2001} and all(s for _, _, s in draws)
    assert abs(np.mean([dfn for _, dfn, _ in draws]) - .25) < .025          # Bernoulli(D)


def test_xbow_class_sample_is_seeded_and_touches_only_xbow_rows():
    logits, off = two_class_logits(.4, off_cells=(5 * 36 + 9, 5 * 36 + 10))   # near the enemy king: offensive
    class XModel:
        def cell_logits(self, enc, slot):
            return logits.repeat(len(slot), 1)
    enc = {'g': torch.zeros(3, 2)}
    heads = {'card': torch.tensor([[0., 9, 0, 0], [9., 0, 0, 0], [0., 9, 0, 0]])}
    names = [['Rocket', 'x_bow', 'Log', 'Knight']] * 3
    opts = DecisionOptions(xbow_class='class_sample', xbow_class_floor=.2)
    def run(seed):
        return [decide_batch(XModel(), enc, heads, np.full(3, .9), np.ones((3, 4), bool), np.zeros(3, bool),
                             tau=.35, device='cpu', options=opts, rngs=[np.random.default_rng([seed, r]) for r in range(3)],
                             card_names=names, enemy_alive=[(True, True, True)] * 3, grid='lattice') for _ in range(1)][0]
    a, b = run(3), run(3)
    assert a == b
    assert a[1]['cell'] == int(logits.argmax())                               # Rocket row: plain argmax
    cells = {d['cell'] for s in range(40) for d in run(s) if d['slot'] == 1}
    assert cells == {5 * 36 + 9, 2001}                                        # both classes, argmax inside each
    with pytest.raises(ValueError, match='enemy tower'):
        decide_batch(XModel(), enc, heads, np.full(3, .9), np.ones((3, 4), bool), np.zeros(3, bool), tau=.35,
                     device='cpu', options=opts, rngs=[np.random.default_rng(0)] * 3, card_names=names)


def test_match_kwargs_supplies_phase_time_and_enemy_towers_from_the_prepared_board():
    from pipeline.obs_contract import Tower
    towers = tuple(Tower(s, k, l, 1., a) for s, k, l, a in
                   [(0, 'king', None, 1), (0, 'princess', 'L', 1), (0, 'princess', 'R', 1),
                    (1, 'king', None, 1), (1, 'princess', 'L', 0), (1, 'princess', 'R', 1)])
    m = SimpleNamespace(tag='a', k=1, cfg={'xbow_class': 'class_sample', 'grid': 'lattice'},
                        deck=SimpleNamespace(cards=['x_bow']), _cur=(2400, SimpleNamespace(t_sec=120.0, towers=towers), None))
    kw = match_kwargs([m])
    assert kw['t_sec'] == [120.0] and kw['enemy_alive'] == [(True, False, True)] and kw['grid'] == 'lattice'
    assert 't_sec' not in match_kwargs([SimpleNamespace(tag='b', k=1, cfg={'card_choice': 'filtered'},
                                                        deck=SimpleNamespace(cards=['x_bow']))])


def test_e1_cli_rejects_invalid_new_options_before_loading(tmp_path):
    with pytest.raises(ValueError, match='xbow_class_floor'):
        E.main(['--port', '0', '--out', str(tmp_path / 'u'), '--xbow-class', 'class_sample', '--xbow-class-floor', '.7'])
    with pytest.raises(ValueError, match='policy live'):
        E.main(['--port', '0', '--out', str(tmp_path / 'u2'), '--policy', 'sample', '--tau-phase', '.4', '.45', '.5'])
