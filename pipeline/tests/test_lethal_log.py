"""--lethal-log on (owner 2026-10-09): the lethal finisher also uses the Log when it finishes an enemy PRINCESS, under
--lethal-rocket's phase / crown rules; preferred over the Rocket; cast on my side so its roll reaches the tower."""
import argparse
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline.decision_options import (DecisionOptions, IN_FLIGHT_MARGIN_TICKS, LOG_HIT_TICKS, ROCKET_FLIGHT_TICKS,
                                      add_arguments, config_from_args, decide_batch, in_flight_damage,
                                      lethal_log_cell, lethal_rocket_choice, match_kwargs, options_from_config,
                                      rocket_tower_damage)
from pipeline.model_v3 import cell_xy
from pipeline.obs_contract import PRINCESS_X_L, PRINCESS_X_R
from pipeline.tests.test_lethal_rocket import L_CELL, R_CELL, Model, live_frame, live_pilot, towers

# the deployed bundle's decision options (LIVE_OPTIONS 2026-10-09) without / with the Log finisher
BUNDLE = DecisionOptions(xbow_class='class_sample', xbow_class_floor=.3, tau_phase=(.35, .45, .55),
                         spell_aim='rocket_area', gate_decode='hazard_below_tau', gate_hazard_min_elixir=9,
                         log_aim='log_barrel', lethal_rocket='ot_behind', xbow_dead_lane='block')
LOG = replace(BUNDLE, lethal_log='on')
# the fake live pilot (test_lethal_rocket.live_pilot) has no model batch / hazard clock: Log-at-barrel and the hazard gate
# are exercised on the SIM rows below; live tests use the rest of the bundle
LIVE_BUNDLE = replace(BUNDLE, log_aim='argmax', gate_decode='threshold')
LIVE_LOG = replace(LIVE_BUNDLE, lethal_log='on')
NAMES, OK = ['Knight', 'Rocket', 'Log', 'Tesla'], [True] * 4
LOG_L, LOG_R = 35 * 36 + 7, 35 * 36 + 29                # lattice (3.5, 17.5) / (14.5, 17.5) tiles


def test_flag_default_and_damage():
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args([]))).lethal_log == 'off'
    assert options_from_config(config_from_args(ap.parse_args(['--lethal-log', 'on']))).lethal_log == 'on'
    with pytest.raises(ValueError):
        DecisionOptions(lethal_log='yes')
    assert not DecisionOptions(lethal_log='on').active                    # inert alone: rides on lethal_rocket
    assert rocket_tower_damage(15, 'Log') == 51 and rocket_tower_damage(11, 'Log') == 35   # MEASURED live drops
    assert rocket_tower_damage(15) == 497 and LOG_HIT_TICKS == 57


def test_log_cells_are_own_side_at_the_tower_x():
    assert lethal_log_cell('L', 'lattice') == LOG_L and lethal_log_cell('R', 'lattice') == LOG_R
    np.testing.assert_allclose(cell_xy(LOG_L, 'lattice'), (PRINCESS_X_L, 17.5 / 32))
    np.testing.assert_allclose(cell_xy(LOG_R, 'lattice'), (PRINCESS_X_R, 17.5 / 32))


@pytest.mark.parametrize('side', [0, 1])
@pytest.mark.parametrize('enemy', [(40, 1092), (1092, 40)])
def test_log_preferred_when_it_finishes_both_lanes_both_sides(side, enemy):
    raw_left = enemy[0] == 40
    lane = ('L' if raw_left else 'R') if side == 0 else ('R' if raw_left else 'L')
    slot, cell, target = lethal_rocket_choice(LOG, 200.0, NAMES, OK, towers(side, *enemy), side, 'lattice')
    assert (slot, cell) == (2, LOG_L if lane == 'L' else LOG_R)
    assert target == dict(lane=lane, hp=40, damage=51, level=15, card='Log')
    # off: today's Rocket rule, target without a card key (byte-identical log line)
    assert lethal_rocket_choice(BUNDLE, 200.0, NAMES, OK, towers(side, *enemy), side, 'lattice') == \
        (1, L_CELL if lane == 'L' else R_CELL, dict(lane=lane, hp=40, damage=497, level=15))


