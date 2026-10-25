"""Owner 10-25 lethal_quiet: the finishing Rocket / Log skips an enemy princess something else damaged in the last second."""
import pytest

from pipeline import decision_options as DO


def _towers(hp_l=400, hp_r=4000):
    return [{"side": 0, "type": "princess", "x": 3500, "y": 5500, "hp": 4858, "max_hp": 4858},
            {"side": 0, "type": "king", "x": 9000, "y": 2500, "hp": 7728, "max_hp": 7728},
            {"side": 1, "type": "princess", "x": 3500, "y": 26500, "hp": hp_l, "max_hp": 4858},
            {"side": 1, "type": "princess", "x": 14500, "y": 26500, "hp": hp_r, "max_hp": 4858}]


def test_recently_hit():
    h = [(100, {"L": 900, "R": 4000}), (110, {"L": 600, "R": 4000}), (125, {"L": 400, "R": 4000})]
    assert DO.recently_hit(h, 125, 20) == {"L"}            # 600 -> 400 within the last 20 ticks
    assert DO.recently_hit(h, 125, 10) == set()            # only snapshots from tick 115 on: none before now
    assert DO.recently_hit(h[-1:], 125, 20) == set()       # no earlier evidence: not hit
    assert DO.recently_hit(h, 999, 20) == set()            # no snapshot at the asked tick


def test_target_skip():
    t = DO.lethal_rocket_target(_towers(), 0)
    assert t is not None and t["lane"] == "L"
    assert DO.lethal_rocket_target(_towers(), 0, skip={"L"}) is None
    both = _towers(hp_r=300)
    assert DO.lethal_rocket_target(both, 0, skip={"R"})["lane"] == "L"   # the quiet lethal tower is still taken


def test_option_validates():
    assert DO.DecisionOptions(lethal_quiet=1.0).lethal_quiet == 1.0
    with pytest.raises(ValueError):
        DO.DecisionOptions(lethal_quiet=-1.0)
