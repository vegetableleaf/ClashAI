"""Discrete action space: (hand slot, placement grid cell) -> screen tap points.

The placement grid is anchored to the ARENA PLAYFIELD rectangle (``action.arena_box`` =
normalized [x0, y0, x1, y1] of the board's corners), NOT the full frame, and sized to
Clash Royale's tile lattice (``action.grid`` = 18 columns x 32 rows by default = one cell
per board tile). ``cell_center`` (grid -> normalized tap) and ``coords_to_grid`` / ``cell_at``
(normalized -> grid) are exact inverses over that box, and the labeler + reward helpers
quantize plays through the SAME methods, so a play the policy predicts decodes back to the
tile it was trained on. Cells are clamped to the arena band so a greedy pick never lands on
the card tray.

NB the on-screen board has a mild 3D perspective tilt, so one uniform rectangle is a close
APPROXIMATION of the tile lattice, not a pixel-exact homography; calibrate ``action.arena_box``
to the visible grass corners for the tightest alignment.
"""
from __future__ import annotations


class BoardWarp:
    """Tower-anchored PIECEWISE-LINEAR mapping between BOARD-normalized coordinates (the sim
    engine's space: my princess row = 1 - 6.5/32 = 0.797, my king = 0.906) and FRAME-normalized
    screen coordinates (the capture: my princess measured at ~0.615, king ~0.72).

    WHY (measured 2026-08-14): the screen renders the arena with PERSPECTIVE -- the measured
    frame-per-board slope is ~0.87 near the enemy side, ~0.69 mid-board and ~0.96 near our king
    -- so the single-affine `arena_box` cannot be right anywhere except where it was eyeballed.
    A sim-trained placement 'at my princess' tapped ~3-4 tiles DEEP everywhere on our half, and
    the detector canvas painted units the same 3-4 tiles off vs the sim's board-true training
    canvas. Placements collapsed toward the clamped edges live while the sim spread was healthy.

    Anchors come from the config's own measured tower positions (env.my_towers/enemy_towers) +
    the sim board's tile geometry, so no new calibration is needed; segments interpolate
    linearly between anchors and extrapolate with the edge slopes (clamped to [0, 1]). If the
    anchor lists are missing, both directions degrade to the plain arena-box affine."""

    def __init__(self, cfg, bx0, by0, bx1, by1):
        self.bx0, self.by0, self.bx1, self.by1 = bx0, by0, bx1, by1
        mt = cfg.get("env", "my_towers", default=None)
        et = cfg.get("env", "enemy_towers", default=None)
        b = dict(cfg.get("sim", "board", default=None) or {})
        tx, ty = float(b.get("tiles_x", 18.0)), float(b.get("tiles_y", 32.0))
        pt = list(b.get("princess_tile", [3.5, 6.5]))
        kt = list(b.get("king_tile", [9.0, 3.0]))
        self.ok = bool(mt and et and len(mt) >= 3 and len(et) >= 3)
        if not self.ok:
            return
        # y anchors: (board_y, frame_y), ordered top (enemy) -> bottom (mine)
        ek_b, ep_b = kt[1] / ty, pt[1] / ty                    # enemy king 0.094, princess 0.203
        mp_b, mk_b = 1.0 - pt[1] / ty, 1.0 - kt[1] / ty        # mine 0.797, 0.906
        ep_f = (float(et[0][1]) + float(et[1][1])) / 2.0
        mp_f = (float(mt[0][1]) + float(mt[1][1])) / 2.0
        self.ya = [(ek_b, float(et[2][1])), (ep_b, ep_f), (mp_b, mp_f), (mk_b, float(mt[2][1]))]
        # x anchors: princess columns + the king column (average of both sides' measurements)
        lx_b, rx_b = pt[0] / tx, 1.0 - pt[0] / tx              # 0.194 / 0.806
        lx_f = (float(mt[0][0]) + float(et[0][0])) / 2.0
        rx_f = (float(mt[1][0]) + float(et[1][0])) / 2.0
        kx_f = (float(mt[2][0]) + float(et[2][0])) / 2.0
        self.xa = [(lx_b, lx_f), (0.5, kx_f), (rx_b, rx_f)]

    @staticmethod
    def _pw(v, anchors):
        """Piecewise-linear through `anchors` [(a, b), ...] sorted by a; edge-slope extrapolation."""
        if v <= anchors[0][0]:
            (a0, b0), (a1, b1) = anchors[0], anchors[1]
        elif v >= anchors[-1][0]:
            (a0, b0), (a1, b1) = anchors[-2], anchors[-1]
        else:
            for i in range(len(anchors) - 1):
                if anchors[i][0] <= v <= anchors[i + 1][0]:
                    (a0, b0), (a1, b1) = anchors[i], anchors[i + 1]
                    break
        t = (v - a0) / max(1e-9, a1 - a0)
        return b0 + t * (b1 - b0)

    def board_to_frame(self, nx: float, ny: float):
        if not self.ok:
            return (self.bx0 + nx * (self.bx1 - self.bx0),
                    self.by0 + ny * (self.by1 - self.by0))
        return (min(max(self._pw(nx, self.xa), 0.0), 1.0),
                min(max(self._pw(ny, self.ya), 0.0), 1.0))

    def frame_to_board(self, fx: float, fy: float):
        if not self.ok:
            return ((fx - self.bx0) / max(1e-9, self.bx1 - self.bx0),
                    (fy - self.by0) / max(1e-9, self.by1 - self.by0))
        inv_x = [(f, b) for b, f in self.xa]
        inv_y = [(f, b) for b, f in self.ya]
        return (min(max(self._pw(fx, inv_x), 0.0), 1.0),
                min(max(self._pw(fy, inv_y), 0.0), 1.0))


