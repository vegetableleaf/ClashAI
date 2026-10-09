"""--tau-threatened X: while a tower of mine lost HP within 2 s AND an enemy unit is within 8 tiles of THAT tower, the gate
threshold is X instead of the phase tau. Card and cell stay the model's; off (default) = byte-identical, RNG included.
One helper (decision_options.tau_threat_state / threat_taus) for SIM match_kwargs + decide_batch and live_gen_v2."""
import copy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline import live_gen_v2
from pipeline.decision_options import (DecisionOptions, add_arguments, config_from_args, match_kwargs, tau_threat_state,
                                       threat_taus)
from pipeline.live_mem import deck_of
from pipeline.obs_contract import _ANCHOR_XY, TOWER_ORDER
from pipeline.tests.test_decision_options import two_class_logits
from pipeline.tests.test_live_decision_options import DEF, HAND, OFF, icebow_frame, pilot

DEPLOYED = DecisionOptions(tau_phase=(.35, .45, .55))              # the phase gate alone; hazard combo tested below
ON = replace(DEPLOYED, tau_threatened=.2)
AFFORD_3 = np.array([[True, False, False, False]])      # Knight 3 affordable at 3 elixir
K, L, R = 0, 1, 2                                       # my tower index (TOWER_ORDER)


def board(t, my_hp=(1.0, 1.0, 1.0), near=()):
    """A live BoardState (my frame); ``near`` = [(tower index, tiles from it toward the river, side)] units."""
    bs = pilot(DEPLOYED).row(icebow_frame(1000))[1]['bs']
    towers = tuple(replace(tw, hp_frac=h, alive=h > 0) for tw, h in zip(bs.towers[:3], my_hp)) + bs.towers[3:]
    u0 = bs.units[0]
    units = tuple(replace(u0, side=side, x=_ANCHOR_XY[TOWER_ORDER[i]][0], y=_ANCHOR_XY[TOWER_ORDER[i]][1] - d / 32)
                  for i, d, side in near)
    return replace(bs, t_sec=t, towers=towers, units=units)


def test_default_off_active_and_bounds():
    assert DecisionOptions().tau_threatened is None and not DecisionOptions().active
    assert DecisionOptions(tau_threatened=0.0).active and DecisionOptions(tau_threatened=1.0).active
    for bad in (-.01, 1.01, float('nan'), float('inf')):
        with pytest.raises(ValueError):
            DecisionOptions(tau_threatened=bad)
    import argparse
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert config_from_args(ap.parse_args([]))['tau_threatened'] is None
    assert config_from_args(ap.parse_args(['--tau-threatened', '.15']))['tau_threatened'] == .15


def test_threat_needs_hp_loss_and_an_enemy_near_that_tower():
    near_l = [(L, 7.9, 1)]
    s, thr = tau_threat_state(None, board(10.0, near=near_l))
    assert not thr                                                              # no history
    s, thr = tau_threat_state(s, board(10.5, (1.0, .9, 1.0), near_l))
    assert thr                                                                  # L lost HP, enemy 7.9 tiles from L
    assert tau_threat_state(s, board(10.5, (1.0, .9, 1.0), near_l)) == (s, True)   # idempotent on a repeated board
    s2, thr = tau_threat_state(s, board(12.5, (1.0, .9, 1.0), near_l))
    assert thr                                                                  # 2.0 s after the loss: in the window
    assert not tau_threat_state(s2, board(12.6, (1.0, .9, 1.0), near_l))[1]     # 2.1 s: out


def test_other_tower_enemy_far_enemy_or_own_unit_do_not_count():
    def run(near, hp=(1.0, .9, 1.0)):
        s, _ = tau_threat_state(None, board(10.0, near=near))
        return tau_threat_state(s, board(10.5, hp, near))[1]
    assert run([(L, 7.9, 1)])
    assert not run([(L, 8.2, 1)])                                               # beyond 8 tiles
    assert not run([(L, 3.0, 0)])                                               # my own unit
    assert not run([(R, 3.0, 1)])                                               # near R, but R lost nothing
    assert not run([])                                                          # no enemy at all
    assert run([(L, 3.0, 1), (R, 3.0, 1)])
    assert run([(L, 3.0, -1)])                                                  # unknown team (live) counts as enemy
    # an enemy that arrives after the loss still threatens within the window; a tower that fell keeps its place
    s, _ = tau_threat_state(None, board(10.0))
    s, thr = tau_threat_state(s, board(10.5, (1.0, .9, 1.0)))
    assert not thr
    s, thr = tau_threat_state(s, board(11.5, (1.0, .9, 1.0), [(L, 5.0, 1)]))
    assert thr
    s, thr = tau_threat_state(s, board(12.0, (1.0, 0.0, 1.0), [(L, 5.0, 1)]))
    assert thr


