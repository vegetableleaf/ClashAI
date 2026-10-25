"""GENERALIST imitation model: S1's trunk + card-IDENTITY inputs and pointer heads, so one network plays any deck.

Spec: ``scratchpad/gauntlet/L68/generalist/plan.md`` ("Design"). Inputs are ``pipeline.dataset_gen`` rows: S1's
unit tokens and 70-d ``sc`` (hand/next deck-slot columns 7..51 zeroed) plus identity arrays.
  * TRUNK = ``S1Model``'s, reused by subclassing: unit tokens, patch tokens, one global token, transformer, same
    d / layers. Only the global token's INPUT changes: ``global_in`` reads ``sc`` + pooled card embeddings + past
    plays by card identity (S1's ``past_slot`` path is fed an empty past, see ``encode_gen``).
  * card embedding = E_card[card] + E_form[form] (123 x d_c and 4 x d_c; card 0 / form 3 = pad).
  * HAND and DECK enter the global token ORDER-INVARIANTLY (masked mean + max over real cards), so the card
    pointer is exactly equivariant to hand order and every output except the deck pointer is invariant to deck
    order. The plan said "position-ordered" for the hand; that would contradict the equivariance gate -- the hand
    position is an engine artefact, not game state, so the pooled form was chosen.
  * CARD head = pointer over the 4 hand positions: <W g, E(hand_i)> + b(card_i), pad -> -inf.
  * CELL head = S1's cell head with the query conditioned on the chosen card's IDENTITY embedding (teacher-forced
    on the pro's card in training).
  * WAIT head = pointer over the 8 deck cards ("wait for card X"), pad -> -inf. GATE, VALUE heads = S1's.
"""
from __future__ import annotations

import math
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as Fn

from .dataset import PAST_K
from .model_v3 import S1Model, _fourier, mirror_batch, N_PATCHES, PATCH_X, PATCH_Y, GRID_X, GRID_Y, cell_index, cell_label
from .obs_contract import S as SC_S

N_CARDS = 123          # 122 base keys + pad 0 (dataset_gen card_vocab)
N_FORMS = 4            # base / evo / hero / pad
CARD_PAD, FORM_PAD = 0, 3
IDENT = ("hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form")

# Step c (scratchpad/gauntlet/L74/cues/STEP_C_SPEC.md): human-visible per-unit cues, one CUE_N row per unit token
# (b["cue"] [B, U, CUE_N]); a row of zeros = cue unknown. Fields = pipeline/sim_unit_state.extract's (= the live reader's).
CUE_STATES = ("idle", "moving", "engaged", "deploying", "jumping", "tunnelling", "casting")
CUE_PHASES = ("idle", "windup", "hit")
# S6 (L74/parity/S6_CUES_1016.md): taunted (the SIM never sets it) and stunned (stun reads frozen) are not trainable
CUE_STATUS = ("frozen", "slowed", "raged", "invisible", "shielded")
CUE_N = 1 + len(CUE_STATES) + 2 + 2 + len(CUE_PHASES) + 1 + len(CUE_STATUS) + 1     # 22


def cue_vector(u: dict, target_is_tower: bool) -> list:
    """One unit (sim_unit_state.extract schema) -> its CUE_N floats: [cue_known=1, state one-hot 7, charging, Tesla
    hidden, has_target, target_is_tower, attack phase one-hot 3, attack progress frac, status 5, slow_frac]."""
    a, s = u["attack"], u["status"]
    return ([1.0] + [float(u["state"] == k) for k in CUE_STATES] + [float(bool(u["charging"])), float(u["hide"] == "hidden")]
            + [float(a["target"] is not None), float(bool(target_is_tower))] + [float(a["phase"] == k) for k in CUE_PHASES]
            + [float(a["frac"] or 0.0)] + [float(bool(s[k])) for k in CUE_STATUS] + [float(s["slow_frac"] or 0.0)])


class UnitFormInput(nn.Module):
    """V3: small actual-form embedding added to each entity embedding."""
    def __init__(self, base: nn.Linear, d: int):
        super().__init__()
        self.base = base
        self.form = nn.Embedding(3, 8)
        self.project = nn.Linear(8, d, bias=False)

    def forward(self, features):
        # S1.encode appends Fourier coordinates after the token's non-class columns.
        form = features[..., 13].long()
        return self.base(torch.cat([features[..., :13], features[..., 14:]], -1)) + self.project(self.form(form))


def _pool(e: torch.Tensor, m: torch.Tensor) -> torch.Tensor:
    """Masked mean + max over dim 1: [B, n, d_c], [B, n] -> [B, 2 d_c] (order-invariant)."""
    mf = m.unsqueeze(-1).float()
    mean = (e * mf).sum(1) / mf.sum(1).clamp(min=1)
    mx = e.masked_fill(~m.unsqueeze(-1), -1e4).max(1).values * (mf.sum(1) > 0)
    return torch.cat([mean, mx], -1)


