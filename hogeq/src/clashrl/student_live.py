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
                 gate_tau: float = 0.5, fill_missing: bool = True,
                 stall_elixir: Optional[float] = None, stall_seconds: float = 12.0) -> None:
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
        # (deck_slot, board_x, board_y, t_wall). Longer than PAST_K (_past_array takes the newest PAST_K) so that
        # dropping a phantom entry under the cycle rule (record_play) does not also drop a real older play.
        self._past: deque = deque(maxlen=PAST_HISTORY)
        self._plays_match = 0
        self.stats: dict[str, int] = {}
        # ANTI-STALL (L67k). When elixir sits at cap and nothing has been played for `stall_seconds`, take the
        # top AFFORDABLE candidate regardless of the gate. It never overrides a gate that already wants to
        # play, and it cannot pick an unaffordable card.
        #   WHY, measured: in the states the live bot freezes in, PROS play 23-36% of the time (units<=1 at
        #   8-10 elixir 0.230; 2-3 units 0.357) and overflowing at 10 elixir is strictly wasted resource.
        #   WHAT THE SIM SAYS, honestly: +0.245 +- 0.174 tower pooled over 24 matches on two disjoint seed
        #   slices (t=1.40, positive in all 6 arm/slice comparisons, NOT significant). And the sim barely
        #   tests it -- the sim actor plays ~50 times a match and stalls rarely, so the rule fired only ~1
        #   per match there. This is shipped on "does no harm in the sim + the live state is measurably one
        #   pros act in", NOT on a demonstrated win. play.stall_elixir: null disables it.
        self.stall_elixir = None if stall_elixir is None else float(stall_elixir)
        self.stall_seconds = float(stall_seconds)
        self._last_play_t: Optional[float] = None
        self.hand_memory = HandMemory()
        self.dump_low_gate = None      # set to a path to capture the freeze states (see CaptureBudget)
        self.capture = CaptureBudget()
        self._match_idx = 0
        self.last: dict[str, Any] = {}

    # -- state ---------------------------------------------------------------------------------------
    def reset_match(self) -> None:
        self.hand_memory.reset()
        # L67r F2: the anti-stall idle clock starts at MATCH START. It was None here, and the stall check counted idle
        # time from 0.0 -- so it fired the first time elixir read >= 9, one forced opening play per match at t 3-5 s
        # (22 of 75 captured stalls, HANDOFF 5cs.99 X), cutting the pro-like opening wait (pro first play median 12 s).
        self._last_play_t = time.time()
        self._plays_match = 0
        self.capture.reset_match()     # L67q: the capture budget is per match
        self._match_idx += 1
        """Forget the previous match's plays. `past` ages are WALL-CLOCK, so without this the first
        decisions of a new match carry entries from the last one, aged by however long the menus took --
        values training never contains (its max age is 95.5 s, median 8.55)."""
        self._past.clear()

    def record_play(self, card_id: int, board_xy: tuple[float, float], deck_keys: Sequence[str]) -> None:
        """Call after a tap so ``past`` matches the dataset's own 'my last 3 accepted plays'."""
        self._last_play_t = time.time()
        self._plays_match += 1
        slot = self.deck.slot_of(_key_of(card_id, deck_keys))
        if slot >= 0:
            # L67r F1: THE CYCLE RULE. A played card returns to hand only after 3 other plays, so the same card inside
            # the last 3 recorded plays means the OLDER record was a phantom (a tap that did not deploy, or a misread
            # tray). Training never contains such a history (0.000) and the gate collapses on it: 71.9% of captured
            # freeze states held one, and dropping the older copy lifted them 0.019 -> 0.497 (5cs.99 X).
            dropped = drop_cycle_repeats(self._past, slot)
            if dropped:
                self.stats["past_repeat_dropped"] = self.stats.get("past_repeat_dropped", 0) + dropped
            self._past.append((slot, float(board_xy[0]), float(board_xy[1]), time.time()))

    def _past_array(self, now: float) -> np.ndarray:
        p = np.full((PAST_K, 4), -1.0, dtype=np.float32)
        for k, (slot, x, y, t0) in enumerate(list(self._past)[::-1][:PAST_K]):
            p[k] = (float(slot), float(x), float(y), float(now - t0))
        return p

    # -- decision ------------------------------------------------------------------------------------
    def _stalled(self, elixir: float, now: float) -> bool:
        """Anti-stall trigger: elixir >= stall_elixir with no play for stall_seconds, timed from the last play or the
        match start (L67r F2). A caller that never signalled a match start gets its clock started here."""
        if self.stall_elixir is None or elixir < self.stall_elixir:
            return False
        if self._last_play_t is None:
            self._last_play_t = now
        return now - self._last_play_t >= self.stall_seconds

    def decide(self, detections: Sequence[Any], reads: LiveReads, hand_ids: Sequence[int],
               deck_keys: Sequence[str], card_elixir: Optional[Sequence[float]] = None
               ) -> Optional[tuple[int, int, float]]:
        """-> (live card_id, live cell index, p_play), or None when the gate says WAIT / nothing maps."""
        torch = self._torch
        t0 = time.perf_counter()
        bs = from_live(detections, reads, self.deck, warp=self.actions.warp,
                       unit_hp_default=(1.0 if self.fill_missing else None))
        # L67i: how often does the TRAY READER fail? An unreadable hand card becomes -1, which
        # obs_contract._slot_onehot encodes as bit 8 ("not in my deck") -- a bit set in 0.0009% of the
        # 339,192 training rows. The collapse frames captured live are full of them, but those frames were
        # SELECTED for low p, so the rate across all frames is what says whether it can explain the freeze.
        self.stats["frames"] = self.stats.get("frames", 0) + 1
        if any(int(c) < 0 for c in bs.my_hand):
            self.stats["hand_unmapped"] = self.stats.get("hand_unmapped", 0) + 1
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
                cid = _tray_id_for_slot(self.deck.cards[s], hand_ids, deck_keys)
                if cid is None:
                    continue
                # AFFORDABILITY BELONGS IN THE MASK, not in a veto after the fact. play.py used to check the
                # cost AFTER this returned and skip the whole decision when the argmax card was too
                # expensive -- so a frame that passed the gate produced NOTHING even when a cheaper card was
                # in hand. MEASURED on the owner's own runs: 11% / 6% / 20% of gate-passing decisions thrown
                # away that way (live_run3/5/6). The sim actor has always masked here, which is part of why
                # it plays 40-50 times a match.
                if card_elixir is not None:
                    cost = float(card_elixir[int(cid)]) if int(cid) < len(card_elixir) else 0.0
                    if cost > float(reads.elixir_int) + 1e-6:
                        continue
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
                     "ms": (time.perf_counter() - t0) * 1e3, "units": len(bs.units), "spells": len(bs.spells),
                     # L67i: the fields that are CONSTANT in every training row and can vary live. A gate that
                     # pins at p=0.00 in a state the engine says is worth 0.63 is being driven by one of
                     # these, and guessing which cost a whole session -- so the live log now carries them.
                     "digest": state_digest(bs)}
        self.stats["decisions"] = self.stats.get("decisions", 0) + 1
        stalled = self._stalled(float(reads.elixir_int), time.time())
        # L67q: CAPTURE THE FREEZE ITSELF for offline bisection -- the failing input, tokens and all. The L67i rule
        # (p < 0.02, first 60 per process) spent its whole budget in match 1 of the owner's 77-match run and caught
        # none of the late-game freezes (5cs.99 V). CaptureBudget picks anti-stall moments and late pinned waits,
        # budgeted per match. `dump_low_gate` None switches it off.
        if self.dump_low_gate is not None:
            why = self.capture.choose(p_play=p_play, gate_tau=self.gate_tau, stalled=stalled,
                                      elixir=float(reads.elixir_int), t_sec=float(bs.t_sec))
            if why is not None:
                try:
                    import json as _json
                    rec = {"why": why, "p": p_play, "t_sec": bs.t_sec, "elixir": float(reads.elixir_int),
                           "match": self._match_idx, "wall": time.time(),
                           "idle_s": (None if self._last_play_t is None else time.time() - self._last_play_t),
                           "plays_this_match": self._plays_match,
                           "deck_slot": slot, "student_cell": cell,
                           "tok": np.asarray(tok).tolist(), "mask": np.asarray(mask).tolist(),
                           "sc": np.asarray(sc).tolist(), "past": past.tolist(), "digest": self.last["digest"]}
                    with open(self.dump_low_gate, "a", encoding="utf-8") as fh:
                        fh.write(_json.dumps(rec) + chr(10))
                except Exception:
                    pass
        if p_play <= self.gate_tau and not stalled:
            self.stats["wait"] = self.stats.get("wait", 0) + 1
            return None
        if p_play <= self.gate_tau:
            self.stats["stall_fired"] = self.stats.get("stall_fired", 0) + 1
            self.last["stall"] = True
        return int(card_id), live_cell, p_play


