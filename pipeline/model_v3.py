"""S1 imitation v3 model: entity tokens + coordinate patch tokens -> transformer -> full-resolution cell head.

Inputs are exactly the ``pipeline.dataset`` rows (``to_tokens`` unit rows, the 70-d scalar vector, the
past-actions channel). Design points from the Square One proposal (HANDOFF §5cs.5x C):
  * ENTITY tokens: vocab embedding + the unit's features + Fourier features of its (x, y).
  * PATCH tokens: a 9 x 16 grid of 2-tile patches, each a learned position embedding + Fourier coords +
    the sum of the entity embeddings that fall inside it (so a patch knows what stands on it).
  * one GLOBAL token from the scalars (clock, elixir, hand/next one-hots, towers) and the past plays.
  * CELL head at half-tile resolution (36 x 64 = 2,304 cells) with NO upsampling: every cell has its own
    learned embedding, added to the transformer output of the patch it lies in; the logit is a dot
    product with a query built from the global token and the card being placed (teacher-forced in
    training, the chosen card at play time).
  * hand-masked CARD head, state-conditioned GATE, WAIT-FOR-CARD head, categorical VALUE head over the
    real crown difference (-3..3), all from the global token.
Both decks share this module unchanged.
"""
from __future__ import annotations

import math
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as Fn

from . import vocab
from .obs_contract import F as TOK_F, S as SC_S
from .dataset import PAST_K

GRID_X, GRID_Y = 36, 64             # half-tile cells: cx = floor(x * 36), cy = floor(y * 64)
PATCH_X, PATCH_Y = 9, 16            # 2-tile patches
N_CELLS = GRID_X * GRID_Y
N_PATCHES = PATCH_X * PATCH_Y
N_SLOTS = 8
VALUE_CLASSES = 7                   # crown diff -3..3


def cell_index(xy: torch.Tensor, gx: int = GRID_X, gy: int = GRID_Y) -> torch.Tensor:
    """Continuous board (x, y) in [0, 1] -> cell id (row-major, y then x)."""
    cx = (xy[..., 0] * gx).long().clamp_(0, gx - 1)
    cy = (xy[..., 1] * gy).long().clamp_(0, gy - 1)
    return cy * gx + cx


def cell_label(xy: torch.Tensor, grid: str = "floor", gx: int = GRID_X, gy: int = GRID_Y) -> torch.Tensor:
    """Placement LABEL cell. ``floor``: ``cell_index`` (the v3 checkpoints). ``lattice``: pro placements sit on the
    500-unit lattice, i.e. x * 36 is an integer to +-0.002, so floor let a 1-unit jitter in the crawl (500k vs 500k-1,
    random at the same point) flip the label one cell (§5cs.70); round makes lattice points the cell centres."""
    if grid == "floor":
        return cell_index(xy, gx, gy)
    if grid != "lattice":
        raise ValueError(f"grid {grid!r}")
    cx = torch.round(xy[..., 0] * gx).long().clamp_(0, gx - 1)
    cy = torch.round(xy[..., 1] * gy).long().clamp_(0, gy - 1)
    return cy * gx + cx