def test_enemy_tower_damage_is_not_a_threat():
    bs0 = board(10.0, near=[(L, 3.0, 1)])
    s, _ = tau_threat_state(None, bs0)
    hit = replace(bs0, t_sec=10.5, towers=bs0.towers[:3] + tuple(replace(t, hp_frac=.5) for t in bs0.towers[3:]))
    assert not tau_threat_state(s, hit)[1]


def test_threat_taus():
    assert threat_taus(DEPLOYED, .35, None) == .35 and threat_taus(DEPLOYED, .35, [True]) == .35   # off: untouched
    assert threat_taus(ON, .35, [True, False]).tolist() == [.2, .35]
    assert threat_taus(ON, np.array([.35, .45]), [True, True]).tolist() == [.2, .2]
    assert threat_taus(ON, np.array([.35, .45]), [False, False]).tolist() == [.35, .45]
    with pytest.raises(ValueError):
        threat_taus(ON, .35, None)


# ---- SIM decide_batch ---------------------------------------------------------------------------------------------
class SimModel:
    def cell_logits(self, enc, slot):
        return two_class_logits(.4, OFF, DEF)[0].repeat(len(slot), 1)


def sim(options, p, threatened, *, seed=0, card=(9., 0., 0., 0.), t=10.0):
    heads = {'card': torch.tensor([list(card)])}
    m = SimpleNamespace(cfg={k: getattr(options, k) for k in DecisionOptions.__dataclass_fields__} | dict(
        grid='lattice', decide_every=10), tag='t', k=0, deck=SimpleNamespace(cards=['knight', 'xbow', 'rocket', 'tesla']),
        _cur=(0, board(t, (1.0, .9, 1.0), [(L, 3.0, 1)] if threatened else []), None),
        rng_decision_options=np.random.default_rng(seed))
    m.tau_threat_state = tau_threat_state(None, board(t - .5))[0] if options.tau_threatened is not None else None
    kw = match_kwargs([m])
    out = E.live_decide_batch(SimModel(), {'g': torch.zeros(1, 2)}, heads, [p], AFFORD_3, np.zeros(1, bool), tau=.35,
                              decision_options=kw.pop('decision_options'), **kw)[0]
    return out, m, kw


def test_sim_threatened_row_plays_at_p_above_x_with_the_models_own_card_and_cell():
    off, _, _ = sim(replace(ON, tau_threatened=None), .25, True)
    assert not off['play']                                                      # p .25 < phase tau .35 (1x)
    on, m, kw = sim(ON, .25, True)
    assert kw['tau_threat'] == [True] and on['play'] and on['why'] == 'tau_threat'
    assert (on['slot'], on['cell']) == (0, sim(ON, .8, True)[0]['cell'])        # the model's argmax card; same cell
    assert not sim(ON, .15, True)[0]['play']                                    # p below X still waits
    quiet, _, kw = sim(ON, .25, False)
    assert kw['tau_threat'] == [False] and not quiet['play']                    # not threatened: the phase tau
    assert sim(ON, .8, False)[0]['why'] == 'gate'                               # normal gate plays unchanged


def test_sim_off_is_byte_identical_and_adds_nothing():
    for threatened in (False, True):
        for p in (.1, .25, .5):
            a, m, kw = sim(DEPLOYED, p, threatened, seed=3)
            assert 'tau_threat' not in kw and not hasattr(m, 'tau_threat')
    # a threshold X above tau is taken literally (X replaces tau while threatened)
    assert not sim(replace(ON, tau_threatened=.6), .5, True)[0]['play']


# ---- live pilot ---------------------------------------------------------------------------------------------------
def _hit(frame, side, mine_hp):
    for e in frame['entities']:
        if e['kind'] == 12 and e['side'] == side:
            e['hp'] = mine_hp
    return frame


def _add_enemy(frame, side, d=4000):
    """An enemy knight d native units from MY king toward the river."""
    king = next(e for e in frame['entities'] if e['kind'] == 12 and e['side'] == side)
    u = copy.deepcopy(next(e for e in frame['entities'] if e['kind'] == 15))
    u.update(side=1 - side, x=king['x'], y=king['y'] + (d if side == 0 else -d), address='0xbeef')
    frame['entities'].append(u)
    return frame


