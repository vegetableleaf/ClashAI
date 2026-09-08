"""L67f (3): WHY does the placement head collapse on live input? Ablate the live-only features, one at a time.

(1) measured, at matched unit counts, that the live top-1 cell share is ~3x the engine one (0.33 vs 0.10 at
2-3 units). Sparsity explains part of the raw gap but not the matched gap. Every remaining candidate is a
feature that is CONSTANT in training and varies live (5cs.95 A measured the training side: side_unknown 0,
hp_known 1.0, conf 1.0, my_elixir_exact 1.0, opp_known 1.0, spell tokens 0, `_evo` tokens 0).

So: run the detector ONCE over the frames, cache the BoardStates, then re-score them with each live-only
feature normalised back to its TRAINING constant. Whichever normalisation restores dispersion names the cause.
No retraining, and the model is untouched -- only its input changes.

usage: python scratchpad/gauntlet/L67/ablate_live.py <session_dir> --ckpt <pt> --out <json> [--every 12] [--limit 300]
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))


def variants(bs):
    """Each entry: label -> a BoardState with ONE live-only feature pushed to its training value."""
    rep = dataclasses.replace
    out = {"live (baseline)": bs}
    out["no_spell_tokens"] = rep(bs, spells=())
    out["side_resolved"] = rep(bs, units=tuple(rep(u, side=(1 if u.side < 0 else u.side)) for u in bs.units),
                               spells=tuple(rep(u, side=(1 if u.side < 0 else u.side)) for u in bs.spells))
    out["conf_1.0"] = rep(bs, units=tuple(rep(u, conf=1.0) for u in bs.units),
                          spells=tuple(rep(u, conf=1.0) for u in bs.spells))
    out["hp_known"] = rep(bs, units=tuple(rep(u, hp_frac=(1.0 if u.hp_frac is None else u.hp_frac)) for u in bs.units),
                          spells=tuple(rep(u, hp_frac=(1.0 if u.hp_frac is None else u.hp_frac)) for u in bs.spells))
    towers = tuple(rep(t, hp_frac=(1.0 if t.hp_frac is None else t.hp_frac)) for t in bs.towers)
    out["scalars_known"] = rep(bs, my_elixir_exact=True, opp_elixir=5.0, towers=towers)
    # everything at once: the full "look like an engine state" transform
    allb = rep(bs, spells=(), my_elixir_exact=True, opp_elixir=5.0, towers=towers,
               units=tuple(rep(u, side=(1 if u.side < 0 else u.side), conf=1.0,
                               hp_frac=(1.0 if u.hp_frac is None else u.hp_frac)) for u in bs.units))
    out["ALL of the above"] = allb
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("session", type=Path)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--deck", default="icebow")
    ap.add_argument("--every", type=int, default=12)
    ap.add_argument("--limit", type=int, default=300)
    a = ap.parse_args()

    import cv2
    import torch
    from clashrl.actions import ActionSpace
    from clashrl.config import Config
    from clashrl.replay_mine import load_detector
    from clashrl.student_live import live_reads
    from clashrl.vision import Vision
    from pipeline.model_v3 import S1Model, hand_mask_from_sc
    from pipeline.obs_contract import from_live, load_deck, to_tokens

    cfg = Config.load()
    vision, actions = Vision(cfg), ActionSpace(cfg)
    det = load_detector(cfg)
    if not det.available:
        raise SystemExit("detector weights not found")
    deck = load_deck(a.deck)
    conf_thr = float(cfg.get("observation", "detector_conf", default=0.35))

    st = torch.load(a.ckpt, map_location="cpu")
    args = dict(st.get("args", {}) or {})
    grid = str(args.get("grid", "floor"))
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4)))
    model.load_state_dict(st["model"])
    model.eval()

    class _NullHp:
        my_hp: list = []
        enemy_hp: list = []
        my_full = 0
        full = 0

    class _NullTowers:
        mine_alive = [True, True, True]
        enemy_alive = [True, True, True]

    cap = cv2.VideoCapture(str(a.session / "video.mp4"))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {a.session / 'video.mp4'}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 12.0)

    states, fi, used = [], -1, 0
    while used < a.limit:                                   # ONE detector pass; every variant reuses it
        ok, frame = cap.read()
        if not ok:
            break
        fi += 1
        if fi % a.every:
            continue
        dets = det.detect(frame, conf=conf_thr)
        hand_ids = list(vision.recognize_hand(frame))
        nxt = vision.recognize_next(frame)
        reads = live_reads(elixir=float(vision.read_elixir(frame)), hand_ids=hand_ids,
                           deck_keys=list(vision.deck_keys),
                           next_name=(vision.deck_keys[nxt] if isinstance(nxt, int) and 0 <= nxt < len(vision.deck_keys) else None),
                           hp_tracker=_NullHp(), tower_tracker=_NullTowers(), t_sec=fi / max(fps, 1e-6))
        states.append(from_live(dets, reads, deck, warp=actions.warp))
        used += 1
    cap.release()

    rec = []
    labels = list(variants(states[0]).keys()) if states else []
    for label in labels:
        cells = []
        with torch.no_grad():
            for bs in states:
                v = variants(bs)[label]
                tok, mask, sc = to_tokens(v)
                tt = torch.from_numpy(np.asarray(tok)[None])
                mm = torch.from_numpy(np.asarray(mask)[None])
                ss = torch.from_numpy(np.asarray(sc)[None])
                pp = torch.full((1, 3, 4), -1.0)
                enc = model.encode(tt, mm, ss, pp)
                h = model.heads(enc, hand_mask_from_sc(ss))
                slot = h["card"].argmax(-1)
                cells.append(int(model.cell_logits(enc, slot).argmax(-1).item()))
        k = collections.Counter(cells)
        rec.append({"variant": label, "n": len(cells), "top1_share": round(k.most_common(1)[0][1] / len(cells), 4),
                    "distinct": len(k), "top3": k.most_common(3)})
        print(json.dumps(rec[-1]), flush=True)
    a.out.write_text(json.dumps({"session": a.session.name, "ckpt": str(a.ckpt), "grid": grid, "rows": rec},
                                indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
