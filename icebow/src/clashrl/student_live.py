"""L67d: the S1 student (pipeline/) as a live policy -- BoardState from the screen, (deck slot, half-tile cell) out.

The student was trained on ENGINE states (pipeline/dataset.py) and graded on pro agreement; this module is the
only thing standing between it and ``play.py``. It does NOT replace play's decision machinery: it returns a
(card_id, cell) in play.py's OWN conventions (live card ids, the 18x24 ``action.grid`` cell index), so the
affordability mask, ``deploy_clamp``, the aim assists and the tap path all still apply exactly as before.

Wiring is OFF unless ``play.student_ckpt`` is set in config (or --student on the CLI); with it unset, play.py
behaves exactly as it did before this file existed.

What is UNTESTED here and must not be reported as working (L67d):
  * ``degrade()`` is a MODEL of the detector shift, not the shift itself -- the student has never seen real
    detector output. Expect the -4.2 pp cell / -12.4 pp card of 5cs.95 A to be a LOWER bound on the live loss.
  * The gate threshold is the training decision boundary (0.5), not a tuned live number.
  * A live ``_evo`` unit token and any spell token are classes the training rows never contained (5cs.95 A).
"""
from __future__ import annotations

import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import vocab                                                     # noqa: E402
from pipeline.obs_contract import LiveReads, from_live, load_deck, to_tokens   # noqa: E402

PAST_K = 3


class StudentPolicy:
    """Loads an S1 checkpoint and answers ``decide(...)`` with (card_id, cell) in live conventions."""

    def __init__(self, ckpt_path: Path, deck_name: str, actions: Any, *, device: str = "cpu",
                 gate_tau: float = 0.5, fill_missing: bool = True) -> None:
        import torch
        from pipeline.model_v3 import GRID_X, S1Model, cell_xy, hand_mask_from_sc

        self._torch, self._cell_xy, self._hand_mask = torch, cell_xy, hand_mask_from_sc
        self.GRID_X = GRID_X
        self.dev = torch.device(device)
        st = torch.load(Path(ckpt_path), map_location=self.dev)
        args = dict(st.get("args", {}) or {})
        self.grid_kind = str(args.get("grid", "floor"))
        self.model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(self.dev)
        self.model.load_state_dict(st["model"])
        self.model.eval()
        self.deck = load_deck(deck_name)
        self.actions = actions
        self.gate_tau = float(gate_tau)
        # L67f: supplying a plausible value beats flagging it unknown -- MEASURED against pro labels on the
        # v3 VAL (blank_both 18.78 exact cell / 52.11 card -> fill_both 20.15 / 63.25). The live path has no
        # unit HP at all, so every unit is sent at full health; play.py supplies the real opponent-elixir
        # estimate and the king's alive-proxy through LiveReads.
        self.fill_missing = bool(fill_missing)
        self.ckpt = str(ckpt_path)
        self.epoch = st.get("epoch")
        self._past: deque = deque(maxlen=PAST_K)          # (deck_slot, board_x, board_y, t_wall)
        self.stats: dict[str, int] = {}
        self.last: dict[str, Any] = {}

    # -- state ---------------------------------------------------------------------------------------
    def record_play(self, card_id: int, board_xy: tuple[float, float], deck_keys: Sequence[str]) -> None:
        """Call after a tap so ``past`` matches the dataset's own 'my last 3 accepted plays'."""
        slot = self.deck.slot_of(_key_of(card_id, deck_keys))
        if slot >= 0:
            self._past.append((slot, float(board_xy[0]), float(board_xy[1]), time.time()))

    def _past_array(self, now: float) -> np.ndarray:
        p = np.full((PAST_K, 4), -1.0, dtype=np.float32)
        for k, (slot, x, y, t0) in enumerate(list(self._past)[::-1][:PAST_K]):
            p[k] = (float(slot), float(x), float(y), float(now - t0))
        return p

    # -- decision ------------------------------------------------------------------------------------
    def decide(self, detections: Sequence[Any], reads: LiveReads, hand_ids: Sequence[int],
               deck_keys: Sequence[str]) -> Optional[tuple[int, int, float]]:
        """-> (live card_id, live cell index, p_play), or None when the gate says WAIT / nothing maps."""
        torch = self._torch
        t0 = time.perf_counter()
        bs = from_live(detections, reads, self.deck, warp=self.actions.warp,
                       unit_hp_default=(1.0 if self.fill_missing else None))
        tok, mask, sc = to_tokens(bs)
        past = self._past_array(time.time())
        tt = torch.from_numpy(np.asarray(tok)[None]).to(self.dev)
        mm = torch.from_numpy(np.asarray(mask)[None]).to(self.dev)
        ss = torch.from_numpy(np.asarray(sc)[None]).to(self.dev)
        pp = torch.from_numpy(past[None]).to(self.dev)
        with torch.no_grad():
            # encode ONCE: the cell head is card-conditioned, so a naive forward() then a second
            # forward(card_slot=...) would run the whole encoder twice on every live frame.
            enc = self.model.encode(tt, mm, ss, pp)
            out = self.model.heads(enc, self._hand_mask(ss))
            p_play = float(torch.sigmoid(out["gate"][0]).item())
            # only slots that are BOTH in the student's hand view and readable in the live tray
            card_logits = out["card"][0].clone()
            live_ok = torch.zeros_like(card_logits, dtype=torch.bool)
            for s in range(int(card_logits.shape[0])):
                if _tray_id_for_slot(self.deck.cards[s], hand_ids, deck_keys) is not None:
                    live_ok[s] = True
            if not bool(live_ok.any()):
                # L67g: record the read BEFORE returning. This branch used to leave ``self.last`` holding the
                # previous decision, so play.py's WAIT line printed a STALE p and a run of tray-read failures
                # was indistinguishable from a run of genuine low-gate waits -- which is exactly the evidence
                # needed to read a live freeze.
                self.stats["no_mappable_card"] = self.stats.get("no_mappable_card", 0) + 1
                self.last = {"p_play": p_play, "deck_slot": -1, "student_cell": None, "board_xy": (0.0, 0.0),
                             "live_cell": None, "card_id": None, "no_mappable_card": True,
                             "ms": (time.perf_counter() - t0) * 1e3, "units": len(bs.units),
                             "spells": len(bs.spells)}
                return None
            card_logits = card_logits.masked_fill(~live_ok, float("-inf"))
            slot = int(card_logits.argmax().item())
            # the cell head is CARD-CONDITIONED (model_v3.cell_logits): read it on the chosen slot,
            # the same conditioning train_s1.evaluate teacher-forces on the true card.
            cell = int(self.model.cell_logits(enc, torch.tensor([slot], device=self.dev))[0].argmax().item())
        bx, by = self._cell_xy(cell, self.grid_kind)                # board frame, [0,1]
        nx, ny = self.actions.warp.board_to_frame(float(bx), float(by))
        live_cell = int(self.actions.cell_at(float(nx), float(ny)))
        card_id = _tray_id_for_slot(self.deck.cards[slot], hand_ids, deck_keys)
        self.last = {"p_play": p_play, "deck_slot": slot, "student_cell": cell,
                     "board_xy": (float(bx), float(by)), "live_cell": live_cell, "card_id": card_id,
                     "ms": (time.perf_counter() - t0) * 1e3, "units": len(bs.units), "spells": len(bs.spells)}
        self.stats["decisions"] = self.stats.get("decisions", 0) + 1
        if p_play <= self.gate_tau:
            self.stats["wait"] = self.stats.get("wait", 0) + 1
            return None
        return int(card_id), live_cell, p_play


