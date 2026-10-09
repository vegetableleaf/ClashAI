"""--card-levels NAME=LEVEL ... (owner 2026-10-09: Knight, X-Bow, Rocket level 16; IW 14; the rest 15): the lethal Rocket /
Log damage and the in-flight guard use each card's own level; unlisted cards fall back to my tower level."""
import argparse
from dataclasses import replace

import numpy as np
import pytest
import torch

from pipeline.decision_options import (DecisionOptions, add_arguments, config_from_args, decide_batch,
                                      in_flight_damage, lethal_rocket_choice, match_kwargs, options_from_config,
                                      rocket_tower_damage)
from pipeline.tests.test_lethal_rocket import Model, towers

OWNER = ['Rocket=16', 'Knight=16', 'Xbow=16', 'IceWizard=14', 'Log=15', 'Tesla=15', 'Tornado=15', 'Skeletons=15']
ON = DecisionOptions(lethal_rocket='ot_behind', lethal_log='on')
LV = replace(ON, card_levels=OWNER)
NAMES, OK = ['Knight', 'Rocket', 'Log', 'Tesla'], [True] * 4


def test_flag_parse_validation_and_default():
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args([]))).card_levels is None
    opts = options_from_config(config_from_args(ap.parse_args(['--card-levels', 'Rocket=16', 'the-log=15', 'x-bow=16'])))
    assert opts.card_levels == (('Log', 15), ('Rocket', 16), ('Xbow', 16))
    assert DecisionOptions(card_levels=opts.card_levels) == opts                 # idempotent (configs, match_kwargs)
    assert DecisionOptions(card_levels={'rocket': 16}).card_levels == (('Rocket', 16),)
    assert not DecisionOptions(card_levels=OWNER).active                         # inert alone
    for bad in (['Rocket=17'], ['Log=7'], ['Nope=11'], ['Rocket=16', 'rocket=15'], ['Rocket'], ['Rocket=x']):
        with pytest.raises(ValueError):
            DecisionOptions(card_levels=bad)


def test_damage_at_the_cards_own_level():
    assert rocket_tower_damage(16) == 546 and rocket_tower_damage(15) == 497
    assert rocket_tower_damage(15, 'Log') == 51
    tw = towers(0, 520, 4424)                                                    # my towers: level 15
    assert lethal_rocket_choice(ON, 200.0, NAMES, OK, tw, 0, 'lattice') is None  # 520 > 497 at the tower level
    slot, _, target = lethal_rocket_choice(LV, 200.0, NAMES, OK, tw, 0, 'lattice')
    assert slot == 1 and target == dict(lane='L', hp=520, damage=546, level=16)
    assert lethal_rocket_choice(LV, 200.0, NAMES, OK, towers(0, 547, 4424), 0, 'lattice') is None
    # Log=15 unchanged (= the tower level): 51
    hit = lethal_rocket_choice(LV, 200.0, NAMES, OK, towers(0, 51, 4424), 0, 'lattice')
    assert hit[0] == 2 and hit[2] == dict(lane='L', hp=51, damage=51, level=15, card='Log')
    assert lethal_rocket_choice(LV, 200.0, NAMES, OK, towers(0, 52, 4424), 0, 'lattice')[2]['damage'] == 546


@pytest.mark.parametrize('side', [0, 1])
def test_off_and_tower_level_entries_are_identical(side):
    same = replace(ON, card_levels=['Rocket=15', 'Log=15'])                      # = my tower level: no change
    for state in (towers(side, 40, 1092), towers(side, 497, 4424), towers(side, 498, 4424),
                  towers(side, 40, 1092, my_hp=(0, 4424))):
        for t in (95.0, 200.0):
            base = lethal_rocket_choice(ON, t, NAMES, OK, state, side, 'lattice')
            assert lethal_rocket_choice(same, t, NAMES, OK, state, side, 'lattice') == base
            assert lethal_rocket_choice(replace(ON, card_levels=None), t, NAMES, OK, state, side, 'lattice') == base
    # an explicit level always wins over the tower level -- so never pass the LIVE card levels to the level-11 SIM
    sim = towers(side, 300, 3052, my_max=3052, enemy_max=3052)
    assert lethal_rocket_choice(ON, 200.0, NAMES, OK, sim, side, 'lattice')[2]['damage'] == 342
    assert lethal_rocket_choice(same, 200.0, NAMES, OK, sim, side, 'lattice')[2]['damage'] == 497


def test_in_flight_guard_uses_the_per_card_damage():
    rk = ('rocket', 3.5 / 18, 6.5 / 32, 199.5)
    assert in_flight_damage([rk], 200.0, 15) == {'L': 497}
    assert in_flight_damage([rk], 200.0, 15, levels={'Rocket': 16}) == {'L': 546}
    assert in_flight_damage([('the-log', 3.5 / 18, 17.5 / 32, 199.5)], 200.0, 15, levels={'Rocket': 16}) == {'L': 51}
    # my level-16 Rocket flying at a 520-HP tower finishes it: no second spell (at level 15 it would not -> the Log /
    # Rocket rule could not finish it either: nothing lethal)
    tw = towers(0, 520, 4424)
    assert lethal_rocket_choice(LV, 200.0, ['Knight', 'Rocket', 'Log', 'Tesla'], OK, tw, 0, 'lattice', own=[rk]) is None
    assert lethal_rocket_choice(LV, 200.0, NAMES, OK, tw, 0, 'lattice')[0] == 1


def test_sim_rows_unaffected_when_off_and_match_kwargs_accepts_levels():
    from types import SimpleNamespace
    enc = {'g': torch.zeros(2, 2)}
    heads = {'card': torch.tensor([[9., 0, 0, 0]] * 2)}
    names = [['knight', 'rocket', 'the-log', 'tesla']] * 2
    lethal = [(towers(1, 520, 4424), 1, False, []), (towers(0, 40, 1092), 0, False, [])]
    kw = dict(tau=.35, device='cpu', card_names=names, t_sec=[200.0] * 2, grid='lattice', lethal=lethal)

    def run(opts):
        rngs = [np.random.default_rng(s) for s in range(2)]
        out = decide_batch(Model(), enc, heads, np.array([.1, .1]), np.ones((2, 4), bool), np.zeros(2, bool),
                           options=opts, rngs=rngs, **kw)
        return out, [r.bit_generator.state for r in rngs]
    assert run(ON) == run(replace(ON, card_levels=None))
    on, _ = run(LV)
    assert on[0]['why'] == 'lethal_rocket' and run(ON)[0][0]['why'] == 'wait'      # 520 HP: only at Rocket level 16
    assert on[1] == run(ON)[0][1]
    m = SimpleNamespace(tag='a', k=1, cfg={'lethal_rocket': 'ot_behind', 'card_levels': OWNER, 'grid': 'lattice'},
                        side=1, deck=SimpleNamespace(cards=['rocket']), state={'episode': {'crown_towers': []}},
                        _cur=(3700, SimpleNamespace(t_sec=186.3), None))
    assert match_kwargs([m])['decision_options'].card_levels == LV.card_levels
