"""Owner 10-25 barrel_lane: Knight / Ice Wizard / Skeletons / Tornado answering an enemy Goblin Barrel go to its lane."""
import numpy as np
import torch

from pipeline import decision_options as DO

GRID = "lattice"


def _cell(tx, ty):
    x, y = DO.cell_centres_tiles(GRID)
    return int(np.argmin(np.hypot(x - tx, y - ty)))


def _logits(best):
    x, _ = DO.cell_centres_tiles(GRID)
    lg = torch.zeros(len(x))
    lg[best] = 5.0
    return lg


def test_moves_wrong_lane_defence_to_the_barrel():
    wrong = _cell(14.5, 25.0)                       # right lane, my half
    goblins = [(3.5, 24.0), (4.0, 25.0)]           # left princess
    cell = DO.barrel_lane_cell(_logits(wrong), goblins, wrong, GRID)
    x, y = DO.cell_centres_tiles(GRID)
    assert cell is not None and x[cell] < 9 and y[cell] > 16
    assert min(np.hypot(x[cell] - gx, y[cell] - gy) for gx, gy in goblins) <= DO.BARREL_LANE_TILES


def test_leaves_right_lane_offence_and_split_threats():
    x, _ = DO.cell_centres_tiles(GRID)
    goblins = [(3.5, 24.0)]
    right_lane = _cell(4.0, 22.0)
    assert DO.barrel_lane_cell(_logits(right_lane), goblins, right_lane, GRID) is None          # already its lane
    offence = _cell(14.5, 10.0)
    assert DO.barrel_lane_cell(_logits(offence), goblins, offence, GRID) is None               # enemy half: untouched
    wrong = _cell(14.5, 25.0)
    assert DO.barrel_lane_cell(_logits(wrong), goblins + [(14.0, 24.0)], wrong, GRID) is None  # both lanes threatened
    assert DO.barrel_lane_cell(_logits(wrong), [(3.5, 10.0)], wrong, GRID) is None             # threat not on my half


def test_choose_cells_scope():
    opts = DO.DecisionOptions(barrel_lane="on")
    wrong = _cell(14.5, 25.0)
    lg = torch.stack([_logits(wrong)] * 3)
    barrels = [[(3.5 / 18, 24.0 / 32)], [(3.5 / 18, 24.0 / 32)], []]   # in flight, normalised my frame
    out = DO.choose_cells(lg, ["Knight", "XBow", "IceWizard@hero"], opts, grid=GRID, barrels=barrels,
                          barrel_goblins=[(), (), ((3.5, 24.0),)])
    x, _ = DO.cell_centres_tiles(GRID)
    assert x[int(out[0])] < 9          # Knight moved to the barrel lane
    assert int(out[1]) == wrong        # X-Bow not in scope
    assert x[int(out[2])] < 9          # Hero Ice Wizard moved by the landed goblins
    assert DO.choose_cells(lg[:1], ["Knight"], DO.DecisionOptions(), grid=GRID).tolist() == [wrong]   # off = unchanged
