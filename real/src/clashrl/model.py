"""CNN policy network for the learning bot.

Takes a downscaled arena image, the identities of the cards currently in hand (a
multi-hot over the deck), **and the next (preview) card that will rotate in** (a
one-hot over the deck), and outputs two heads:
  - card:  which of the DECK cards to play (identity, not tray position)
  - cell:  which placement grid cell (grid.w * grid.h classes)

Acting on card identity -- not tray slot -- is the point: the same card cycles
through different tray positions, so a slot-indexed policy would learn an
inconsistent target. The hand multi-hot is fed in because the arena image is
downscaled too far to read the tray; the next card is fed in so the policy can
plan cycles (hold a cheap card to line up the counter that's coming). At
inference the card logits are masked to the cards actually in hand, and the
chosen identity is mapped to its live slot.

Shared conv trunk + adaptive pool keeps it robust to the exact observation size.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class PolicyNet(nn.Module):
    def __init__(self, in_ch: int = 3, n_cards: int = 8, n_cells: int = 96):
        super().__init__()
        self.n_cards = n_cards
        self.features = nn.Sequential(
            nn.Conv2d(in_ch, 32, 5, stride=2, padding=2), nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, 3, stride=2, padding=1), nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((6, 4)),
        )
        self.trunk = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 6 * 4, 256), nn.ReLU(inplace=True),
        )
        self.hand_fc = nn.Sequential(nn.Linear(n_cards, 32), nn.ReLU(inplace=True))
        self.next_fc = nn.Sequential(nn.Linear(n_cards, 16), nn.ReLU(inplace=True))
        self.elixir_fc = nn.Sequential(nn.Linear(1, 8), nn.ReLU(inplace=True))
        self.embed_dim = 256 + 32 + 16 + 8
        self.card_head = nn.Linear(self.embed_dim, n_cards)
        self.cell_head = nn.Linear(self.embed_dim, n_cells)

    def features_vec(self, x: torch.Tensor, hand: torch.Tensor,
                     nxt: torch.Tensor | None = None, elx: torch.Tensor | None = None) -> torch.Tensor:
        """Shared embedding of (image, hand multi-hot, next-card one-hot, normalized elixir).
        Exposed so RL can add heads. ``nxt``/``elx`` may be None (treated as all-zero =
        next card unknown / elixir 0)."""
        z = self.trunk(self.features(x))
        if nxt is None:
            nxt = torch.zeros(hand.shape[0], self.n_cards, device=hand.device, dtype=hand.dtype)
        if elx is None:
            elx = torch.zeros(hand.shape[0], 1, device=hand.device, dtype=hand.dtype)
        return torch.cat([z, self.hand_fc(hand), self.next_fc(nxt), self.elixir_fc(elx)], dim=1)

    def forward(self, x: torch.Tensor, hand: torch.Tensor, nxt: torch.Tensor | None = None,
                elx: torch.Tensor | None = None):
        z = self.features_vec(x, hand, nxt, elx)
        return self.card_head(z), self.cell_head(z)

