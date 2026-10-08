"""Generalist (GenModel) decision from a live memory-reader frame (L68 live reader).

Builds ONE row exactly as ``dataset_gen`` does for training (``to_tokens`` board + ``sc`` with the deck-slot columns
7..51 zeroed, card-identity hand / next / deck arrays by the checkpoint's ``card_vocab``, past = my last PAST_K
confirmed plays as (card, form, x, y, seconds ago)) and runs gate -> card pointer -> cell head.

Opponent elixir: the owner's rule forbids the opponent's hidden value, so it comes from
``pipeline.opp_elixir_count.LiveOppElixir`` -- a counter over PUBLIC board events (start 6.0, regen schedule, minus
the cost of each opponent play it sees). ``observe(frame)`` must see EVERY active+coherent frame (not only the ones
it decides on). RoyaleSim screen (HANDOFF L68ao, 58 matches): hidden 0.879 -> counter 0.983 for this generalist.
``use_counter=False`` feeds None (unknown) instead.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

import numpy as np
import torch

from .dataset import PAST_K
from .dataset_gen import SC_SLOT_COLS, card_key
from .model_gen import load_model
from . import vocab
from .e1_eval import allowed_slots
from .live_mem import board_state, deck_of, my_side_of
from .model_v3 import cell_xy
from collections import deque

from .extrapolate import DropTracker, extrapolate
from .opp_elixir_count import LiveOppElixir, card_cost, regen_between
from .obs_contract import to_tokens
from .train_s1 import MAX_U

FORM_PAD = 3


class GenPilot:
    def __init__(self, ckpt, device: str = "cpu", gate_tau: float = 0.5, use_counter: bool = True,
                 extrapolate_ticks: int = 0, predict_drops: bool = False):
        self.model, st = load_model(ckpt, torch.device(device))
        self.model.eval()
        self.feature_version = int(st["args"].get("feature_version", 1))
        self.gid = {k: i for i, k in enumerate(st["card_vocab"])}          # 0 = <pad>
        self.grid = str(st["args"].get("grid", "lattice"))
        self.dev, self.gate_tau = torch.device(device), float(gate_tau)
        self.past: list[tuple[int, int, float, float, float]] = []       # (card gid, form, x, y, t_sec) confirmed
        self.history: dict = {}
        self.use_counter = use_counter
        self.opp = LiveOppElixir() if use_counter or self.feature_version >= 3 else None
        self.opp_est: float | None = None
        self.public = None
        self.public_battle = None
        # Board extrapolation (pipeline/extrapolate.py, HANDOFF L68as): decide on the board H ticks ahead, where our
        # card will land (~26 ticks after the decision frame live). Velocity window ~10 ticks, as the screen arm.
        self.ext_h = int(extrapolate_ticks)
        self.frames: deque = deque(maxlen=30)            # (tick, raw reader frame), fed by observe()
        # OPT-IN predict_drops (extrapolate.py docstring): observed Skeleton Barrel balloon disappearances -> the 7 skeletons
        # appear in the look-ahead 12 ticks later. None = off = the look-ahead is byte-identical.
        self.drops = DropTracker() if predict_drops and self.ext_h else None

    def reset_match(self) -> None:
        self.past.clear()
        self.history.clear()
        self.frames.clear()
        if getattr(self, 'drops', None) is not None:
            self.drops.reset()
        if self.opp:
            self.opp.reset()
        self.opp_est = None
        if getattr(self, 'public', None) is not None:
            self.public.reset()
        self.public_battle = None

    def observe(self, frame: Mapping[str, Any]) -> float | None:
        """Feed the opponent-elixir counter one active+coherent frame (call on EVERY such frame)."""
        from .reader_identity_aliases import dedupe_hero_bodies
        frame = dedupe_hero_bodies(frame)        # lead 2026-10-06: the 203000023 Hero + FloatingCube pair -> one Hero
        if getattr(self, 'feature_version', 1) >= 4:
            from .public_observation import PublicObserver
            side = my_side_of(frame)
            battle = (frame.get('chain') or {}).get('battle')
            if (getattr(self, 'public', None) is None or self.public.side != side or
                    (battle is not None and self.public_battle is not None and battle != self.public_battle)):
                self.public = PublicObserver(side)
            if battle is not None:
                self.public_battle = battle
            self.opp_est = self.public.update(frame, source='reader')
        elif self.opp:
            self.opp_est = self.opp.update(frame)
        if self.frames and int(frame["game_tick"]) < self.frames[-1][0]:
            self.frames.clear()                          # tick went backwards: a new match
        self.frames.append((int(frame["game_tick"]), frame))
        if getattr(self, 'drops', None) is not None:
            try:
                self.drops.observe(frame, my_side_of(frame))
            except ValueError:                           # hand unreadable this frame (my_side_of): skip, keep the tracker
                pass
        return self.opp_est

    def record_play(self, card: int, form: int, xy: tuple[float, float], t_sec: float) -> None:
        self.past.append((card, form, float(xy[0]), float(xy[1]), float(t_sec)))
        if getattr(self,'feature_version',1)>=4 and self.public is not None:
            name=next(k for k,v in self.gid.items() if v==card)
            self.public.own_events.append(dict(card=name,tick=round(t_sec/.05),side=self.public.side,accepted=True,ability=False))

    def record_ability(self, card: str, tick: int, *, accepted: bool=True) -> None:
        """Feed the confirmed OWN live press log; never call on an attempted tap."""
        if getattr(self,'feature_version',1)>=4 and self.public is not None and accepted:
            self.public.own_events.append(dict(card=card,tick=int(tick),side=self.public.side,accepted=True,ability=True))

    def _card(self, name: str) -> int:
        k = card_key(name)
        if k not in self.gid:
            raise KeyError(f"card {name!r} ({k}) not in the generalist's card_vocab")
        return self.gid[k]

    def row(self, frame: Mapping[str, Any]) -> tuple[dict, dict]:
        from .reader_identity_aliases import dedupe_hero_bodies
        frame = dedupe_hero_bodies(frame)        # lead 2026-10-06: the 203000023 Hero + FloatingCube pair -> one Hero
        side = my_side_of(frame)
        _, names = deck_of(frame, side)
        me = next(p for p in frame["players"] if int(p["side"]) == side)
        forms = list(me.get("deck_form_flags") or [0] * 8)                # reader 0/1/2 = base/evo/hero (as ours)
        opp = self.opp_est
        if self.ext_h:
            # ALWAYS advance (prev None -> clock + my elixir only), so history ages never jump by H mid-match
            tick = int(frame["game_tick"])
            prev = next((f for t, f in reversed(self.frames) if t <= tick - 10), None)
            object_context = (self.public.object_context(tick)
                              if getattr(self, 'feature_version', 1) >= 4 and self.public is not None else {})
            if getattr(self, 'drops', None) is not None:
                object_context = dict(object_context, drops=self.drops.pending)
            frame = extrapolate(frame, prev, self.ext_h, side, **object_context)
            if opp is not None:
                opp = min(10.0, opp + regen_between(tick, tick + self.ext_h))
        if getattr(self, 'feature_version', 1) >= 4 and getattr(self, 'public', None) is not None:
            opp = self.public.estimate_at(int(frame['game_tick'])) if self.use_counter else None
        if getattr(self, "feature_version", 1) >= 3:
            from dataclasses import replace
            from .live_mem import to_observe
            from .obs_contract import from_engine
            live_deck, live_names = deck_of(frame, side)
            bs = from_engine(to_observe(frame, side, live_names), side, live_deck, history=self.history,
                             engine_deck=live_names, unmapped=set(), feature_version=self.feature_version)
            bs = replace(bs, source="live_mem", opp_elixir=opp if self.use_counter else None)
        else:
            bs = board_state(frame, history=self.history, opp_elixir=opp)
        if getattr(self, 'feature_version', 1) >= 4:
            from .public_observation import body_only_board
            bs = body_only_board(bs)
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
        if getattr(self, "feature_version", 1) >= 3:
            from .dataset_gen import opponent_past
            from .obs_contract import to_unit_forms
            b["unit_form"] = T(to_unit_forms(bs, MAX_U))
            if self.feature_version >= 4:
                if self.public is None:
                    raise ValueError('observe() must receive reader frames before gen_v3.1 row()')
                for key, value in self.public.features(int(frame['game_tick']), self.gid,
                        objects_override=frame.get('extrapolated_public_objects')).items():
                    b[key] = T(value, torch.float32)
            else:
                b["opp_past"] = T(opponent_past(self.opp.detected_plays, int(frame["game_tick"]), side, self.gid), torch.float32)
        # Affordability, as the sim's live rule (e1_eval.allowed_slots): int(elixir the model's own input shows, i.e. at
        # tick+H when extrapolating) vs the card's cost. Unknown cost (Mirror, pad slot) -> 0 = never blocks.
        costs = [(card_cost(vocab.engine_key(names[d])) or 0.0) if d >= 0 else 0.0 for d in me["hand_deck_indices"]]
        info = {"bs": bs, "hand": hand, "hand_deck_indices": list(me["hand_deck_indices"]), "names": names,
                "costs": costs, "el_int": int(bs.my_elixir)}
        if 'public_lookahead_counts' in frame:
            info['public_lookahead_counts'] = frame['public_lookahead_counts']
        return b, info

    @torch.no_grad()
    def decide(self, frame: Mapping[str, Any]) -> dict:
        """{'play': bool, 'p_play', 'hand_pos', 'deck_index', 'card', 'form', 'xy' (my board frame), 'bs'}."""
        b, info = self.row(frame)
        lookahead = ({'public_lookahead_counts': info['public_lookahead_counts']}
                     if 'public_lookahead_counts' in info else {})
        out = self.model(b)
        p = float(torch.sigmoid(out["gate"][0]))
        # sim rule (e1_eval.live_decide): argmax over hand slots we can afford; none affordable -> wait
        allowed = allowed_slots(np.array([h[0] > 0 for h in info["hand"]]), info["costs"], info["el_int"])
        if not allowed.any():
            return {"play": False, "no_affordable": True, "p_play": p, "hand_pos": -1, "deck_index": -1, "card": 0,
                    "form": FORM_PAD, "bs": info["bs"], "name": None, "el_int": info["el_int"], **lookahead}
        logits = out["card"][0].masked_fill(~torch.from_numpy(allowed).to(out["card"].device), float("-inf"))
        pos = int(logits.argmax())
        card, form = info["hand"][pos]
        d = {"play": p > self.gate_tau and card > 0, "p_play": p, "hand_pos": pos, "no_affordable": False,
             "deck_index": info["hand_deck_indices"][pos], "card": card, "form": form, "bs": info["bs"],
             "name": info["names"][info["hand_deck_indices"][pos]] if card > 0 else None, **lookahead}
        if card > 0:
            enc_card = torch.tensor([card], device=self.dev)
            logits = self.model(b, card=enc_card, form=torch.tensor([form], device=self.dev))["cell"][0]
            d["xy"] = cell_xy(int(logits.argmax()), self.grid)
        return d
