"""LOOP-REC: the fast loop's per-match trajectory record, its codec, and the spool the learner reads it from.

A record is ONE learner match as rl_royale's learner consumes it: the result dict an rl_royale actor puts on its queue
(``e1_eval`` ``Match.result`` / ``SelfPlayMatch.result`` with ``cfg["record"]``), cut to the fields below, plus ``wver``.
``to_result`` gives back the dict ``rl_royale.collate`` / ``Learner.one_update`` take; ``from_result`` makes a record
from an rl_royale result (the converter test: scratchpad/gauntlet/L74/plan1026/pilot/lrn/rec_identity.py).

Record (a dict; ``REC_V`` = 1):
  v            1
  wver         int64 [n]   the policy version (weights push V) that produced decision row i's log-probs (LOOP-SRV)
  traj         dict of numpy arrays, row i = the learner's i-th decision, n rows each, ``e1_eval.Match._traj_arrays``
               dtypes. Always:
                 tok f32 [n, 64, F] / mask bool [n, 64] / sc f32 [n, S] / past f32 [n, K, 5]   model inputs
                 allowed bool [n, 8]   card slots the sampler could pick (afford mask applied)
                 gate_sampled bool, played bool, slot int64, cell int64, stalled bool
                 lp_gate / lp_card / lp_cell f64   the behaviour log-probs of the action taken, EXACTLY as
                     rl_royale.policy_terms recomputes them: gate log sigmoid(+-(z - logit(tau_row)) / T_gate) on
                     gate-sampled rows (0 otherwise), card log softmax over allowed (masked logits / T), cell log softmax
                     over 2,304 / T for the slot's card on played rows (0 otherwise); the stored lp_old = their sum
                 p_gate f64 (rollout_monitors), T f64
               GenModel rows: + e1_eval.GEN_IDENT_KEYS (int64), GEN_V3_KEYS, GEN_V31_KEYS, GEN_CUE_KEYS as the model takes
               them (e1_eval.gen_row_keys). Per config feature: tick int64 (gae_gamma_unit tick, shaping, spell, crown,
               habit), mem_t int64 (memory model), phi_state f64 [n, D] (shaping: reward_shaping.phi_record /
               state_record of the mode), gate_tau f64 (tau_phase), ab_sampled / ab_press bool, ab_lp f64, ab_feat f32
               [n, A], ab_cand bool, ab_q f64 (ability_head), ctx int64 [n, 5] (critic_ctx / posture), elixir f64
               (kl_ref_gate_max_elixir), posture / posture_dtau / posture_lp / posture_new (posture_head), forced bool.
  memory       match_memory table (memory model): the match's event table, ``MatchMemory.table``
  scalars      entry_index, k, tag, side, outcome ("win" / "loss" / "draw", the learner's own), end_tick, seconds
  monitors     plays_attempted, plays_accepted, card_mix_attempted, refuse_reasons, play_elixir, stall_fired,
               p_gate_mean, ghost_delivered, ghost_refused, ghost_undelivered, won_after_script (0 / False in self-play)
  per config   plays (spell / crown), spell, crown, habit, cf, pipeline_decisions, wall_s, ability_presses (ability_head),
               league (the matchup spec: tag, opp {type, id}, learner_bucket, deck names, learner_side, seed),
               opp_side {plays_attempted, ...}, opp_style (opp_style on)
Fields outside TOP_KEYS (wall clocks, diagnostics) are not part of the record; collate and every monitor and guard the
learner computes are byte-identical without them (rec_identity.py).

Codec: pickle protocol 5 of the record (trusted, same-pod processes; numpy arrays travel as raw buffers).
Spool: one file per finished match in a directory (default /dev/shm/loop/spool), written ``*.tmp`` then os.replace'd to
``{finish ns:020d}_{pid}_{seq:08d}_w{min wver}-{max wver}.rec``, so the learner sees only whole records and knows each
record's staleness from its name alone (``take``).
"""
from __future__ import annotations

import itertools
import os
import pickle
import time
from pathlib import Path
from typing import Optional

import numpy as np

REC_V = 1
TOP_KEYS = ("entry_index", "k", "tag", "side", "outcome", "end_tick", "seconds", "traj", "memory",
            "plays_attempted", "plays_accepted", "card_mix_attempted", "refuse_reasons", "play_elixir", "stall_fired",
            "p_gate_mean", "ghost_delivered", "ghost_refused", "ghost_undelivered", "won_after_script",
            "plays", "spell", "crown", "habit", "cf", "pipeline_decisions", "wall_s", "ability_presses",
            "league", "opp_side", "opp_style")
