"""--xbow-dead-lane block (owner 2026-10-08: dead-lane X-Bows give little value; never go for the king): the X-Bow never
takes a cell that reaches the enemy king or a destroyed princess's position but no alive princess."""
import argparse
import copy
import itertools
import math
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline import live_gen_v2
from pipeline.decision_options import (XBOW_REACH_TILES, DecisionOptions, add_arguments, choose_cells,
                                      config_from_args, decide_batch, match_kwargs, options_from_config,
                                      xbow_dead_lane_cells, xbow_offensive_cells)
from pipeline.live_mem import deck_of
from pipeline.model_v3 import cell_xy
from pipeline.tests.test_lethal_rocket import towers as raw_towers
from pipeline.tests.test_live_decision_options import HAND, icebow_frame, pilot, sim_decide

BLOCK = DecisionOptions(xbow_dead_lane='block')
# the deployed bundle's decision options (scratchpad/gauntlet/L70/live/LIVE_OPTIONS minus the live-only flags)
BUNDLE = dict(xbow_class='class_sample', xbow_class_floor=.3, tau_phase=(.35, .45, .55), spell_aim='rocket_area',
              gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0, log_aim='log_barrel', lethal_rocket='ot')
TOWERS = {'K': (9.0, 3.0), 'L': (3.5, 6.5), 'R': (14.5, 6.5)}
STATES = list(itertools.product((True, False), repeat=2))     # (L alive, R alive)


def cell(x, y):
    """Lattice cell at board tiles (x, y), my frame: enemy towers at the top, forward = decreasing y."""
    return int(round(y * 2)) * 36 + int(round(x * 2))


LOCK = {'L': cell(2.5, 19.5), 'R': cell(15.5, 19.5)}     # the X-Bow row live uses (152 of 168 dead-lane X-Bows)
BACK = {'L': cell(2.5, 22.5), 'R': cell(15.5, 22.5)}     # a deeper dead-lane row: out of the dead princess's reach
POCKET = {'L': cell(2.5, 12.5), 'R': cell(15.5, 12.5)}   # in the dead princess's pocket: reaches the king only


def reference(x, y, alive_l, alive_r):
    """The definition, cell by cell: within reach of K or a dead princess's position, of no alive princess."""
    near = {k: math.hypot(x - tx, y - ty) <= XBOW_REACH_TILES for k, (tx, ty) in TOWERS.items()}
    alive = {'L': alive_l, 'R': alive_r}
    return (near['K'] or any(near[k] and not alive[k] for k in 'LR')) and not any(near[k] and alive[k] for k in 'LR')


def test_default_allow_and_flag():
    assert DecisionOptions().xbow_dead_lane == 'allow' and not DecisionOptions().active and BLOCK.active
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args([]))) == DecisionOptions()
    assert options_from_config(config_from_args(ap.parse_args(['--xbow-dead-lane', 'block']))) == BLOCK
    with pytest.raises(ValueError):
        DecisionOptions(xbow_dead_lane='king')


