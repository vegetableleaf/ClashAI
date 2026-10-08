"""Owner 2026-10-07 "one tile left/right": the tap mapping (Layout.board) on both sides and the live legal-cell guard
(pipeline.live_gen.legal_cells / GenPilot.guard_cells). Audit on recorded logs: tap_audit.py."""
from pathlib import Path
import sys

import pytest
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))
import live_play as lp  # noqa: E402
from pipeline import obs_contract  # noqa: E402
from pipeline.live_gen import legal_cells  # noqa: E402
from pipeline.model_v3 import cell_xy  # noqa: E402
from pipeline.tests.test_live_decision_options import icebow_frame, pilot  # noqa: E402
from pipeline.decision_options import DecisionOptions  # noqa: E402

if not (obs_contract.REPO / "research/ext").is_dir() and obs_contract.REPO.parent.name == "worktrees":
    obs_contract.REPO = obs_contract.REPO.parents[2]     # a worktree has no untracked catalog: read the main checkout's

LAY = lp.Layout(900, 1600)
KNIGHT, TESLA, XBOW, LOG, MINER = 26000000, 27000006, 27000008, 28000011, 26000032


def tapped_tiles(px):
    """screen pixel -> continuous my-frame tiles (X 0-18 left->right as I see it, Y 0-32 from my back wall)."""
    fx = (px[0] - LAY.ax0) / (LAY.ax1 - LAY.ax0)
    fy = (px[1] - LAY.ay0) / (LAY.ay1 - LAY.ay0)
    return (1 - fx) * 18, (1 - fy) * 32


def lattice(cx, cy):
    return cx / 36, cy / 64


@pytest.mark.parametrize("side", (0, 1))
def test_centre_taps_land_mid_tile_on_both_sides(side):
    for cx in range(1, 36, 2):
        for cy in range(1, 64, 2):
            X, Y = tapped_tiles(LAY.board(lattice(cx, cy), side))
            assert abs(X - cx / 2) < 0.02 and abs(Y - (32 - cy / 2)) < 0.02      # exact, 0.5 tile from each edge


@pytest.mark.parametrize("side", (0, 1))
def test_spells_and_edge_points_are_tapped_exactly(side):
    for cx, cy in ((0, 0), (18, 32), (17, 33), (35, 63), (10, 40)):
        X, Y = tapped_tiles(LAY.board(lattice(cx, cy), side))
        assert abs(X - cx / 2) < 0.02 and abs(Y - (32 - cy / 2)) < 0.02


@pytest.mark.parametrize("side", (0, 1))
def test_tesla_tap_is_a_quarter_tile_inside_the_tile_whose_native_lower_left_corner_is_the_target(side):
    for cx, cy in ((18, 36), (10, 40), (26, 46), (4, 52)):          # tile corners (even, even)
        X, Y = tapped_tiles(LAY.board(lattice(cx, cy), side, even=True))
        tX, tY = cx / 2, 32 - cy / 2
        nat = (lambda x, y: (18 - x, 32 - y)) if side == 1 else (lambda x, y: (x, y))
        (nx, ny), (ncx, ncy) = nat(X, Y), nat(tX, tY)
        assert abs(nx - ncx - 0.25) < 0.02 and abs(ny - ncy - 0.25) < 0.02, (side, cx, cy, nx - ncx, ny - ncy)


def ok_at(mask, X, Y):
    """mask value at the lattice point of my-frame tiles (X, Y)."""
    return bool(mask[round((1 - Y / 32) * 64) * 36 + round(X / 18 * 36)])


def ent(side, cid, x, y, kind=15, hp=100):
    return dict(side=side, card_id=cid, x=x, y=y, kind=kind, hp=hp)


def towers(king_kind=13, princess_kind=13):
    """Six standing towers, native coordinates (side 0 at the native bottom). The reader's `kind` is a STATE, not a
    tower type (10-05..07 play decisions: kings read 12 asleep / 13 awake -- 2,505 + 3,252 x 13 -- princesses 13, and
    12 in 63): default = both kings awake (13), the case a kind-keyed guard reads as a third princess."""
    return [ent(0, -1, 9000, 3000, king_kind), ent(0, -1, 3500, 6500, princess_kind),
            ent(0, -1, 14500, 6500, princess_kind), ent(1, -1, 9000, 29000, king_kind),
            ent(1, -1, 3500, 25500, princess_kind), ent(1, -1, 14500, 25500, princess_kind)]


def test_spells_and_deploy_anywhere_cards_are_never_restricted():
    assert legal_cells(towers(), 1, LOG, "Log") is None
    assert legal_cells(towers(), 1, MINER, "Miner") is None


@pytest.mark.parametrize("side", (0, 1))
def test_own_towers_block_their_footprint_only(side):
    m = legal_cells(towers(), side, KNIGHT, "Knight")
    assert not ok_at(m, 3.5, 6.5) and not ok_at(m, 14.5, 6.5) and not ok_at(m, 9.5, 3.5)   # princess / king
    assert ok_at(m, 3.5, 8.5) and ok_at(m, 5.5, 6.5) and ok_at(m, 9.5, 5.5)                # the next tile out
    t = legal_cells(towers(), side, TESLA, "Tesla")
    assert not ok_at(t, 4.0, 8.0) and ok_at(t, 4.0, 9.0)       # 2x2 overlapping the princess / touching it