REQUIRED = ("entry_index", "k", "side", "outcome", "end_tick", "seconds", "traj", "plays_attempted", "plays_accepted",
            "card_mix_attempted", "refuse_reasons", "play_elixir", "stall_fired", "ghost_delivered", "ghost_refused",
            "ghost_undelivered", "won_after_script")
TRAJ_REQUIRED = ("tok", "mask", "sc", "past", "allowed", "gate_sampled", "played", "slot", "cell", "stalled",
                 "lp_gate", "lp_card", "lp_cell", "p_gate")
_seq = itertools.count()


def check(rec: dict) -> dict:
    """ValueError naming the first problem; the record itself when it is well formed."""
    if rec.get("v") != REC_V:
        raise ValueError(f"record version {rec.get('v')!r} != {REC_V}")
    miss = [k for k in REQUIRED if k not in rec] + [f"traj.{k}" for k in TRAJ_REQUIRED if k not in rec["traj"]]
    if miss:
        raise ValueError(f"record without {miss}")
    if rec["outcome"] not in ("win", "loss", "draw"):
        raise ValueError(f"outcome {rec['outcome']!r}")
    n = len(rec["wver"])
    bad = {k: len(v) for k, v in rec["traj"].items() if len(v) != n}
    if bad:
        raise ValueError(f"traj arrays with != {n} rows (len wver): {bad}")
    return rec


def from_result(result: dict, wver) -> dict:
    """An rl_royale actor result -> a record; ``wver`` = one version for every row (an int) or a per-row array."""
    n = len(result["traj"]["played"])
    w = np.full(n, int(wver), dtype=np.int64) if np.ndim(wver) == 0 else np.asarray(wver, dtype=np.int64)
    return check({"v": REC_V, "wver": w, **{k: result[k] for k in TOP_KEYS if k in result}})


def to_result(rec: dict) -> dict:
    """A record -> the result dict rl_royale.collate / Learner.one_update consume (the record minus v / wver)."""
    return {k: v for k, v in check(rec).items() if k not in ("v", "wver")}


def encode(rec: dict) -> bytes:
    return pickle.dumps(check(rec), protocol=5)


def decode(b: bytes) -> dict:
    return check(pickle.loads(b))


def put(spool: Path, rec: dict) -> Path:
    """Producer side: one finished match -> one spool file (atomic)."""
    w = rec["wver"]
    lo, hi = (int(w.min()), int(w.max())) if len(w) else (-1, -1)
    name = f"{time.time_ns():020d}_{os.getpid()}_{next(_seq):08d}_w{lo}-{hi}.rec"
    tmp = Path(spool) / (name + ".tmp")
    tmp.write_bytes(encode(rec))
    os.replace(tmp, Path(spool) / name)
    return Path(spool) / name


def _min_wver(p: Path) -> int:
    return int(p.stem.rsplit("_w", 1)[1].split("-")[0])


def take(spool: Path, n: int, min_wver: int, stop: Optional[Path] = None, poll_s: float = 0.2) -> tuple[list, dict]:
    """Learner side: the NEWEST ``n`` records whose every row is at least version ``min_wver`` (staleness <= current -
    min_wver), oldest first; records below it are deleted unread (counted), taken ones are read then deleted, newer
    valid ones beyond ``n`` stay for the next call. Waits (polling) until ``n`` are there; ``stop`` file -> SystemExit.
    Newest-by-finish-time = a time-window sample of finished matches (no match-length bias at a version flip)."""
    t0, stale = time.perf_counter(), 0
    while True:
        files = sorted(Path(spool).glob("*.rec"))
        old = [p for p in files if _min_wver(p) < min_wver]
        for p in old:
            p.unlink(missing_ok=True)
        stale += len(old)
        ok = [p for p in files if _min_wver(p) >= min_wver]
        if len(ok) >= n:
            break
        if stop is not None and Path(stop).exists():
            raise SystemExit(f"STOP file {stop} while waiting for records ({len(ok)}/{n})")
        time.sleep(poll_s)
    pick = ok[-n:]
    recs = []
    for p in pick:
        recs.append(decode(p.read_bytes()))
        p.unlink()
    w = np.concatenate([r["wver"] for r in recs]) if recs else np.zeros(0, dtype=np.int64)
    return recs, {"taken": len(recs), "stale_deleted": stale, "left": len(ok) - n, "wait_s": time.perf_counter() - t0,
                  "wver_min": int(w.min()) if len(w) else None, "wver_max": int(w.max()) if len(w) else None,
                  "rows_at_min_wver_share": float((w == min_wver).mean()) if len(w) else None}