@pytest.mark.parametrize('grid', ['lattice', 'floor'])
@pytest.mark.parametrize('alive_l,alive_r', STATES)
def test_blocked_cells_match_the_definition_cell_by_cell(grid, alive_l, alive_r):
    off = 0.5 if grid == 'floor' else 0.0
    c = np.arange(2304)
    x, y = (c % 36 + off) * 0.5, (c // 36 + off) * 0.5
    want = np.array([reference(a, b, alive_l, alive_r) for a, b in zip(x, y)])
    np.testing.assert_array_equal(xbow_dead_lane_cells((True, alive_l, alive_r), grid), want)
    # never the whole board: my back half (y >= 20) always keeps cells, so an X-Bow always has somewhere to go
    assert (~want & (y >= 20)).sum() > 300


@pytest.mark.parametrize('alive_l,alive_r', STATES)
def test_left_right_mirror(alive_l, alive_r):
    a = xbow_dead_lane_cells((True, alive_l, alive_r), 'lattice').reshape(64, 36)
    b = xbow_dead_lane_cells((True, alive_r, alive_l), 'lattice').reshape(64, 36)
    np.testing.assert_array_equal(a[:, 1:], b[:, 1:][:, ::-1])  # lattice x = col/2: mirror col c <-> 36 - c


def test_named_cells_by_lane_state():
    both = xbow_dead_lane_cells((True, True, True), 'lattice')
    assert not both[LOCK['L']] and not both[LOCK['R']] and not both[BACK['L']]   # lanes alive: nothing on my half
    assert not (both.reshape(64, 36)[32:]).any()
    for dead, other in (('L', 'R'), ('R', 'L')):
        blocked = xbow_dead_lane_cells((True, dead != 'L', dead != 'R'), 'lattice')
        assert blocked[LOCK[dead]] and blocked[POCKET[dead]]          # dead-lane lock cell, king-only pocket
        assert not blocked[BACK[dead]]                               # deeper defensive dead-lane row stays
        assert not blocked[LOCK[other]]                              # locking the remaining princess stays
        # the pocket really reaches the king and nothing alive; the lock cell reaches nothing alive
        assert xbow_offensive_cells((True, dead != 'L', dead != 'R'), 'lattice')[POCKET[dead]]
        assert not xbow_offensive_cells((True, dead != 'L', dead != 'R'), 'lattice')[LOCK[dead]]


def peaked(mass):
    p = torch.full((2304,), 1e-9)
    for c, m in mass.items():
        p[c] = m
    return p.log()


def test_choose_cells_touches_only_xbow_rows():
    alive = (True, False, True)                                       # the enemy L princess is down (my frame)
    logits = torch.stack([peaked({LOCK['L']: .6, BACK['L']: .3, LOCK['R']: .1})] * 3)
    names = ['Xbow', 'Knight', 'XBowEvo']
    plain = choose_cells(logits, names, DecisionOptions(), enemy_alive=[alive] * 3, grid='lattice')
    out = choose_cells(logits, names, BLOCK, enemy_alive=[alive] * 3, grid='lattice')
    assert plain.tolist() == [LOCK['L']] * 3
    assert out.tolist() == [BACK['L'], LOCK['L'], BACK['L']]
    assert torch.equal(logits, torch.stack([peaked({LOCK['L']: .6, BACK['L']: .3, LOCK['R']: .1})] * 3))  # unmutated
    with pytest.raises(ValueError, match='xbow_dead_lane'):
        choose_cells(logits, names, BLOCK)


def test_class_sample_draws_over_the_remaining_cells():
    """Dead lane L: the lock cell reaches nothing alive, so the reach rule calls it DEFENSIVE -- class_sample alone keeps
    it (D = .8 > the .3 floor's majority); with block the remaining mass is split .2/.2 and the class is drawn."""
    alive = (True, False, True)
    logits = peaked({LOCK['L']: .6, BACK['L']: .2, LOCK['R']: .2})[None]
    cs = DecisionOptions(xbow_class='class_sample', xbow_class_floor=.3)
    rng = np.random.default_rng(0); before = copy.deepcopy(rng.bit_generator.state)
    assert choose_cells(logits, ['Xbow'], cs, rngs=[rng], enemy_alive=[alive], grid='lattice').item() == LOCK['L']
    assert rng.bit_generator.state == before                          # confident majority: no draw
    both = DecisionOptions(xbow_class='class_sample', xbow_class_floor=.3, xbow_dead_lane='block')
    seen = {choose_cells(logits, ['Xbow'], both, rngs=[np.random.default_rng(s)], enemy_alive=[alive],
                         grid='lattice').item() for s in range(40)}
    assert seen == {BACK['L'], LOCK['R']}
    # every offensive cell blocked (king-only pocket): defensive majority, no draw
    only_pocket = peaked({POCKET['L']: .7, BACK['L']: .3})[None]
    rng = np.random.default_rng(1); before = copy.deepcopy(rng.bit_generator.state)
    assert choose_cells(only_pocket, ['Xbow'], both, rngs=[rng], enemy_alive=[alive], grid='lattice').item() == BACK['L']
    assert rng.bit_generator.state == before


class SimModel:
    def __init__(self, per_slot):
        self.per_slot = per_slot

    def cell_logits(self, enc, slot):
        return torch.stack([self.per_slot[int(s)] for s in slot])


NAMES = ['knight', 'xbow', 'rocket', 'tesla']


def sim(options, cells, *, card=(0., 9., 5., 1.), allowed=(1, 1, 1, 1), alive=(True, False, True), p=.9, **kw):
    out = decide_batch(SimModel(cells), {'g': torch.zeros(1, 2)}, {'card': torch.tensor([card])}, np.array([p]),
                       np.array([allowed], bool), np.zeros(1, bool), tau=.35, device='cpu', options=options,
                       rngs=[np.random.default_rng(0)], card_names=[NAMES], enemy_alive=[alive], grid='lattice', **kw)
    return out[0]


def test_sim_block_reaims_and_falls_back_to_the_next_card_only_with_no_cell():
    xb = peaked({LOCK['L']: .7, BACK['L']: .3})
    cells = {0: peaked({2000: 1.}), 1: xb, 2: peaked({cell(3.5, 6.5): 1.}), 3: peaked({2100: 1.})}
    assert sim(DecisionOptions(spell_aim='rocket_area'), cells) == dict(play=True, slot=1, cell=LOCK['L'], why='gate')
    assert sim(BLOCK, cells) == dict(play=True, slot=1, cell=BACK['L'], why='gate')
    assert sim(BLOCK, cells, alive=(True, True, True)) == dict(play=True, slot=1, cell=LOCK['L'], why='gate')
    # only blocked cells finite (as a legality mask could leave): X-Bow not chosen -> the next card by the card logits
    only_blocked = torch.where(torch.as_tensor(xbow_dead_lane_cells((True, False, True), 'lattice')), xb, -torch.inf)
    cells[1] = only_blocked
    assert sim(BLOCK, cells) == dict(play=True, slot=2, cell=cell(3.5, 6.5), why='gate')
    assert sim(BLOCK, cells, allowed=(0, 1, 0, 0)) == dict(play=False, slot=1, cell=-1, why='wait')   # never forced
    assert sim(BLOCK, cells, p=.1) == dict(play=False, slot=1, cell=-1, why='wait')                  # WAIT: untouched


def test_lethal_rocket_still_overrides_and_block_applies_otherwise():
    xb = peaked({LOCK['R']: .7, BACK['R']: .3})
    cells = {0: peaked({2000: 1.}), 1: xb, 2: peaked({2050: 1.}), 3: peaked({2100: 1.})}
    both = DecisionOptions(lethal_rocket='ot', xbow_dead_lane='block')
    lethal = [(raw_towers(0, 4000, 0), 0, False)]                          # enemy R down (side 0: raw x 14500 = my R)
    d = sim(both, cells, alive=(True, True, False), t_sec=[200.0], lethal=lethal)
    assert d == dict(play=True, slot=1, cell=BACK['R'], why='gate')
    lethal = [(raw_towers(0, 453, 0), 0, False)]                            # my L... enemy L at 453 HP: lethal
    d = sim(both, cells, alive=(True, True, False), t_sec=[200.0], lethal=lethal)
    assert d['why'] == 'lethal_rocket' and d['slot'] == 2


def test_match_kwargs_supplies_enemy_towers_for_block():
    from pipeline.obs_contract import Tower
    towers = tuple(Tower(s, k, l, 1., a) for s, k, l, a in
                   [(0, 'king', None, 1), (0, 'princess', 'L', 1), (0, 'princess', 'R', 1),
                    (1, 'king', None, 1), (1, 'princess', 'L', 0), (1, 'princess', 'R', 1)])
    m = SimpleNamespace(tag='a', k=1, cfg={'xbow_dead_lane': 'block', 'grid': 'lattice'},
                        deck=SimpleNamespace(cards=['x_bow']), _cur=(2400, SimpleNamespace(t_sec=120.0, towers=towers), None))
    kw = match_kwargs([m])
    assert kw['decision_options'] == BLOCK and kw['enemy_alive'] == [(True, False, True)] and kw['grid'] == 'lattice'


# ---- live GenPilot (live_play's pilot) on a real reader frame, both observer sides ------------------------------------
def dead_lane(side, drop):
    """My-frame lane of the dropped ENEMY princess (native x 3500 is my L for side 0, my R for side 1)."""
    return None if drop is None else ('L' if (drop == 3500) == (side == 0) else 'R')


CASES = [(side, drop) for side in (0, 1) for drop in (None, 3500, 14500)]


@pytest.mark.parametrize('side,drop', CASES)
def test_live_block_removes_the_dead_lane_cell_on_both_sides(side, drop):
    lane = dead_lane(side, drop) or 'L'
    other = 'R' if lane == 'L' else 'L'
    logits = peaked({LOCK[lane]: .5, POCKET[lane]: .3, BACK[lane]: .15, LOCK[other]: .05})
    f = icebow_frame(1000, side, drop)
    plain = pilot(DecisionOptions(), .6, cell=logits).decide(f)
    new = pilot(BLOCK, .6, cell=logits).decide(f)
    assert plain['play'] and plain['name'] == 'Xbow' and plain['xy'] == cell_xy(LOCK[lane], 'lattice')
    assert new['play'] and new['name'] == 'Xbow' and new['hand_pos'] == plain['hand_pos']
    if drop is None:                                           # no princess down: block is a no-op on these cells
        assert new == plain
    else:
        assert new['xy'] == cell_xy(BACK[lane], 'lattice') and new['why'] == 'xbow_dead_lane'
        assert tuple(t.alive for t in new['bs'].towers[3:6]) == (True, lane != 'L', lane != 'R')


@pytest.mark.parametrize('side,drop', CASES)
def test_live_and_sim_agree_with_block_and_the_bundle(side, drop):
    lane = dead_lane(side, drop) or 'L'
    other = 'R' if lane == 'L' else 'L'
    logits = peaked({LOCK[lane]: .4, BACK[lane]: .3, LOCK[other]: .3})
    opts = DecisionOptions(tau_phase=(.3, .5, .7), xbow_class='class_sample', xbow_class_floor=.2, xbow_dead_lane='block')
    f = icebow_frame(1000, side, drop)
    _, names = deck_of(f, side)
    for seed in range(20):
        d = pilot(opts, .6, cell=logits, seed=seed).decide(f)
        s = sim_decide(d, 1000, [names[i] for i in HAND], opts, seed, logits)
        assert (d['play'], d['hand_pos']) == (s['play'], s['slot']) and d['xy'] == cell_xy(s['cell'], 'lattice')


def test_live_falls_back_to_the_next_card_when_no_xbow_cell_is_left(monkeypatch):
    f = icebow_frame(1000, 1, 3500)                                  # side 1, enemy native-3500 princess down = my R
    p = pilot(BLOCK, .6, card_logits=(0., 9., 5., 1.), cell=peaked({LOCK['R']: .9, BACK['R']: .1}))
    blocked = torch.as_tensor(xbow_dead_lane_cells((True, True, False), 'lattice'))
    p.guard_cells = lambda frame, d, logits: logits.masked_fill(~blocked, -torch.inf)   # a legality mask leaving none
    d = p.decide(f)
    # X-Bow 9 > Rocket 5 > Tesla 1 > Knight 0: the Rocket (no other affordable card -> WAIT is the SIM test above;
    # with icebow's hand an affordable X-Bow means every card is affordable)
    assert d['play'] and d['name'] == 'Rocket' and d['hand_pos'] == 2 and d['why'] == 'xbow_dead_lane'


def test_live_wait_keeps_the_plain_xbow_argmax_and_draws_no_rng():
    p = pilot(DecisionOptions(xbow_dead_lane='block', xbow_class='class_sample', xbow_class_floor=.2), .2,
              cell=peaked({LOCK['R']: .9, BACK['R']: .1}), seed=4)
    before = copy.deepcopy(p.rng_decisions.bit_generator.state)
    d = p.decide(icebow_frame(1000, 1, 3500))
    assert not d['play'] and d['xy'] == cell_xy(LOCK['R'], 'lattice') and 'why' not in d
    assert p.rng_decisions.bit_generator.state == before


@pytest.mark.parametrize('side', [0, 1])
@pytest.mark.parametrize('tick,gate_p', [(1000, .6), (1000, .2), (3000, .5), (3700, .6), (3700, .3)])
def test_live_bundle_block_is_a_no_op_with_every_princess_standing(side, tick, gate_p):
    """Deployed bundle (log_aim left out: the stub pilot has no fv >= 4 projectile tokens) +/- block: with both enemy
    princesses up no X-Bow cell on my half is blocked, so decisions and the decision RNG stay identical. The cross-tree
    NEW-vs-main default parity is scratchpad/gauntlet/L74/deadlane/parity_vs_main.py."""
    bundle = {k: v for k, v in BUNDLE.items() if k != 'log_aim'}
    logits = peaked({LOCK['L']: .35, BACK['L']: .25, LOCK['R']: .25, cell(9.5, 24.5): .15})
    f = icebow_frame(tick, side)
    for seed in range(6):
        a = pilot(DecisionOptions(**bundle), gate_p, cell=logits, seed=seed)
        b = pilot(DecisionOptions(**bundle, xbow_dead_lane='block'), gate_p, cell=logits, seed=seed)
        for q in (a, b):
            q._hazard_prev = (tick - 40, True)                       # 2 s of waiting: hazard draws happen
        assert a.decide(f) == b.decide(f)
        assert a.rng_decisions.bit_generator.state == b.rng_decisions.bit_generator.state
