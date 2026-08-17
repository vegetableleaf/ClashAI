"""Soft placement targets: give a neighbouring tile partial credit instead of none.

WHY, MEASURED. Exact one-hot cross-entropy on a 432-cell grid calls a strategically identical
neighbour completely wrong, so almost every gradient the placement head sees says "not here"
about a cell that was fine. The failure mode that produces is collapse onto one safe tile, and
this project keeps measuring exactly that:

    champion (shared cell head)      row 13 = 78.7% of plays,  48/432 cells,  top cell 41%
    per-card head, fresh              row 13 = 41.2%,          62/432 cells,  top cell 20.5%
    per-card head, 19k matches        row 13 = 84.5%,          28/432 cells,  top cell 36.8%

The per-card head fixed the EXPRESSIVENESS problem -- cards can finally differ -- and training
collapsed the distribution anyway, worse than before. Widening what counts as correct attacks the
other half: the supervision.

Normalised over LEGAL cells only, so probability is never assigned to a tile the game would
refuse, and the mass a smoothed target would have wasted off-board is redistributed onto legal
neighbours instead of quietly lowering the target's total.
"""
from __future__ import annotations

import torch
from torch import Tensor

#: Fallback per-kind widths, in CELLS. A building's pull geometry is precise; a spell's value is
#: its blast radius, so the tolerance should be about that wide.
DEFAULT_SIGMA = {"building": 0.6, "troop": 1.0, "spell": 1.5}


def gaussian_spatial_target(target_cell: Tensor, legal_mask: Tensor, grid_w: int, grid_h: int,
                            sigma: Tensor | float) -> Tensor:
    """(B,) demonstrated cell + (B, G) legal mask -> (B, G) target distribution over LEGAL cells.

    ``sigma`` may be a scalar or a per-sample tensor, so a building and a spell in the same batch
    can carry different tolerances.
    """
    if legal_mask.dim() != 2:
        raise ValueError("legal_mask must be [B, G], got %s" % (tuple(legal_mask.shape),))
    b, g = legal_mask.shape
    if g != grid_w * grid_h:
        raise ValueError("grid %dx%d does not match %d cells" % (grid_w, grid_h, g))
    if target_cell.dim() != 1 or target_cell.shape[0] != b:
        raise ValueError("target_cell must be [B] matching the mask batch")

    dev = legal_mask.device
    ys, xs = torch.meshgrid(torch.arange(grid_h, device=dev), torch.arange(grid_w, device=dev),
                            indexing="ij")
    coords = torch.stack((xs.reshape(-1), ys.reshape(-1)), dim=-1).float()      # (G, 2)
    tx = (target_cell % grid_w).float()
    ty = torch.div(target_cell, grid_w, rounding_mode="floor").float()
    d2 = (coords.unsqueeze(0) - torch.stack((tx, ty), dim=-1).unsqueeze(1)).pow(2).sum(-1)

    if not torch.is_tensor(sigma):
        sigma = torch.full((b,), float(sigma), device=dev)
    sigma = sigma.reshape(b, 1).to(d2.dtype).clamp_min(1e-3)
    w = torch.exp(-d2 / (2.0 * sigma.pow(2))) * legal_mask.to(d2.dtype)

    total = w.sum(-1, keepdim=True)
    # A demonstrated cell that is itself illegal means stale grid metadata, not a wide target --
    # smearing the mass over unrelated legal cells would teach a placement nobody demonstrated.
    if bool((total <= 0).any()):
        bad = int((total <= 0).sum())
        raise ValueError("%d sample(s) have no legal probability mass -- the demonstrated cell is "
                         "illegal under the current grid; re-label or quarantine them" % bad)
    return w / total


def soft_cell_loss(cell_logits: Tensor, target: Tensor) -> Tensor:
    """Cross-entropy against a distribution rather than an index."""
    return -(target * torch.log_softmax(cell_logits, dim=-1)).sum(-1).mean()


def sigma_for(db, keys, default: float = 1.0) -> list[float]:
    """Per-card tolerance from the card KB, so it lives in data rather than in training code."""
    out = []
    for k in keys:
        base = k[:-4] if str(k).endswith("_evo") else str(k)
        c = (db.get(base) or {}) if db is not None else {}
        kind = str(c.get("type", "")).lower()
        out.append(DEFAULT_SIGMA.get("spell" if kind == "spell"
                                     else "building" if kind == "building"
                                     else "troop", default))
    return out


def placement_report(pred_cells, true_cells, grid_w: int) -> dict:
    """Within-1 / within-2 / distance, which one-hot accuracy alone cannot show.

    A head that collapses onto one common tile can post a respectable exact accuracy on an
    imbalanced set; a large gap between exact and within-1 is the signature of that, which is why
    both are reported together.
    """
    import math
    n = len(true_cells)
    if not n:
        return {}
    exact = w1 = w2 = 0
    dist = 0.0
    for p, t in zip(pred_cells, true_cells):
        px, py = int(p) % grid_w, int(p) // grid_w
        tx, ty = int(t) % grid_w, int(t) // grid_w
        d = math.hypot(px - tx, py - ty)
        dist += d
        exact += d == 0
        w1 += d <= 1.5           # 8-neighbourhood
        w2 += d <= 2.9
    return {"exact": exact / n, "within_1": w1 / n, "within_2": w2 / n,
            "mean_cell_distance": dist / n, "n": n}