def _key_of(card_id: int, deck_keys: Sequence[str]) -> Optional[str]:
    return str(deck_keys[int(card_id)]) if 0 <= int(card_id) < len(deck_keys) else None


def _tray_id_for_slot(deck_card: str, hand_ids: Sequence[int], deck_keys: Sequence[str]) -> Optional[int]:
    """The live card id currently in the tray for a student deck slot.

    The student's deck has 8 BASE slots; the live identity list has 10 (an evolved slot carries a second
    ``<key>_evo`` identity, cards.py:499-505), so this matches on the base key and returns whichever of the
    two the tray is actually showing."""
    want = vocab.base_key(str(deck_card))
    for cid in hand_ids:
        if int(cid) < 0:
            continue
        k = _key_of(int(cid), deck_keys)
        if k and vocab.base_key(k) == want:
            return int(cid)
    return None


def live_reads(*, elixir: float, hand_ids: Sequence[int], deck_keys: Sequence[str], next_name: Optional[str],
               hp_tracker: Any, tower_tracker: Any, t_sec: float, t_source: str = "clock",
               opp_elixir: Optional[float] = None, fill_king_hp: bool = True) -> LiveReads:
    """Assemble the contract's scalars from play.py's own readers.

    Tower order is the CONTRACT's (my king, my L, my R, opp king, opp L, opp R) -- NOT play.py's
    ``_tower_frac`` order (L, R, king per side). The king's HP is never printed on screen, so its fraction
    stays None (hp_known=0) and only its alive flag is real."""
    my_alive = list(getattr(tower_tracker, "mine_alive", []) or [])
    en_alive = list(getattr(tower_tracker, "enemy_alive", []) or [])
    my_full = float(getattr(hp_tracker, "my_full", 0) or 0) or 1.0
    en_full = float(getattr(hp_tracker, "full", 0) or 0) or 1.0
    my_hp = list(getattr(hp_tracker, "my_hp", []) or [])
    en_hp = list(getattr(hp_tracker, "enemy_hp", []) or [])

    def frac(hp: list, full: float, i: int) -> Optional[float]:
        if i >= len(hp) or hp[i] is None:
            return None
        return min(1.0, max(0.0, float(hp[i]) / full))

    def alive(flags: list, i: int) -> bool:
        return bool(flags[i]) if i < len(flags) else True

    # The king's HP is never printed on screen. `fill_king_hp` sends the alive-proxy (undamaged while alive,
    # play.py's own `_tower_frac` convention) instead of None -- measured better than the unknown flag (L67f).
    king = 1.0 if fill_king_hp else None
    tower_hp = (king, frac(my_hp, my_full, 0), frac(my_hp, my_full, 1),
                king, frac(en_hp, en_full, 0), frac(en_hp, en_full, 1))
    tower_alive = (alive(my_alive, 2), alive(my_alive, 0), alive(my_alive, 1),
                   alive(en_alive, 2), alive(en_alive, 0), alive(en_alive, 1))
    names = tuple((_key_of(int(c), deck_keys) if int(c) >= 0 else None) for c in list(hand_ids)[:4])
    while len(names) < 4:
        names = names + (None,)
    return LiveReads(elixir_int=int(round(float(elixir))), hand_names=names, next_name=next_name,
                     tower_hp=tower_hp, t_sec=float(t_sec), t_source=str(t_source), tower_alive=tower_alive,
                     opp_elixir=(None if opp_elixir is None else float(opp_elixir)))
