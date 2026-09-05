"""CNN policy network for the learning bot.

Takes a downscaled arena image, the identities of the cards currently in hand (a
multi-hot over the deck), the next (preview) card (a one-hot), the normalized
elixir, **and an enemy-threat feature vector** (colour/size/count/lane/depth/speed
+ projectile, from clashrl.threats), and outputs two heads:
  - card:  which of the DECK cards to play (identity, not tray position)
  - cell:  which placement grid cell (grid.w * grid.h classes)

Acting on card identity -- not tray position -- is the point: the same card cycles
through different tray positions, so a slot-indexed policy would learn an
inconsistent target. The hand multi-hot is fed in because the arena image is
downscaled too far to read the tray; the next card is fed in so the policy can
plan cycles (hold a cheap card to line up the counter that's coming); the threat
vector is fed in so the policy can learn REACTIVE counters (the small image loses
the cues -- goblin green, swarm vs tank, lane, an incoming barrel -- that pick the
right defence). At inference the card logits are masked to the cards actually in
hand, and the chosen identity is mapped to its live slot.

Shared conv trunk + adaptive pool keeps it robust to the exact observation size.
"""
from __future__ import annotations

import os

import torch
import torch.nn as nn
import torch.nn.functional as F

# n_cells -> (grid_w, grid_h). Every construction site passes n_cells, so the placement grid can
# be inferred here without touching a single caller (matches cli._GRID_SIZES).
_GRIDS = {432: (18, 24), 576: (18, 32)}
_LOGIT_CAP = 8.0   # both heads' logits are tanh-bounded to +/- this (see forward_parts) -- wide
                   # enough for a near-deterministic policy (e^16 ~ 9M:1 across the cap range),
                   # tight enough that softmax never saturates into zero-gradient territory