def test_log_only_when_finishable_else_rocket_else_nothing():
    tw = lambda l: towers(0, l, 1092)                                    # noqa: E731
    assert lethal_rocket_choice(LOG, 200.0, NAMES, OK, tw(51), 0, 'lattice')[0] == 2          # HP == damage: Log
    assert lethal_rocket_choice(LOG, 200.0, NAMES, OK, tw(52), 0, 'lattice')[0] == 1          # only the Rocket
    assert lethal_rocket_choice(LOG, 200.0, NAMES, [True, True, False, True], tw(40), 0, 'lattice')[0] == 1
    no_rocket = ['Knight', 'Xbow', 'Log', 'Tesla']
    assert lethal_rocket_choice(LOG, 200.0, no_rocket, OK, tw(40), 0, 'lattice')[0] == 2
    assert lethal_rocket_choice(LOG, 200.0, no_rocket, OK, tw(52), 0, 'lattice') is None
    assert lethal_rocket_choice(LOG, 200.0, NAMES, OK, tw(40), 0, 'lattice', pending=True) is None
    assert lethal_rocket_choice(LOG, 200.0, NAMES, OK, towers(0, 1092, 1092, king_hp=30), 0, 'lattice') is None
    level11 = towers(0, 35, 3052, my_max=3052, enemy_max=3052)
    assert lethal_rocket_choice(LOG, 200.0, NAMES, OK, level11, 0, 'lattice')[2]['damage'] == 35
    assert lethal_rocket_choice(LOG, 200.0, NAMES, OK, towers(0, 36, 3052, my_max=3052, enemy_max=3052), 0,
                                'lattice')[0] == 1
    off = DecisionOptions(lethal_log='on')                                # lethal_rocket off: inert
    assert lethal_rocket_choice(off, 200.0, NAMES, OK, tw(40), 0, 'lattice') is None


def test_log_phase_crowns_and_its_own_cutoff():
    behind, tied = towers(0, 40, 1092, my_hp=(0, 4424)), towers(0, 40, 1092)
    assert lethal_rocket_choice(LOG, 95.0, NAMES, OK, behind, 0, 'lattice')[0] == 2            # regulation, behind
    assert lethal_rocket_choice(LOG, 95.0, NAMES, OK, tied, 0, 'lattice') is None              # tied: wait for OT
    ot_mode = replace(LOG, lethal_rocket='ot')
    assert lethal_rocket_choice(ot_mode, 95.0, NAMES, OK, behind, 0, 'lattice') is None        # 'ot': OT only
    assert lethal_rocket_choice(ot_mode, 180.0, NAMES, OK, tied, 0, 'lattice')[0] == 2
    log_cut, rk_cut = (3600 - LOG_HIT_TICKS) * .05, (3600 - ROCKET_FLIGHT_TICKS) * .05
    assert lethal_rocket_choice(LOG, log_cut, NAMES, OK, behind, 0, 'lattice')[0] == 2         # hits at 3600
    assert lethal_rocket_choice(LOG, log_cut + .05, NAMES, OK, behind, 0, 'lattice') is None
    # between the cutoffs the Log can still land and the Rocket cannot
    assert lethal_rocket_choice(LOG, rk_cut + .05, NAMES, OK, behind, 0, 'lattice')[0] == 2
    assert lethal_rocket_choice(BUNDLE, rk_cut + .05, NAMES, OK, behind, 0, 'lattice') is None


@pytest.mark.parametrize('side', [0, 1])
def test_live_pilot_casts_the_log(side):
    d = live_pilot(LIVE_LOG, 200.0).decide(live_frame(side, 40, 1092))
    lane = 'L' if side == 0 else 'R'
    assert d['play'] and d['name'] == 'Log' and d['hand_pos'] == 2 and d['why'] == 'lethal_log'
    assert d['lethal_rocket'] == dict(lane=lane, hp=40, damage=51, level=15, card='Log')
    np.testing.assert_allclose(d['xy'], (PRINCESS_X_L if lane == 'L' else PRINCESS_X_R, 17.5 / 32))
    e = live_pilot(LIVE_BUNDLE, 200.0).decide(live_frame(side, 40, 1092))               # off: the Rocket, as deployed
    assert e['name'] == 'Rocket' and e['why'] == 'lethal_rocket' and 'card' not in e['lethal_rocket']