PAST_HISTORY = 8      # plays kept internally; the model sees the newest PAST_K
CYCLE_GAP = 3         # a card cannot reappear within this many recorded plays (4 in hand, played card to queue back)


def drop_cycle_repeats(past: deque, slot: int, window: int = CYCLE_GAP) -> int:
    """Remove entries of ``slot`` among the newest ``window`` plays of ``past`` (in place); return how many.

    Called before appending a new play of ``slot``: under the card cycle those entries cannot have been real plays,
    while an older entry of the same card (a legal return after 3 other plays) is kept."""
    items = list(past)
    cut = max(0, len(items) - int(window))
    keep = items[:cut] + [e for e in items[cut:] if int(e[0]) != int(slot)]
    n = len(items) - len(keep)
    if n:
        past.clear()
        past.extend(keep)
    return n


class CaptureBudget:
    """Which live decisions are written to disk for offline freeze bisection (L67q).

    The L67i rule was "p < 0.02, the first 60 per process". MEASURED on the owner's 77-match run (5cs.99 V): all
    60 went to match 1 (the opening wait, low-elixir waits) and none of the late-game high-elixir freezes it was
    built for were captured. Now two reasons, each budgeted PER MATCH:
      stall      the anti-stall rule fired: the gate stayed <= tau for stall_seconds at >= stall_elixir -- the
                 freeze itself, at the moment it was overridden.
      pinned_hi  p < pinned_p at elixir >= pinned_elixir after the opening (t >= min_t_sec: pros' first play is at
                 a median 12.0 s, so earlier waits are normal), spaced min_gap_s apart.
    ~6 KB a record: a 77-match session at full budget is ~7 MB; session_cap bounds a runaway run.
    """

    def __init__(self, per_match_stall: int = 10, per_match_pinned: int = 6, session_cap: int = 2000,
                 pinned_p: float = 0.05, pinned_elixir: float = 8.0, min_t_sec: float = 20.0,
                 min_gap_s: float = 5.0):
        self.per_match = {"stall": int(per_match_stall), "pinned_hi": int(per_match_pinned)}
        self.session_cap = int(session_cap)
        self.pinned_p, self.pinned_elixir = float(pinned_p), float(pinned_elixir)
        self.min_t_sec, self.min_gap_s = float(min_t_sec), float(min_gap_s)
        self.total = 0
        self.reset_match()

    def reset_match(self) -> None:
        self.n = {"stall": 0, "pinned_hi": 0}
        self._last_pinned_t: Optional[float] = None

    def choose(self, *, p_play: float, gate_tau: float, stalled: bool, elixir: float, t_sec: float) -> Optional[str]:
        """The capture reason for this decision ("stall" / "pinned_hi"), or None. A returned reason is counted."""
        if self.total >= self.session_cap:
            return None
        why = None
        if stalled and p_play <= gate_tau:
            if self.n["stall"] < self.per_match["stall"]:
                why = "stall"
        elif (p_play < self.pinned_p and elixir >= self.pinned_elixir and t_sec >= self.min_t_sec
              and self.n["pinned_hi"] < self.per_match["pinned_hi"]
              and (self._last_pinned_t is None or t_sec - self._last_pinned_t >= self.min_gap_s)):
            why = "pinned_hi"
            self._last_pinned_t = t_sec
        if why is not None:
            self.n[why] += 1
            self.total += 1
        return why


