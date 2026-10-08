"""W4 hazard gate decoding: the rate inversion and the threshold default."""
import math

import numpy as np

from pipeline.decision_options import DecisionOptions, PLAY_WINDOW_S, WAIT_STRIDE_S, gate_rate, hazard_play


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
    import pytest
    assert DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0).gate_hazard_min_elixir == 9.0
    with pytest.raises(ValueError):
        DecisionOptions(gate_hazard_min_elixir=11.0)