def tile_of_cell(cell: torch.Tensor) -> torch.Tensor:
    """Half-tile cell id -> 1-tile id on the (GRID_X // 2, GRID_Y // 2) grid (pairs of adjacent half-cells)."""
    return (cell // GRID_X // 2) * (GRID_X // 2) + (cell % GRID_X) // 2


def cell_xy(cell: int, grid: str = "floor", gx: int = GRID_X, gy: int = GRID_Y) -> tuple[float, float]:
    """Inverse of ``cell_label``: board-frame (x, y) in [0, 1] -- the cell centre under ``floor``, the lattice point
    under ``lattice`` (so the engine places where the pros place, not 250 units off)."""
    cell = int(cell)
    off = 0.5 if grid == "floor" else 0.0
    return (cell % gx + off) / gx, (cell // gx + off) / gy


def _fourier(xy: torch.Tensor, n: int = 8) -> torch.Tensor:
    """[..., 2] -> [..., 4n] sin/cos features at frequencies 1..n (board is periodic in neither axis; the
    low frequencies give a smooth coordinate code, the high ones tile-scale resolution)."""
    freqs = torch.arange(1, n + 1, device=xy.device, dtype=xy.dtype) * math.pi
    a = xy.unsqueeze(-1) * freqs                     # [..., 2, n]
    return torch.cat([a.sin(), a.cos()], dim=-1).flatten(-2)


class S1Model(nn.Module):
    def __init__(self, d: int = 128, layers: int = 4, heads: int = 4, n_fourier: int = 8, dropout: float = 0.1):
        super().__init__()
        self.d, self.nf = d, n_fourier
        nfeat = 4 * n_fourier
        self.cls_emb = nn.Embedding(vocab.N_VOCAB + 1, d)             # +1 pad
        self.unit_in = nn.Linear(TOK_F - 1 + nfeat, d)                # all token cols but cls, + fourier(x, y)
        self.patch_pos = nn.Parameter(torch.randn(N_PATCHES, d) * 0.02)
        self.patch_in = nn.Linear(nfeat, d)
        self.past_slot = nn.Embedding(N_SLOTS + 1, 16)                # +1 none
        self.global_in = nn.Sequential(nn.Linear(SC_S + PAST_K * (16 + 2 + nfeat + 1), d), nn.GELU(), nn.Linear(d, d))
        self.type_emb = nn.Embedding(3, d)                            # global / patch / unit
        enc = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=dropout, batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(enc, layers)
        self.norm = nn.LayerNorm(d)
        self.gate_head = nn.Linear(d, 1)
        self.card_head = nn.Linear(d, N_SLOTS)
        self.wait_head = nn.Linear(d, N_SLOTS)
        self.value_head = nn.Linear(d, VALUE_CLASSES)
        self.card_emb = nn.Embedding(N_SLOTS, d)
        self.query = nn.Sequential(nn.Linear(2 * d, d), nn.GELU(), nn.Linear(d, d))
        self.cell_emb = nn.Parameter(torch.randn(N_CELLS, d) * 0.02)
        self.cell_key = nn.Linear(d, d)
        self.cell_bias = nn.Parameter(torch.zeros(N_CELLS))
        cy, cx = torch.meshgrid(torch.arange(GRID_Y), torch.arange(GRID_X), indexing="ij")
        self.register_buffer("cell_patch", ((cy // (GRID_Y // PATCH_Y)) * PATCH_X + cx // (GRID_X // PATCH_X)).flatten())
        py, px = torch.meshgrid(torch.arange(PATCH_Y), torch.arange(PATCH_X), indexing="ij")
        self.register_buffer("patch_xy", torch.stack([(px.flatten() + 0.5) / PATCH_X, (py.flatten() + 0.5) / PATCH_Y], -1).float())

    # ---- encoder -------------------------------------------------------------------------------------
    def encode(self, tok: torch.Tensor, mask: torch.Tensor, sc: torch.Tensor, past: torch.Tensor) -> dict:
        B, U, _ = tok.shape
        cls = tok[..., 0].long().clamp(0, vocab.N_VOCAB - 1)
        cls = torch.where(mask, cls, torch.full_like(cls, vocab.N_VOCAB))   # pad id = N_VOCAB
        xy = tok[..., 4:6]
        u = self.cls_emb(cls) + self.unit_in(torch.cat([tok[..., 1:], _fourier(xy, self.nf)], -1))
        u = u * mask.unsqueeze(-1)
        # patch tokens: position + coords + sum of the units standing on the patch
        pid = cell_index(xy, PATCH_X, PATCH_Y)                         # [B, U]
        p = self.patch_pos.unsqueeze(0).expand(B, -1, -1) + self.patch_in(_fourier(self.patch_xy, self.nf)).unsqueeze(0)
        p = p.clone()
        p.scatter_add_(1, pid.unsqueeze(-1).expand(-1, -1, self.d), u)
        # global token
        ps = self.past_slot(past[..., 0].long().clamp(min=-1) + 1)      # [B, K, 16]
        pxy = past[..., 1:3].clamp(0, 1)
        g_in = torch.cat([sc, torch.cat([ps, pxy, _fourier(pxy, self.nf), (past[..., 3:4] / 30.0)], -1).flatten(1)], -1)
        g = self.global_in(g_in).unsqueeze(1)
        x = torch.cat([g + self.type_emb.weight[0], p + self.type_emb.weight[1], u + self.type_emb.weight[2]], 1)
        pad = torch.cat([torch.zeros(B, 1 + N_PATCHES, dtype=torch.bool, device=tok.device), ~mask], 1)
        h = self.norm(self.encoder(x, src_key_padding_mask=pad))
        return {"g": h[:, 0], "p": h[:, 1:1 + N_PATCHES]}

    def heads(self, enc: dict, hand_mask: Optional[torch.Tensor] = None) -> dict:
        g = enc["g"]
        card = self.card_head(g)
        if hand_mask is not None:
            card = card.masked_fill(~hand_mask, -1e4)
        return {"gate": self.gate_head(g).squeeze(-1), "card": card, "wait": self.wait_head(g),
                "value": self.value_head(g)}

    def cell_logits(self, enc: dict, card_slot: torch.Tensor) -> torch.Tensor:
        """[B, N_CELLS] logits for placing ``card_slot`` (LongTensor [B])."""
        q = self.query(torch.cat([enc["g"], self.card_emb(card_slot)], -1))            # [B, d]
        # key(patch_feat + cell_emb) . q == key(patch_feat) . q + key(cell_emb) . q  (linear), so the
        # [B, 2304, d] tensor is never materialised: per-patch dots gathered to cells + per-cell dots.
        kp = (self.cell_key(enc["p"]) * q.unsqueeze(1)).sum(-1)                        # [B, P]
        kc = q @ self.cell_key(self.cell_emb).t()                                       # [B, C]
        return (kp[:, self.cell_patch] + kc) / math.sqrt(self.d) + self.cell_bias

    def forward(self, tok, mask, sc, past, card_slot: Optional[torch.Tensor] = None,
                hand_mask: Optional[torch.Tensor] = None) -> dict:
        enc = self.encode(tok, mask, sc, past)
        out = self.heads(enc, hand_mask)
        out["g"] = enc["g"]
        if card_slot is not None:
            out["cell"] = self.cell_logits(enc, card_slot)
        return out


def hand_mask_from_sc(sc: torch.Tensor) -> torch.Tensor:
    """[B, 8] True for deck slots currently in hand (from the 4 x 9 one-hots at sc[7:43])."""
    oh = sc[:, 7:43].reshape(-1, 4, 9)[:, :, :N_SLOTS]
    return oh.sum(1) > 0


def mirror_batch(tok, sc, past, xy):
    """Left-right mirror of a batch (x -> 1 - x; L/R towers swapped). Returns new tensors."""
    tok = tok.clone(); tok[..., 4] = torch.where(tok[..., 4] > 0, 1.0 - tok[..., 4], tok[..., 4])
    past = past.clone(); ok = past[..., 0] >= 0; past[..., 1] = torch.where(ok, 1.0 - past[..., 1], past[..., 1])
    xy = xy.clone(); xy[..., 0] = torch.where(xy[..., 0] >= 0, 1.0 - xy[..., 0], xy[..., 0])
    sc = sc.clone()
    for base in (52, 58, 64):                                          # tower hp / hp_known / alive: K L R K L R
        for a, b in ((1, 2), (4, 5)):
            sc[:, [base + a, base + b]] = sc[:, [base + b, base + a]]
    return tok, sc, past, xy
