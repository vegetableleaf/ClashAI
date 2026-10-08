"""--lethal-rocket ot (owner 2026-10-08): in overtime, Rocket an alive enemy PRINCESS my Rocket finishes in one hit.
ot_behind (owner extension): also in regulation while the opponent leads on crowns, if the Rocket lands before 3:00."""
import argparse
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline.decision_options import (DecisionOptions, ROCKET_FLIGHT_TICKS, add_arguments, config_from_args,
                                      crowns_behind, decide_batch,
                                      lethal_rocket_cell, lethal_rocket_choice, lethal_rocket_target, match_kwargs,
                                      options_from_config, rocket_tower_damage)
from pipeline.live_gen_v2 import GenPilot
from pipeline.model_v3 import cell_xy
from pipeline.obs_contract import OPP_PRINCESS_Y, PRINCESS_X_L, PRINCESS_X_R

ON = DecisionOptions(lethal_rocket='ot')
L_CELL, R_CELL = 13 * 36 + 7, 13 * 36 + 29          # lattice (3.5, 6.5) / (14.5, 6.5) tiles


def towers(side, enemy_l, enemy_r, *, my_max=4424, enemy_max=4424, king_hp=None, my_hp=None):
    """Raw crown towers (1/1000 tile); side 0 sits at low y. ``enemy_l`` / ``enemy_r`` = RAW-x 3500 / 14500 HP."""
    me, foe = side, 1 - side
    y = lambda s, k: (3000 if k == 'king' else 6500) if s == 0 else (29000 if k == 'king' else 25500)  # noqa: E731
    rows = [dict(side=me, type='king', x=9000, y=y(me, 'king'), hp=6000, max_hp=round(my_max * 4824 / 3052)),
            dict(side=me, type='princess', x=3500, y=y(me, 'p'), hp=(my_hp or (my_max, my_max))[0], max_hp=my_max),
            dict(side=me, type='princess', x=14500, y=y(me, 'p'), hp=(my_hp or (my_max, my_max))[1], max_hp=my_max),
            dict(side=foe, type='king', x=9000, y=y(foe, 'king'), hp=king_hp or 7032, max_hp=7032),
            dict(side=foe, type='princess', x=3500, y=y(foe, 'p'), hp=enemy_l, max_hp=enemy_max),
            dict(side=foe, type='princess', x=14500, y=y(foe, 'p'), hp=enemy_r, max_hp=enemy_max)]
    return [r for r in rows if r['hp'] > 0]


def test_default_off_and_flag():
    assert DecisionOptions().lethal_rocket == 'off' and not DecisionOptions().active and ON.active
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args([]))) == DecisionOptions()
    assert options_from_config(config_from_args(ap.parse_args(['--lethal-rocket', 'ot']))) == ON
    with pytest.raises(ValueError):
        DecisionOptions(lethal_rocket='always')


def test_catalog_damage_equals_measured_live_and_sim_level():
    assert rocket_tower_damage(15) == 497     # MEASURED live 131352 t4304: 1092 -> 595
    assert rocket_tower_damage(11) == 342     # RoyaleSim corpus level (princess 3052)


@pytest.mark.parametrize('side', [0, 1])
def test_target_lane_follows_my_frame_for_both_observer_sides(side):
    raw_left_lane = 'L' if side == 0 else 'R'            # side 1 is mirrored: raw x 3500 is MY right
    t = lethal_rocket_target(towers(side, 453, 1092), side)
    assert t == dict(lane=raw_left_lane, hp=453, damage=497, level=15)
    t = lethal_rocket_target(towers(side, 1092, 453), side)
    assert t['lane'] == {'L': 'R', 'R': 'L'}[raw_left_lane]
    assert lethal_rocket_target(towers(side, 300, 200), side)['hp'] == 200          # both lethal: the lower HP
    assert lethal_rocket_target(towers(side, 497, 4000), side)['hp'] == 497         # HP == damage still dies
    assert lethal_rocket_target(towers(side, 498, 4000), side) is None
    assert lethal_rocket_target(towers(side, 0, 1092), side) is None                 # destroyed: not a target
    assert lethal_rocket_target(towers(side, 4000, 4000, king_hp=100), side) is None  # never the king
    # SIM level 11: 342 damage
    assert lethal_rocket_target(towers(side, 343, 3052, my_max=3052, enemy_max=3052), side) is None
    assert lethal_rocket_target(towers(side, 342, 3052, my_max=3052, enemy_max=3052), side)['damage'] == 342


