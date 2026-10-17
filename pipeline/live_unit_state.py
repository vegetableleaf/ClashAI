"""LIVE twin of ``pipeline.sim_unit_state.extract`` for the step-c cue inputs (scratchpad/gauntlet/L74/cues/STEP_C_SPEC.md
section 6, mapping rules measured in scratchpad/gauntlet/L74/parity/S6_CUES_1016.md).

    cues = LiveCues()                                     # the SIM's own card table, sha-checked
    rows, log = cues.rows(frame, prev, tok, mask, side)   # [len(tok), CUE_N] float32 = the model's b["cue"]

``frame`` = one merged-reader frame (the decision frame, BEFORE extrapolation: the SIM extracts the battle at the
decision tick and matches it to the extrapolated view, e1_eval.sim_cue_rows); ``prev`` = the reader frame before it
(None = unknown; only the charge rule reads it). Inputs are PUBLIC on-screen state only: each body's
behavior_state_raw, its phase-2 buffs and its phase-3 attack row (target generation, progress). Never the opponent's
hand / next card / elixir.

Shared with the training side, so the two cannot drift: the card table (sim_unit_state._tbl over the same 160402017
JSON the SIM embeds), the buff classes (sim_unit_state._statuses), the slow_frac total (max of remaining, this match's
memo, the table duration: extract's formula), the 22-float layout (model_gen.cue_vector), the token match radius
(e1_eval.CUE_MATCH_TILES) and the hit-speed source (the table's hit_speed_ms, as extract). Live-only rules (S6, then
swept on 413k paired live/SIM body-frames, scratchpad/gauntlet/L74/cues/STEP_C_SPEC.md section 6): state from behavior_state_raw
(raw 'engaged' with no acquired target -> moving / idle, extract's definition), charging from 2-frame speed on charger
cards, Tesla hide from raw 0/2, a far target dropped (edge distance > max(sight, range) + 1.5 tiles; a unit with no
attack holds none), shield-hp cards shielded while hp == max hp (the stream has no shield hp).
A degraded frame (cues_degraded, an invalid block, no blocks at all) -> every row 0 (cue_known 0), never stale cues.
"""
from __future__ import annotations

import hashlib
import math
import sys
import types
from pathlib import Path

import numpy as np

from .e1_eval import CUE_MATCH_TILES
from .model_gen import CUE_N, cue_vector
from .sim_unit_state import SENTINEL_MS, _statuses, _tbl

REPO = Path(__file__).resolve().parents[1]
# The SIM's embedded table (royalesim 0.1.35 EMBEDDED_CARDS_160402017_JSON) is byte-identical to this RoyaleSim data file
# (sha below, checked 10-17). The live venv has no royalesim, so live reads a local copy (git-ignored icebow/data); a
# changed or missing file refuses (restore: copy research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json).
TABLE_PATH = REPO / "icebow/data/cue_table/cards-160402017-20261006.json"
TABLE_SHA256 = "babaa3d129e370c5838f12001683e2a5579dbaec581fd94968e689aacfc3fb60"
HIT_WINDOW_MS = 100       # the live 2-tick sampling; the SIM side is extracted with hit_window_ms=100 too
SIGHT_SLACK_MT = 1500     # S6: a target farther than max(sight, range) + 1.5 tiles is a path / default target, not acquired
CHARGE_SPEED = 1.6        # S6 / READER_VALIDATION_1016: charged = >= 1.6 x walk over two frames (table speed 60 = 59 mt/tick)
STATE = {0: "idle", 1: "moving", 2: "engaged", 3: "jumping", 4: "deploying", 5: "jumping", 6: "tunnelling",
         10: "casting", 11: "deploying"}     # READER_STREAM_SPEC section 5; any other raw value -> 'idle'
TOWER_KINDS = (12, 13)    # live_mem KING_KIND, PRINCESS_KIND (crown towers carry card_id -1)


