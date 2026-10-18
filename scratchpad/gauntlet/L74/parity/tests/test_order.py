"""H-ORDER (diag_night/r6a): fights.live_creation_order deals creation_seq out in live generation order, team_seq untouched."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity import fights as F


def test_live_creation_order_reorders_seq_values_in_generation_order():
    E = dict(team=['Blue', 'Blue', 'Red', 'Red', 'Blue'], creation_seq=[6, 7, 8, 9, 2], team_seq=[3, 4, 3, 4, 1])
    F.live_creation_order(E, {0: 103, 1: 101, 2: 100, 3: 102})       # index 4 (a tower) is not a set-up body
    assert E['creation_seq'] == [9, 7, 6, 8, 2]
    assert E['team_seq'] == [3, 4, 3, 4, 1]
    assert F.live_creation_order(E, {}) is E and E['creation_seq'] == [9, 7, 6, 8, 2]