def test_cell_is_the_tower_centre():
    assert lethal_rocket_cell('L', 'lattice') == L_CELL and lethal_rocket_cell('R', 'lattice') == R_CELL
    np.testing.assert_allclose(cell_xy(L_CELL, 'lattice'), (PRINCESS_X_L, OPP_PRINCESS_Y))
    np.testing.assert_allclose(cell_xy(R_CELL, 'lattice'), (PRINCESS_X_R, OPP_PRINCESS_Y))


def test_choice_needs_ot_rocket_affordable_and_no_pending():
    names, ok = ['Knight', 'Rocket', 'Log', 'Tesla'], [True] * 4
    tw = towers(0, 453, 1092)
    assert lethal_rocket_choice(ON, 180.0, names, ok, tw, 0, 'lattice')[:2] == (1, L_CELL)
    assert lethal_rocket_choice(ON, 179.95, names, ok, tw, 0, 'lattice') is None          # 2x, not OT
    assert lethal_rocket_choice(DecisionOptions(), 200.0, names, ok, tw, 0, 'lattice') is None
    assert lethal_rocket_choice(ON, 200.0, names, [True, False, True, True], tw, 0, 'lattice') is None  # 5 elixir
    assert lethal_rocket_choice(ON, 200.0, ['Knight', 'Xbow', 'Log', 'Tesla'], ok, tw, 0, 'lattice') is None
    assert lethal_rocket_choice(ON, 200.0, names, ok, tw, 0, 'lattice', pending=True) is None
    assert lethal_rocket_choice(ON, 200.0, names, ok, towers(0, 1000, 1092), 0, 'lattice') is None


class Model:
    def cell_logits(self, enc, slot):
        return torch.zeros(len(slot), 2304)


def test_sim_decide_batch_overrides_only_qualifying_rows():
    enc = {'g': torch.zeros(3, 2)}
    heads = {'card': torch.tensor([[9., 0, 0, 0]] * 3)}
    allowed, stalled, p = np.ones((3, 4), bool), np.zeros(3, bool), np.array([.1, .9, .1])
    names = [['knight', 'rocket', 'the-log', 'tesla']] * 3
    lethal = [(towers(1, 453, 1092), 1, False), (towers(0, 4000, 4000), 0, False), (towers(0, 453, 1092), 0, True)]
    kw = dict(tau=.35, device='cpu', rngs=[None] * 3, card_names=names, t_sec=[200.0] * 3, grid='lattice',
              lethal=lethal)
    out = decide_batch(Model(), enc, heads, p, allowed, stalled, options=ON, **kw)
    base = decide_batch(Model(), enc, heads, p, allowed, stalled, options=DecisionOptions(spell_aim='rocket_area'), **kw)
    assert out[0] == dict(play=True, slot=1, cell=R_CELL, why='lethal_rocket')    # side 1: raw-left = my R
    assert out[1:] == base[1:]                                                      # non-lethal / pending: unchanged
    with pytest.raises(ValueError, match='lethal_rocket'):
        decide_batch(Model(), enc, heads, p, allowed, stalled, options=ON, **{**kw, 'lethal': None})


def test_match_kwargs_reads_decision_state_side_and_pending():
    tw = towers(1, 453, 1092)
    m = SimpleNamespace(tag='a', k=1, cfg={'lethal_rocket': 'ot', 'grid': 'lattice'}, side=1,
                        deck=SimpleNamespace(cards=['rocket']), state={'episode': {'crown_towers': tw}},
                        _cur=(3700, SimpleNamespace(t_sec=186.3), None))
    kw = match_kwargs([m])
    assert kw['t_sec'] == [186.3] and kw['grid'] == 'lattice' and kw['lethal'] == [(tw, 1, False)]
    m.pending = (3720, .5, {})
    assert match_kwargs([m])['lethal'][0][2] is True