class HandMemory:
    """Last confidently-read identity per tray slot, to fill the MODEL's hand during the cycle animation.

    MEASURED (L67j, `_tray_anim.py`, the bot's own footage): the tray reader fails on 48.4% of frames within
    0.5 s of a hand change and only 7.7% once the hand has been stable for 2 s. The failing crops are the
    slide animation -- a blend of the outgoing and incoming card -- which is why the best-scoring template is
    the RIGHT card only 20.6% of the time there, and why lowering `match_threshold` would be wrong 79% of the
    time. So the reader is behaving correctly; what is wrong is what we do with its -1.

    An unreadable slot currently reaches the model as bit 8 of the hand one-hot ("card not in my deck"), a bit
    set in 0.0009% of the 339,192 training rows. Filling it with the slot's last known card is a plausible
    in-distribution value, and supplying beats flagging on this model by measurement (5cs.98 E: blank_both
    18.78 exact cell / 52.11 card -> fill_both 20.15 / 63.25).

    TTL: 30 s, not 3 s. The dominant failure is not the 1-2 s cycle animation but the UNAFFORDABLE DIM --
    Clash renders a card you cannot afford desaturated toward grey, which mixes colour channels and so is NOT
    cancelled by the per-channel centring that makes template matching brightness-invariant (measured: the
    same card scores ~0.1-0.19 lower while unaffordable, and in the 22:51 run the failing scores sat at a
    median 0.49 against a 0.5 threshold). A card can stay unaffordable for tens of seconds, so a 3 s TTL
    expires mid-dim and the slot falls back to -1 exactly when elixir is low. Matching on luminance instead
    was tested and recovers only 3 of 53 failures, so it is not the answer. Holding the identity is: a dimmed
    card has not CHANGED, it is only drawn differently, and `invalidate()` drops the one slot that really did
    change.

    ⚠ This fills the MODEL'S VIEW ONLY. The tap path keeps the raw ids, so the bot still refuses to play a
    slot it cannot identify -- holding a stale identity there would tap a slot whose card has just changed,
    which is exactly the misplay the animation would cause.
    """

    def __init__(self, ttl_s: float = 30.0) -> None:
        self.ttl_s = float(ttl_s)
        self._slots: dict[int, tuple[int, float]] = {}
        self.filled = 0
        self.seen = 0

    def stabilize(self, hand_ids: Sequence[int], now: float) -> list[int]:
        out = []
        for si, cid in enumerate(list(hand_ids)[:4]):
            cid = int(cid)
            self.seen += 1
            if cid >= 0:
                self._slots[si] = (cid, float(now))
                out.append(cid)
                continue
            hit = self._slots.get(si)
            if hit is not None and float(now) - hit[1] <= self.ttl_s:
                self.filled += 1
                out.append(int(hit[0]))
            else:
                out.append(-1)
        return out

    def invalidate(self, slot_index: int) -> None:
        """Forget one slot -- call it when THAT slot's card is played, which is the only way its identity
        changes. With this, the TTL no longer has to be short: a slot that is merely unreadable (dimmed while
        unaffordable, or mid-animation) keeps its identity, while a slot that genuinely changed drops it."""
        self._slots.pop(int(slot_index), None)

    def reset(self) -> None:
        self._slots.clear()


def state_digest(bs) -> str:
    """One compact line of the live-only fields, for the WAIT log when the gate collapses."""
    tw = "".join(("-" if t.hp_frac is None else f"{t.hp_frac:.1f}") + ("" if t.alive else "x")
                 for t in bs.towers)
    return (f"exact={int(bs.my_elixir_exact)} opp={'?' if bs.opp_elixir is None else round(bs.opp_elixir, 1)} "
            f"next={bs.my_next} t={bs.t_sec:.0f}s hand={list(bs.my_hand)} tw={tw} "
            f"sp={len(bs.spells)} unk={sum(1 for u in bs.units if u.side < 0)}")


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
