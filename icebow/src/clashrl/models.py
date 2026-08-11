"""`run.py models` -- say plainly which NETWORKS exist and which one each path actually uses.

WHY THIS EXISTS. Nothing in this project tells you how many neural networks it trains. There are
TWO, they share no weights, no data and no training command, and they fail in completely different
ways:

  VISION AI   a YOLO detector -- reads the arena into boxes.   trained by tools/detect/train.py
  PLAYING AI  a PolicyNet     -- decides what to play, where.  trained by train-bc / train-rl /
                                                               train-sim / train-sim-ppo

Conflating them has cost real time: the detector plateaued across four generations while the
policy's problems were entirely in the reward.

"Which detector am I running?" used to need this report, because many generations sat on disk
with one selected by a config pin. That question no longer exists -- training writes
runs/detect/vision and REPLACES it, and _resolve_weights reads that one path. What remains worth
printing is the part that still bites: an inference resolution that does not match training, a
taxonomy that has drifted from the trained weights, policy checkpoints on a stale schema, and sim
noise knobs that no longer describe the detector in place.

Read-only. It reads model_card.json and checkpoint METADATA, never weights onto a device.
"""
from __future__ import annotations

from pathlib import Path


def _fmt(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except Exception:
        return str(p)


def models(cfg) -> None:
    root = cfg.root
    print("=" * 78)
    print("VISION AI  --  what the bot SEES        (ONE YOLO detector, not selectable)")
    print("=" * 78)

    from .detect import VISION_RUN, _resolve_weights
    sel, runs = _resolve_weights(cfg, None)
    if sel is None:
        print(f"  MODEL      not trained yet -- runs/detect/{VISION_RUN}/weights/best.pt is missing")
        print("             train it from the panel, or with tools/detect/train.py")
    else:
        print(f"  MODEL      {_fmt(sel, root)}")

    card = {}
    if sel is not None:
        cp = sel.parent.parent / "model_card.json"
        if cp.exists():
            import json
            try:
                card = json.loads(cp.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                card = {}

    imgsz = int(cfg.get("detect", "imgsz", default=960))
    conf = cfg.get("observation", "detector_conf", default=0.40)
    by_card = cfg.get("observation", "detector_conf_by_card", default=None) or {}
    print(f"  inference  imgsz {imgsz}, conf {conf}"
          + (f", {len(by_card)} per-card gate(s)" if by_card else ", no per-card gates"))

    # Prefer model_card.json, written by tools/detect/train.py when a run COMPLETES. Reading it
    # instead of unpickling best.pt matters now that bundles move between machines: an ultralytics
    # checkpoint needs weights_only=False to introspect, i.e. arbitrary unpickling of a file that
    # may have come from someone else. The card is plain JSON and carries the same facts.
    if card:
        ep = card.get("epochs")
        m50, pre, rec = card.get("mAP50"), card.get("precision"), card.get("recall")
        bits = [f"started from {card.get('model')}"] if card.get("model") else []
        if ep is not None:
            bits.append(f"{ep:g} epochs")
        if card.get("trained_on_boxes") is not None:
            bits.append(f"{card['trained_on_boxes']} labelled boxes")
        print(f"  trained    {', '.join(bits)}" if bits else "  trained    (card has no detail)")
        if m50 is not None:
            print(f"  measured   mAP50 {m50:.1%}, precision {pre:.1%}, recall {rec:.1%}"
                  if pre is not None and rec is not None else f"  measured   mAP50 {m50:.1%}")
        timg = card.get("imgsz")
        if timg and int(timg) != imgsz:
            print(f"  *** MISMATCH: trained at imgsz {timg} but inference is set to {imgsz}. "
                  f"ultralytics defaults predict() to 640 regardless of training size; that gap "
                  f"cost 7.3pp of whitelist recall when it was last measured. ***")
        elif timg:
            print(f"  OK         inference imgsz matches training ({timg})")
    elif sel is not None:
        print("  trained    no model_card.json beside the weights -- either the run was interrupted "
              "before it could write one, or the weights predate the card. Retrain to get numbers.")

    try:
        from .detect import _load_classes
        print(f"  taxonomy   config/detect_classes.yaml has {len(_load_classes(cfg))} classes")
    except Exception:
        pass

    # A leftover generation folder is not a second model -- nothing loads it -- but it is the
    # ONLY copy of a detector you may want back, so say it is there rather than let it look
    # like the current one.
    others = sorted(d.name for d in runs.glob("*")
                    if d.name != VISION_RUN and (d / "weights" / "best.pt").exists()) \
        if runs.exists() else []
    if others:
        print(f"  archived   {len(others)} older folder(s) NOT in use: {', '.join(others[:6])}"
              + (" ..." if len(others) > 6 else ""))
        print("             nothing loads these. Compare one with "
              "`detect-eval --weights runs/detect/<name>/weights/best.pt`.")

    print()
    print("=" * 78)
    print("PLAYING AI  --  what the bot DOES       (one PolicyNet, several training routes)")
    print("=" * 78)
    routes = [
        ("checkpoint", "data/policy.pt", "train-bc", "behaviour cloning from your recorded sessions"),
        ("rl_checkpoint", "data/policy_rl.pt", "train-rl", "LIVE fine-tune; `play` PREFERS this if present"),
        ("sim_checkpoint", "data/policy_sim.pt", "train-sim", "simulator DDQN prior, LATEST state"),
        # Listed explicitly because `train-sim --resume` now continues from this one by DEFAULT
        # (--resume-from best). Leaving it out made the report describe a file nobody trains from.
        (None, "data/policy_sim_best.pt", "train-sim", "the best benchmark so far -- resumed from by default"),
        ("sim_ppo_checkpoint", "data/policy_sim_ppo.pt", "train-sim-ppo", "simulator PPO prior"),
    ]
    import torch
    # What shape does the CURRENT code expect? A checkpoint from an older schema still LOADS for
    # inspection but cannot be resumed or played, and the failure is otherwise silent until a
    # shape error deep in a training run.
    want = None
    try:
        from .sim.env import SimMatchEnv
        e = SimMatchEnv(cfg, seed=0)
        want = {"n_cards": e.n_cards, "n_cells": e.n_cells, "threat_dim": e.threat_dim}
        print(f"  current schema expects: n_cards={want['n_cards']} n_cells={want['n_cells']} "
              f"threat_dim={want['threat_dim']}\n")
    except Exception:
        pass
    stale = []
    for key, dflt, cmd, note in routes:
        # key None = a fixed sibling path, not a configurable route
        p = cfg.path(cfg.get("train", key, default=dflt) if key else dflt)
        if not p.exists():
            print(f"  {'-':<3} {_fmt(p, root):<34} (none yet)   {cmd}")
            continue
        try:
            ck = torch.load(p, map_location="cpu")
            algo = ck.get("algo", "dqn")
            bits = [f"algo {algo}"]
            for k, lbl in (("matches", "matches"), ("best_wr", "best_wr"), ("epoch", "epoch")):
                if ck.get(k) is not None:
                    v = ck[k]
                    bits.append(f"{lbl} {v:.2f}" if isinstance(v, float) else f"{lbl} {v}")
            shape = []
            for k in ("n_cards", "n_cells", "threat_dim"):
                if ck.get(k) is not None:
                    shape.append(f"{k}={ck[k]}")
            print(f"  {'*':<3} {_fmt(p, root):<34} {', '.join(bits)}")
            print(f"      {'':<34} {' '.join(shape)}   <- {cmd}: {note}")
            if want is not None:
                bad = [k for k in want if ck.get(k) is not None and int(ck[k]) != int(want[k])]
                if bad:
                    stale.append((_fmt(p, root), ", ".join(f"{k} {ck[k]} != {want[k]}" for k in bad)))
                    print(f"      {'':<34} *** STALE SCHEMA: {stale[-1][1]} -- cannot be resumed or "
                          f"played against the current code ***")
        except Exception as exc:
            print(f"  {'?':<3} {_fmt(p, root):<34} (unreadable: {exc})")

    print()
    print("  which one PLAYS:  `play` loads train.checkpoint, then OVERRIDES it with "
          "train.rl_checkpoint if that file exists.")
    print("  the sim priors do NOT play by themselves -- warm-start train-rl from them.")

    print()
    print("=" * 78)
    print("WHERE THEY MEET")
    print("=" * 78)
    r = cfg.get("observation", "sim_detector_recall", default=None)
    pr = cfg.get("observation", "sim_detector_precision", default=None)
    print(f"  The sim TRAINS the playing AI against a SIMULATED detector, not the real one:")
    print(f"    sim_detector_recall {r}   sim_detector_precision {pr}")
    print(f"  These must describe the detector above. Re-measure them after every retrain --")
    print(f"  otherwise the policy learns to compensate for perception errors it will never meet.")
    print(f"  gate threshold: sim.ppo_gate_threshold "
          f"{cfg.get('sim', 'ppo_gate_threshold', default=0.25)} "
          f"(shared by training, benchmark and live so all three agree)")