def live_frame(side, enemy_l, enemy_r, elixir=7.3, tick=3700, my_hp=None):
    """A reader frame: my hand Knight / Rocket / Log / Tesla (deck 0-3), towers as ``towers()`` (raw coordinates)."""
    ents = [dict(card_id=-1, kind=12 if t['type'] == 'king' else 13, side=t['side'], x=t['x'], y=t['y'], hp=t['hp'],
                 max_hp=t['max_hp'], address=f'0x{i}') for i, t in enumerate(towers(side, enemy_l, enemy_r, my_hp=my_hp))]
    me = dict(side=side, elixir_raw=int(elixir * 1e4), next_deck_index=4, hand_deck_indices=[0, 1, 2, 3])
    foe = dict(side=1 - side, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[-1] * 4)
    return dict(game_tick=tick, players=[me, foe] if side == 0 else [foe, me], entities=ents)


def live_pilot(options, t_sec, p_gate=-3.):
    pilot = object.__new__(GenPilot)
    pilot.decision_options, pilot.rng_decisions = options, np.random.default_rng(0)
    pilot.dev, pilot.grid, pilot.gate_tau, pilot.public_audit = torch.device('cpu'), 'lattice', .35, False
    names = ['Knight', 'Rocket', 'Log', 'Tesla', 'Xbow', 'IceWizard', 'Skeletons', 'Tornado']
    info = dict(hand=[(1, 0), (2, 0), (3, 0), (4, 0)], costs=[3, 6, 2, 4], el_int=7, names=names,
                hand_deck_indices=[0, 1, 2, 3], bs=SimpleNamespace(t_sec=t_sec, my_elixir=7.3, towers=()))
    pilot.row = lambda frame: ({}, info)
    pilot.stalled = lambda frame, el: False
    pilot.guard_cells = lambda frame, d, logits: logits

    class LiveModel:
        def __call__(self, b, card=None, form=None):
            if card is not None:
                return {'cell': torch.zeros(1, 2304)}
            return {'gate': torch.tensor([p_gate]), 'card': torch.tensor([[9., 0, 0, 0]])}
    pilot.model = LiveModel()
    return pilot


@pytest.mark.parametrize('side', [0, 1])
def test_live_fires_in_ot_on_the_lethal_tower_whatever_the_gate(side):
    d = live_pilot(ON, 215.2).decide(live_frame(side, 453, 1092))
    assert d['play'] and d['name'] == 'Rocket' and d['hand_pos'] == 1 and d['why'] == 'lethal_rocket'
    lane = 'L' if side == 0 else 'R'
    assert d['lethal_rocket'] == dict(lane=lane, hp=453, damage=497, level=15)
    np.testing.assert_allclose(d['xy'], (PRINCESS_X_L if lane == 'L' else PRINCESS_X_R, OPP_PRINCESS_Y))


@pytest.mark.parametrize('frame_args,t_sec', [((453, 1092, 7.3), 179.9),     # regulation
                                             ((800, 1092, 7.3), 215.2),     # nothing lethal
                                             ((453, 1092, 5.5), 215.2)])    # Rocket unaffordable (int 5)
def test_live_unchanged_when_the_rule_does_not_hold(frame_args, t_sec):
    p = live_pilot(ON, t_sec)
    if frame_args[2] < 6:
        p.row(None)[1]['el_int'] = 5
    d = p.decide(live_frame(0, *frame_args))
    q = live_pilot(DecisionOptions(spell_aim='rocket_area'), t_sec)
    if frame_args[2] < 6:
        q.row(None)[1]['el_int'] = 5
    e = q.decide(live_frame(0, *frame_args))
    assert 'why' not in d and d == e and d['play'] is False and d['name'] == 'Knight'