def _live(options, side, enemy, hp_falls=True, n=12, gate_p=.25, seed=0):
    p = pilot(options, gate_p=gate_p, seed=seed)
    p.match_index, p.decision_seed = -1, 0
    p.reset_match()
    p.rng_decisions = np.random.default_rng(seed)
    out = []
    for i in range(n):
        f = icebow_frame(tick=1000 + 10 * i, side=side)
        next(pl for pl in f['players'] if pl['side'] == side)['elixir_raw'] = 30000      # 3 elixir
        if enemy:
            _add_enemy(f, side)
        out.append(p.decide(_hit(f, side, 2000 - (50 * i if hp_falls else 0))))
    return p, out


@pytest.mark.parametrize('side', [0, 1])
def test_live_plays_while_threatened_and_not_otherwise(side):
    _, hit = _live(ON, side, enemy=True)
    assert [d['tau_threat'] for d in hit] == [False] + [True] * 11
    assert not hit[0]['play'] and all(d['play'] and d['gate_tau'] == .2 for d in hit[1:])
    assert {d['hand_pos'] for d in hit} == {d['hand_pos'] for d in _live(ON, side, enemy=False, gate_p=.8)[1]}   # model's card
    _, no_enemy = _live(ON, side, enemy=False)
    assert not any(d['tau_threat'] for d in no_enemy) and not any(d['play'] for d in no_enemy)
    _, no_hit = _live(ON, side, enemy=True, hp_falls=False)
    assert not any(d['tau_threat'] for d in no_hit) and not any(d['play'] for d in no_hit)
    _, below = _live(ON, side, enemy=True, gate_p=.15)
    assert not any(d['play'] for d in below)


@pytest.mark.parametrize('side', [0, 1])
def test_live_off_reads_no_state_and_is_unchanged(monkeypatch, side):
    def boom(*a, **k):
        raise AssertionError('tau_threat_state called with the option off')
    monkeypatch.setattr(live_gen_v2, 'tau_threat_state', boom)
    p, out = _live(DEPLOYED, side, enemy=True)
    assert not any(d['play'] for d in out) and not any('tau_threat' in d for d in out)
    assert p._tau_threat_state is None
    p.reset_match()
    assert p._tau_threat_state is None


def test_live_reset_match_clears_the_state():
    p, _ = _live(ON, 1, enemy=True, n=3)
    assert p._tau_threat_state is not None
    p.reset_match()
    assert p._tau_threat_state is None


@pytest.mark.parametrize('side', [0, 1])
def test_sim_and_live_agree_on_threat_and_play(side):
    """The live pilot's own decision boards through SIM's match_kwargs + live_decide_batch (p=.25, X=.2, tau .35):
    same flag at every decision and the same play / slot."""
    _, names = deck_of(icebow_frame(side=side), side)
    hand_names = [names[i] for i in HAND]
    cell = two_class_logits(.4, OFF, DEF)[0]
    cfg = {k: getattr(ON, k) for k in DecisionOptions.__dataclass_fields__} | dict(grid='lattice', decide_every=10)
    p = pilot(ON, gate_p=.25, cell=cell)
    p.match_index, p.decision_seed = -1, 0
    p.reset_match()
    m = SimpleNamespace(cfg=cfg, tag='t', k=0, deck=SimpleNamespace(cards=hand_names))
    plays = flags = 0
    for i in range(30):
        f = icebow_frame(tick=1000 + 10 * i, side=side)
        next(pl for pl in f['players'] if pl['side'] == side)['elixir_raw'] = 30000
        if i % 9 > 2:
            _add_enemy(f, side)
        d = p.decide(_hit(f, side, 2000 - (60 * i if i % 7 < 3 else 0)))
        m._cur = (1000 + 10 * i, d['bs'], None)
        m.rng_decision_options = np.random.default_rng(0)
        kw = match_kwargs([m])
        assert kw['tau_threat'] == [d['tau_threat']]
        s = E.live_decide_batch(SimModel(), {'g': torch.zeros(1, 2)}, {'card': torch.tensor([[0., 9., 0., 0.]])},
                                [d['p_play']], AFFORD_3, np.zeros(1, bool), tau=.35,
                                decision_options=kw.pop('decision_options'), **kw)[0]
        assert (s['play'], s['slot']) == (d['play'], d['hand_pos'])
        plays += d['play']
        flags += d['tau_threat']
    assert plays > 3 and flags == plays        # every play here is a tau_threat play (p .25 < tau .35)


def test_combines_with_the_deployed_hazard_gate():
    both = replace(ON, gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0, gate_hazard_threatened=2.0)
    _, out = _live(both, 1, enemy=True)
    assert [d['tau_threat'] for d in out] == [False] + [True] * 11
    assert all(d['play'] and d['gate_tau'] == .2 and not d['hazard_play'] for d in out[1:])   # the threshold plays, no draw
