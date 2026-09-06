"""S0 step 2b: own-click contract test, one session per process.

usage (from the repo root, icebow venv):
  python scratchpad/gauntlet/L63/s0/ownclick_run.py <project: icebow|hogeq> <session_dir> <out_json>

Per play (from label._extract_plays, NOT re-implemented): recover the BOARD-click time, run the deployed detector on
every frame in [t_click+0.25, t_click+1.5] (12 fps), build from_live BoardStates with board_warp(deck), warp the click
with the same frame_to_board, and find the nearest same-class (strict) / any-deck-class (fallback) unit on my/unknown side.
Also one pre-click frame (t_click-0.10) so a pre-existing same-class unit near the click can be flagged.
"""
from __future__ import annotations

import bisect
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\benpe\ClashBot")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))

from clashrl.config import Config                      # noqa: E402  (icebow's clashrl for BOTH projects)
from clashrl.label import _extract_plays, _load        # noqa: E402
from clashrl.replay_mine import load_detector          # noqa: E402
from clashrl.vision import Vision                      # noqa: E402
from clashrl import card_threat                        # noqa: E402
from pipeline import obs_contract as oc                # noqa: E402
from pipeline import vocab                             # noqa: E402

T0, T1, T_PRE = 0.25, 1.5, 0.10
FOUND_R_TILES = 3.0          # a candidate within this many tiles (euclidean, tile units) counts as the placed unit


def tile_err(ux, uy, cx, cy):
    return (ux - cx) * oc.TILES_X, (uy - cy) * oc.TILES_Y