def test_sim_and_live_choose_the_same_slot_and_cell():
    tw_frame = live_frame(1, 453, 1092)
    d = live_pilot(ON, 200.0).decide(tw_frame)
    raw = [dict(side=e['side'], type='king' if abs(e['x'] - 9000) < 1500 else 'princess', x=e['x'], y=e['y'],
                hp=e['hp'], max_hp=e['max_hp']) for e in tw_frame['entities']]
    slot, cell, _ = lethal_rocket_choice(ON, 200.0, ['Knight', 'Rocket', 'Log', 'Tesla'], [True] * 4, raw, 1, 'lattice')
    assert d['hand_pos'] == slot and d['xy'] == cell_xy(cell, 'lattice')


# ---- ot_behind -------------------------------------------------------------------------------------------------
BEHIND = DecisionOptions(lethal_rocket='ot_behind')
NAMES, OK = ['Knight', 'Rocket', 'Log', 'Tesla'], [True] * 4
CUT_T = (3600 - ROCKET_FLIGHT_TICKS) * 0.05                  # last model-board time whose Rocket lands by tick 3600


def test_ot_behind_flag_and_crown_count():
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args(['--lethal-rocket', 'ot_behind']))) == BEHIND
    assert BEHIND.active and ROCKET_FLIGHT_TICKS == 66
    assert crowns_behind(towers(0, 453, 1092, my_hp=(0, 4424)), 0)              # 0-1: behind
    assert crowns_behind(towers(1, 453, 1092, my_hp=(4424, 300)), 1) is False     # 0-0: tied
    assert not crowns_behind(towers(0, 453, 0, my_hp=(0, 4424)), 0)              # 1-1: tied
    assert not crowns_behind(towers(0, 453, 0), 0)                               # 1-0: ahead
    destroyed = [dict(t, hp=0, destroyed=True) if t['side'] == 0 and t['x'] == 3500 and t['type'] == 'princess' else t
                 for t in towers(0, 453, 1092)]                                 # SIM rows keep a destroyed flag
    assert crowns_behind(destroyed, 0)
    assert not crowns_behind([t for t in towers(0, 453, 1092, my_hp=(0, 4424)) if t['type'] != 'king'], 0)


@pytest.mark.parametrize('side', [0, 1])
@pytest.mark.parametrize('enemy', [(453, 1092), (1092, 453)])
def test_ot_behind_fires_in_regulation_only_when_behind_and_finishable(side, enemy):
    behind = towers(side, *enemy, my_hp=(0, 4424))
    slot, cell, target = lethal_rocket_choice(BEHIND, 95.0, NAMES, OK, behind, side, 'lattice')
    raw_left = enemy[0] == 453
    lane = ('L' if raw_left else 'R') if side == 0 else ('R' if raw_left else 'L')   # side 1 mirrors x
    assert slot == 1 and target['lane'] == lane and cell == (L_CELL if lane == 'L' else R_CELL)
    assert lethal_rocket_choice(BEHIND, 95.0, NAMES, OK, towers(side, *enemy), side, 'lattice') is None      # 0-0
    up = [t for t in towers(side, *enemy) if not (t['side'] != side and t['hp'] == 1092)]                 # 1-0 up
    assert lethal_rocket_choice(BEHIND, 95.0, NAMES, OK, up, side, 'lattice') is None
    level = [t for t in up if not (t['side'] == side and t['type'] == 'princess' and t['x'] == 3500)]     # 1-1
    assert lethal_rocket_choice(BEHIND, 95.0, NAMES, OK, level, side, 'lattice') is None
    assert lethal_rocket_choice(ON, 95.0, NAMES, OK, behind, side, 'lattice') is None                       # 'ot'
    assert lethal_rocket_choice(BEHIND, 95.0, NAMES, OK, towers(side, 800, 1092, my_hp=(0, 4424)), side,
                                'lattice') is None                                                         # not finishable
    assert lethal_rocket_choice(BEHIND, 95.0, NAMES, [True, False, True, True], behind, side, 'lattice') is None
    assert lethal_rocket_choice(BEHIND, 95.0, ['Knight', 'Xbow', 'Log', 'Tesla'], OK, behind, side, 'lattice') is None
    assert lethal_rocket_choice(BEHIND, 95.0, NAMES, OK, behind, side, 'lattice', pending=True) is None
    assert lethal_rocket_choice(BEHIND, 95.0, NAMES, OK, towers(side, 4000, 4000, king_hp=100, my_hp=(0, 4424)),
                                side, 'lattice') is None                                                   # never the king


