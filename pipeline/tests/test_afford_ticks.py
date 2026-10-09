"""L74 afford horizon (live --afford-ticks / SIM cfg 'afford_ticks'): unset = today's mask; A == the look-ahead H
reproduces it exactly; A < H blocks a card that can be paid only between A and H ticks after the decision frame."""
from types import SimpleNamespace

import numpy as np
import pytest

from pipeline import e1_eval as E
from pipeline import live_gen_v2
from pipeline.decision_options import DecisionOptions
from pipeline.live_gen import GenPilot as LegacyGenPilot
from pipeline.opp_elixir_count import regen_between
from pipeline.tests.test_live_decision_options import OPTS, icebow_frame, pilot

XBOW_FIRST = (0., 9., 0., 0.)          # hand Knight 3, Xbow 6, Rocket 6, Tesla 4: the model wants the X-Bow


def frame(tick, elixir):
    f = icebow_frame(tick)
    f['players'][1]['elixir_raw'] = round(elixir * 1e4)
    return f


@pytest.mark.parametrize('cls,options', [(live_gen_v2.GenPilot, DecisionOptions()), (live_gen_v2.GenPilot, OPTS),
                                         (LegacyGenPilot, None)])
def test_afford_ticks_equal_to_the_lookahead_is_byte_identical(cls, options):
    for tick in (1000, 2390, 2400, 4790, 5990):                # 1x, the 2x / 3x boundaries, the end of regen
        for el in np.arange(0.0, 10.01, 0.137):
            base, same = pilot(options, ext_h=26, cls=cls), pilot(options, ext_h=26, cls=cls, seed=0)
            same.afford_ticks = 26
            f = frame(tick, float(el))
            _, info = base.row(f)
            _, info2 = same.row(f)
            assert info2['el_afford'] == info['el_int'] == info['el_afford'], (tick, el)
            assert base.decide(f) == same.decide(f)


@pytest.mark.parametrize('cls,options', [(live_gen_v2.GenPilot, DecisionOptions()), (LegacyGenPilot, None)])
def test_shorter_horizon_blocks_a_card_paid_only_after_it(cls, options):
    tick, el = 1000, 5.6                                       # 1x: 6.0 is reached 23 ticks later
    assert 5.6 + regen_between(tick, tick + 22) < 6 <= 5.6 + regen_between(tick, tick + 26)
    old = pilot(options, card_logits=XBOW_FIRST, ext_h=26, cls=cls)
    new = pilot(options, card_logits=XBOW_FIRST, ext_h=26, cls=cls)
    new.afford_ticks = 22
    f = frame(tick, el)
    assert old.decide(f)['name'] == 'Xbow'
    d = new.decide(f)
    assert d['name'] != 'Xbow' and d['name'] in ('Knight', 'Tesla')
    new.afford_ticks = 23
    assert new.decide(f)['name'] == 'Xbow'


def test_model_input_is_unchanged_by_the_afford_horizon():
    a, b = pilot(OPTS, ext_h=26), pilot(OPTS, ext_h=26)
    b.afford_ticks = 10
    f = frame(1000, 5.6)
    ra, _ = a.row(f)
    rb, _ = b.row(f)
    assert ra.keys() == rb.keys() and all(bool((ra[k] == rb[k]).all()) for k in ra)


def sim(cfg_extra, view_elixir, raw_elixir, tick=1000):
    """A prepared SIM match, just what Match.pre reads; slots 0..7 cost the Icebow deck's elixir."""
    return SimpleNamespace(cfg=dict(policy='live', afford_mask=True, stall_elixir=None, stall_seconds=12.0, **cfg_extra),
                           _cur=(tick, None, SimpleNamespace(my_elixir=view_elixir)), costs=[3, 6, 6, 4, 2, 6, 3, 1],
                           last_play_tick=0, side=0,
                           state={'players': [{'side': 0, 'elixir_exact': raw_elixir}, {'side': 1, 'elixir_exact': 9.0}]})


def test_sim_pre_unset_and_equal_horizon_match_the_view_mask():
    hand = np.array([1, 1, 1, 1, 0, 0, 0, 0], bool)
    raw = 5.6
    view = min(10.0, raw + regen_between(1000, 1026))          # what extrapolate shows at H = 26
    base = E.Match.pre(sim({}, view, raw), hand)
    assert E.Match.pre(sim({'afford_ticks': 26}, view, raw), hand)[1].tolist() == base[1].tolist()
    el, allowed, _ = E.Match.pre(sim({'afford_ticks': 22}, view, raw), hand)
    assert base[1].tolist() == [True, True, True, True, False, False, False, False]
    assert allowed.tolist() == [True, False, False, True, False, False, False, False] and el == int(view)


def test_afford_elixir_matches_extrapolate_on_both_state_forms():
    from pipeline.extrapolate import extrapolate
    for raw in (0.0, 3.3, 5.6, 9.99, 10.0):
        live = {'game_tick': 2390, 'players': [{'side': 1, 'elixir_raw': round(raw * 1e4)}], 'entities': []}
        sim_state = {'tick': 2390, 'players': [{'side': 1, 'elixir_exact': raw}], 'entities': []}
        assert E.afford_elixir(live['players'], 1, 2390, 26) == extrapolate(live, None, 26, 1)['players'][0]['elixir_raw'] / 1e4
        assert E.afford_elixir(sim_state['players'], 1, 2390, 26) == extrapolate(sim_state, None, 26, 1)['players'][0]['elixir_exact']