def load_table(path: Path = TABLE_PATH) -> dict:
    """sim_unit_state._tbl of the 160402017 table: the running royalesim's embedded copy when it is imported (pods),
    else ``path``; either way it must hash to TABLE_SHA256."""
    sim = sys.modules.get("royalesim")
    text = getattr(sim, "EMBEDDED_CARDS_160402017_JSON", None)
    if text is None:
        if not path.is_file():
            raise FileNotFoundError(f"cue table {path} missing (copy research/ext/Royale/RoyaleSim/data/derived/"
                                    f"cards-160402017-20261006.json there)")
        text = path.read_text(encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if sha != TABLE_SHA256:
        raise ValueError(f"cue table sha256 {sha} != {TABLE_SHA256} (the table the cue models trained on)")
    return _tbl(types.SimpleNamespace(EMBEDDED_CARDS_160402017_JSON=text))


def align(tok: np.ndarray, mask: np.ndarray, side: int, bodies: list) -> np.ndarray:
    """e1_eval.sim_cue_rows' token match, verbatim: ``bodies`` = [(team, x tiles, y tiles, cue floats)] in engine
    coordinates; unit tokens (mask, not a spell, side mine / enemy) take the nearest same-side body in this side's board
    frame, pairs nearest-first, one body per token, within CUE_MATCH_TILES. Unmatched tokens / spells / pads stay 0."""
    out = np.zeros((len(tok), CUE_N), np.float32)
    ti = np.flatnonzero(mask & (tok[:, 13] == 0) & ((tok[:, 1] > 0) | (tok[:, 2] > 0)))
    if not len(ti) or not bodies:
        return out
    bx = np.array([b[1] / 18.0 for b in bodies])
    by = np.array([1.0 - b[2] / 32.0 for b in bodies])
    if side == 1:                                             # obs_contract._engine_xy: side 1 sees the board mirrored
        bx, by = 1.0 - bx, 1.0 - by
    mine = np.array([b[0] == side for b in bodies])
    d = np.hypot((tok[ti, 4:5] - bx) * 18.0, (tok[ti, 5:6] - by) * 32.0)
    d[(tok[ti, 1:2] > 0) != mine] = np.inf
    while True:
        i, j = np.unravel_index(np.argmin(d), d.shape)
        if not d[i, j] <= CUE_MATCH_TILES:
            return out
        out[ti[i]] = bodies[j][3]
        d[i, :] = np.inf
        d[:, j] = np.inf


class LiveCues:
    """Per-pilot cue builder: the table, the reader's attack definitions seen so far (sight / range fallback for names
    the table lacks), and this match's buff-total memo (reset() between matches; a game tick going backwards also
    clears it, as GenPilot.observe clears its frames)."""

    def __init__(self, table: dict | None = None):
        self.T = table if table is not None else load_table()
        self.defs: dict = {}
        self.memo: dict = {}
        self.last_tick = -1

    def reset(self) -> None:
        self.memo.clear()
        self.last_tick = -1

    def observe(self, frame: dict) -> None:
        """Keep the merged reader's per-card definitions (emitted once per reader process, any frame)."""
        for d in (frame.get("phase3") or {}).get("defs") or ():
            self.defs[d["definition_id"]] = d

    @staticmethod
    def usable(frame: dict) -> bool:
        p2, p3 = frame.get("phase2"), frame.get("phase3")
        return bool(not frame.get("cues_degraded") and p2 and p3 and p2.get("valid") and p3.get("valid"))

    def units(self, frame: dict, prev: dict | None = None) -> list | None:
        """The frame's bodies in extract's schema (the fields cue_vector reads, + generation / tower / target_is_tower);
        None for a degraded frame."""
        if not self.usable(frame):
            return None
        self.observe(frame)
        tick = int(frame["game_tick"])
        if tick < self.last_tick:                             # a new match without reset(): generation ids restart
            self.memo.clear()
        self.last_tick = tick
        ents = list(frame.get("entities") or ())
        p2 = {u["generation"]: u for u in frame["phase2"].get("units") or ()}
        p3 = {b["generation"]: b for b in frame["phase3"].get("bodies") or ()}
        by_gen = {e.get("category"): e for e in ents}
        towers = {e.get("category") for e in ents if int(e["card_id"]) < 0 and e["kind"] in TOWER_KINDS}
        before, dt = {}, 0
        if prev is not None:
            dt = tick - int(prev["game_tick"])
            before = {e.get("category"): e for e in prev.get("entities") or ()}
        out = []
        for e in ents:
            g = e.get("category")
            u2, u3 = p2.get(g) or {}, p3.get(g) or {}
            name = u2.get("name")
            ct = self.T["char"].get(name) or {}
            raw = e.get("behavior_state_raw")
            hide = None
            if ct.get("hides_when_not_attacking"):
                hide = {0: "hidden", 2: "up"}.get(raw)
            charging = False
            b0 = before.get(g)
            if ct.get("charge") and ct.get("speed") and raw == 1 and b0 is not None and 0 < dt <= 4:
                v = math.hypot(e["x"] - b0["x"], e["y"] - b0["y"]) / dt
                charging = v >= CHARGE_SPEED * ct["speed"] * 59 / 60
            att = u3.get("attack")
            tgt = att.get("target_gen") if att else None
            if tgt is not None and ct and not (ct.get("range_milli") or ct.get("sight_range_milli")):
                tgt = None                                    # a unit with no attack (Tombstone...) acquires nothing
            elif tgt is not None and tgt in by_gen:           # drop a far default / path target (S6; edge distance)
                dd = self.defs.get(u3.get("definition_id")) or {}
                reach = max(ct.get("sight_range_milli") or dd.get("SightRange") or 0,
                            ct.get("range_milli") or dd.get("Range") or 0)
                tb = by_gen[tgt]
                edge = (math.hypot(e["x"] - tb["x"], e["y"] - tb["y"]) - (ct.get("collision_radius_milli") or 0)
                        - ((self.T["char"].get((p2.get(tgt) or {}).get("name")) or {}).get("collision_radius_milli") or 0))
                if reach and edge > reach + SIGHT_SLACK_MT:
                    tgt = None
            state = STATE.get(raw, "idle")
            if state == "engaged" and tgt is None:            # extract: engaged = has a target and the attack cycle runs
                state = "moving" if ct.get("kind") == "troop" and (ct.get("speed") or 0) > 0 else "idle"
            prog = (att.get("progress_raw") or 0) if att else 0   # attack null = no component (deploying / frozen)
            hs = ct.get("hit_speed_ms")                       # extract's source: the table (not the device defs)
            if tgt is None or prog <= 0:
                phase = "idle"
            else:
                phase = "hit" if hs and prog % hs < HIT_WINDOW_MS else "windup"
            status = dict.fromkeys(("frozen", "slowed", "raged", "invisible", "shielded"), False)
            slow_frac = None
            for bu in u2.get("buffs") or ():
                bn, ms, cfg = bu["name"], bu["remaining_ms_raw"], bu.get("config")
                rows = ({bn: {"speed_multiplier_raw": cfg.get("SpeedMultiplier"),
                              "hit_speed_multiplier_raw": cfg.get("HitSpeedMultiplier")}} if cfg else self.T["buffs"])
                tags = _statuses(bn, rows)                    # the SIM's rule, on the live buff's own multipliers
                if cfg and cfg.get("Invisible"):
                    tags.add("invisible")
                if (cfg and cfg.get("Shield")) or bu.get("shield_value_raw"):
                    tags.add("shielded")
                frac = None
                if ms < SENTINEL_MS:                          # extract's total: max(remaining, memo, table duration)
                    total = self.memo[g, bn] = max(ms, self.memo.get((g, bn), 0), self.T["totals"].get(bn, 0))
                    frac = round(ms / total, 3) if total else None
                for tag in tags:
                    if tag in status:
                        status[tag] = True
                    if tag == "slowed" and frac is not None:
                        slow_frac = max(slow_frac or 0, frac)
            if (ct.get("shield_hitpoints") or 0) > 0 and 0 < e["max_hp"] <= e["hp"]:
                status["shielded"] = True                     # shield hp is not in the stream: intact body = shield up
            status["slow_frac"] = slow_frac
            out.append(dict(generation=g, team=int(e["side"]), x=e["x"] / 1000.0, y=e["y"] / 1000.0, name=name,
                            tower=g in towers, state=state, charging=charging, hide=hide, status=status,
                            target_is_tower=tgt in towers,
                            attack=dict(target=tgt, phase=phase, progress_ms=prog,
                                        frac=round(prog % hs / hs, 3) if hs and phase != "idle" else None)))
        return out

    def rows(self, frame: dict, prev: dict | None, tok: np.ndarray, mask: np.ndarray, side: int):
        """-> (rows [len(tok), CUE_N] float32 aligned to the tokens, log dict for the decision event). A malformed cue
        block never stops a live match: that frame reads 'no cue' (all 0) and the log names the error."""
        try:
            us = self.units(frame, prev)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            return np.zeros((len(tok), CUE_N), np.float32), dict(degraded=True, error=repr(exc)[:200])
        if us is None:
            return np.zeros((len(tok), CUE_N), np.float32), dict(degraded=True)
        bodies = [(u["team"], u["x"], u["y"], cue_vector(u, u["target_is_tower"])) for u in us if not u["tower"]]
        out = align(tok, mask, side, bodies)
        known = out[:, 0] > 0
        return out, dict(degraded=False, bodies=len(bodies), known=int(known.sum()),
                         nz=[int(v) for v in (out[known] != 0).sum(0)])
