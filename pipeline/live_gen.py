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

import math
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import torch

from .dataset import PAST_K
from .dataset_gen import SC_SLOT_COLS, card_key
from .model_gen import load_model
from . import vocab
from .e1_eval import allowed_slots, anti_stall, pending_hand
from .live_mem import board_state, deck_of, my_side_of
from .model_v3 import cell_xy
from collections import deque

from .extrapolate import DropTracker, catalog, extrapolate, pending_board
from .opp_elixir_count import LiveOppElixir, card_cost, regen_between
from .obs_contract import to_tokens
from .train_s1 import MAX_U

FORM_PAD = 3
EVEN_BUILDINGS = {"Tesla"}           # owner 2026-10-07: Tesla is the ONLY 2x2 building; all others are 3x3
ANYWHERE = {"Miner", "GoblinDrill"}  # deploy anywhere on the arena: never restricted
SIM_START_TICK = 90                  # royale_env warmup_ticks: the SIM's first decision = its anti-stall clock start


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


OWN_FX_TICKS = 150                   # as e1_eval: own plays older than 7.5 s act on nothing


def own_effects_raw(own_fx, side: int, tick: int) -> list:
    """GenPilot.own_fx (model-frame xy, live_play.my_frame_xy) -> extrapolate's own_effects (raw engine units)."""
    out = []
    for p in own_fx:
        if tick - OWN_FX_TICKS <= p["tick"]:
            x, y = p["xy"][0] * 18000.0, (1 - p["xy"][1]) * 32000.0
            x, y = (18000.0 - x, 32000.0 - y) if side == 1 else (x, y)
            out.append(dict(card=p["card"], x=x, y=y, tick=p["tick"], ability=p.get("ability", False)))
    return out


def pending_frame(frame, me, side: int, pend: list) -> dict:
    """--pipeline-decisions: the (look-ahead) reader frame plus my pending plays as the game will show them at its tick
    (extrapolate.pending_board, the SIM's Match._pending_raw rule): reader-shaped bodies (kind 14 troop / 12 building = the
    reader's fresh own bodies; hp = max_hp: only hp_frac 1 reaches the model for these cards) and, when the frame carries
    look-ahead public objects, the spell projectile / area rows."""
    plays = []
    for q in pend:
        x, y = q["xy"][0] * 18000.0, (1 - q["xy"][1]) * 32000.0
        x, y = (18000.0 - x, 32000.0 - y) if side == 1 else (x, y)
        plays.append(dict(card=q["name"], x=x, y=y, land=q["land"]))
    bodies, shots, areas = pending_board(plays, side, int(frame["game_tick"]))
    if not (bodies or shots or areas):
        return frame
    cid = {card_key(q["name"]): me["deck_card_ids"][q["deck_index"]] for q in pend}
    out = dict(frame, entities=list(frame.get("entities") or []) + [
        dict(side=side, x=x, y=y, card_id=cid[k], hp=float(catalog()[k]["hitpoints"] or 1),
             max_hp=float(catalog()[k]["hitpoints"] or 1), kind=12 if catalog()[k]["kind"] == "building" else 14,
             address=eid) for k, x, y, eid in bodies])
    objs = frame.get("extrapolated_public_objects")
    if objs is not None and (shots or areas):
        out["extrapolated_public_objects"] = dict(projectiles=list(objs["projectiles"]) + shots,
                                                  effects=list(objs["effects"]) + areas)
    return out


