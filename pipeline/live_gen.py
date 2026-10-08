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
from .e1_eval import allowed_slots, anti_stall
from .live_mem import board_state, deck_of, my_side_of
from .model_v3 import cell_xy
from collections import deque

from .extrapolate import DropTracker, extrapolate
from .opp_elixir_count import LiveOppElixir, card_cost, regen_between
from .obs_contract import to_tokens
from .train_s1 import MAX_U

FORM_PAD = 3
EVEN_BUILDINGS = {"Tesla"}           # owner 2026-10-07: Tesla is the ONLY 2x2 building; all others are 3x3
ANYWHERE = {"Miner", "GoblinDrill"}  # deploy anywhere on the arena: never restricted


def legal_cells(entities, side: int, card_id: int, name: str, grid: str = "lattice", gx: int = 36, gy: int = 64):
    """[gx*gy] bool, True where this troop / building lands AS TAPPED; None = no restriction (spells, Miner, ...).

    Rejects (1) a footprint overlapping a building / crown tower footprint of EITHER side, (2) a footprint not wholly
    on my half (y <= 15 tiles) unless it lies wholly inside an OPEN pocket: the lane half (x 0-9 / 9-18) behind a
    destroyed enemy princess, y 17-21. Crown towers: card_id -1 bodies of tower kind (12 / 13) at a tower POSITION
    (king x 9, princess x 3.5 / 14.5); the kind only says asleep (12) / awake (13), so an awake king reads 13 like a
    princess, and kind-15 card_id -1 bodies are cursed troops, never towers. A building's footprint follows its
    position: tile corner (integer x and y) = 2x2 (Tesla, Goblin Drill), tile centre = 3x3; a mixed position is a
    moving body carrying a building id (hut spawn, drill digging), not a building.
    Evidence (live logs 10-05..07, L68 tap_audit / pocket audit): own building/tower overlap moved 67/69; troops at
    y 20.5 in an open pocket landed as aimed 27/27, X-Bows at 18.5 2/2, a Tesla corner at 23.0 was moved to 20.0;
    a Tesla on an ENEMY Goblin Drill (2x2, my half) was moved 5/5. Untested live: y 17 (RoyaleSim arena.rs bound; no
    plays aimed at y 15-17) and footprints crossing y 15 from my half (arena.rs box_zone; 0 such plays logged)."""
    kind = int(card_id) // 1_000_000                  # 26 troop, 27 building, 28 spell
    if kind not in (26, 27) or name in ANYWHERE:
        return None
    from .obs_contract import _catalog_names
    names = _catalog_names()
    buildings = {n for i, n in names.items() if i // 1_000_000 == 27}
    h = 0.0 if kind == 26 else (1.0 if name in EVEN_BUILDINGS else 1.5)
    off = 0.5 if grid == "floor" else 0.0
    c = np.arange(gx * gy)
    X, Y = (c % gx + off) / gx * 18, (1 - (c // gx + off) / gy) * 32     # my frame, tiles; my king at Y = 3
    ok = np.ones(gx * gy, bool)
    standing = {3.5: False, 14.5: False}              # enemy princess alive per lane (my-frame x)
    for e in entities:
        if e.get("hp", 1) <= 0:
            continue
        bx, by = ((18000 - e["x"]) / 1000, (32000 - e["y"]) / 1000) if side == 1 else (e["x"] / 1000, e["y"] / 1000)
        cid = int(e["card_id"])
        tower = cid == -1 and int(e.get("kind", -1)) in (12, 13)
        king = tower and abs(bx - 9) < 1 and min(abs(by - 3), abs(by - 29)) < 1
        princess = tower and min(abs(bx - 3.5), abs(bx - 14.5)) < 1 and min(abs(by - 6.5), abs(by - 25.5)) < 1
        if princess and int(e["side"]) != side:
            standing[3.5 if bx < 9 else 14.5] = True
        if king or princess:
            hb = 2.0 if king else 1.5
        elif names.get(cid) in buildings and int(e.get("kind", -1)) in (12, 13):
            # kind 14/15 bodies with a building id walk (Furnace troop, hut / drill spawns): live 180632 t3467,
            # 222521 t3464 -- a kind-15 spawn on a dead hut's tile centre blocked a legal Knight
            q = [v / 500 for v in (e["x"], e["y"])]       # 500-unit lattice index; +-2 units of reader jitter
            parity = {round(v) % 2 for v in q}
            if any(abs(v - round(v)) > .004 for v in q) or len(parity) > 1:
                continue                                  # moving body with a building id (hut spawn, digging drill)
            hb = 1.0 if parity == {0} else 1.5            # tile corner: 2x2 / tile centre: 3x3
        else:
            continue
        ok &= ~((np.abs(X - bx) < hb + h) & (np.abs(Y - by) < hb + h))
    lane_open = np.where(X + h <= 9, not standing[3.5], np.where(X - h >= 9, not standing[14.5],
                                                                not (standing[3.5] or standing[14.5])))
    mine = (Y + h <= 15) if h else (Y < 15)          # buildings: whole footprint; troops: strictly off the y 15 line
    ok &= mine | (lane_open & (Y - h >= 17) & (Y + h <= 21))
    return ok if ok.any() else None


class GenPilot:
    # Live-only (live_play.py turns it on; --no-legal-guard): the cell argmax is taken over legal_cells. Off here so
    # the SIM-parity tests keep checking the unguarded decision rule.
    legal_guard = False
    # OPT-IN live anti-leak (live_play.py --anti-leak): the SIM's anti-stall rule (e1_eval.anti_stall), None = off.
    anti_leak_elixir: Optional[float] = None
    anti_leak_seconds = 12.0

    def __init__(self, ckpt, device: str = "cpu", gate_tau: float = 0.5, use_counter: bool = True,
                 extrapolate_ticks: int = 0, predict_drops: bool = False):
        self.model, st = load_model(ckpt, torch.device(device))
        self.model.eval()
        self.feature_version = int(st["args"].get("feature_version", 1))
        self.gid = {k: i for i, k in enumerate(st["card_vocab"])}          # 0 = <pad>
        self.grid = str(st["args"].get("grid", "lattice"))
        self.dev, self.gate_tau = torch.device(device), float(gate_tau)
        self.past: list[tuple[int, int, float, float, float]] = []       # (card gid, form, x, y, t_sec) confirmed
        self.last_play_tick: Optional[int] = None       # anti-leak clock: last CONFIRMED play (or first decision)
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
        self.last_play_tick = None
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
        self.last_play_tick = round(t_sec / .05)        # the LANDING (confirmation) tick, as SIM's Match._land
        if getattr(self,'feature_version',1)>=4 and self.public is not None:
            name=next(k for k,v in self.gid.items() if v==card)
            self.public.own_events.append(dict(card=name,tick=round(t_sec/.05),side=self.public.side,accepted=True,ability=False))

    def record_ability(self, card: str, tick: int, *, accepted: bool=True) -> None:
        """Feed the confirmed OWN live press log; never call on an attempted tap."""
        if getattr(self,'feature_version',1)>=4 and self.public is not None and accepted:
            self.public.own_events.append(dict(card=card,tick=int(tick),side=self.public.side,accepted=True,ability=True))

    def stalled(self, frame: Mapping[str, Any], el_int: float) -> bool:
        """e1_eval.anti_stall on the REAL frame tick (SIM: the decision / landing clock stays real) and the elixir of
        the board the model sees (SIM: tick + H). The clock starts at the match's first decision, as Match.prepare."""
        if self.anti_leak_elixir is None:               # off: the frame / clock are not even read
            return False
        tick = int(frame["game_tick"])
        if getattr(self, "last_play_tick", None) is None:
            self.last_play_tick = tick
        return anti_stall(el_int, tick, self.last_play_tick, self.anti_leak_elixir, self.anti_leak_seconds)

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
        stalled = self.stalled(frame, info["el_int"])
        # sim rule (e1_eval.live_decide): argmax over hand slots we can afford; none affordable -> wait
        allowed = allowed_slots(np.array([h[0] > 0 for h in info["hand"]]), info["costs"], info["el_int"])
        if not allowed.any():
            return {"play": False, "no_affordable": True, "p_play": p, "hand_pos": -1, "deck_index": -1, "card": 0,
                    "form": FORM_PAD, "bs": info["bs"], "name": None, "el_int": info["el_int"], "stalled": stalled,
                    **lookahead}
        logits = out["card"][0].masked_fill(~torch.from_numpy(allowed).to(out["card"].device), float("-inf"))
        pos = int(logits.argmax())
        card, form = info["hand"][pos]
        # stalled: play even when the gate says wait (e1_eval.live_decide: p <= tau and not stalled -> WAIT)
        d = {"play": (p > self.gate_tau or stalled) and card > 0, "p_play": p, "hand_pos": pos, "no_affordable": False,
             "stalled": stalled,
             "deck_index": info["hand_deck_indices"][pos], "card": card, "form": form, "bs": info["bs"],
             "name": info["names"][info["hand_deck_indices"][pos]] if card > 0 else None, **lookahead}
        if card > 0:
            enc_card = torch.tensor([card], device=self.dev)
            logits = self.model(b, card=enc_card, form=torch.tensor([form], device=self.dev))["cell"][0]
            d["xy"] = cell_xy(int(self.guard_cells(frame, d, logits).argmax()), self.grid)
        return d

    def guard_cells(self, frame: Mapping[str, Any], d: dict, logits: torch.Tensor) -> torch.Tensor:
        """``logits`` ([..., N_CELLS]) with the cells the card would not land on as tapped set to -inf (legal_cells);
        unchanged when the guard is off, the row waits, or nothing is restricted. d['xy_unguarded'] = the plain argmax
        it replaced."""
        if not self.legal_guard or not d["play"]:
            return logits
        side = my_side_of(frame)
        me = next(p for p in frame["players"] if int(p["side"]) == side)
        ok = legal_cells(frame.get("entities", []), side, me["deck_card_ids"][d["deck_index"]], d["name"], self.grid)
        if ok is None:
            return logits
        ok = torch.from_numpy(ok).to(logits.device)
        raw = int(logits.reshape(-1, ok.numel())[0].argmax())
        if not ok[raw]:
            d["xy_unguarded"] = cell_xy(raw, self.grid)
        return logits.masked_fill(~ok, float("-inf"))