class PolicyNet(nn.Module):
    """SPATIAL cell head (2026-08-14). The cell head used to be ``nn.Linear(embed, n_cells)`` --
    432 placement logits read out of a GLOBAL embedding whose image half had been flattened
    through a 256-dim bottleneck. That function class has no spatial correspondence between board
    positions and cell outputs, and three training generations never learned one: MEASURED, the
    strongest checkpoint (win 19.3%) kept a near-constant cell argmax across 40 varied states on
    BOTH sim and live observations, and a live session put 44/44 plays of seven different cards
    on one tile regardless of the recognised threat. "Place the counter in the threat's lane"
    was architecturally out of reach.

    The cell head is now a logit MAP: the pre-pool conv feature map (in_h/8 x in_w/8, e.g. 12x8
    for the 96x64 obs) is conditioned on the full context embedding (broadcast-concat), passed
    through 1x1 convs to a 1-channel map, and bilinearly resized to the placement grid. Placement
    thereby inherits translation structure from convolution itself: threat features at a board
    position produce placement logits at that position by construction, instead of hoping a dense
    layer learns 432 special cases. Output shape/order is unchanged (row-major gy*gw+gx, exactly
    ActionSpace's indexing), so every consumer keeps working; OLD checkpoints (cell_head.*) are
    deliberately incompatible -- this head must be retrained (BC -> sim)."""

    def __init__(self, in_ch: int = 3, n_cards: int = 8, n_cells: int = 576, threat_dim: int = 14,
                 grid_wh: "tuple[int, int] | None" = None):
        super().__init__()
        self.n_cards = n_cards
        self.threat_dim = threat_dim
        gw, gh = grid_wh or _GRIDS.get(n_cells, (0, 0))
        if gw * gh != n_cells:
            raise ValueError(f"n_cells {n_cells} does not match a known grid; pass grid_wh=(w, h)")
        self.grid_wh = (gw, gh)
        self.features = nn.Sequential(
            nn.Conv2d(in_ch, 32, 5, stride=2, padding=2), nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, 3, stride=2, padding=1), nn.ReLU(inplace=True),
        )
        # the GLOBAL path (card head / RL gate heads) still pools -- embed_dim and the trunk/
        # card_head parameter names are unchanged, so nothing downstream needs relearning names.
        self.pool = nn.AdaptiveAvgPool2d((6, 4))
        self.trunk = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 6 * 4, 256), nn.ReLU(inplace=True),
        )
        self.hand_fc = nn.Sequential(nn.Linear(n_cards, 32), nn.ReLU(inplace=True))
        self.next_fc = nn.Sequential(nn.Linear(n_cards, 16), nn.ReLU(inplace=True))
        self.elixir_fc = nn.Sequential(nn.Linear(1, 8), nn.ReLU(inplace=True))
        self.threat_fc = nn.Sequential(nn.Linear(threat_dim, 16), nn.ReLU(inplace=True))
        self.embed_dim = 256 + 32 + 16 + 8 + 16
        self.card_head = nn.Linear(self.embed_dim, n_cards)
        # spatial cell head: context -> per-location conditioning -> 1x1 convs -> logit map
        self.cell_ctx = nn.Sequential(nn.Linear(self.embed_dim, 32), nn.ReLU(inplace=True))
        # PER-CARD logit maps: the last conv emits ONE MAP PER CARD, not one map per state.
        #
        # It used to emit a single channel, so the network produced one 432-cell distribution for
        # the whole board state and every card sampled from it. MEASURED on the champion over 80
        # greedy matches: row 13 (the frontmost legal row) took 78.7% of all placements, and the
        # concentration held for every card at once -- tesla 88%, x_bow 85%, skeletons 80%,
        # tornado 62% -- which is the signature of a shared map rather than ten learned ones. On
        # one fixed board with a Giant and Musketeer committed, all ten cards resolved to the
        # identical tile.
        #
        # That made whole classes of doctrine unlearnable rather than merely unlearned: "knight in
        # front of the bow, ice wizard behind it, skeletons onto the attacker" is four different
        # placements for four cards in ONE state, and the old head could not represent it at any
        # weights. Cost is one extra conv channel per card (10 x 432 outputs) in the same pass.
        # SINGLE-MAP CELL HEAD (CLASHRL_SINGLE_CELL_MAP=1) -- the pre-206f467 shape.
        # Every checkpoint this project ever trained to a good winrate has a SINGLE map:
        #     single map   n=9   best_wr max 33.2  mean 23.7
        #     per-card     n=5   best_wr max 10.2  mean  7.5
        # and at matched budget/in_ch it is 17.9% vs 10.2% at 1500 matches. Per-card gives the
        # head 10x the outputs (10 x 432 = 4320); measured, that head then moves sd(log r) 0.478
        # per update against the gate's 0.002 -- +-61% swings on a ~0 gradient, i.e. Adam noise on
        # a head too large for the signal available. This flag restores the old width so the two
        # can be run head to head; the forward pass broadcasts the one map across cards, so every
        # caller sees the same (B, n_cards, n_cells) shape either way.
        self.cell_per_card = not os.environ.get("CLASHRL_SINGLE_CELL_MAP")
        _cell_out = n_cards if self.cell_per_card else 1
        self.cell_conv = nn.Sequential(
            nn.Conv2d(64 + 32, 48, 1), nn.ReLU(inplace=True),
            nn.Conv2d(48, 24, 1), nn.ReLU(inplace=True),
            nn.Conv2d(24, _cell_out, 1),
        )
        # PER-CARD CELL BIAS MAP (2026-09-05, owner-approved; HANDOFF 5cs.36/5cs.37). One
        # board-independent logit per (card, cell), added to the conv map BEFORE the tanh cap. The
        # conv head has no coordinate input, so "x-bow goes at the river" -- a fixed place, not a
        # feature at a place -- is out of its function class: three BC attempts left x_bow at 0/91
        # held-out pro placements, and the head sat below the board-blind per-card prior
        # (13.65 / 40.04 top-1 / top-5). Initialised from that prior (log(count+1) over the pro
        # corpus) and fine-tuned, the same head reaches 15.4 / 46.6 on sim boards and 15.0 / 43.5 on
        # real-engine boards; zero-initialised it changes nothing, and checkpoints written before
        # this parameter existed load with a zero map (see load_state_dict).
        self.cell_bias_map = nn.Parameter(torch.zeros(n_cards, n_cells))

    def load_state_dict(self, state_dict, strict: bool = True, **kw):
        if "cell_bias_map" not in state_dict:        # pre-2026-09-05 checkpoint: zero map == old net
            state_dict = dict(state_dict)
            state_dict["cell_bias_map"] = torch.zeros_like(self.cell_bias_map)
        return super().load_state_dict(state_dict, strict=strict, **kw)

    @staticmethod
    def load_compat(policy, state: dict) -> "list[str]":
        """Load what still fits, and REPORT what did not. Returns the dropped parameter names.

        The cell head changed shape when it became per-card (one output channel -> n_cards), so
        every checkpoint written before that has a `cell_conv` last layer of the wrong width. A
        strict load raises; loading with strict=False alone would silently leave the head at its
        random init while printing "warm-started", which is the worst of the three outcomes because
        the run looks warm and behaves fresh.

        The trunk, the card head and the embedding are unaffected and worth keeping -- they are the
        expensive part -- so those load and only the mismatched tensors are dropped and named.
        """
        own = policy.state_dict()
        keep = {k: v for k, v in state.items()
                if k in own and tuple(own[k].shape) == tuple(v.shape)}
        if "cell_bias_map" not in keep:          # absent == zero map, not a dropped tensor
            keep["cell_bias_map"] = torch.zeros_like(own["cell_bias_map"])
        dropped = sorted(set(own) - set(keep))
        policy.load_state_dict(keep, strict=False)
        return dropped

    def _embed(self, fmap: torch.Tensor, hand: torch.Tensor,
               nxt: torch.Tensor | None, elx: torch.Tensor | None,
               thr: torch.Tensor | None) -> torch.Tensor:
        z = self.trunk(self.pool(fmap))
        if nxt is None:
            nxt = torch.zeros(hand.shape[0], self.n_cards, device=hand.device, dtype=hand.dtype)
        if elx is None:
            elx = torch.zeros(hand.shape[0], 1, device=hand.device, dtype=hand.dtype)
        if thr is None:
            thr = torch.zeros(hand.shape[0], self.threat_dim, device=hand.device, dtype=hand.dtype)
        return torch.cat([z, self.hand_fc(hand), self.next_fc(nxt),
                          self.elixir_fc(elx), self.threat_fc(thr)], dim=1)

    def features_vec(self, x: torch.Tensor, hand: torch.Tensor,
                     nxt: torch.Tensor | None = None, elx: torch.Tensor | None = None,
                     thr: torch.Tensor | None = None) -> torch.Tensor:
        """Shared embedding of (image, hand multi-hot, next-card one-hot, normalized elixir,
        enemy-threat vector). Exposed so RL can add heads (gate). Unchanged width (328)."""
        return self._embed(self.features(x), hand, nxt, elx, thr)

    def _cell_logits(self, fmap: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """(B, n_cards, n_cells) -- one placement map PER CARD, row-major gy*gw+gx.

        Callers index by the card they are placing: ``cells[b, card_id]``. Anything that wants a
        card-agnostic view (a heatmap, a diagnostic) should say so explicitly with ``.amax(1)``
        rather than assuming the old 2-D shape.
        """
        ctx = self.cell_ctx(z)[:, :, None, None].expand(-1, -1, fmap.shape[2], fmap.shape[3])
        m = self.cell_conv(torch.cat([fmap, ctx], dim=1))         # (B, out, h', w')
        gw, gh = self.grid_wh
        cells = F.interpolate(m, size=(gh, gw), mode="bilinear", align_corners=False)
        cells = cells.flatten(2)                                  # (B, out, gh*gw)
        if not self.cell_per_card:
            # one shared map, broadcast across cards so callers are unchanged. expand() is a view,
            # so the gradient from every card accumulates into the SAME map -- which is the point:
            # 10x fewer parameters fed by 10x the samples.
            cells = cells.expand(-1, self.n_cards, -1)
        return cells + self.cell_bias_map[None]                   # (B, n_cards, gh*gw)

    def forward_parts(self, x: torch.Tensor, hand: torch.Tensor, nxt: torch.Tensor | None = None,
                      elx: torch.Tensor | None = None, thr: torch.Tensor | None = None):
        """(embed z, card logits, cell logits) in ONE conv pass. The RL wrappers (gate/value heads
        on z) and the visualisers must use THIS instead of features_vec + .cell_head(z): the
        spatial cell head needs the pre-pool FEATURE MAP, which features_vec discards -- and
        `cell_head` no longer exists as a module (that dense readout is the collapse this head
        replaced; see the class docstring)."""
        fmap = self.features(x)                                   # (B, 64, in_h/8, in_w/8)
        z = self._embed(fmap, hand, nxt, elx, thr)
        # LOGIT CAP (2026-08-14). Round 5 diagnosed CARD-HEAD LOGIT EXPLOSION: raw logits reached
        # +/-140 (a delta softmax per state), which zeroed tornado and x_bow FOREVER -- at that
        # saturation the gradient to ever raise a suppressed card is ~e^-200, so neither the 15%
        # exploration floor nor the entropy bonus could recover it. A scaled tanh bounds every
        # logit to +/-_LOGIT_CAP: ranking is preserved (monotone), softmax can never fully
        # saturate, and the entropy gradient stays alive at any weight norm. Checkpoints trained
        # BEFORE the cap carry raw weights in the saturated zone -- rescale them into the linear
        # region first (tools/repair_card_head.py), or the tanh just freezes them at the rails.
        cards = _LOGIT_CAP * torch.tanh(self.card_head(z) / _LOGIT_CAP)
        cells = _LOGIT_CAP * torch.tanh(self._cell_logits(fmap, z) / _LOGIT_CAP)
        return z, cards, cells

    def forward(self, x: torch.Tensor, hand: torch.Tensor, nxt: torch.Tensor | None = None,
                elx: torch.Tensor | None = None, thr: torch.Tensor | None = None):
        _, cards, cells = self.forward_parts(x, hand, nxt, elx, thr)
        return cards, cells

