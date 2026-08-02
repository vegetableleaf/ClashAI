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


class ActionSpace:
    def __init__(self, cfg):
        self.slots = cfg.get("hand", "slots", default=[])
        self.gw, self.gh = cfg.get("action", "grid", default=[18, 32])
        self.a_top = float(cfg.get("label", "arena_top", default=0.10))
        self.a_bot = float(cfg.get("label", "arena_bottom", default=0.86))
        self.deploy_top = float(cfg.get("action", "deploy_top", default=0.44))
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

    def cell_center(self, gx: int, gy: int):
        """Grid cell -> normalized (nx, ny) tap at the cell's centre, mapped over the arena box
        (so columns/rows 0..gw-1 / 0..gh-1 span the playfield, not the whole frame)."""
        nx = self.bx0 + (gx + 0.5) / self.gw * (self.bx1 - self.bx0)
        ny = self.by0 + (gy + 0.5) / self.gh * (self.by1 - self.by0)
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
        min_gy = self.row_at(self.deploy_top)       # first grid row on your side of the river
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
        the deploy line, matching :meth:`deploy_clamp`). Masking the cell head to this BEFORE the argmax
        stops the policy from SELECTING an enemy-half cell that would just clamp/no-op -- the 'impossible
        coordinate' the model otherwise keeps trying (and that made it look inactive)."""
        gw, gh = int(self.gw), int(self.gh)
        if anywhere:
            return [True] * (gw * gh)
        min_gy = self.row_at(self.deploy_top)
        return [(c // gw) >= min_gy for c in range(gw * gh)]
