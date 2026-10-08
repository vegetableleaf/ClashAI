"""Owner 2026-10-08: the Hero Ice Wizard 'higher bar' -- live_play --iw-press-pstar overrides the fitted P*(V)."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scratchpad/gauntlet/L68/live_reader'))
import ability_ice_wizard as A  # noqa: E402


def test_pstar_override_raises_the_bar(monkeypatch):
    monkeypatch.setattr(A, 'live_features', lambda *a, **k: {})
    monkeypatch.setattr(A, 'frosty_fella_press_probability', lambda feats: 0.025)
    frame = {'game_tick': 1000}
    assert A.P_STAR_BY_V[4.0] < 0.025 < 0.03
    assert A.should_press_pro(None, frame, 1, 900, geometry_ok=True, v_min=4.0)[0] is True             # fitted P* .0196
    assert A.should_press_pro(None, frame, 1, 900, geometry_ok=True, v_min=4.0, p_star=0.03)[0] is False
    assert A.should_press_pro(None, frame, 1, 900, geometry_ok=False, v_min=4.0, p_star=0.01)[0] is False  # geometry still gates
    assert 'P*=0.0300' in A.should_press_pro(None, frame, 1, 900, geometry_ok=True, v_min=4.0, p_star=0.03)[1]