@pytest.mark.parametrize("side", (0, 1))
def test_own_tesla_blocks_a_knight_dropped_on_it_but_a_huts_walking_spawn_does_not(side):
    nat = (lambda X, Y: (18000 - X, 32000 - Y)) if side == 1 else (lambda X, Y: (X, Y))
    m = legal_cells(towers() + [ent(side, TESLA, *nat(9000, 14000), kind=12)], side, KNIGHT, "Knight")
    assert not ok_at(m, 9.5, 14.5) and not ok_at(m, 8.5, 13.5)          # the live case: Knight on its own Tesla
    assert ok_at(m, 10.5, 14.5) and ok_at(m, 7.5, 14.5)
    goblin = ent(side, 27000001, *nat(9000 + 237, 14000 - 120))         # GoblinHut id on a walking body
    assert ok_at(legal_cells(towers() + [goblin], side, KNIGHT, "Knight"), 9.5, 14.5)


@pytest.mark.parametrize("side", (0, 1))
def test_river_and_enemy_half_only_through_an_open_pocket(side):
    m = legal_cells(towers(), side, KNIGHT, "Knight")
    assert ok_at(m, 8.5, 14.5) and not ok_at(m, 8.5, 15.5) and not ok_at(m, 8.5, 20.5)
    # enemy princess on MY-frame right (X 14.5) destroyed: its pocket opens, the left one stays shut
    right_native_x = 3500 if side == 1 else 14500
    ents = [e for e in towers() if not (e["side"] != side and e["y"] in (6500, 25500) and e["x"] == right_native_x)]
    m = legal_cells(ents, side, KNIGHT, "Knight")
    assert ok_at(m, 9.5, 20.5) and not ok_at(m, 8.5, 20.5)            # the live 2026-10-07 (8.5, 20.5) -> 9.5 case
    assert not legal_cells(ents, side, TESLA, "Tesla")[round((1 - 20 / 32) * 64) * 36 + 18]   # centre line: shut


@pytest.mark.parametrize("side", (0, 1))
@pytest.mark.parametrize("king_kind,princess_kind", ((12, 13), (13, 13), (13, 12)))
def test_towers_are_told_apart_by_position_not_by_reader_kind(side, king_kind, princess_kind):
    """An awake king (kind 13) is not a third princess, an asleep princess (kind 12) still stands, and my king keeps
    its 4x4 footprint whatever its kind (live verifier 2026-10-07: the kind-keyed guard shut an open pocket in 1,370
    of 11,425 play decisions)."""
    right_native_x = 3500 if side == 1 else 14500
    ents = [e for e in towers(king_kind, princess_kind)
            if not (e["side"] != side and e["y"] in (6500, 25500) and e["x"] == right_native_x)]
    m = legal_cells(ents, side, KNIGHT, "Knight")
    assert ok_at(m, 9.5, 20.5) and ok_at(m, 14.5, 18.5)               # right pocket open
    assert not ok_at(m, 3.5, 20.5) and not ok_at(m, 8.5, 18.5)        # left princess (any kind) still stands
    assert not ok_at(m, 9.5, 4.5) and not ok_at(m, 7.5, 1.5)          # my king's 4x4 footprint (x 7-11, y 1-5)


@pytest.mark.parametrize("side", (0, 1))
def test_an_open_pocket_ends_at_y_21_and_starts_past_the_river(side):
    right_native_x = 3500 if side == 1 else 14500
    ents = [e for e in towers() if not (e["side"] != side and e["y"] in (6500, 25500) and e["x"] == right_native_x)]
    m = legal_cells(ents, side, KNIGHT, "Knight")
    assert ok_at(m, 12.5, 17.5) and ok_at(m, 12.5, 20.5)              # live: 27/27 troops at y 20.5 landed as aimed
    assert not ok_at(m, 12.5, 21.5) and not ok_at(m, 12.5, 15.5) and not ok_at(m, 12.5, 16.5)
    t = legal_cells(ents, side, TESLA, "Tesla")
    assert ok_at(t, 12.0, 20.0) and not ok_at(t, 12.0, 23.0)          # live: a Tesla corner at 23.0 was moved to 20.0
    assert not ok_at(t, 12.0, 17.0) and ok_at(t, 12.0, 18.0)          # footprint must clear the river (y < 17)
    x = legal_cells(ents, side, XBOW, "Xbow")
    assert ok_at(x, 12.5, 18.5) and not ok_at(x, 12.5, 20.5)          # live: X-Bows at 18.5 accepted 2/2


def open_right(side):
    """towers() with the enemy princess on MY-frame right destroyed."""
    right_native_x = 3500 if side == 1 else 14500
    return [e for e in towers() if not (e["side"] != side and e["y"] in (6500, 25500) and e["x"] == right_native_x)]


