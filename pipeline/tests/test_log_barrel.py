"""log_aim=log_barrel: Log / Barbarian Barrel aimed at an in-flight enemy Goblin Barrel's visible landing; CPU only."""
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline.decision_options import (DecisionOptions, barrel_landings, choose_cells, match_kwargs, rolling_corridor,
                                      cell_centres_tiles)
from pipeline.live_gen_v2 import GenPilot

GB = 5                                    # the test vocabulary's goblin-barrel id
LAND = (3.5 / 18, 25.5 / 32)              # my left princess tower, board-normalised (me at the bottom)
PEAK = 20 * 36 + 30                       # plain argmax: far right, enemy half


def logits():
    x = torch.full((1, 2304), -5.0)
    x[0, PEAK] = 5.0
    x[0, 55 * 36 + 7] = 1.0               # (3.5, 27.5): 2 tiles behind the landing, inside the corridor
    x[0, 52 * 36 + 7] = 0.5               # (3.5, 26.0): also covering, lower
    return x


def tokens(*rows):
    p = np.zeros((64, 8), np.float32)
    for i, r in enumerate(rows):
        p[i] = r
    return p


BARREL = (GB, 1, .5, .1, *LAND, .5, 1)


def covers(cell, land=LAND, corridor=(1.95, .6, 10.1)):
    x, y = cell_centres_tiles('lattice')
    ahead = y[cell] - land[1] * 32
    return abs(x[cell] - land[0] * 18) <= corridor[0] and -corridor[1] <= ahead <= corridor[2]


def test_catalog_corridors_and_card_names():
    assert rolling_corridor('Log') == rolling_corridor('the-log') == (1.95, .6, 10.1)
    assert rolling_corridor('BarbarianBarrel') == rolling_corridor('barbarian-barrel') == (1.3, .6, 4.5)
    assert rolling_corridor('Rocket') is None and rolling_corridor('Tornado') is None


def test_barrel_decode_skips_friendly_unknown_and_other_cards():
    rows = tokens(BARREL, (GB, 0, .5, .9, .5, .2, .1, 1), (GB, 1, .5, .1, -1, -1, 0, 0), (7, 1, .5, .1, .3, .7, .1, 1))
    assert barrel_landings(rows, GB) == [pytest.approx(LAND)]
    assert barrel_landings(torch.from_numpy(rows), GB) == barrel_landings(rows, GB)
    assert barrel_landings(rows, None) == []


def test_log_aims_at_the_best_covering_cell_and_leaves_everything_else_plain():
    on = DecisionOptions(log_aim='log_barrel')
    x = logits()
    assert int(choose_cells(x, ['Log'], DecisionOptions())[0]) == PEAK
    cell = int(choose_cells(x, ['Log'], on, grid='lattice', barrels=[[LAND]])[0])
    assert cell == 55 * 36 + 7 and covers(cell)
    # no barrel, another card, or every covering cell masked (legal guard) -> the plain argmax
    assert int(choose_cells(x, ['Log'], on, grid='lattice', barrels=[[]])[0]) == PEAK
    assert int(choose_cells(x, ['Knight'], on, grid='lattice', barrels=[[LAND]])[0]) == PEAK
    masked = x.clone()
    for c in range(2304):
        if covers(c):
            masked[0, c] = -torch.inf
    assert int(choose_cells(masked, ['Log'], on, grid='lattice', barrels=[[LAND]])[0]) == PEAK
    with pytest.raises(ValueError, match='barrel landing'):
        choose_cells(x, ['Log'], on)


def test_barbarian_barrel_uses_its_shorter_corridor_and_two_barrels_prefer_covering_both():
    x = logits()
    on = DecisionOptions(log_aim='log_barrel')
    far = (3.5 / 18, 20.0 / 32)            # 7.5 tiles ahead of (3.5, 27.5): Log reaches, Barbarian Barrel does not
    assert int(choose_cells(x, ['Log'], on, grid='lattice', barrels=[[far]])[0]) == 55 * 36 + 7
    cell = int(choose_cells(x, ['BarbarianBarrel'], on, grid='lattice', barrels=[[far]])[0])
    assert covers(cell, far, (1.3, .6, 4.5)) and not covers(55 * 36 + 7, far, (1.3, .6, 4.5))
    other = (6.0 / 18, 25.5 / 32)          # evo barrel + decoy 2.5 tiles apart: one corridor covers both
    cell = int(choose_cells(x, ['Log'], on, grid='lattice', barrels=[[LAND, other]])[0])
    assert covers(cell) and covers(cell, other)


