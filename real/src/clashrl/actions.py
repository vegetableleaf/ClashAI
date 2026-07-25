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
        self.chat_box = cfg.get("buttons", "chat_avoid_box", default=None)
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
