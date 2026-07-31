"""Discrete action space: (hand slot, placement grid cell) -> screen tap points.

The grid mapping mirrors the labeler exactly (cell over the FULL frame:
gx = floor(nx * gw), gy = floor(ny * gh)), so actions the policy predicts decode
back to the same on-screen positions it was trained on. Placement is clamped to
the arena band so an untrained/greedy pick never lands on the card tray.
"""
from __future__ import annotations


class ActionSpace:
    def __init__(self, cfg):
        self.slots = cfg.get("hand", "slots", default=[])
        self.gw, self.gh = cfg.get("action", "grid", default=[8, 12])
        self.a_top = float(cfg.get("label", "arena_top", default=0.10))
        self.a_bot = float(cfg.get("label", "arena_bottom", default=0.86))
        self.deploy_top = float(cfg.get("action", "deploy_top", default=0.47))
        self.chat_box = cfg.get("buttons", "chat_avoid_box", default=None)
        _my_towers = cfg.get("env", "my_towers", default=[[0.245, 0.615], [0.745, 0.615], [0.48, 0.72]])
        self.king_xy = _my_towers[2] if len(_my_towers) >= 3 else [0.48, 0.72]
        self.king_half = cfg.get("action", "king_avoid_half", default=[0.09, 0.06])
        self.n_slots = len(self.slots)
        self.n_cells = int(self.gw) * int(self.gh)

    def cell_center(self, gx: int, gy: int):
        nx = (gx + 0.5) / self.gw
        ny = (gy + 0.5) / self.gh
        nx = min(max(nx, 0.02), 0.98)
        ny = min(max(ny, self.a_top), self.a_bot)   # keep placements off the card tray
        if self.chat_box:                            # never tap the emote/chat icon (it stalls the bot)
            x0, y0, x1, y1 = self.chat_box
            if x0 <= nx <= x1 and y0 <= ny <= y1:
                ny = max(self.a_top, y0 - 0.01)      # nudge the placement up out of the icon
        return nx, ny

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
        king tower is likewise undeployable, so it's pulled to the row just in front of the king."""
        if anywhere:
            return cell
        gw, gh = int(self.gw), int(self.gh)
        gx, gy = cell % gw, cell // gw
        min_gy = int(round(self.deploy_top * gh))   # first grid row on your side of the river
        if gy < min_gy:
            gy = min_gy
        # A troop can't be deployed ON your king tower (centre-back): the place-tap is a no-op
        # and the card just 'shuffles'. If the cell sits on the king's footprint, pull it to the
        # row just in FRONT of the king (toward the river), where it actually deploys.
        kx, ky = self.king_xy
        khx, khy = self.king_half
        nx, ny = (gx + 0.5) / gw, (gy + 0.5) / gh
        if abs(nx - kx) <= khx and abs(ny - ky) <= khy:
            gy = max(min_gy, int((ky - khy) * gh) - 1)
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
        min_gy = int(round(self.deploy_top * gh))
        return [(c // gw) >= min_gy for c in range(gw * gh)]
