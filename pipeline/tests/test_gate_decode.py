"""W4 hazard gate decoding: the rate inversion, the threshold default, and its live wiring in live_gen_v2.GenPilot
(the pilot live_play.py loads): cadence invariance, the step rule (pending / lockout accrue nothing, the cap), and
missing context raising instead of silently waiting."""
import math
from dataclasses import replace

import numpy as np
import pytest
import torch

from pipeline import live_gen_v2
from pipeline.decision_options import (DecisionOptions, PLAY_WINDOW_S, WAIT_STRIDE_S, decide_batch, gate_rate,
                                       hazard_draw, hazard_play)

LIVE = DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0)


def test_gate_rate_inverts_row_odds():
    r = np.array([0.0, 0.05, 0.16, 0.6, 2.0])
    o = WAIT_STRIDE_S * r * np.exp(PLAY_WINDOW_S * r)
    assert np.allclose(gate_rate(o / (1 + o)), r, atol=1e-7)


def test_hazard_draw_frequency():
    rng = np.random.default_rng(0)
    q = np.mean([hazard_play(0.3, 0.5, rng) for _ in range(20000)])
    assert abs(q - (1 - math.exp(-gate_rate(0.3) * 0.5))) < 0.01


def test_threshold_is_default_and_inactive():
    assert DecisionOptions().gate_decode == 'threshold' and not DecisionOptions().active
    assert DecisionOptions(gate_decode='hazard_below_tau').active


def test_min_elixir_bounds():
    assert DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0).gate_hazard_min_elixir == 9.0
    with pytest.raises(ValueError):
        DecisionOptions(gate_hazard_min_elixir=11.0)


# ---- live wiring ----------------------------------------------------------------------------------------------------
def _live_pilot(options, gate_p, seed=0):
    from pipeline.tests.test_live_decision_options import icebow_frame, pilot
    p = pilot(options, gate_p=gate_p, seed=seed)
    f = icebow_frame(tick=1000)                        # 10 elixir, X-Bow argmax, one enemy body on the board
    cached = p.row(f)
    p.row = lambda frame: cached                       # the frame parse is not under test; decide() is
    return p, f


def _set_gate(p, gate_p):
    p.model.gate = torch.logit(torch.tensor([gate_p], dtype=torch.float64)).float()


def _plays_within(options, gate_p, every, horizon_ticks, seed):
    p, f = _live_pilot(options, gate_p, seed)
    for t in range(0, horizon_ticks + 1, every):
        f['game_tick'] = 1000 + t
        if p.decide(f)['play']:
            return True
    return False


@pytest.mark.parametrize('every,n', [(2, 800), (10, 2000), (30, 2000)])
def test_live_cadence_invariance(every, n):
    """Fixed p .25 (below tau): P(play within 6 s -- a common multiple of the three cadences, so every cadence has a
    decision exactly at the horizon) = the learned rate integrated over 6 s, whether live decides every 2, 10 or 30
    ticks."""
    hits = sum(_plays_within(LIVE, .25, every, 120, seed) for seed in range(n))
    want = 1 - math.exp(-6 * float(gate_rate(.25)))
    assert abs(hits / n - want) < 4 * math.sqrt(want * (1 - want) / n), (every, hits / n, want)


def test_live_step_rule_pending_and_lockout_add_no_hazard():
    p, f = _live_pilot(LIVE, .6)
    f['game_tick'] = 1000
    d = p.decide(f)
    assert d['play'] and d['hazard_step_s'] == 0.0 and not d['hazard_play']      # first decision; a gate play
    _set_gate(p, .25)
    f['game_tick'] = 1060                                                         # after a 3-s pending window
    d = p.decide(f)
    assert d['hazard_step_s'] == 0.0 and not d['play']                           # pending time accrues nothing
    f['game_tick'] = 1070
    assert p.decide(f)['hazard_step_s'] == .5
    f['game_tick'] = 1170                                                         # a 5-s reader gap: capped
    assert p.decide(f)['hazard_step_s'] == live_gen_v2.HAZARD_STEP_CAP_S
    b, info = p.row(f)
    p.row = lambda frame: (b, dict(info, costs=[99.0] * 4))                        # nothing affordable
    f['game_tick'] = 1180
    assert p.decide(f)['no_affordable']
    p.row = lambda frame: (b, info)
    f['game_tick'] = 1190
    assert p.decide(f)['hazard_step_s'] == 0.0                                    # a lockout interval accrues nothing
    plays = 0
    for seed in range(300):                     # a play, then 10 s pending at p .34 < tau: step 0 -> never a hazard play
        q, g = _live_pilot(LIVE, .6, seed)
        g['game_tick'] = 1000
        q.decide(g)
        _set_gate(q, .34)
        g['game_tick'] = 1200
        plays += q.decide(g)['play']
    assert plays == 0


def test_live_reset_match_clears_the_step_clock():
    p, f = _live_pilot(LIVE, .25)
    f['game_tick'] = 1000
    p.decide(f)
    p.match_index, p.decision_seed = -1, 0             # the stub skips __init__
    p.reset_match()
    f['game_tick'] = 1010
    assert p.decide(f)['hazard_step_s'] == 0.0


def test_live_missing_context_raises_not_noop():
    p, f = _live_pilot(LIVE, .25)
    b, info = p.row(f)
    p.row = lambda frame: (b, dict(info, bs=replace(info['bs'], my_elixir=None)))
    f['game_tick'] = 1000
    with pytest.raises(ValueError):
        p.decide(f)
    with pytest.raises(ValueError):
        hazard_draw(LIVE, .25, .5, np.random.default_rng(0), elixir=None)
    with pytest.raises(ValueError):
        hazard_draw(DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_quiet=True), .25, .5,
                    np.random.default_rng(0), enemy_units=None)
    with pytest.raises(ValueError):
        hazard_draw(LIVE, .25, None, np.random.default_rng(0), elixir=10)
    with pytest.raises(ValueError):                                               # SIM path without the decision step
        decide_batch(None, {}, {'card': np.zeros((1, 4))}, [.25], np.ones((1, 4), bool), np.zeros(1, bool),
                     tau=.35, device='cpu', options=LIVE, rngs=[np.random.default_rng(0)], card_names=None)


@pytest.mark.parametrize('enemy', [False, True])
def test_live_quiet_scope_draws_only_on_an_enemy_empty_board(enemy):
    q, g = _live_pilot(DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_quiet=True), .34)
    b, info = q.row(g)                                 # the test frame holds one body, mine (my frame side 0)
    if enemy:
        info = dict(info, bs=replace(info['bs'], units=tuple(replace(u, side=1) for u in info['bs'].units)))
    q.row = lambda frame: (b, info)
    plays = 0
    for t in range(200):
        g['game_tick'] = 1000 + 10 * t
        plays += q.decide(g)['play']
    assert (plays == 0) if enemy else plays > 0


def test_live_threshold_options_consume_no_hazard_rng():
    p, f = _live_pilot(DecisionOptions(tau_phase=(.35, .45, .55)), .25)
    for t in range(20):
        f['game_tick'] = 1000 + 10 * t
        d = p.decide(f)
        assert not d['play'] and 'hazard_step_s' not in d
    assert p.rng_decisions.bit_generator.state == np.random.default_rng(0).bit_generator.state
