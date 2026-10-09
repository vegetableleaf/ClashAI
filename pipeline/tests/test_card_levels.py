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


def test_sim_ignores_card_levels():
    """card_levels is LIVE-ONLY: SIM decide_batch rows and match_kwargs are identical with and without it (a deployed
    LIVE_OPTIONS bundle in a SIM run must not give the level-11 SIM a 546-damage Rocket)."""
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
    assert run(LV) == run(ON) == run(replace(ON, card_levels=None))
    assert run(LV)[0][0]['why'] == 'wait'                                          # 520 HP: no Rocket in the SIM

    def match(cfg):
        return SimpleNamespace(tag='a', k=1, cfg=cfg, side=1, deck=SimpleNamespace(cards=['rocket']),
                               state={'episode': {'crown_towers': towers(1, 520, 4424)}},
                               _cur=(3700, SimpleNamespace(t_sec=186.3), None))
    base = {'lethal_rocket': 'ot_behind', 'grid': 'lattice'}
    a, b = match_kwargs([match(base)]), match_kwargs([match({**base, 'card_levels': OWNER})])
    assert a.keys() == b.keys() and a['decision_options'] == b['decision_options'] == options_from_config(base)
    assert a['lethal'] == b['lethal'] and [r.random() for r in a['rngs']] == [r.random() for r in b['rngs']]
    assert match_kwargs([match({**base, 'card_levels': OWNER}), match(base)])['decision_options'].card_levels is None
    assert match_kwargs([match({'card_levels': OWNER})]) == {}                     # inert alone, as before


def test_rocket_dead_target_king_exception_uses_the_card_level():
    from pipeline.decision_options import my_rocket_damage, rocket_kills_king
    tw = towers(0, 4424, 4424, king_hp=520)                                        # my towers: level 15
    assert my_rocket_damage(tw, 0) == 497 and my_rocket_damage(tw, 0, {'Rocket': 16}) == 546
    assert not rocket_kills_king(tw, 0) and rocket_kills_king(tw, 0, {'Rocket': 16})
    assert rocket_kills_king(tw, 0, {'Log': 15}) is False                          # Rocket not listed: tower level
    assert rocket_kills_king(towers(0, 4424, 4424, king_hp=547), 0, {'Rocket': 16}) is False


def test_in_flight_spell_unlisted_uses_the_tower_level_not_the_evaluated_cards():
    """Verifier: with Rocket=16 alone, my Log in flight is costed at the TOWER level (15: 51), not Rocket's 16 (56)."""
    only_rocket = replace(ON, card_levels=['Rocket=16'])
    log = ('the-log', 3.5 / 18, 17.5 / 32, 199.5)                      # my Log rolling at my L, not hit yet
    for hp in (52, 56):                                                  # 51 < hp <= 56: the Log does NOT finish it
        tw = towers(0, hp, 4424)
        hit = lethal_rocket_choice(only_rocket, 200.0, NAMES, OK, tw, 0, 'lattice', own=[log])
        assert hit is not None and hit[0] == 1 and hit[2] == dict(lane='L', hp=hp, damage=546, level=16)
    tw = towers(0, 51, 4424)                                             # 51: the Log in flight finishes it
    assert lethal_rocket_choice(only_rocket, 200.0, NAMES, OK, tw, 0, 'lattice', own=[log]) is None
    # a listed Log level is used for the Log in flight (Log=16 -> 56)
    both = replace(ON, card_levels=['Rocket=16', 'Log=16'])
    assert lethal_rocket_choice(both, 200.0, ['Knight', 'Rocket', 'Xbow', 'Tesla'], OK, towers(0, 56, 4424), 0,
                                'lattice', own=[log]) is None


# ---- impossible card levels (verifier: a lower-level account's King reads level 8; the Log starts at 9) -------------------
def low_towers(side, l, r):
    return towers(side, l, r, my_max=2352, enemy_max=2352)                        # princess 2352 -> level 8


def test_impossible_level_never_raises_and_does_not_fire_that_card():
    from pipeline.decision_options import my_rocket_damage, rocket_kills_king, tower_damage_or_none
    assert tower_damage_or_none(8, 'Log') is None and tower_damage_or_none(15, 'Log') == 51
    assert tower_damage_or_none(8) == rocket_tower_damage(8) == 258               # Rocket exists at level 8
    with pytest.raises(ValueError):
        rocket_tower_damage(8, 'Log')                                            # the raw table still refuses
    for side in (0, 1):
        tw = low_towers(side, 40, 1092)
        lane = 'L' if side == 0 else 'R'                                         # the raw-left (40 HP) tower
        hit = lethal_rocket_choice(ON, 200.0, NAMES, OK, tw, side, 'lattice')     # Log impossible -> the Rocket
        assert hit[0] == 1 and hit[2] == dict(lane=lane, hp=40, damage=258, level=8)
        assert lethal_rocket_choice(ON, 200.0, ['Knight', 'Xbow', 'Log', 'Tesla'], OK, tw, side, 'lattice') is None
        # my Log in flight at an impossible level counts as finishing: no Rocket after it
        log = ('the-log', (3.5 if lane == 'L' else 14.5) / 18, 17.5 / 32, 199.5)
        assert lethal_rocket_choice(ON, 200.0, NAMES, OK, tw, side, 'lattice', own=[log]) is None
        # a listed level still wins (live --card-levels)
        assert rocket_tower_damage(9, 'Log') == 29
        assert lethal_rocket_choice(replace(ON, card_levels=['Log=9']), 200.0, NAMES, OK, low_towers(side, 25, 1092),
                                    side, 'lattice')[2] == dict(lane=lane, hp=25, damage=29, level=9, card='Log')
    tiny = towers(0, 4424, 4424, my_max=320, enemy_max=4424, king_hp=100)        # my towers read level 1: no Rocket
    assert my_rocket_damage(tiny, 0) is None and rocket_kills_king(tiny, 0) is False


def test_live_pilot_survives_a_level_8_board():
    from types import SimpleNamespace
    from pipeline.live_gen_v2 import GenPilot
    tw = low_towers(0, 40, 1092)
    ents = [dict(card_id=-1, kind=12 if t['type'] == 'king' else 13, side=t['side'], x=t['x'], y=t['y'], hp=t['hp'],
                 max_hp=t['max_hp'], address=f'0x{i}') for i, t in enumerate(tw)]
    frame = dict(game_tick=4000, entities=ents, players=[
        dict(side=0, elixir_raw=80000, next_deck_index=4, hand_deck_indices=[0, 1, 2, 3]),
        dict(side=1, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[-1] * 4)])
    p = object.__new__(GenPilot)
    p.decision_options, p.grid = ON, 'lattice'
    p.gid, p.past = {'the-log': 3}, [(3, 0, 3.5 / 18, 17.5 / 32, 199.5)]
    names = ['Knight', 'Rocket', 'Log', 'Tesla', 'Xbow', 'IceWizard', 'Skeletons', 'Tornado']
    info = dict(names=names, hand_deck_indices=[0, 1, 2, 3], bs=SimpleNamespace(t_sec=200.0))
    assert p.lethal_rocket(frame, info, np.ones(4, bool)) is None              # Log impossible + Log in flight: no fire
    p.past = []
    assert p.lethal_rocket(frame, info, np.ones(4, bool))[2]['damage'] == 258   # the Rocket at level 8