class ActionSpace:
    def __init__(self, cfg):
        self.slots = cfg.get("hand", "slots", default=[])
        self.gw, self.gh = cfg.get("action", "grid", default=[18, 32])
        self.a_top = float(cfg.get("label", "arena_top", default=0.10))
        self.a_bot = float(cfg.get("label", "arena_bottom", default=0.86))
        self.deploy_top = float(cfg.get("action", "deploy_top", default=0.44))
        # FIRST LEGAL TROOP ROW, decided in BOARD space (2026-08-14). deploy_top is a FRAME-y
        # line tuned in the affine era; converting it to a row with the affine row_at() while
        # the actual taps go through the WARP let the mask permit rows whose taps land on the
        # river or the enemy side. MEASURED on the 2026-08-14 evening live sessions: 33% of one
        # session's plays (23/70) tapped row 11 at frame y=0.40 -- enemy side of the real river
        # (warp puts board 0.5 at frame 0.410) -- and 17 more hit row 12 inside the water band;
        # every such troop tap is refused in-game, the card just sits selected, and the bot
        # 'shuffles' without deploying. The river is a BOARD fact, so the rule lives in board
        # space (bottom of the water band = 0.5 + one 1/32 game tile) and is warp-independent:
        # sim and live agree on the same rows by construction.
        self.deploy_board = float(cfg.get("action", "deploy_board", default=0.53125))
        _gh = int(cfg.get("action", "grid", default=[18, 32])[1])
        _c = self.deploy_board * _gh - 0.5               # first row whose CENTER is on your land
        self.min_own_gy = min(_gh - 1, max(0, int(_c) + (1 if _c > int(_c) else 0)))
        # arena PLAYFIELD rectangle (normalized frame corners) the tile grid is anchored to;
        # defaults to env.arena_region so the grid lines up with the board, not the whole frame.
        bx = cfg.get("action", "arena_box", default=None) or \
            cfg.get("env", "arena_region", default=[0.03, 0.10, 0.97, 0.86])
        self.bx0, self.by0, self.bx1, self.by1 = float(bx[0]), float(bx[1]), float(bx[2]), float(bx[3])
        self.chat_box = cfg.get("buttons", "chat_avoid_box", default=None)
        _my_towers = cfg.get("env", "my_towers", default=[[0.245, 0.615], [0.745, 0.615], [0.48, 0.72]])
        self.king_xy = _my_towers[2] if len(_my_towers) >= 3 else [0.48, 0.72]
        self.king_half = cfg.get("action", "king_avoid_half", default=[0.09, 0.06])
        self.princess_xy = [list(t) for t in _my_towers[:2]] if len(_my_towers) >= 2 else [[0.245, 0.615], [0.745, 0.615]]
        self.princess_half = cfg.get("action", "princess_avoid_half", default=[0.06, 0.05])
        self.n_slots = len(self.slots)
        self.n_cells = int(self.gw) * int(self.gh)
        # Tower-anchored perspective warp (see BoardWarp). In the SIM the tower overrides are
        # board-true, so all anchors are identity points and the warp is exactly the identity.
        self.warp = BoardWarp(cfg, self.bx0, self.by0, self.bx1, self.by1)

    def cell_center(self, gx: int, gy: int):
        """Grid cell -> normalized (nx, ny) tap at the cell's centre, mapped over the arena box
        (so columns/rows 0..gw-1 / 0..gh-1 span the playfield, not the whole frame)."""
        nx, ny = self.warp.board_to_frame((gx + 0.5) / self.gw, (gy + 0.5) / self.gh)
        nx = min(max(nx, 0.02), 0.98)
        ny = min(max(ny, self.a_top), self.a_bot)   # safety: keep placements off the card tray
        if self.chat_box:                            # never tap the emote/chat icon (it stalls the bot)
            x0, y0, x1, y1 = self.chat_box
            if x0 <= nx <= x1 and y0 <= ny <= y1:
                ny = max(self.a_top, y0 - 0.01)      # nudge the placement up out of the icon
        return nx, ny

    def coords_to_grid(self, nx: float, ny: float):
        """Normalized (nx, ny) -> (gx, gy) grid indices, the exact inverse of ``cell_center`` over
        the arena box (clamped to the grid). The labeler + reward helpers quantize through here so
        their cells decode back to the same tap points the policy was trained on."""
        gw, gh = int(self.gw), int(self.gh)
        fx = (nx - self.bx0) / (self.bx1 - self.bx0) if self.bx1 > self.bx0 else 0.0
        fy = (ny - self.by0) / (self.by1 - self.by0) if self.by1 > self.by0 else 0.0
        gx = min(gw - 1, max(0, int(fx * gw)))
        gy = min(gh - 1, max(0, int(fy * gh)))
        return gx, gy

    def cell_at(self, nx: float, ny: float) -> int:
        """Normalized (nx, ny) -> flat grid cell index (gy * gw + gx)."""
        gx, gy = self.coords_to_grid(nx, ny)
        return gy * int(self.gw) + gx

    def row_at(self, ny: float) -> int:
        """Normalized frame y -> grid row (0..gh), for the deploy line / king footprint."""
        fy = (ny - self.by0) / (self.by1 - self.by0) if self.by1 > self.by0 else 0.0
        return min(int(self.gh), max(0, int(round(fy * self.gh))))

    def decode(self, slot: int, gx: int, gy: int):
        """Return (slot_nx, slot_ny, target_nx, target_ny) normalized tap points."""
        snx, sny = self.slots[slot]
        tnx, tny = self.cell_center(gx, gy)
        return snx, sny, tnx, tny

    def deploy_clamp(self, anywhere: bool, cell: int) -> int:
        """Only ROCKET and MINER may target anywhere; every other card (troops, buildings incl.
        the X-Bow, royal delivery) can only deploy on YOUR half of the river. A restricted card whose
        cell is in the enemy half can't be placed -- the card tap just selects it and the arena
        tap does nothing, so the bot 'shuffles' cards without deploying. Clamp such cells down
        to the deploy line; ``anywhere`` cards pass through unchanged. A cell landing on YOUR OWN
        king OR a princess tower is likewise undeployable, so it's pulled to the row just in front of it."""
        if anywhere:
            return cell
        gw = int(self.gw)
        gx, gy = cell % gw, cell // gw
        min_gy = self.min_own_gy                    # first grid row on your side of the river (board-space)
        if gy < min_gy:
            gy = min_gy
        # A troop can't be deployed ON your king tower (centre-back): the place-tap is a no-op
        # and the card just 'shuffles'. If the cell sits on the king's footprint, pull it to the
        # row just in FRONT of the king (toward the river), where it actually deploys.
        kx, ky = self.king_xy
        khx, khy = self.king_half
        nx, ny = self.cell_center(gx, gy)
        if abs(nx - kx) <= khx and abs(ny - ky) <= khy:
            gy = max(min_gy, self.row_at(ky - khy) - 1)
        else:
            # ...and each of the two PRINCESS towers (front-left / front-right): a cell on a princess
            # footprint is undeployable too -> pull it to the row just in FRONT of that tower.
            phx, phy = self.princess_half
            for px, py in self.princess_xy:
                if abs(nx - px) <= phx and abs(ny - py) <= phy:
                    gy = max(min_gy, self.row_at(py - phy) - 1)
                    break
        return gy * gw + gx

    def deployable_mask(self, anywhere: bool) -> "list[bool]":
        """Per-cell deployability over the placement grid: True where a card of this kind can actually
        be placed. ``anywhere`` (rocket / miner) -> every cell; otherwise only YOUR half (rows at/below
        the deploy line) MINUS your own tower footprints (king + both princesses -- placing there is a
        no-op tap in-game, so those cells are now excluded from SELECTION, not just clamp-corrected).
        Masking the cell head to this BEFORE the argmax stops the policy from selecting a cell that
        would just clamp/no-op -- the 'impossible coordinate' the model otherwise keeps trying."""
        gw, gh = int(self.gw), int(self.gh)
        if anywhere:
            return [True] * (gw * gh)
        min_gy = self.min_own_gy                    # board-space river rule (see __init__)
        kx, ky = self.king_xy
        khx, khy = self.king_half
        phx, phy = self.princess_half

        def _ok(c: int) -> bool:
            gy = c // gw
            if gy < min_gy:
                return False                          # enemy half
            nx, ny = self.cell_center(c % gw, gy)
            if abs(nx - kx) <= khx and abs(ny - ky) <= khy:
                return False                          # your KING tower footprint (undeployable)
            return not any(abs(nx - px) <= phx and abs(ny - py) <= phy
                           for px, py in self.princess_xy)   # your PRINCESS tower footprints

        return [_ok(c) for c in range(gw * gh)]
