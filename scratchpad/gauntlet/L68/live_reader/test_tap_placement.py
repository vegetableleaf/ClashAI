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


def towers():
    """Six standing towers, native coordinates (side 0 at the native bottom)."""
    return [ent(0, -1, 9000, 3000, 12), ent(0, -1, 3500, 6500, 13), ent(0, -1, 14500, 6500, 13),
            ent(1, -1, 9000, 29000, 12), ent(1, -1, 3500, 25500, 13), ent(1, -1, 14500, 25500, 13)]


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
    ents = [e for e in towers() if not (e["side"] != side and e["kind"] == 13 and e["x"] == right_native_x)]
    m = legal_cells(ents, side, KNIGHT, "Knight")
    assert ok_at(m, 9.5, 20.5) and not ok_at(m, 8.5, 20.5)            # the live 2026-10-07 (8.5, 20.5) -> 9.5 case
    assert not legal_cells(ents, side, TESLA, "Tesla")[round((1 - 20 / 32) * 64) * 36 + 18]   # centre line: shut


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
