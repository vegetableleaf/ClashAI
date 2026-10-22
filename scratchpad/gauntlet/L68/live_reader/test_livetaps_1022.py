"""W21 10-22 (L74/livetaps): deploy_closed (no taps in the tiebreak drain) and button_cells (cells under the hero button)."""
import live_play as LP
from pipeline.model_v3 import cell_xy


def _cell(x_tiles, y_from_back):
    """lattice cell index of (x tiles, y tiles from my back edge) in my frame."""
    return int(round(x_tiles * 2)) + 36 * int(round((1 - y_from_back / 32) * 64))


def test_deploy_closed_boundary():
    # measured: the latest taken tap 5976 (landing 6001); none of the taps that would land at >= 6002 was taken
    assert not LP.deploy_closed(5976) and not LP.deploy_closed(5979)
    assert LP.deploy_closed(5980) and LP.deploy_closed(6150)
    assert not LP.deploy_closed(150) and not LP.deploy_closed(3600)


def test_button_cells_cover_the_corner_not_the_mirror():
    m = LP.button_cells(LP.Layout(900, 1600), "lattice")
    corner, mirror, lane = _cell(0.5, 1.5), _cell(17.5, 1.5), _cell(3.5, 10.0)
    assert cell_xy(corner, "lattice") == (0.5 / 18, 1 - 1.5 / 32)
    assert m[corner] and not m[mirror] and not m[lane]
    assert 5 <= int(m.sum()) <= 40                  # a dozen-odd lattice points of the back corner, nothing else