@pytest.mark.parametrize("side", (0, 1))
def test_a_cursed_troop_on_a_dead_princess_spot_is_not_a_standing_princess(side):
    """card_id -1 + kind 15 = a cursed troop (live 20261007_132112 ticks 1997-2159 stood on a princess position)."""
    right_native_x = 3500 if side == 1 else 14500
    cursed = ent(1 - side, -1, right_native_x, 25500 if side == 0 else 6500, kind=15)
    m = legal_cells(open_right(side) + [cursed], side, KNIGHT, "Knight")
    assert ok_at(m, 14.5, 18.5) and ok_at(m, 9.5, 20.5)


@pytest.mark.parametrize("side", (0, 1))
def test_a_building_footprint_must_lie_wholly_on_my_half(side):
    """arena.rs box_zone: an X-Bow centred at y 14.5 reaches y 16 (river); a Tesla corner at y 15 reaches 16."""
    x = legal_cells(towers(), side, XBOW, "Xbow")
    assert ok_at(x, 12.5, 13.5) and not ok_at(x, 12.5, 14.5)
    t = legal_cells(towers(), side, TESLA, "Tesla")
    assert ok_at(t, 12.0, 14.0) and not ok_at(t, 12.0, 15.0)
    assert ok_at(legal_cells(towers(), side, KNIGHT, "Knight"), 12.5, 14.5)


@pytest.mark.parametrize("side", (0, 1))
def test_an_enemy_goblin_drill_blocks_its_2x2_but_a_digging_body_does_not(side):
    """live: my Tesla on an enemy Goblin Drill (corner (16, 10) / (15, 9), my half) was moved 5/5 (151240 t1179,
    155830 t3262, 222521 t3464 / t4922)."""
    nat = (lambda X, Y: (18000 - X, 32000 - Y)) if side == 1 else (lambda X, Y: (X, Y))
    drill = ent(1 - side, 27000013, *nat(16000, 10000), kind=12)
    t = legal_cells(towers() + [drill], side, TESLA, "Tesla")
    assert not ok_at(t, 15.0, 9.0) and not ok_at(t, 16.0, 11.0)       # 2x2 vs 2x2 overlap
    assert ok_at(t, 14.0, 9.0) and ok_at(t, 16.0, 12.0)               # touching edges only
    assert not ok_at(legal_cells(towers() + [drill], side, KNIGHT, "Knight"), 15.5, 9.5)
    digging = ent(1 - side, 27000013, *nat(16000, 10500))              # mixed corner/centre position: not placed
    assert ok_at(legal_cells(towers() + [digging], side, TESLA, "Tesla"), 15.0, 9.0)


def guarded(cell_first, cell_second, legal_guard=True, gate_p=.6, options=None):
    logits = torch.full((36 * 64,), -5.0)
    logits[cell_first], logits[cell_second] = 9.0, 8.0
    p = pilot(options or DecisionOptions(), gate_p, card_logits=(9., 0., 0., 0.), cell=logits)   # pos 0 = Knight
    p.legal_guard = legal_guard
    return p.decide(icebow_frame(1000, side=1))


def cell_of(X, Y):
    return round((1 - Y / 32) * 64) * 36 + round(X / 18 * 36)


@pytest.mark.parametrize("options", (DecisionOptions(), DecisionOptions(tau_phase=(.3, .5, .7))))  # legacy / v2 path
def test_guard_re_aims_an_illegal_argmax_to_the_best_legal_cell_and_logs_it(options):
    on_tower, beside = cell_of(14.5, 6.5), cell_of(14.5, 8.5)          # my princess (side 1 frame) / the tile above
    d = guarded(on_tower, beside, options=options)
    assert d["play"] and d["name"] == "Knight"
    assert d["xy"] == cell_xy(beside, "lattice") and d["xy_unguarded"] == cell_xy(on_tower, "lattice")


def test_guard_off_or_legal_argmax_or_wait_leaves_the_decision_unchanged():
    on_tower, beside = cell_of(14.5, 6.5), cell_of(14.5, 8.5)
    d = guarded(on_tower, beside, legal_guard=False)
    assert d["xy"] == cell_xy(on_tower, "lattice") and "xy_unguarded" not in d
    d = guarded(beside, on_tower)
    assert d["xy"] == cell_xy(beside, "lattice") and "xy_unguarded" not in d
    d = guarded(on_tower, beside, gate_p=.2)                            # WAIT: logged xy keeps the plain argmax
    assert not d["play"] and d["xy"] == cell_xy(on_tower, "lattice") and "xy_unguarded" not in d


def test_live_play_turns_the_guard_on_by_default_and_the_flag_turns_it_off(monkeypatch):
    from types import SimpleNamespace
    made = []

    class Fake:
        def __init__(self, *a, **k):
            made.append(self)
    monkeypatch.setattr(lp, "GenPilot", Fake)
    base = dict(device="cpu", tau=.35, no_opp_counter=False, extrapolate=26, decision_seed=0, public_audit=True,
                ckpt="x.pt")
    assert lp.load_pilot(SimpleNamespace(**base, no_legal_guard=False), {})[1].legal_guard is True
    assert lp.load_pilot(SimpleNamespace(**base, no_legal_guard=True), {})[1].legal_guard is False
