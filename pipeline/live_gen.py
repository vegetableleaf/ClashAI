"""Generalist (GenModel) decision from a live memory-reader frame (L68 live reader).

Builds ONE row exactly as ``dataset_gen`` does for training (``to_tokens`` board + ``sc`` with the deck-slot columns
7..51 zeroed, card-identity hand / next / deck arrays by the checkpoint's ``card_vocab``, past = my last PAST_K
confirmed plays as (card, form, x, y, seconds ago)) and runs gate -> card pointer -> cell head.

KNOWN train/live gap (b, measured separately): the generalist was trained on engine rows where opponent elixir is
always known (``opp_known = 1``); the owner's rule forces it unknown live (``opp_known = 0``), a state it never saw.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

import numpy as np
import torch

from .dataset import PAST_K
from .dataset_gen import SC_SLOT_COLS, card_key
from .eval_gen import load_model
from .live_mem import board_state, deck_of, my_side_of
from .model_v3 import cell_xy
from .obs_contract import to_tokens
from .train_s1 import MAX_U

FORM_PAD = 3


class GenPilot:
    def __init__(self, ckpt, device: str = "cpu", gate_tau: float = 0.5):
        self.model, st = load_model(ckpt, torch.device(device))
        self.model.eval()
        self.gid = {k: i for i, k in enumerate(st["card_vocab"])}          # 0 = <pad>
        self.grid = str(st["args"].get("grid", "lattice"))
        self.dev, self.gate_tau = torch.device(device), float(gate_tau)
        self.past: list[tuple[int, int, float, float, float]] = []       # (card gid, form, x, y, t_sec) confirmed
        self.history: dict = {}

    def reset_match(self) -> None:
        self.past.clear()
        self.history.clear()

    def record_play(self, card: int, form: int, xy: tuple[float, float], t_sec: float) -> None:
        self.past.append((card, form, float(xy[0]), float(xy[1]), float(t_sec)))

    def _card(self, name: str) -> int:
        k = card_key(name)
        if k not in self.gid:
            raise KeyError(f"card {name!r} ({k}) not in the generalist's card_vocab")
        return self.gid[k]

    def row(self, frame: Mapping[str, Any]) -> tuple[dict, dict]:
        side = my_side_of(frame)
        _, names = deck_of(frame, side)
        me = next(p for p in frame["players"] if int(p["side"]) == side)
        forms = list(me.get("deck_form_flags") or [0] * 8)                # reader 0/1/2 = base/evo/hero (as ours)
        bs = board_state(frame, history=self.history)
        tok, mask, sc = to_tokens(bs, MAX_U)
        sc = sc.copy()
        sc[SC_SLOT_COLS] = 0.0
        deck = [self._card(n) for n in names]
        hand = [(deck[d], forms[d]) if d >= 0 else (0, FORM_PAD) for d in me["hand_deck_indices"]]
        nd = int(me["next_deck_index"])
        nxt = (deck[nd], forms[nd]) if nd >= 0 else (0, FORM_PAD)
        order = np.argsort(deck, kind="stable")                           # dataset_gen: canonical deck order
        past = np.tile(np.array([0, FORM_PAD, -1, -1, -1], np.float32), (PAST_K, 1))
        for i, (c, f, x, y, t) in enumerate(reversed(self.past[-PAST_K:])):
            past[i] = (c, f, x, y, bs.t_sec - t)
        T = lambda a, dt=torch.long: torch.as_tensor(np.asarray(a), dtype=dt, device=self.dev).unsqueeze(0)  # noqa: E731
        b = {"tok": T(tok, torch.float32), "mask": T(mask, torch.bool), "sc": T(sc, torch.float32),
             "past": T(past, torch.float32),
             "hand_card": T([h[0] for h in hand]), "hand_form": T([h[1] for h in hand]),
             "next_card": T([nxt[0]]).squeeze(0), "next_form": T([nxt[1]]).squeeze(0),
             "deck_card": T(np.asarray(deck)[order]), "deck_form": T(np.asarray(forms)[order])}
        info = {"bs": bs, "hand": hand, "hand_deck_indices": list(me["hand_deck_indices"]), "names": names}
        return b, info

    @torch.no_grad()
    def decide(self, frame: Mapping[str, Any]) -> dict:
        """{'play': bool, 'p_play', 'hand_pos', 'deck_index', 'card', 'form', 'xy' (my board frame), 'bs'}."""
        b, info = self.row(frame)
        out = self.model(b)
        p = float(torch.sigmoid(out["gate"][0]))
        pos = int(out["card"][0].argmax())
        card, form = info["hand"][pos]
        d = {"play": p > self.gate_tau and card > 0, "p_play": p, "hand_pos": pos,
             "deck_index": info["hand_deck_indices"][pos], "card": card, "form": form, "bs": info["bs"],
             "name": info["names"][info["hand_deck_indices"][pos]] if card > 0 else None}
        if card > 0:
            enc_card = torch.tensor([card], device=self.dev)
            logits = self.model(b, card=enc_card, form=torch.tensor([form], device=self.dev))["cell"][0]
            d["xy"] = cell_xy(int(logits.argmax()), self.grid)
        return d