class GenPilot:
    # Live-only (live_play.py turns it on; --no-legal-guard): the cell argmax is taken over legal_cells. Off here so
    # the SIM-parity tests keep checking the unguarded decision rule.
    legal_guard = False
    # OPT-IN live anti-leak (live_play.py --anti-leak): the SIM's anti-stall rule (e1_eval.anti_stall), None = off.
    anti_leak_elixir: Optional[float] = None
    anti_leak_seconds = 12.0
    # OPT-IN (live_play.py --afford-ticks, L74): the afford mask uses my elixir this many ticks after the decision
    # frame (e1_eval.afford_elixir, raw frame) instead of the look-ahead board's. None = off = unchanged.
    afford_ticks: Optional[int] = None
    # OPT-IN (live_play.py --identity-ext on, L74): body_identity.extension() around the board's from_engine (new card
    # ids + ability / evo spawn bodies -> learned classes). False = off = unchanged.
    identity_ext = False

    def __init__(self, ckpt, device: str = "cpu", gate_tau: float = 0.5, use_counter: bool = True,
                 extrapolate_ticks: int = 0, predict_drops: bool = False, own_effects: bool = False,
                 hero_ability_spec: str = "off"):
        self.model, st = load_model(ckpt, torch.device(device))
        self.model.eval()
        self.feature_version = int(st["args"].get("feature_version", 1))
        self.gid = {k: i for i, k in enumerate(st["card_vocab"])}          # 0 = <pad>
        self.grid = str(st["args"].get("grid", "lattice"))
        self.dev, self.gate_tau = torch.device(device), float(gate_tau)
        self.past: list[tuple[int, int, float, float, float]] = []       # (card gid, form, x, y, t_sec) confirmed
        self.last_play_tick: Optional[int] = None       # anti-leak clock: last CONFIRMED play (None = SIM_START_TICK)
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
        # OPT-IN own_effects (W1, extrapolate.py docstring): my confirmed plays / ability presses (card, model xy, confirm
        # tick) move the enemy bodies they reach in the look-ahead, as SIM's cfg "own_effects". None = off = unchanged.
        self.own_fx = [] if own_effects and self.ext_h else None
        # OPT-IN live-only own-ability catalog switch (live_play.py --hero-ability-spec, L74 econ2 parity fix): 'off' =
        # the pinned catalog (my Hero Ice Wizard reads 'readiness unknown', unchanged); 'supplement' = own_ability.SUPPLEMENT
        # (the training-style token). Only the own_ability token changes.
        from .own_ability import HERO_SPECS
        if hero_ability_spec not in HERO_SPECS:
            raise ValueError(f"hero_ability_spec {hero_ability_spec!r} not in {HERO_SPECS}")
        self.hero_ability_spec = hero_ability_spec
        # OPT-IN --pipeline-decisions (live_play set_pending): my tapped, not yet confirmed plays, each dict(hand_pos,
        # deck_index, card, form, name, xy, land). A decision sees every one still in my hand as executed at its landing
        # (row(); e1_eval.Match._pending_view's rule). Empty = every code path below is skipped = unchanged.
        self.pending_plays: list = []

    def set_pending(self, plays: list) -> None:
        """live_play: my outstanding taps (oldest first) before every decision; [] = none."""
        self.pending_plays = list(plays)

    def _pending_in_hand(self, me: Mapping[str, Any]) -> list:
        """Pending plays whose card still sits at its hand position (not executed yet), oldest first."""
        hand = list(me["hand_deck_indices"])
        return [q for q in getattr(self, "pending_plays", None) or [] if hand[q["hand_pos"]] == q["deck_index"]]

    def reset_match(self) -> None:
        self.pending_plays = []
        self.past.clear()
        self.last_play_tick = None
        self.history.clear()
        self.frames.clear()
        if getattr(self, 'drops', None) is not None:
            self.drops.reset()
        if getattr(self, 'own_fx', None) is not None:
            self.own_fx.clear()
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
        if getattr(self, 'own_fx', None) is not None:
            self.own_fx.append(dict(card=next(k for k, v in self.gid.items() if v == card), xy=tuple(xy),
                                    tick=round(t_sec / .05)))
        if getattr(self,'feature_version',1)>=4 and self.public is not None:
            name=next(k for k,v in self.gid.items() if v==card)
            self.public.own_events.append(dict(card=name,tick=round(t_sec/.05),side=self.public.side,accepted=True,ability=False))

    def record_ability(self, card: str, tick: int, *, accepted: bool=True) -> None:
        """Feed the confirmed OWN live press log; never call on an attempted tap."""
        if getattr(self, 'own_fx', None) is not None and accepted:   # own_effects: the CONFIRMATION frame's tick (the
            self.own_fx.append(dict(card=card, xy=(0.0, 0.0), ability=True,     # freeze window is measured from it)
                                    tick=self.frames[-1][0] if self.frames else int(tick)))
        if getattr(self,'feature_version',1)>=4 and self.public is not None and accepted:
            self.public.own_events.append(dict(card=card,tick=int(tick),side=self.public.side,accepted=True,ability=True))

    def stalled(self, frame: Mapping[str, Any], el_int: float) -> bool:
        """e1_eval.anti_stall on the REAL frame tick (SIM: the decision / landing clock stays real) and the elixir of
        the board the model sees (SIM: tick + H). With no confirmed play yet the clock runs from SIM_START_TICK, the
        SIM's first decision (Match.prepare), whatever tick live first decides at (>= UI_READY_MIN_TICK 150)."""
        if self.anti_leak_elixir is None:               # off: the frame / clock are not even read
            return False
        tick = int(frame["game_tick"])
        if getattr(self, "last_play_tick", None) is None:
            self.last_play_tick = SIM_START_TICK
        return anti_stall(el_int, tick, self.last_play_tick, self.anti_leak_elixir, self.anti_leak_seconds)

    def _card(self, name: str) -> int:
        k = card_key(name)
        if k not in self.gid:
            raise KeyError(f"card {name!r} ({k}) not in the generalist's card_vocab")
        return self.gid[k]

    def row(self, frame: Mapping[str, Any]) -> tuple[dict, dict]:
        from .reader_identity_aliases import dedupe_hero_bodies
        frame = dedupe_hero_bodies(frame)        # lead 2026-10-06: the 203000023 Hero + FloatingCube pair -> one Hero
        raw_tick = frame["game_tick"]
        side = my_side_of(frame)
        _, names = deck_of(frame, side)
        me = next(p for p in frame["players"] if int(p["side"]) == side)
        forms = list(me.get("deck_form_flags") or [0] * 8)                # reader 0/1/2 = base/evo/hero (as ours)
        opp = self.opp_est
        pend = self._pending_in_hand(me) if getattr(self, "pending_plays", None) else []   # --pipeline-decisions
        if self.ext_h:
            # ALWAYS advance (prev None -> clock + my elixir only), so history ages never jump by H mid-match
            tick = int(frame["game_tick"])
            prev = next((f for t, f in reversed(self.frames) if t <= tick - 10), None)
            object_context = (self.public.object_context(tick)
                              if getattr(self, 'feature_version', 1) >= 4 and self.public is not None else {})
            if getattr(self, 'drops', None) is not None:
                object_context = dict(object_context, drops=self.drops.pending)
            if getattr(self, 'own_fx', None) is not None:      # + a pending play at its expected landing tick
                fx = self.own_fx + [dict(card=card_key(q["name"]), xy=q["xy"], tick=q["land"]) for q in pend]
                object_context = dict(object_context, own_effects=own_effects_raw(fx, side, tick))
            frame = extrapolate(frame, prev, self.ext_h, side, **object_context)
            if opp is not None:
                opp = min(10.0, opp + regen_between(tick, tick + self.ext_h))
        if pend:                                          # --pipeline-decisions: pending plays on the look-ahead board
            frame = pending_frame(frame, me, side, pend)
        if getattr(self, 'feature_version', 1) >= 4 and getattr(self, 'public', None) is not None:
            opp = self.public.estimate_at(int(frame['game_tick'])) if self.use_counter else None
        if getattr(self, "feature_version", 1) >= 3:
            from dataclasses import replace
            from .live_mem import to_observe
            from .obs_contract import from_engine
            from contextlib import nullcontext
            from .body_identity import extension
            live_deck, live_names = deck_of(frame, side)
            with extension() if getattr(self, "identity_ext", False) else nullcontext():
                bs = from_engine(to_observe(frame, side, live_names), side, live_deck, history=self.history,
                                 engine_deck=live_names, unmapped=set(), feature_version=self.feature_version)
            bs = replace(bs, source="live_mem", opp_elixir=opp if self.use_counter else None)
        else:
            bs = board_state(frame, history=self.history, opp_elixir=opp)
        if getattr(self, 'feature_version', 1) >= 4:
            from .public_observation import body_only_board
            bs = body_only_board(bs)
        deck = [self._card(n) for n in names]
        hand_idx, nd, pos = list(me["hand_deck_indices"]), int(me["next_deck_index"]), []
        cost_of = lambda d: (card_cost(vocab.engine_key(names[d])) or 0.0) if d >= 0 else 0.0   # noqa: E731
        spent = 0.0
        if pend:   # --pipeline-decisions: pending = executed (e1_eval.pending_hand; the SIM's Match._pending_view)
            from dataclasses import replace
            hand_idx, nd, pos = pending_hand(list(range(len(deck))), hand_idx, nd,
                                             [deck.index(c) for c, *_ in self.past], [q["deck_index"] for q in pend])
            spent = sum(cost_of(me["hand_deck_indices"][i]) for i in pos)
            bs = replace(bs, my_elixir=max(0.0, bs.my_elixir - spent))
        tok, mask, sc = to_tokens(bs, MAX_U)
        sc = sc.copy()
        sc[SC_SLOT_COLS] = 0.0
        hand = [(deck[d], forms[d]) if d >= 0 else (0, FORM_PAD) for d in hand_idx]
        nxt = (deck[nd], forms[nd]) if nd >= 0 else (0, FORM_PAD)
        order = np.argsort(deck, kind="stable")                           # dataset_gen: canonical deck order
        past = np.tile(np.array([0, FORM_PAD, -1, -1, -1], np.float32), (PAST_K, 1))
        rows = self.past + [(q["card"], q["form"], *q["xy"], min(q["land"] * 0.05, bs.t_sec)) for q in pend]
        for i, (c, f, x, y, t) in enumerate(reversed(rows[-PAST_K:])):
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
                if getattr(self, "hero_ability_spec", "off") != "off":   # same rows / events / tick as features()
                    from bisect import bisect_right
                    from .own_ability import tokens
                    pub, t = self.public, int(frame['game_tick'])
                    ai = bisect_right(pub.ability_ticks, t) - 1
                    b["own_ability"] = T(tokens(pub.ability_rows[ai] if ai >= 0 else [], self.gid, pub.own_events, t,
                                                hero_spec=self.hero_ability_spec), torch.float32)
            else:
                b["opp_past"] = T(opponent_past(self.opp.detected_plays, int(frame["game_tick"]), side, self.gid), torch.float32)
        # Affordability, as the sim's live rule (e1_eval.allowed_slots): int(elixir the model's own input shows, i.e. at
        # tick+H when extrapolating) vs the card's cost. Unknown cost (Mirror, pad slot) -> 0 = never blocks.
        # --pipeline-decisions: a pending play's hand position (the view shows the next card there) is never choosable --
        # the game still holds the pending card there, a tap would replay it
        costs = [float("inf") if i in pos else cost_of(d) for i, d in enumerate(me["hand_deck_indices"])]
        info = {"bs": bs, "hand": hand, "hand_deck_indices": hand_idx, "names": names,   # = the reader's unless pending
                "costs": costs, "el_int": int(bs.my_elixir)}
        info["el_afford"] = info["el_int"]
        if getattr(self, "afford_ticks", None) is not None:    # raw frame `me` (before extrapolation)
            from .e1_eval import afford_elixir
            info["el_afford"] = int(max(0.0, afford_elixir([me], side, int(raw_tick), int(self.afford_ticks)) - spent))
        if pend:
            info["pending"] = True                          # decision_options / live_gen_v2: pending-only rules
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
        allowed = allowed_slots(np.array([h[0] > 0 for h in info["hand"]]), info["costs"],
                                info.get("el_afford", info["el_int"]))
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
        ents = list(frame.get("entities", []))
        for q in self._pending_in_hand(me) if getattr(self, "pending_plays", None) else []:
            # --pipeline-decisions: a pending building occupies its tapped tile as the game snaps it (3x3: tile centre, 2x2:
            # tile corner) -- legal_cells reads that position parity; a pending troop / spell blocks nothing
            snap = round if q["name"] in EVEN_BUILDINGS else (lambda v: math.floor(v) + 0.5)
            x, y = snap(q["xy"][0] * 18) * 1000, snap((1 - q["xy"][1]) * 32) * 1000
            x, y = (18000 - x, 32000 - y) if side == 1 else (x, y)
            ents.append(dict(side=side, x=x, y=y, card_id=me["deck_card_ids"][q["deck_index"]], kind=12, hp=1))
        ok = legal_cells(ents, side, me["deck_card_ids"][d["deck_index"]], d["name"], self.grid)
        if ok is None:
            return logits
        ok = torch.from_numpy(ok).to(logits.device)
        raw = int(logits.reshape(-1, ok.numel())[0].argmax())
        if not ok[raw]:
            d["xy_unguarded"] = cell_xy(raw, self.grid)
        return logits.masked_fill(~ok, float("-inf"))