def main(project: str, session: Path, out_json: Path):
    proj_root = REPO / project
    cfg = Config.load(proj_root / "config" / "config.yaml")
    cfg.root = proj_root                                    # templates/, config/cards.yaml, runs/ under the PROJECT
    cfg.data.setdefault("hand", {})["cache_diff"] = 0      # TRAP #3: wall-clock slot cache is wrong offline
    deck = oc.load_deck(project)
    warp = oc.board_warp(deck)
    deck_bases = {vocab.base_key(c) for c in deck.cards}

    meta, events, video = _load(session)
    region = meta["region"]
    frame_times = meta["frame_times"]
    left, top, w, h = region
    slots = cfg.get("hand", "slots", default=[])
    click_r = float(cfg.get("hand", "click_radius", default=0.06))
    pair_timeout = float(cfg.get("label", "pair_timeout", default=3.0))
    a_top = float(cfg.get("label", "arena_top", default=0.10))
    a_bot = float(cfg.get("label", "arena_bottom", default=0.86))
    plays = _extract_plays(events, region, slots, click_r, pair_timeout, a_top, a_bot)

    # --- recover the BOARD click time (label.py stamps the SELECT time) ---
    clicks = [e for e in events if e.get("type") == "click"]
    for p in plays:
        p["t_sel"] = p["t"]
        p["t_click"] = None
        for e in clicks:
            if e["t"] < p["t"]:
                continue
            nx, ny = (e["x"] - left) / w, (e["y"] - top) / h
            if abs(nx - p["nx"]) < 1e-9 and abs(ny - p["ny"]) < 1e-9:
                p["t_click"] = e["t"]
                break
    n_noclick = sum(1 for p in plays if p["t_click"] is None)

    det = load_detector(cfg)
    assert det.available, "detector weights not found"
    det_conf = float(cfg.get("observation", "detector_conf", default=0.35))
    vision = Vision(cfg)
    deck_keys = list(vision.deck_keys)

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vw, vh = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    def read_frame(fi):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
        ok, f = cap.read()
        return f if ok else None

    det_cache: dict[int, list] = {}
    all_dets: list[dict] = []                 # every detection over every processed frame (calibration stats)

    def dets_at(fi):
        if fi in det_cache:
            return det_cache[fi]
        f = read_frame(fi)
        ds = det.detect(f, conf=det_conf) if f is not None else []
        det_cache[fi] = ds
        for d in ds:
            all_dets.append({"fi": int(fi), "cls": d.cls, "conf": float(d.conf), "team": d.team,
                             "cx": float(d.cx), "cy": float(d.cy), "gy": float(d.gy), "w": float(d.w), "h": float(d.h)})
        return ds

    reads = oc.LiveReads(elixir_int=0, hand_names=(None,) * 4, next_name=None, tower_hp=(None,) * 6,
                         t_sec=0.0, t_source="clock")
    rows = []
    t_start = time.time()
    for k, p in enumerate(plays):
        tc = p["t_click"]
        row = {"k": k, "slot": p["slot"], "t_sel": p["t_sel"], "t_click": tc, "nx": p["nx"], "ny": p["ny"]}
        if tc is None:
            row["skip"] = "no_click_event"
            rows.append(row)
            continue
        # card identity from the hand at the SELECT frame (same frame label.py uses)
        fs = min(max(bisect.bisect_left(frame_times, p["t_sel"]), 0), max(total - 1, 0))
        fr = read_frame(fs)
        hand_ids = vision.recognize_hand(fr) if fr is not None else [-1] * 4
        card_i = hand_ids[p["slot"]] if 0 <= p["slot"] < len(hand_ids) else -1
        card_key = deck_keys[card_i] if 0 <= card_i < len(deck_keys) else None
        card_base = vocab.base_key(card_key) if card_key else None
        row.update({"card_key": card_key, "card_base": card_base, "hand_ids": [int(i) for i in hand_ids],
                    "card_slot_in_deck": deck.slot_of(card_key) if card_key else -1,
                    "card_kind": (vocab.kind_of(deck.card_ids[deck.slot_of(card_key)]) if card_key and deck.slot_of(card_key) >= 0 else None)})
        # click -> board, with the contract's own transform (from_live: warp.frame_to_board(cx, gy))
        bx, by = warp.frame_to_board(float(p["nx"]), float(p["ny"]))
        row["click_board"] = [bx, by]
        # pre-click frame: same-base unit already near the click?
        fpre = min(max(bisect.bisect_right(frame_times, tc - T_PRE) - 1, 0), total - 1)
        pre_bs = oc.from_live(dets_at(fpre), reads, deck, warp=warp)
        pre_same = []
        for u in pre_bs.units + pre_bs.spells:
            nm = vocab.UNIT_VOCAB[u.cls]
            if card_base and vocab.base_key(nm) == card_base:
                ex, ey = tile_err(u.x, u.y, bx, by)
                pre_same.append((float(np.hypot(ex, ey)), u.side))
        row["pre_same_min_tiles"] = min((d for d, _ in pre_same), default=None)
        # the window
        f0 = bisect.bisect_left(frame_times, tc + T0)
        f1 = bisect.bisect_right(frame_times, tc + T1) - 1
        frames = []
        for fi in range(max(0, f0), min(f1, total - 1) + 1):
            ds = dets_at(fi)
            bs = oc.from_live(ds, reads, deck, warp=warp)
            fr_rec = {"fi": fi, "dt": frame_times[fi] - tc, "n_units": len(bs.units), "n_spells": len(bs.spells),
                      "strict": None, "fallback": None}
            for mode in ("strict", "fallback"):
                best = None
                for u in bs.units + bs.spells:
                    if u.side == 1:
                        continue
                    nm = vocab.UNIT_VOCAB[u.cls]
                    b = vocab.base_key(nm)
                    if mode == "strict":
                        if not card_base or b != card_base:
                            continue
                    else:
                        if b not in deck_bases:
                            continue
                    ex, ey = tile_err(u.x, u.y, bx, by)
                    d = float(np.hypot(ex, ey))
                    if best is None or d < best["d"]:
                        best = {"d": d, "ex": ex, "ey": ey, "cls": nm, "side": u.side, "conf": u.conf,
                                "x": u.x, "y": u.y, "is_spell": vocab.is_spell(u.cls)}
                fr_rec[mode] = best
            frames.append(fr_rec)
        row["frames"] = frames
        # summaries
        for mode in ("strict", "fallback"):
            hit = next((f for f in frames if f[mode] and f[mode]["d"] <= FOUND_R_TILES), None)
            nearest = min((f[mode]["d"] for f in frames if f[mode]), default=None)
            row[f"{mode}_found"] = hit is not None
            row[f"{mode}_first"] = ({"dt": hit["dt"], "fi": hit["fi"], **hit[mode]} if hit else None)
            row[f"{mode}_nearest_any"] = nearest
            row[f"{mode}_n_frames_hit"] = sum(1 for f in frames if f[mode] and f[mode]["d"] <= FOUND_R_TILES)
        rows.append(row)
        if k % 20 == 0:
            print(f"[{project}/{session.name}] play {k}/{len(plays)} frames_run={len(det_cache)} "
                  f"{time.time() - t_start:.0f}s", flush=True)
    cap.release()

    out = {"project": project, "session": str(session), "region": region, "video_wh": [vw, vh],
           "n_events": len(events), "n_plays": len(plays), "n_plays_no_click_event": n_noclick,
           "n_frames_detected": len(det_cache), "det_conf": det_conf, "found_r_tiles": FOUND_R_TILES,
           "window": [T0, T1], "deck": list(deck.cards), "vision_deck_keys": deck_keys,
           "warp_xa": warp.xa, "warp_ya": warp.ya, "plays": rows, "all_dets": all_dets}
    out_json.write_text(json.dumps(out), encoding="utf-8")
    print(f"[done] {project}/{session.name}: plays={len(plays)} frames={len(det_cache)} dets={len(all_dets)} "
          f"-> {out_json}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