def test_ot_behind_landing_cutoff_and_ot_unchanged():
    behind = towers(0, 453, 1092, my_hp=(0, 4424))
    assert lethal_rocket_choice(BEHIND, CUT_T, NAMES, OK, behind, 0, 'lattice') is not None        # lands at 3600
    assert lethal_rocket_choice(BEHIND, CUT_T + 0.05, NAMES, OK, behind, 0, 'lattice') is None     # cannot land
    assert lethal_rocket_choice(BEHIND, 179.95, NAMES, OK, behind, 0, 'lattice') is None
    tied = towers(0, 453, 1092)
    for t in (180.0, 215.2):                                                                       # OT: as 'ot'
        hit = lethal_rocket_choice(BEHIND, t, NAMES, OK, tied, 0, 'lattice')
        assert hit is not None and hit == lethal_rocket_choice(ON, t, NAMES, OK, tied, 0, 'lattice')


@pytest.mark.parametrize('side', [0, 1])
def test_live_ot_behind_fires_in_regulation_when_behind(side):
    d = live_pilot(BEHIND, 95.0).decide(live_frame(side, 453, 1092, tick=1874, my_hp=(0, 4424)))
    lane = 'L' if side == 0 else 'R'
    assert d['play'] and d['name'] == 'Rocket' and d['why'] == 'lethal_rocket' and d['lethal_rocket']['lane'] == lane
    np.testing.assert_allclose(d['xy'], (PRINCESS_X_L if lane == 'L' else PRINCESS_X_R, OPP_PRINCESS_Y))
    tied = live_pilot(BEHIND, 95.0).decide(live_frame(side, 453, 1092, tick=1874))
    assert 'why' not in tied and tied['play'] is False


@pytest.mark.parametrize('mode', ['off', 'ot'])
def test_off_and_ot_unchanged_in_regulation_incl_rng(mode):
    """A regulation behind-and-finishable state: off / ot decide exactly as the rule-less options, same RNG draws."""
    plain = DecisionOptions(spell_aim='rocket_area', card_choice='filtered', card_ratio=.01)
    frame = live_frame(0, 453, 1092, tick=1874, my_hp=(0, 4424))
    a = live_pilot(DecisionOptions(**{**vars(plain), 'lethal_rocket': mode}), 95.0, p_gate=3.)
    b = live_pilot(plain, 95.0, p_gate=3.)
    da, db = a.decide(frame), b.decide(frame)
    assert da == db and 'why' not in da
    assert a.rng_decisions.bit_generator.state == b.rng_decisions.bit_generator.state


def test_sim_decide_batch_ot_behind_regulation_rows():
    enc = {'g': torch.zeros(2, 2)}
    heads = {'card': torch.tensor([[9., 0, 0, 0]] * 2)}
    names = [['knight', 'rocket', 'the-log', 'tesla']] * 2
    lethal = [(towers(1, 453, 1092, my_hp=(4424, 0)), 1, False), (towers(1, 453, 1092), 1, False)]
    out = decide_batch(Model(), enc, heads, np.array([.1, .1]), np.ones((2, 4), bool), np.zeros(2, bool), tau=.35,
                       device='cpu', options=BEHIND, rngs=[None] * 2, card_names=names, t_sec=[95.0] * 2,
                       grid='lattice', lethal=lethal)
    assert out[0] == dict(play=True, slot=1, cell=R_CELL, why='lethal_rocket') and out[1]['why'] == 'wait'