def test_off_identical_incl_rng_where_the_log_would_fire():
    """lethal_log off vs a bundle without the field set: same decision, same RNG, on Log-finishable states."""
    for frame, t in ((live_frame(0, 40, 1092, tick=1874, my_hp=(0, 4424)), 95.0), (live_frame(1, 40, 1092), 200.0),
                     (live_frame(0, 40, 1092, tick=1874), 95.0)):
        a, b = live_pilot(replace(LIVE_BUNDLE, lethal_log='off'), t, p_gate=3.), live_pilot(LIVE_BUNDLE, t, p_gate=3.)
        assert a.decide(frame) == b.decide(frame)
        assert a.rng_decisions.bit_generator.state == b.rng_decisions.bit_generator.state


def test_sim_decide_batch_with_hazard_gate_and_dead_lane():
    """SIM rows under the bundle (hazard_below_tau + xbow_dead_lane block): lethal rows -> the Log; other rows and every
    RNG stream identical to lethal_log off."""
    enc = {'g': torch.zeros(3, 2)}
    heads = {'card': torch.tensor([[9., 0, 0, 0]] * 3)}
    names = [['knight', 'rocket', 'the-log', 'tesla']] * 3
    lethal = [(towers(1, 40, 1092), 1, False), (towers(0, 1092, 1092), 0, False), (towers(0, 300, 1092), 0, False)]

    def run(opts):
        rngs = [np.random.default_rng(s) for s in range(3)]
        out = decide_batch(Model(), enc, heads, np.array([.1, .1, .1]), np.ones((3, 4), bool), np.zeros(3, bool),
                           tau=.35, device='cpu', options=opts, rngs=rngs, card_names=names, t_sec=[200.0] * 3,
                           grid='lattice', lethal=lethal, step_s=.5, elixir=[9.5] * 3, enemy_units=[0] * 3,
                           enemy_alive=[(True, True, True)] * 3, projectiles=[np.zeros((64, 8))] * 3)
        return out, [r.bit_generator.state for r in rngs]
    on, rs_on = run(LOG)
    off, rs_off = run(BUNDLE)
    assert on[0] == dict(play=True, slot=2, cell=LOG_R, why='lethal_log')         # side 1: raw-left = my R
    assert off[0]['why'] == 'lethal_rocket' and on[1:] == off[1:] and on[2]['why'] == 'lethal_rocket'
    assert rs_on == rs_off


# ---- in-flight guard (verifier finding 1: Rocket then Log at one tower; Log then a wasted Rocket) ----------------------
RK_L, LOG_AT_L = ('rocket', 3.5 / 18, 6.5 / 32), ('the-log', 3.5 / 18, 17.5 / 32)   # my accepted plays: card, x, y


def test_in_flight_geometry_and_window():
    t = 200.0
    assert in_flight_damage([(*RK_L, t - .5)], t, 15) == {'L': 497}
    assert in_flight_damage([(*LOG_AT_L, t - .5)], t, 15) == {'L': 51}
    assert in_flight_damage([('Log', 14.5 / 18, 17.5 / 32, t - .5)], t, 15) == {'R': 51}
    assert in_flight_damage([('the-log', 3.5 / 18, 19.5 / 32, t - .5)], t, 15) == {}    # rolls short (live 0/54)
    assert in_flight_damage([('knight', 3.5 / 18, 6.5 / 32, t - .5)], t, 15) == {}
    assert in_flight_damage([(*RK_L, t + .05)], t, 15) == {}                              # not landed yet
    last = (ROCKET_FLIGHT_TICKS + 26 + IN_FLIGHT_MARGIN_TICKS) * .05
    assert in_flight_damage([(*RK_L, t - last)], t, 15) == {'L': 497}
    assert in_flight_damage([(*RK_L, t - last - .05)], t, 15) == {}                       # window over
    assert in_flight_damage([(*RK_L, t - .5), (*LOG_AT_L, t - .5)], t, 11) == {'L': 342 + 35}


