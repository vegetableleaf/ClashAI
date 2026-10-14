import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cal_summary import pick


def r(name, old, e4, ok=True):
    return dict(name=name, old=old, e4=e4, ok=ok)


def test_pick_closest_to_55_among_old_ge_e4():
    assert pick([r("a", 69, 70), r("b", 57, 56), r("c", 51, 49), r("d", 55, 40, False)])[0]["name"] == "b" 


def test_pick_none_reproduces_live_ranking_takes_lowest_old():
    row, why = pick([r("a", 69, 70), r("b", 60, 64), r("c", 52, 53)])
    assert row["name"] == "c" and "no set reproduces" in why
