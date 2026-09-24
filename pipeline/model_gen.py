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

from .dataset import PAST_K
from .model_v3 import S1Model, _fourier, mirror_batch
from .obs_contract import S as SC_S

N_CARDS = 123          # 122 base keys + pad 0 (dataset_gen card_vocab)
N_FORMS = 4            # base / evo / hero / pad
CARD_PAD, FORM_PAD = 0, 3
IDENT = ("hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form")


def _pool(e: torch.Tensor, m: torch.Tensor) -> torch.Tensor:
    """Masked mean + max over dim 1: [B, n, d_c], [B, n] -> [B, 2 d_c] (order-invariant)."""
    mf = m.unsqueeze(-1).float()
    mean = (e * mf).sum(1) / mf.sum(1).clamp(min=1)
    mx = e.masked_fill(~m.unsqueeze(-1), -1e4).max(1).values * (mf.sum(1) > 0)
    return torch.cat([mean, mx], -1)


class GenModel(S1Model):
    def __init__(self, d: int = 128, layers: int = 4, heads: int = 4, n_fourier: int = 8, dropout: float = 0.1,
                 d_c: int = 64, n_cards: int = N_CARDS):
        super().__init__(d=d, layers=layers, heads=heads, n_fourier=n_fourier, dropout=dropout)
        del self.card_head, self.wait_head, self.card_emb       # the deck-slot heads; pointers replace them
        self.d_c, self.n_cards = d_c, n_cards
        nfeat = 4 * n_fourier
        self.card_id = nn.Embedding(n_cards, d_c)
        self.form_id = nn.Embedding(N_FORMS, d_c)
        g_in = SC_S + 2 * d_c + d_c + 2 * d_c + PAST_K * (d_c + 2 + nfeat + 1)   # sc, hand, next, deck, past
        self.global_in = nn.Sequential(nn.Linear(g_in, d), nn.GELU(), nn.Linear(d, d))
        self.card_q = nn.Linear(d, d_c)
        self.card_b = nn.Embedding(n_cards, 1)
        self.wait_q = nn.Linear(d, d_c)
        self.wait_b = nn.Embedding(n_cards, 1)
        self.query = nn.Sequential(nn.Linear(d + d_c, d), nn.GELU(), nn.Linear(d, d))

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
        return torch.cat([b["sc"], _pool(hand, b["hand_card"] > 0), nxt, _pool(deck, b["deck_card"] > 0), pf], -1)

    def encode_gen(self, b: dict) -> dict:
        # ponytail: S1Model.encode builds g_in = cat[sc, past-channel]; passing our full global vector as `sc` and a
        # K=0 past reuses the whole trunk unchanged (its past_slot path sees an empty tensor).
        empty = b["past"].new_zeros(b["past"].shape[0], 0, 4)
        return self.encode(b["tok"], b["mask"], self.global_features(b), empty)

    def heads_gen(self, enc: dict, b: dict) -> dict:
        g = enc["g"]
        hand = self.emb(b["hand_card"], b["hand_form"])
        card = (hand * self.card_q(g).unsqueeze(1)).sum(-1) + self.card_b(b["hand_card"].long()).squeeze(-1)
        deck = self.emb(b["deck_card"], b["deck_form"])
        wait = (deck * self.wait_q(g).unsqueeze(1)).sum(-1) + self.wait_b(b["deck_card"].long()).squeeze(-1)
        return {"gate": self.gate_head(g).squeeze(-1), "value": self.value_head(g),
                "card": card.masked_fill(b["hand_card"] == CARD_PAD, float("-inf")),
                "wait": wait.masked_fill(b["deck_card"] == CARD_PAD, float("-inf"))}

    def cell_logits_gen(self, enc: dict, card: torch.Tensor, form: torch.Tensor) -> torch.Tensor:
        """[B, N_CELLS] logits for placing card identity ``card`` (+ ``form``), LongTensors [B]."""
        q = self.query(torch.cat([enc["g"], self.emb(card, form)], -1))
        kp = (self.cell_key(enc["p"]) * q.unsqueeze(1)).sum(-1)                        # same algebra as S1
        kc = q @ self.cell_key(self.cell_emb).t()
        return (kp[:, self.cell_patch] + kc) / math.sqrt(self.d) + self.cell_bias

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

