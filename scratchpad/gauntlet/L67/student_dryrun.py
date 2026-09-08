"""L67d dry run: the live student adapter on REAL recorded frames, with NO game and NO clicks.

Runs the real detector over a recorded session's video, assembles the same LiveReads play.py would
(elixir / hand / next / tower HP from the same readers), and asks `StudentPolicy.decide` for a decision on
every sampled frame. Nothing is tapped: the harness only records what the student WOULD do, plus latency.

This is the closest thing to a live test that costs no ladder trophies, and it is the first time the student
has ever seen real detector output (training and every bench number so far are engine states).

usage:
  python scratchpad/gauntlet/L67/student_dryrun.py <session_dir> --ckpt <s1 ckpt> --out <jsonl> [--every 15] [--limit 200]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("session", type=Path)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--deck", default="icebow")
    ap.add_argument("--every", type=int, default=15, help="sample every Nth frame")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--gate-tau", type=float, default=0.5)
    a = ap.parse_args()

    import cv2
    from clashrl.actions import ActionSpace
    from clashrl.config import Config
    from clashrl.replay_mine import load_detector
    from clashrl.student_live import StudentPolicy, live_reads
    from clashrl.vision import Vision

    cfg = Config.load()
    vision = Vision(cfg)
    actions = ActionSpace(cfg)
    det = load_detector(cfg)
    if not det.available:
        raise SystemExit("detector weights not found -- the dry run needs the real detector")
    pol = StudentPolicy(a.ckpt, a.deck, actions, gate_tau=a.gate_tau)
    deck_keys = list(vision.deck_keys)

    cap = cv2.VideoCapture(str(a.session / "video.mp4"))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {a.session / 'video.mp4'}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 12.0)
    conf = float(cfg.get("observation", "detector_conf", default=0.75))   # the live value play.py uses

    rows, fi, used = [], -1, 0
    t_all = time.perf_counter()
    while used < a.limit:
        ok, frame = cap.read()
        if not ok:
            break
        fi += 1
        if fi % a.every:
            continue
        t0 = time.perf_counter()
        dets = det.detect(frame, conf=conf)
        t_det = (time.perf_counter() - t0) * 1e3
        hand_ids = list(vision.recognize_hand(frame))
        elixir = float(vision.read_elixir(frame))
        nxt = vision.recognize_next(frame)
        next_name = deck_keys[nxt] if isinstance(nxt, int) and 0 <= nxt < len(deck_keys) else None
        reads = live_reads(elixir=elixir, hand_ids=hand_ids, deck_keys=deck_keys, next_name=next_name,
                           hp_tracker=_NullHp(), tower_tracker=_NullTowers(), t_sec=fi / max(fps, 1e-6))
        act = pol.decide(dets, reads, hand_ids, deck_keys)
        r = {"frame": fi, "t_sec": round(fi / max(fps, 1e-6), 2), "n_det": len(dets),
             "hand_ids": [int(h) for h in hand_ids], "elixir": elixir, "det_ms": round(t_det, 1),
             "decision": None if act is None else {"card_id": act[0], "cell": act[1], "p_play": round(act[2], 4)},
             **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in pol.last.items()}}
        rows.append(r)
        used += 1
    cap.release()

    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as h:
        for r in rows:
            h.write(json.dumps(r) + "\n")
    played = [r for r in rows if r["decision"]]
    ms = [r["ms"] for r in rows if "ms" in r]
    summary = {"session": a.session.name, "ckpt": str(a.ckpt), "frames_scored": len(rows),
               "plays": len(played), "play_rate": round(len(played) / max(len(rows), 1), 3),
               "student_ms_median": round(float(np.median(ms)), 1) if ms else None,
               "student_ms_p95": round(float(np.percentile(ms, 95)), 1) if ms else None,
               "det_ms_median": round(float(np.median([r["det_ms"] for r in rows])), 1) if rows else None,
               "p_play_median": round(float(np.median([r["p_play"] for r in rows if "p_play" in r])), 3) if rows else None,
               "distinct_cards": sorted({r["decision"]["card_id"] for r in played}),
               "distinct_cells": len({r["decision"]["cell"] for r in played}),
               "no_mappable_card": pol.stats.get("no_mappable_card", 0),
               "units_median": float(np.median([r.get("units", 0) for r in rows])) if rows else None,
               "spells_seen": int(sum(r.get("spells", 0) for r in rows)),
               "wall_s": round(time.perf_counter() - t_all, 1)}
    print(json.dumps(summary))
    return 0


class _NullHp:
    """Tower-HP reader stand-in: the digit CNN needs its own trackers stepped over a live match; the dry run
    is about the ADAPTER and the detector, so tower HP reads as unknown (hp_known=0) here. That is the same
    state the live path reports before the first successful digit read."""
    my_hp: list = []
    enemy_hp: list = []
    my_full = 0
    full = 0


class _NullTowers:
    mine_alive = [True, True, True]
    enemy_alive = [True, True, True]


if __name__ == "__main__":
    raise SystemExit(main())
