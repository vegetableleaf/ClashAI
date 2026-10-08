"""Optional ``TowerRefine`` add-on for GenModel (L73 chip-Rocket investigation). Opt-in by checkpoint CONTENT: a state dict
holding ``tower_refine.*`` keys builds it on load (GenModel.load_state_dict); a checkpoint without them is untouched.

The six public crown towers (fixed anchors, model_tower.anchors(); per tower side, kind, hp fraction, hp-known, alive --
the sc[52:70] scalars the model already reads) become
  (a) pseudo-units scattered onto the 36 x 64 lattice by a second ``CellRefine`` -> per-cell residual . cell query
      (the base has no board token at a tower, so nothing pulls a card's cell mass onto a lone tower), and
  (b) a per-hand-slot card residual  emb(card) . W [g, tower feats, sc[:7]].
Both outputs are zero-initialised, so a freshly attached module leaves every logit byte-identical. Public inputs only."""
import torch
from torch import nn

from .model_gen import CellRefine
from .model_tower import anchors


def tower_features(sc):
    """[B, 6, 5] (side, kind, hp, known, alive) and the alive mask -- model_tower.TowerModel.tower_features."""
    alive = sc[:, 64:70] > .5
    raw = sc[:, 52:58]
    known = (sc[:, 58:64] > .5) & alive & torch.isfinite(raw)
    hp = torch.where(known, raw, torch.zeros_like(raw))
    b = len(sc)
    side = sc.new_tensor([0., 0, 0, 1, 1, 1]).expand(b, -1)
    kind = sc.new_tensor([0., 1, 1, 0, 1, 1]).expand(b, -1)
    return torch.stack([side, kind, hp, known.to(sc.dtype), alive.to(sc.dtype)], -1), alive


class TowerRefine(nn.Module):
    def __init__(self, d: int, d_c: int, c: int = 32, layers: int = 4, hidden: int = 128, card: bool = True, cell: bool = True):
        super().__init__()
        self.use_card, self.use_cell = bool(card), bool(cell)
        self.unit = nn.Sequential(nn.Linear(5, d), nn.GELU(), nn.Linear(d, d))
        self.cell = CellRefine(d, c, layers)                                      # zero-init output
        self.card = nn.Sequential(nn.Linear(d + 30 + 7, hidden), nn.GELU(), nn.Linear(hidden, d_c))
        nn.init.zeros_(self.card[2].weight); nn.init.zeros_(self.card[2].bias)
        self.register_buffer("xy", torch.tensor(anchors(), dtype=torch.float32))
        self.register_buffer("cfg", torch.tensor([c, layers, hidden, int(card), int(cell)]))

    def card_residual(self, g, sc, hand_emb):
        f, _ = tower_features(sc)
        h = self.card(torch.cat([g, f.flatten(1), sc[:, :7]], -1))
        return (hand_emb * h.unsqueeze(1)).sum(-1)

    def cell_feat(self, sc):
        f, alive = tower_features(sc)
        return self.cell.features(self.unit(f), self.xy.expand(len(sc), -1, -1), alive)