def test_no_second_spell_on_a_tower_my_spell_will_finish():
    t, tw = 200.0, towers(0, 40, 1092)
    assert lethal_rocket_choice(LOG, t, NAMES, OK, tw, 0, 'lattice', own=[(*RK_L, t - .5)]) is None   # Rocket flying
    assert lethal_rocket_choice(LOG, t, NAMES, OK, tw, 0, 'lattice', own=[(*LOG_AT_L, t - .5)]) is None  # Log rolling
    both = towers(0, 30, 45)                                                  # L covered -> the other lethal tower
    slot, cell, target = lethal_rocket_choice(LOG, t, NAMES, OK, both, 0, 'lattice', own=[(*RK_L, t - .5)])
    assert (slot, cell, target['lane'], target['hp']) == (2, LOG_R, 'R', 45)
    # a Log in flight does not finish a 300-HP tower: the Rocket still fires
    assert lethal_rocket_choice(LOG, t, NAMES, OK, towers(0, 300, 1092), 0, 'lattice',
                                own=[(*LOG_AT_L, t - .5)])[:2] == (1, L_CELL)
    # an expired / missed spell no longer blocks
    assert lethal_rocket_choice(LOG, t, NAMES, OK, tw, 0, 'lattice', own=[(*RK_L, t - 10)])[0] == 2
    # regulation behind, Log fired: the Rocket rule does not follow it up
    behind = towers(0, 40, 1092, my_hp=(0, 4424))
    assert lethal_rocket_choice(LOG, 95.0, NAMES, OK, behind, 0, 'lattice', own=[(*LOG_AT_L, 94.5)]) is None
    # lethal_log off: the guard is off too (today's rule exactly)
    assert lethal_rocket_choice(BUNDLE, t, NAMES, OK, tw, 0, 'lattice', own=[(*RK_L, t - .5)]) == \
        lethal_rocket_choice(BUNDLE, t, NAMES, OK, tw, 0, 'lattice')


def test_match_kwargs_own_plays_only_when_on():
    tw = towers(1, 40, 1092)
    m = SimpleNamespace(tag='a', k=1, cfg={'lethal_rocket': 'ot_behind', 'grid': 'lattice'}, side=1,
                        deck=SimpleNamespace(cards=['rocket', 'the-log']), state={'episode': {'crown_towers': tw}},
                        _cur=(3700, SimpleNamespace(t_sec=186.3), None), done_plays=[(3690, 0, .2, .2)])
    assert match_kwargs([m])['lethal'] == [(tw, 1, False)]                              # off: unchanged
    m.cfg = {**m.cfg, 'lethal_log': 'on'}
    del m.rng_decision_options
    assert match_kwargs([m])['lethal'] == [(tw, 1, False, [('rocket', .2, .2, 3690 * .05)])]


def test_sim_rows_and_live_pilot_share_the_guard():
    enc = {'g': torch.zeros(1, 2)}
    heads = {'card': torch.tensor([[9., 0, 0, 0]])}
    names = [['knight', 'rocket', 'the-log', 'tesla']]
    own = [('rocket', 14.5 / 18, 6.5 / 32, 199.5)]                     # my Rocket flying at my R = side 1 raw-left
    out = decide_batch(Model(), enc, heads, np.array([.1]), np.ones((1, 4), bool), np.zeros(1, bool), tau=.35,
                       device='cpu', options=LOG, rngs=[np.random.default_rng(0)], card_names=names, t_sec=[200.0],
                       grid='lattice', lethal=[(towers(1, 40, 1092), 1, False, own)], step_s=.5, elixir=[5.],
                       enemy_units=[0], enemy_alive=[(True, True, True)], projectiles=[np.zeros((64, 8))])
    assert out[0]['why'] not in ('lethal_log', 'lethal_rocket')
    p = live_pilot(LIVE_LOG, 200.0)
    p.gid, p.past = {'rocket': 2}, [(2, 0, 14.5 / 18, 6.5 / 32, 199.5)]
    assert p.decide(live_frame(1, 40, 1092)).get('why') is None
    p.past = [(2, 0, 14.5 / 18, 6.5 / 32, 190.0)]                     # long landed (and missed): fires again
    assert p.decide(live_frame(1, 40, 1092))['why'] == 'lethal_log'
