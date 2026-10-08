"""Prototype (offline only, NOT wired into pipeline/live): TowerRefine = the 6 public crown towers (fixed anchors; side, kind,
hp fraction, hp-known, alive -- the same sc[52:70] scalars the model already reads) fed as
  (a) pseudo-units into a second CellRefine-style lattice scatter -> per-cell residual . q   (Rocket / any card aim), and
  (b) a per-hand-slot card residual  emb(card) . W [g, tower feats, sc[:7]].
Both outputs are zero-initialised, so step 0 is the base bit-for-bit. Base weights are frozen and stay in eval()."""
import sys
import torch
from torch import nn
sys.path.insert(0, "C:/Users/benpe/ClashBot")
from pipeline.model_gen import CellRefine, load_model
from pipeline.model_tower import anchors

SIDE = torch.tensor([0., 0, 0, 1, 1, 1]); KIND = torch.tensor([0., 1, 1, 0, 1, 1])


def tower_features(sc):
    """[B, 6, 5] (side, kind, hp, known, alive) + alive mask, exactly model_tower.TowerModel.tower_features."""
    alive = sc[:, 64:70] > .5; raw = sc[:, 52:58]
    known = (sc[:, 58:64] > .5) & alive & torch.isfinite(raw)
    hp = torch.where(known, raw, torch.zeros_like(raw)); b = len(sc)
    return torch.stack([SIDE.to(sc).expand(b, -1), KIND.to(sc).expand(b, -1), hp, known.to(sc.dtype), alive.to(sc.dtype)], -1), alive


class TowerRefine(nn.Module):
    def __init__(self, d, d_c, c=32, layers=4, hidden=128, card=True, cell=True):
        super().__init__()
        self.use_card, self.use_cell = card, cell
        self.unit = nn.Sequential(nn.Linear(5, d), nn.GELU(), nn.Linear(d, d))
        self.cell = CellRefine(d, c, layers)                       # zero-init output
        self.card = nn.Sequential(nn.Linear(d + 30 + 7, hidden), nn.GELU(), nn.Linear(hidden, d_c))
        nn.init.zeros_(self.card[2].weight); nn.init.zeros_(self.card[2].bias)
        self.register_buffer("xy", torch.tensor(anchors(), dtype=torch.float32))

    def card_residual(self, g, sc, hand_emb):
        f, _ = tower_features(sc)
        h = self.card(torch.cat([g, f.flatten(1), sc[:, :7]], -1))
        return (hand_emb * h.unsqueeze(1)).sum(-1)

    def cell_feat(self, sc):
        f, alive = tower_features(sc)
        return self.cell.features(self.unit(f), self.xy.expand(len(sc), -1, -1), alive)


class Wrapped(nn.Module):
    """base + TowerRefine with GenModel's call signature: m(b) / m(b, card=, form=)."""
    def __init__(self, base, tr):
        super().__init__()
        self.base, self.tr = base, tr
        self.cls_emb = base.cls_emb                                 # probe hooks reach the base embedding

    def forward(self, b, card=None, form=None):
        base = self.base
        enc = base.encode_gen(b); out = base.heads_gen(enc, b); out["g"] = enc["g"]
        if self.tr.use_card:
            out["card"] = out["card"] + self.tr.card_residual(enc["g"], b["sc"], base.emb(b["hand_card"], b["hand_form"]))
        if card is not None:
            form = form if form is not None else torch.zeros_like(card)
            cell = base.cell_logits_gen(enc, card, form)
            if self.tr.use_cell:
                q = base.query(torch.cat([enc["g"], base.emb(card, form)], -1))
                cell = cell + self.tr.cell.residual(self.tr.cell_feat(b["sc"]), q)
            out["cell"] = cell
        return out


def build(base_path, device, **kw):
    base, st = load_model(base_path, device); base.eval()
    for p in base.parameters(): p.requires_grad_(False)
    tr = TowerRefine(base.d, base.d_c, **kw).to(device)
    return Wrapped(base, tr).to(device), st


def load(path, device):
    s = torch.load(path, map_location=device, weights_only=False)
    m, st = build(s["base"], device, **s["cfg"])
    m.tr.load_state_dict(s["tower_refine"]); m.eval()
    return m, st


if __name__ == "__main__":   # self-check: a fresh module leaves every head bit-identical
    import numpy as np
    m, st = build("C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt", torch.device("cpu"))
    B = 3
    b = {"tok": torch.zeros(B, 64, 14), "mask": torch.zeros(B, 64, dtype=torch.bool), "unit_form": torch.zeros(B, 64, dtype=torch.long),
         "sc": torch.rand(B, 70), "past": torch.zeros(B, 3, 5), "hand_card": torch.tensor([[1, 2, 3, 4]] * B), "hand_form": torch.zeros(B, 4, dtype=torch.long),
         "next_card": torch.ones(B, dtype=torch.long), "next_form": torch.zeros(B, dtype=torch.long), "deck_card": torch.tensor([list(range(1, 9))] * B),
         "deck_form": torch.zeros(B, 8, dtype=torch.long), "opp_past": torch.zeros(B, 3, 5), "opp_cycle": torch.zeros(B, 8, 4),
         "projectiles": torch.zeros(B, 64, 8), "effects": torch.zeros(B, 32, 6), "own_ability": torch.zeros(B, 8, 7)}
    b["mask"][:, :2] = True; b["tok"][:, :2, 4:6] = .5
    with torch.no_grad():
        c = torch.ones(B, dtype=torch.long)
        o, r = m(b, card=c), m.base(b, card=c)
    for k in ("gate", "card", "cell"): assert torch.equal(o[k], r[k]), k
    print("self-check OK: zero-init TowerRefine == base on gate/card/cell")
