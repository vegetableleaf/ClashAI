"""L67g: the live gate's response to MY ELIXIR, UNCONDITIONED -- and whether the `exact` flag kills it.

Two things forced this probe:
  * RETRACTION: the "live gate is flat in elixir" reading came from the play.py log, which prints p only on
    WAIT frames. WAIT is p < tau, so the sample is TRUNCATED at the threshold and conditioned on the very
    outcome being explained -- at high elixir the high-p frames leave the sample as PLAYs. A flat curve is
    what a perfectly calibrated gate would ALSO produce there. The log cannot answer the question.
  * On ENGINE states the gate is well calibrated in elixir (gate_vs_elixir.json: model 0.047 -> 0.472 across
    elixir 1 -> 10 against a pro rate of 0.037 -> 0.490), so if the live gate really is flat, the cause is in
    the live INPUT, not the head.

Prime suspect: ``my_elixir_exact``. Engine rows carry sc[4] = 1.0 in ALL 339,192 training rows (5cs.95 A);
the live path reads pips and sends 0.0 -- a value the model has never seen. If the head learned to read the
elixir scalar only when that flag is set, live elixir is being ignored. Measured here by re-scoring the SAME
cached live BoardStates with the flag forced on.

usage: python scratchpad/gauntlet/L67/live_gate_elixir.py <session>... --ckpt <pt> --out <json>
"""
from __future__ import annotations
import argparse, dataclasses, json, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", type=Path, nargs="+")
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--deck", default="icebow")
    ap.add_argument("--every", type=int, default=8)
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--cache", type=Path, default=None)   # detector pass is the expensive half -- reuse it
    a = ap.parse_args()

    import pickle

    import cv2, torch
    from clashrl.actions import ActionSpace
    from clashrl.cards import CardDB
    from clashrl.config import Config
    from clashrl.replay_mine import TeamTracker, load_detector, own_card_bases
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
    db = CardDB(path=deck.config.parent / "cards.yaml")
    tracker = TeamTracker(own_cards=own_card_bases(db))     # the live path tags before the student sees it
    conf_thr = float(cfg.get("observation", "detector_conf", default=0.35))

    st = torch.load(a.ckpt, map_location="cpu")
    args = dict(st.get("args", {}) or {})
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

    states = []
    if a.cache is not None and a.cache.exists():
        states = pickle.loads(a.cache.read_bytes())
        print(f"cache: {len(states)} states", flush=True)
    for sess in (a.sessions if not states else []):
        cap = cv2.VideoCapture(str(sess / "video.mp4"))
        if not cap.isOpened():
            continue
        tracker.reset()
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 12.0)
        fi, used = -1, 0
        while used < a.limit:
            ok, frame = cap.read()
            if not ok:
                break
            fi += 1
            if fi % a.every:
                continue
            used += 1
            dets = tracker.tag(det.detect(frame, conf=conf_thr), fi / max(fps, 1e-6))
            hand_ids = list(vision.recognize_hand(frame))
            nxt = vision.recognize_next(frame)
            el = float(vision.read_elixir(frame))
            reads = live_reads(elixir=el, hand_ids=hand_ids, deck_keys=list(vision.deck_keys),
                               next_name=(vision.deck_keys[nxt] if isinstance(nxt, int) and 0 <= nxt < len(vision.deck_keys) else None),
                               hp_tracker=_NullHp(), tower_tracker=_NullTowers(), t_sec=fi / max(fps, 1e-6),
                               opp_elixir=None)
            states.append((int(round(el)), from_live(dets, reads, deck, warp=actions.warp, unit_hp_default=1.0)))
        cap.release()
        print(f"{sess.name}: {len(states)} states", flush=True)
    if a.cache is not None and not a.cache.exists():
        a.cache.write_bytes(pickle.dumps(states))

    rep = dataclasses.replace

    def variant(bs, name):
        if name == "live":
            return bs
        if name == "exact_on":
            return rep(bs, my_elixir_exact=True)
        if name == "exact_on+opp5":
            return rep(bs, my_elixir_exact=True, opp_elixir=5.0)
        if name.startswith("opp"):                # opponent elixir ALONE -- the L67f live wiring, isolated
            return rep(bs, opp_elixir=float(name[3:]))
        if name == "no_hp_fill":                  # undo the other half of the L67f wiring
            return rep(bs, units=tuple(rep(u, hp_frac=None) for u in bs.units),
                       spells=tuple(rep(u, hp_frac=None) for u in bs.spells))
        raise ValueError(name)

    out = {}
    for name in ("live", "exact_on", "exact_on+opp5", "opp0.0", "opp2.5", "opp5.0", "opp7.5", "opp10.0",
                 "no_hp_fill"):
        by_el, by_u = defaultdict(list), defaultdict(list)
        with torch.no_grad():
            for el, bs in states:
                v = variant(bs, name)
                tok, mask, sc = to_tokens(v)
                tt = torch.from_numpy(np.asarray(tok)[None])
                mm = torch.from_numpy(np.asarray(mask)[None])
                ss = torch.from_numpy(np.asarray(sc)[None])
                enc = model.encode(tt, mm, ss, torch.full((1, 3, 4), -1.0))
                p = float(torch.sigmoid(model.heads(enc, hand_mask_from_sc(ss))["gate"][0]).item())
                b = "0-3" if el <= 3 else "4-6" if el <= 6 else "7-8" if el <= 8 else "9-10"
                by_el[b].append(p)
                nu = len(v.units)
                by_u["0-1" if nu <= 1 else "2-3" if nu <= 3 else "4-6" if nu <= 6 else "7+"].append(p)
        out[name] = {"by_elixir": {k: [len(v), round(float(np.mean(v)), 4)] for k, v in sorted(by_el.items())},
                     "by_units": {k: [len(v), round(float(np.mean(v)), 4)] for k, v in sorted(by_u.items())},
                     "frac_over_tau_0.27": round(float(np.mean([p > 0.27 for g in by_el.values() for p in g])), 4)}
        print(name, json.dumps(out[name]), flush=True)
    a.out.write_text(json.dumps({"ckpt": str(a.ckpt), "n": len(states), "variants": out}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