class Model:
    gid = {'goblin-barrel': GB}

    def cell_logits(self, enc, slot):
        return logits().repeat(len(slot), 1)


def test_sim_batch_needs_and_reads_the_projectile_tokens():
    enc, heads = {'g': torch.zeros(2, 2)}, {'card': torch.tensor([[9., 0, 0, 0], [0., 9, 0, 0]])}
    names = [['Log', 'Knight', 'Rocket', 'Tesla']] * 2
    on = DecisionOptions(log_aim='log_barrel')
    args = (Model(), enc, heads, [.9, .9], np.ones((2, 4), bool), np.zeros(2, bool))
    out = E.live_decide_batch(*args, tau=.35, decision_options=on, card_names=names, grid='lattice',
                              projectiles=[tokens(BARREL)] * 2)
    assert out[0]['cell'] == 55 * 36 + 7 and out[1]['cell'] == PEAK      # Log row aimed; Knight row plain
    base = E.live_decide_batch(*args, tau=.35)
    assert [(d['play'], d['slot']) for d in out] == [(d['play'], d['slot']) for d in base]
    with pytest.raises(ValueError, match='projectile tokens'):
        E.live_decide_batch(*args, tau=.35, decision_options=on, card_names=names, grid='lattice')


def test_match_kwargs_passes_the_rows_the_model_saw():
    row = {'projectiles': tokens(BARREL)}
    m = SimpleNamespace(tag='a', k=1, cfg={'log_aim': 'log_barrel', 'grid': 'lattice'},
                        deck=SimpleNamespace(cards=['Log']), _gen_row=row)
    kw = match_kwargs([m])
    assert kw['grid'] == 'lattice' and kw['projectiles'][0] is row['projectiles']
    with pytest.raises(ValueError, match='feature_version'):
        match_kwargs([SimpleNamespace(tag='b', k=1, cfg={'log_aim': 'log_barrel', 'grid': 'lattice'},
                                      deck=SimpleNamespace(cards=['Log']), _gen_row=None)])


def test_live_and_sim_choose_the_same_log_cell():
    candidate = object.__new__(GenPilot)
    candidate.decision_options = DecisionOptions(log_aim='log_barrel', spell_aim='rocket_area')
    candidate.rng_decisions = np.random.default_rng(7)
    candidate.dev, candidate.grid, candidate.gate_tau, candidate.gid = torch.device('cpu'), 'lattice', .35, Model.gid
    info = dict(hand=[(1, 0), (2, 0)], costs=[2, 3], el_int=10, bs=None, names=['Log', 'Knight'], hand_deck_indices=[0, 1])
    b = {'projectiles': torch.from_numpy(tokens(BARREL))[None]}
    candidate.row = lambda frame: (b, info)

    class LiveModel:
        def __call__(self, b, card=None, form=None):
            return {'cell': logits()} if card is not None else {'gate': torch.tensor([2.]), 'card': torch.tensor([[9., 0.]])}
    candidate.model = LiveModel()
    d = candidate.decide({})
    sim =E.live_decide_batch(Model(), {'g': torch.zeros(1, 2)}, {'card': torch.tensor([[9., 0.]])},
                              [float(torch.sigmoid(torch.tensor(2.)))], np.array([[True, True]]), np.array([False]),
                              tau=.35, decision_options=candidate.decision_options, card_names=[info['names']],
                              grid='lattice', projectiles=[tokens(BARREL)])[0]
    assert d['play'] and sim['cell'] == 55 * 36 + 7
    assert d['xy'] == (sim['cell'] % 36 / 36, sim['cell'] // 36 / 64)