class CellRefine(nn.Module):
    """Optional fine-resolution cell refinement (L73 centre-column fix). The base cell logit's board term is per
    2x2-TILE patch (``cell_patch``), so the cells inside one patch -- e.g. both centre columns X 8.5 / 9.5 (cells 17,
    19) -- differ only through the global query. This adds a per-CELL residual from LOCAL board features: the
    encoder's output unit states (public tokens only) are projected, scattered onto the 36 x 64 half-tile lattice
    (``cell_label(.., "lattice")`` so a left-right mirror maps cell x -> 36 - x exactly like the labels), passed
    through dilated 3x3 convs (4 layers: receptive field +-15 half-cells = 7.5 tiles; 5: +-31) and
    dotted with the cell query: residual_c = (W feat_c) . q / sqrt(d). ``W`` is zero-initialised, so a freshly
    attached module leaves every logit byte-identical."""
    def __init__(self, d: int, c: int = 32, layers: int = 4):
        super().__init__()
        self.C = c
        self.inp = nn.Linear(d, c)
        self.convs = nn.ModuleList(nn.Conv2d(c + 2 if i == 0 else c, c, 3, padding=2 ** i, dilation=2 ** i)
                                   for i in range(layers))     # dilations 1, 2, 4, ...: RF +-(2^layers - 1) cells
        self.out = nn.Linear(self.C, d)
        nn.init.zeros_(self.out.weight); nn.init.zeros_(self.out.bias)
        gy, gx = torch.meshgrid(torch.linspace(-1, 1, GRID_Y), torch.linspace(-1, 1, GRID_X), indexing="ij")
        self.register_buffer("coords", torch.stack([gx, gy]), persistent=False)
        # saved shape (width, depth): load builds the module FROM it, so a state dict missing a layer fails strict load
        self.register_buffer("cfg", torch.tensor([c, layers]))

    def features(self, u: torch.Tensor, xy: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Unit states [B, U, d], their board xy [B, U, 2], mask [B, U] -> per-cell features [B, N_CELLS, C]."""
        B = u.shape[0]
        v = self.inp(u) * mask.unsqueeze(-1).to(u.dtype)
        idx = cell_label(xy.clamp(0, 1), "lattice")
        grid = v.new_zeros(B, GRID_X * GRID_Y, self.C).scatter_add_(1, idx.unsqueeze(-1).expand(-1, -1, self.C), v)
        x = torch.cat([grid.transpose(1, 2).reshape(B, self.C, GRID_Y, GRID_X),
                       self.coords.to(v.dtype).expand(B, -1, -1, -1)], 1)
        for conv in self.convs:
            x = Fn.gelu(conv(x))
        return x.flatten(2).transpose(1, 2)

    def residual(self, feat: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
        """(W feat_c + b) . q / sqrt(d) for every cell, without materialising [B, N_CELLS, d]."""
        return ((feat * (q @ self.out.weight).unsqueeze(1)).sum(-1) + (q @ self.out.bias).unsqueeze(1)) / math.sqrt(q.shape[-1])


class MemoryEncoder(nn.Module):
    """Plan A match memory (``memory: v1``; pipeline/match_memory.py MEM_KEYS): per-event embedding = Linear(F floats) +
    Linear(the model's OWN card + form embedding of the event's card) -> a learned BOS token + 2 pre-norm transformer layers
    (d 64, 4 heads, no dropout) -> masked mean over the events + a learned-query attention pool (over BOS + events, so an
    empty memory stays finite) -> 64-d; the summary (S floats + the answer card's embedding) -> 2-layer MLP -> 64-d; concat
    -> ONE linear into the global feature vector, weight AND bias ZERO-initialised: a fresh encoder changes no output."""

    def __init__(self, d_c: int, out_dim: int, n_feat: int, n_sum: int, d: int = 64, layers: int = 2, heads: int = 4,
                 zero_empty: bool = False):
        super().__init__()
        self.ev_in = nn.Linear(n_feat, d)
        self.card_in = nn.Linear(d_c, d, bias=False)
        self.bos = nn.Parameter(torch.randn(1, 1, d) * 0.02)
        layer = nn.TransformerEncoderLayer(d, heads, 2 * d, dropout=0.0, batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.query = nn.Parameter(torch.randn(d) * 0.02)
        self.summary = nn.Sequential(nn.Linear(n_sum + d_c, d), nn.GELU(), nn.Linear(d, d))
        self.out = nn.Linear(2 * d, out_dim)
        nn.init.zeros_(self.out.weight)
        nn.init.zeros_(self.out.bias)
        # saved shape: load builds the module FROM it (n_feat, n_sum, d, layers, heads, out_dim)
        self.register_buffer("cfg", torch.tensor([n_feat, n_sum, d, layers, heads, out_dim]))
        if zero_empty:      # saved as mem.zero_empty: a checkpoint holding it rebuilds it (GenModel.load_state_dict)
            self.register_buffer("zero_empty", torch.ones(()))

    def forward(self, ev, mask, card_emb, summary, answer_emb, pad_emb=None):
        """``zero_empty`` (skew 10-25): out(rep) - out(rep of an EMPTY memory) = W (rep - rep_empty): an empty memory adds
        exactly 0, so the adapter cannot learn a memory-independent offset (the S3 v1 adapter learned one: |out(empty)| L2
        18.2, gate p -0.12 on every SIM state). ``pad_emb`` = the model's card_id(0) embedding [1, d_c] (the empty answer)."""
        z = self.rep(ev, mask, card_emb, summary, answer_emb)
        if not hasattr(self, "zero_empty"):
            return self.out(z)
        z0 = self.rep(ev.new_zeros(1, 1, ev.shape[-1]), mask.new_zeros(1, 1), card_emb.new_zeros(1, 1, card_emb.shape[-1]),
                      summary.new_zeros(1, summary.shape[-1]), pad_emb)
        return Fn.linear(z - z0, self.out.weight)

    def rep(self, ev, mask, card_emb, summary, answer_emb):
        """The 2d representation BEFORE the zero-init coupling ``out`` (S3-aux: the aux heads read it)."""
        x = self.ev_in(ev) + self.card_in(card_emb)
        B = x.shape[0]
        x = torch.cat([self.bos.expand(B, -1, -1).to(x.dtype), x], 1)
        valid = torch.cat([mask.new_ones(B, 1), mask], 1)
        h = self.encoder(x, src_key_padding_mask=~valid)
        mf = mask.unsqueeze(-1).to(h.dtype)
        mean = (h[:, 1:] * mf).sum(1) / mf.sum(1).clamp(min=1)
        a = ((h @ self.query.to(h.dtype)) / math.sqrt(h.shape[-1])).masked_fill(~valid, float("-inf")).softmax(1)
        pooled = mean + (a.unsqueeze(-1) * h).sum(1)
        return torch.cat([pooled, self.summary(torch.cat([summary, answer_emb], -1))], -1)


# S3-aux (``memory_aux: v1``): prediction heads on the memory representation. Per OWN deck card: the 10 s outcome if played
# now (swing = enemy - own tower HP lost, value removed per elixir), plays until it is back in hand (classes 0..AUX_CYC-1,
# the last = that or more) and the elixir those plays cost; per revealed OPPONENT card (opp_cycle slots): in their hand now;
# global: the opponent's next card (vocab logits) + AUX_GLOB regressions / logits.
AUX_CYC = 5
AUX_OWN = ("swing", "vpe") + tuple(f"cyc{i}" for i in range(AUX_CYC)) + ("cyc_el",)
AUX_GLOB = ("opp_el10", "opp_el_now", "threat", "commit", "xb_lock", "rk_dmg")


class MemoryAux(nn.Module):
    """S3-aux heads (train_memory --aux v1). Inputs: z = MemoryEncoder.rep (2 d_mem), ctx = the FROZEN trunk's global output
    (detached; the board, hand, elixir), card embeddings (detached) + in-hand / next flags. They never feed the policy: only
    the memory encoder learns through them, the zero-init coupling stays zero, so the policy is the base policy exactly."""

    def __init__(self, z_dim: int, ctx_dim: int, d_c: int, n_cards: int, h: int = 128):
        super().__init__()
        self.own = nn.Sequential(nn.Linear(z_dim + ctx_dim + d_c + 2, h), nn.GELU(), nn.Linear(h, len(AUX_OWN)))
        self.opp = nn.Sequential(nn.Linear(z_dim + ctx_dim + d_c, h), nn.GELU(), nn.Linear(h, 1))
        self.glob = nn.Sequential(nn.Linear(z_dim + ctx_dim, h), nn.GELU(), nn.Linear(h, n_cards + len(AUX_GLOB)))
        self.n_cards = n_cards
        self.register_buffer("cfg", torch.tensor([z_dim, ctx_dim, d_c, n_cards, h]))

    def forward(self, z, ctx, own_emb, own_flags, opp_emb):
        zc = torch.cat([z, ctx], -1)
        own = self.own(torch.cat([zc.unsqueeze(1).expand(-1, own_emb.shape[1], -1), own_emb, own_flags], -1))
        opp = self.opp(torch.cat([zc.unsqueeze(1).expand(-1, opp_emb.shape[1], -1), opp_emb], -1)).squeeze(-1)
        g = self.glob(zc)
        return {"own": own, "opp_hand": opp, "opp_next": g[:, :self.n_cards],
                **{k: g[:, self.n_cards + i] for i, k in enumerate(AUX_GLOB)}}


class GenModel(S1Model):
    def __init__(self, d: int = 128, layers: int = 4, heads: int = 4, n_fourier: int = 8, dropout: float = 0.1,
                 d_c: int = 64, n_cards: int = N_CARDS, feature_version: int = 1):
        super().__init__(d=d, layers=layers, heads=heads, n_fourier=n_fourier, dropout=dropout)
        del self.card_head, self.wait_head, self.card_emb       # the deck-slot heads; pointers replace them
        self.d_c, self.n_cards = d_c, n_cards
        self.feature_version = int(feature_version)
        nfeat = 4 * n_fourier
        self.card_id = nn.Embedding(n_cards, d_c)
        self.form_id = nn.Embedding(N_FORMS, d_c)
        g_in = SC_S + 2 * d_c + d_c + 2 * d_c + PAST_K * (d_c + 2 + nfeat + 1)   # sc, hand, next, deck, past
        if self.feature_version >= 3:
            g_in += PAST_K * (d_c + 2 + nfeat + 1)
        if self.feature_version >= 4:
            from .public_observation import CYCLE_K
            g_in += CYCLE_K * (d_c + 2)
            g_in += 4 * d_c  # masked mean/max of projectile and effect tokens
            g_in += 2 * d_c  # own visible ability controllers; readiness unknown
        self.global_in = nn.Sequential(nn.Linear(g_in, d), nn.GELU(), nn.Linear(d, d))
        self.card_q = nn.Linear(d, d_c)
        self.card_b = nn.Embedding(n_cards, 1)
        self.wait_q = nn.Linear(d, d_c)
        self.wait_b = nn.Embedding(n_cards, 1)
        self.query = nn.Sequential(nn.Linear(d + d_c, d), nn.GELU(), nn.Linear(d, d))
        if self.feature_version >= 3:
            self.unit_in = UnitFormInput(self.unit_in, d)
        if self.feature_version >= 4:
            self.projectile_in = nn.Sequential(nn.Linear(d_c+7, d_c), nn.GELU(), nn.Linear(d_c, d_c))
            self.effect_in = nn.Sequential(nn.Linear(d_c+5, d_c), nn.GELU(), nn.Linear(d_c, d_c))
            self.ability_in = nn.Sequential(nn.Linear(d_c+6, d_c), nn.GELU(), nn.Linear(d_c, d_c))
        if self.feature_version >= 6:
            self.projectile_target_in = nn.Sequential(nn.Linear(d_c+7, d), nn.GELU(), nn.Linear(d, d))
            self.projectile_target_spread = nn.Conv2d(d, d, 3, padding=1, groups=d, bias=False)
            nn.init.zeros_(self.projectile_target_spread.weight)

    def target_patches(self, b: dict) -> torch.Tensor:
        """Learned generic target/nearby-patch features; no card-specific rule.

        Zero-initialized spatial residual preserves the source checkpoint.
        Unknown and padded targets contribute nothing, including after training.
        """
        obj = b['projectiles']
        xy = obj[..., 4:6]
        valid = (obj[..., 0] > 0) & torch.isfinite(xy).all(-1) & (xy >= 0).all(-1) & (xy <= 1).all(-1)
        features = torch.where(valid.unsqueeze(-1), obj[..., 1:], 0)
        embedding = self.card_id(obj[..., 0].long())
        vectors = self.projectile_target_in(torch.cat([embedding, features], -1))
        vectors = torch.where(valid.unsqueeze(-1), vectors, 0)
        indexes = cell_index(torch.where(valid.unsqueeze(-1), xy, 0), PATCH_X, PATCH_Y)
        patches = vectors.new_zeros((len(obj), N_PATCHES, self.d))
        patches.scatter_add_(1, indexes.unsqueeze(-1).expand(-1, -1, self.d), vectors)
        patches = patches.transpose(1, 2).reshape(len(obj), self.d, PATCH_Y, PATCH_X)
        return self.projectile_target_spread(patches).flatten(2).transpose(1, 2)

    def emb(self, card: torch.Tensor, form: torch.Tensor) -> torch.Tensor:
        return self.card_id(card.long()) + self.form_id(form.long())

    def global_features(self, b: dict) -> torch.Tensor:
        hand = self.emb(b["hand_card"], b["hand_form"])
        deck = self.emb(b["deck_card"], b["deck_form"])
        nxt = self.emb(b["next_card"], b["next_form"])
        past = b["past"]                                         # [B, K, 5] = card, form, x, y, dt (card 0 = none)
        pe = self.emb(past[..., 0].long(), past[..., 1].long())
        pxy = past[..., 2:4].clamp(0, 1)                         # S1's past channel, with identity for the slot
        pf = torch.cat([pe, pxy, _fourier(pxy, self.nf), past[..., 4:5] / 30.0], -1).flatten(1)
        parts = [b["sc"], _pool(hand, b["hand_card"] > 0), nxt, _pool(deck, b["deck_card"] > 0), pf]
        if self.feature_version >= 3:
            op = b["opp_past"]
            oe = self.emb(op[..., 0].long(), op[..., 1].long())
            oxy = op[..., 2:4].clamp(0, 1)
            parts.append(torch.cat([oe, oxy, _fourier(oxy, self.nf), op[..., 4:5] / 30.0], -1).flatten(1))
        if self.feature_version >= 4:
            cycle = b['opp_cycle']
            ce = self.emb(cycle[..., 0].long(), cycle[..., 1].long())
            parts.append(torch.cat([ce, cycle[..., 2:3]/4.0, cycle[..., 3:4]/30.0], -1).flatten(1))
            for key, layer in (('projectiles', self.projectile_in), ('effects', self.effect_in)):
                obj = b[key]
                embedding = self.card_id(obj[..., 0].long())
                parts.append(_pool(layer(torch.cat([embedding, obj[..., 1:]], -1)), obj[..., 0] > 0))
            obj = b['own_ability']
            embedding = self.card_id(obj[..., 0].long())
            parts.append(_pool(self.ability_in(torch.cat([embedding, obj[..., 1:]], -1)), obj[..., 0] > 0))
        g = torch.cat(parts, -1)
        mem = getattr(self, "mem", None)
        if mem is not None:             # Plan A memory v1: + a zero-initialised projection (b must carry MEM_KEYS)
            g = g + mem(b["mem_ev"].to(g.dtype), b["mem_mask"].bool(), self.emb(b["mem_card"], b["mem_form"]).to(g.dtype),
                        b["mem_summary"].to(g.dtype), self.card_id(b["mem_answer"].long()).to(g.dtype),
                        self.card_id(b["mem_answer"].new_zeros(1).long()).to(g.dtype))
        return g

    def encode_gen(self, b: dict) -> dict:
        # ponytail: S1Model.encode builds g_in = cat[sc, past-channel]; passing our full global vector as `sc` and a
        # K=0 past reuses the whole trunk unchanged (its past_slot path sees an empty tensor).
        empty = b["past"].new_zeros(b["past"].shape[0], 0, 4)
        tok = b["tok"]
        if self.feature_version >= 3:
            tok = torch.cat([tok, b["unit_form"].to(tok.dtype).unsqueeze(-1)], -1)
        cue_in = getattr(self, "cue_in", None)
        if cue_in is not None and "cue" in b:   # step c: + cue_in(cue) on each unit token's embedding (no bias: 0 -> 0)
            hook = self.unit_in.register_forward_hook(lambda m, i, o: o + cue_in(b["cue"].to(o.dtype)))
            try:
                enc = self.encode(tok, b["mask"], self.global_features(b), empty)
            finally:
                hook.remove()
        else:
            enc = self.encode(tok, b["mask"], self.global_features(b), empty)
        if self.feature_version >= 6:
            enc = dict(enc, p=enc['p'] + self.target_patches(b))
        if getattr(self, "cell_refine", None) is not None:
            enc = dict(enc, cell_feat=self.cell_refine.features(enc["u"], tok[..., 4:6], b["mask"]))
        tr = getattr(self, "tower_refine", None)
        if tr is not None and tr.use_cell:
            enc = dict(enc, tower_cell_feat=tr.cell_feat(b["sc"]))
        return enc

    def add_tower_refine(self, **cfg):
        """Attach a fresh (zero-output) ``TowerRefine`` (pipeline/tower_refine.py); checkpoints holding
        ``tower_refine.*`` weights get it on load."""
        from .tower_refine import TowerRefine
        self.tower_refine = TowerRefine(self.d, self.d_c, **cfg).to(self.cell_emb.device)
        return self.tower_refine

    def add_cell_refine(self, c: int = 32, layers: int = 4) -> "CellRefine":
        """Attach a fresh (zero-output) ``CellRefine``; checkpoints holding ``cell_refine.*`` weights get it on load."""
        self.cell_refine = CellRefine(self.d, c, layers).to(self.cell_emb.device)
        return self.cell_refine

    def add_memory(self, d: int = 64, layers: int = 2, heads: int = 4, version: str = "v1",
                   zero_empty: bool = False) -> MemoryEncoder:
        """Attach a fresh (zero-output) ``MemoryEncoder`` (``memory: v1`` / ``v2``: the summary width match_memory.N_SUM
        gives the version, so the saved ``mem.cfg`` rebuilds it); checkpoints holding ``mem.*`` weights get it on load. The
        model then takes the match_memory MEM_KEYS (that version's) in every batch. ``zero_empty``: MemoryEncoder.forward's
        no-offset form (an empty memory adds exactly 0)."""
        from .match_memory import F, N_SUM
        self.mem = MemoryEncoder(self.d_c, self.global_in[0].in_features, F, N_SUM[memory_flag(version)], d, layers,
                                 heads, zero_empty).to(self.cell_emb.device)
        self.mem.version = version
        return self.mem

    def add_memory_aux(self, h: int = 128) -> MemoryAux:
        """Attach fresh S3-aux heads (``memory_aux: v1``; needs the memory encoder); checkpoints holding ``mem_aux.*``
        weights get them on load. Absent = no key, no parameter: the model, its state dict and outputs unchanged."""
        if getattr(self, "mem", None) is None:
            raise ValueError("memory_aux needs the memory encoder (memory v1 / v2) first")
        self.mem_aux = MemoryAux(self.mem.out.in_features, self.d, self.d_c, self.n_cards, h).to(self.cell_emb.device)
        return self.mem_aux

    def memory_aux_out(self, b: dict, ctx: torch.Tensor) -> dict:
        """S3-aux predictions for batch ``b`` (MEM_KEYS + identity + opp_cycle); ``ctx`` = the frozen trunk's global output
        ``encode_gen(b)["g"]`` (detached here). Only the memory encoder (minus its coupling) and the heads get gradients."""
        dt = ctx.dtype
        z = self.mem.rep(b["mem_ev"].to(dt), b["mem_mask"].bool(), self.emb(b["mem_card"], b["mem_form"]).to(dt),
                         b["mem_summary"].to(dt), self.card_id(b["mem_answer"].long()).to(dt))
        dc = b["deck_card"]
        inh = ((dc.unsqueeze(-1) == b["hand_card"].unsqueeze(1)).any(-1) & (dc > 0)).to(dt)
        nxt = ((dc == b["next_card"].unsqueeze(-1)) & (dc > 0)).to(dt)
        oc = b["opp_cycle"]
        with torch.no_grad():
            own = self.emb(dc, b["deck_form"]).to(dt)
            opp = self.emb(oc[..., 0].long(), oc[..., 1].long().clamp(0, N_FORMS - 1)).to(dt)
        return self.mem_aux(z, ctx.detach().to(dt), own, torch.stack([inh, nxt], -1), opp)

    def add_cue_in(self) -> nn.Linear:
        """Attach the step-c cue projection (CUE_N -> d, no bias), ZERO-initialised: every output is unchanged until it
        trains; checkpoints holding ``cue_in.weight`` get it on load (and the model then takes b["cue"])."""
        self.cue_in = nn.Linear(CUE_N, self.d, bias=False).to(self.cell_emb.device)
        nn.init.zeros_(self.cue_in.weight)
        return self.cue_in

    def load_state_dict(self, state_dict, strict: bool = True, assign: bool = False):
        # Opt-in by checkpoint CONTENT: every loader (load_model, eval_gen, rl_royale actors, live) goes through here,
        # so a state dict with the refinement builds it; one without leaves the model exactly as before.
        if "cue_in.weight" in state_dict and getattr(self, "cue_in", None) is None:
            self.add_cue_in()
        elif strict and "cue_in.weight" not in state_dict and getattr(self, "cue_in", None) is not None:
            # a pre-cue checkpoint into a model WITH the layer: that one key zero-filled, every other key still strict
            state_dict = {**state_dict, "cue_in.weight": torch.zeros_like(self.cue_in.weight)}
        if getattr(self, "cell_refine", None) is None and any(k.startswith("cell_refine.") for k in state_dict):
            if "cell_refine.cfg" in state_dict:
                c, layers = (int(v) for v in state_dict["cell_refine.cfg"])
            else:   # files written before the cfg buffer: shape inferred from the keys, cfg filled in for strict load
                c = int(state_dict["cell_refine.inp.weight"].shape[0])
                layers = sum(k.startswith("cell_refine.convs.") and k.endswith(".weight") for k in state_dict)
                state_dict = {**state_dict, "cell_refine.cfg": torch.tensor([c, layers])}
            self.add_cell_refine(c, layers)
        if getattr(self, "mem", None) is None and "mem.cfg" in state_dict:      # Plan A memory v1 / v2, by content
            from .match_memory import N_SUM
            n_feat, n_sum, d, layers, heads, _ = (int(v) for v in state_dict["mem.cfg"])
            ver = next((v for v, n in N_SUM.items() if n == n_sum), None)
            if ver is None:
                raise ValueError(f"memory weights for S={n_sum}: this match_memory has no such version ({N_SUM})")
            self.add_memory(d, layers, heads, version=ver, zero_empty="mem.zero_empty" in state_dict)
            if (n_feat, n_sum) != (self.mem.ev_in.in_features, self.mem.summary[0].in_features - self.d_c):
                raise ValueError(f"memory weights for F={n_feat}, S={n_sum}: this match_memory has another layout")
        elif strict and getattr(self, "mem", None) is not None and not any(k.startswith("mem.") for k in state_dict):
            # a checkpoint without memory into a memory model (fv6 init + memory v1): the fresh zero-output encoder is kept
            state_dict = {**state_dict, **{"mem." + k: v for k, v in self.mem.state_dict().items()}}
        if getattr(self, "mem", None) is not None and "mem.zero_empty" in state_dict and not hasattr(self.mem, "zero_empty"):
            self.mem.register_buffer("zero_empty", torch.ones((), device=self.cell_emb.device))   # load_model(memory=...)
        if getattr(self, "mem_aux", None) is None and "mem_aux.cfg" in state_dict:      # S3-aux heads, by content
            self.add_memory_aux(int(state_dict["mem_aux.cfg"][4]))
        elif strict and getattr(self, "mem_aux", None) is not None and not any(k.startswith("mem_aux.") for k in state_dict):
            state_dict = {**state_dict, **{"mem_aux." + k: v for k, v in self.mem_aux.state_dict().items()}}
        if getattr(self, "tower_refine", None) is None and "tower_refine.cfg" in state_dict:
            c, layers, hidden, card, cell = (int(v) for v in state_dict["tower_refine.cfg"])
            self.add_tower_refine(c=c, layers=layers, hidden=hidden, card=bool(card), cell=bool(cell))
        return super().load_state_dict(state_dict, strict=strict, assign=assign)

    def heads_gen(self, enc: dict, b: dict) -> dict:
        g = enc["g"]
        hand = self.emb(b["hand_card"], b["hand_form"])
        card = (hand * self.card_q(g).unsqueeze(1)).sum(-1) + self.card_b(b["hand_card"].long()).squeeze(-1)
        deck = self.emb(b["deck_card"], b["deck_form"])
        wait = (deck * self.wait_q(g).unsqueeze(1)).sum(-1) + self.wait_b(b["deck_card"].long()).squeeze(-1)
        tr = getattr(self, "tower_refine", None)
        if tr is not None and tr.use_card:
            card = card + tr.card_residual(g, b["sc"], hand)
        return {"gate": self.gate_head(g).squeeze(-1), "value": self.value_head(g),
                "card": card.masked_fill(b["hand_card"] == CARD_PAD, float("-inf")),
                "wait": wait.masked_fill(b["deck_card"] == CARD_PAD, float("-inf"))}

    def cell_logits_gen(self, enc: dict, card: torch.Tensor, form: torch.Tensor) -> torch.Tensor:
        """[B, N_CELLS] logits for placing card identity ``card`` (+ ``form``), LongTensors [B]."""
        q = self.query(torch.cat([enc["g"], self.emb(card, form)], -1))
        kp = (self.cell_key(enc["p"]) * q.unsqueeze(1)).sum(-1)                        # same algebra as S1
        kc = q @ self.cell_key(self.cell_emb).t()
        logits = (kp[:, self.cell_patch] + kc) / math.sqrt(self.d) + self.cell_bias
        if "cell_feat" in enc:
            logits = logits + self.cell_refine.residual(enc["cell_feat"], q)
        if "tower_cell_feat" in enc:
            logits = logits + self.tower_refine.cell.residual(enc["tower_cell_feat"], q)
        return logits

    def forward(self, b: dict, card: Optional[torch.Tensor] = None, form: Optional[torch.Tensor] = None) -> dict:
        """``b``: tok, mask, sc, past + the IDENT arrays (tensors). ``card``/``form``: the card to place (cell head)."""
        enc = self.encode_gen(b)
        out = self.heads_gen(enc, b)
        out["g"] = enc["g"]
        if card is not None:
            out["cell"] = self.cell_logits_gen(enc, card, form if form is not None else torch.zeros_like(card))
        return out


def mirror_gen(tok, sc, past, xy):
    """``model_v3.mirror_batch`` on a generalist batch: past is (card, form, x, y, dt) with card 0 = none, so it is
    passed through in S1's (slot, x, y, dt) layout (slot = card - 1, i.e. -1 = none) and the form column restored."""
    p4 = torch.cat([past[..., :1] - 1, past[..., 2:]], -1)
    tok, sc, p4, xy = mirror_batch(tok, sc, p4, xy)
    return tok, sc, torch.cat([p4[..., :1] + 1, past[..., 1:2], p4[..., 1:]], -1), xy


def card_form_of(deck_card: torch.Tensor, deck_form: torch.Tensor, card: torch.Tensor) -> torch.Tensor:
    """Form a card is DECKED in (dataset_gen: one form per card per side); FORM_PAD when the card is not in the deck."""
    hit = deck_card == card.unsqueeze(-1)
    return torch.where(hit.any(-1), deck_form.gather(-1, hit.long().argmax(-1, keepdim=True)).squeeze(-1),
                       torch.full_like(card, FORM_PAD))


def memory_flag(value):
    """The ``memory`` flag (checkpoint meta / rl_royale config): None (absent) = no memory, "v1" or "v2" (Plan A S1c: v1 +
    match_memory.S1C_FIELDS); anything else refused."""
    if value not in (None, "v1", "v2"):
        raise ValueError(f"memory must be absent / null, 'v1' or 'v2', got {value!r}")
    return value


def mem_version(model):
    """The memory version a model's encoder reads ("v1" / "v2"), None = no memory."""
    mem = getattr(model, "mem", None)
    return None if mem is None else getattr(mem, "version", "v1")


def attach_vocab(model, card_vocab):
    """A memory model's card vocabulary (``mem.gid``: checkpoint_gid): v2 memory rows built from batch tables
    (e1_eval.gen_batch) need it for the counter priors. A plain attribute: no state-dict key, v1 unchanged."""
    if getattr(model, "mem", None) is not None:
        from .dataset_gen import checkpoint_gid
        model.mem.gid = checkpoint_gid(card_vocab)
    return model


def check_memory_meta(st):
    """A v2 checkpoint records the S1c artifacts' sha256 (``memory_v2``): its features need exactly those."""
    rec = st.get("memory_v2")
    if rec is not None:
        from .match_memory import v2_meta
        now = v2_meta()
        if {k: rec.get(k) for k in now} != now:
            raise ValueError(f"memory v2 artifacts changed since this checkpoint: {rec} vs now {now} (counter_priors.json / "
                             "lock_head.json; the model's memory inputs would differ)")


def load_model(ckpt, device, memory=None):
    """Versioned generalist loader. Only stored args enable new observations. ``memory`` "v1" / "v2" (or the checkpoint's
    own ``memory`` meta key): a memory encoder -- the checkpoint's ``mem.*`` weights, or a fresh zero-output one for a
    checkpoint without them (e.g. CLXIII fv6 + memory v1 = CLXIII's outputs exactly). Weights in the file always build it."""
    st = torch.load(ckpt, map_location=device)
    memory = memory_flag(memory if memory is not None else st.get("memory"))
    check_memory_meta(st)
    if not st.get("gen"):
        raise SystemExit(f"{ckpt} is not a generalist checkpoint (no 'gen' key)")
    a = st["args"]
    if st.get("architecture") == "public_tower_spatial_v1":
        if memory is not None:
            raise ValueError("memory v1 is not wired for the public_tower_spatial_v1 architecture")
        # Explicit checkpoint metadata selects this owner-requested architecture;
        # ordinary checkpoints retain the original constructor and exact behavior.
        from .model_tower import construct
        if int(a.get("feature_version", 1)) != 7:
            raise ValueError("Tower architecture requires feature_version=7")
        model = construct(st)
        for key in ("tower_spatial_xy", "tower_spatial_side", "tower_spatial_kind"):
            if not torch.equal(st["model"][key].cpu(), model.state_dict()[key]):
                raise ValueError(f"Invalid fixed public tower geometry: {key}")
        model.load_state_dict(st["model"], strict=True)
        return model.to(device), st
    if st.get("architecture"):
        raise ValueError(f"Unsupported checkpoint architecture: {st['architecture']}")
    model = GenModel(d=int(a["d"]), layers=int(a["layers"]), d_c=int(st["d_c"]),
                     n_cards=len(st["card_vocab"]), feature_version=int(a.get("feature_version", 1))).to(device)
    if memory is not None:
        if int(a.get("feature_version", 1)) < 4:
            raise ValueError(f"memory {memory} needs a feature_version >= 4 model (the public observation it is built from)")
        model.add_memory(version=memory)
    model.load_state_dict(st["model"])
    return attach_vocab(model, st["card_vocab"]), st
