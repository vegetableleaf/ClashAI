"""`run.py models` -- say plainly which NETWORKS exist and which one each path actually uses.

WHY THIS EXISTS. Nothing in this project tells you how many neural networks it trains. There are
TWO, they share no weights, no data and no training command, and they fail in completely different
ways:

  VISION AI   a YOLO detector -- reads the arena into boxes.   trained by tools/detect/train.py
  PLAYING AI  a PolicyNet     -- decides what to play, where.  trained by train-bc / train-rl /
                                                               train-sim / train-sim-ppo

Conflating them has cost real time. The detector plateaued across four generations while the
policy's problems were entirely in the reward; and because the detector has MANY generations on
disk with only one selected, "which model am I actually running?" had no answer short of reading
config and mtimes by hand. This prints it, plus the consistency checks that have actually caught
bugs: a pin that does not resolve, an inference resolution that does not match training, and sim
noise knobs that no longer describe the pinned detector.

Read-only. It loads checkpoint METADATA only, never weights onto a device.
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
    print("VISION AI  --  what the bot SEES        (one YOLO detector, many generations on disk)")
    print("=" * 78)

    pin = cfg.get("detect", "weights", default=None)
    runs = root / "runs" / "detect"
    gens = sorted([d for d in runs.glob("*") if (d / "weights" / "best.pt").exists()],
                  key=lambda d: (d / "weights" / "best.pt").stat().st_mtime) if runs.exists() else []
    sel = None
    if pin:
        p = cfg.path(pin)
        sel = p if p.exists() else None
        print(f"  SELECTED   {pin}")
        if sel is None:
            print("             *** THIS PIN DOES NOT RESOLVE -- _resolve_weights will silently fall "
                  "back to NEWEST-BY-MTIME, which is not the same thing as best ***")
    else:
        print("  SELECTED   (none pinned) -- newest by mtime wins, which is NOT the same as best")

    imgsz = int(cfg.get("detect", "imgsz", default=960))
    conf = cfg.get("observation", "detector_conf", default=0.40)
    by_card = cfg.get("observation", "detector_conf_by_card", default=None) or {}
    print(f"  inference  imgsz {imgsz}, conf {conf}"
          + (f", {len(by_card)} per-card gate(s)" if by_card else ", no per-card gates"))

    if sel is not None:
        try:
            import torch
            ck = torch.load(sel, map_location="cpu", weights_only=False)
            m = ck.get("model")
            nw = len(getattr(m, "names", {}) or {})
            ep = ck.get("epoch")
            ep_s = "stripped for inference" if ep in (None, -1) else f"best around epoch {ep}"
            print(f"  weights    {nw} classes, {ep_s}")
            targs = ck.get("train_args") or {}
            timg = targs.get("imgsz")
            if timg and int(timg) != imgsz:
                print(f"  *** MISMATCH: trained at imgsz {timg} but inference is set to {imgsz}. "
                      f"ultralytics defaults predict() to 640 regardless of training size; that gap "
                      f"cost 7.3pp of whitelist recall when it was last measured. ***")
            elif timg:
                print(f"  OK         inference imgsz matches training ({timg})")
        except Exception as exc:            # a checkpoint we cannot introspect must not break the report
            print(f"  weights    (could not read metadata: {exc})")

    try:
        ncfg = len(cfg.get("detect", "classes_file", default="") and
                   __import__("clashrl.detect", fromlist=["_load_classes"])._load_classes(cfg) or [])
        print(f"  taxonomy   config/detect_classes.yaml has {ncfg} classes")
    except Exception:
        pass

    if gens:
        print(f"  on disk    {len(gens)} generation(s): "
              + ", ".join(d.name for d in gens[-6:]) + (" ..." if len(gens) > 6 else ""))
        if sel is not None:
            newer = [d.name for d in gens
                     if (d / "weights" / "best.pt").stat().st_mtime > sel.stat().st_mtime]
            if newer:
                print(f"  NEWER than the pin, deliberately NOT selected: {', '.join(newer)}")
                print("             (newest is not best -- promote only after "
                      "`detect-eval --sweep --subset data/detect/val_board15.txt` beats the incumbent)")

    print()
    print("=" * 78)
    print("PLAYING AI  --  what the bot DOES       (one PolicyNet, several training routes)")
    print("=" * 78)
    routes = [
        ("checkpoint", "data/policy.pt", "train-bc", "behaviour cloning from your recorded sessions"),
        ("rl_checkpoint", "data/policy_rl.pt", "train-rl", "LIVE fine-tune; `play` PREFERS this if present"),
        ("sim_checkpoint", "data/policy_sim.pt", "train-sim", "simulator DDQN prior"),
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
        p = cfg.path(cfg.get("train", key, default=dflt))
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
    print(f"  These must describe the PINNED detector above. Re-measure them whenever the pin moves,")
    print(f"  or the policy learns to compensate for perception errors it will never actually meet.")
    print(f"  gate threshold: sim.ppo_gate_threshold "
          f"{cfg.get('sim', 'ppo_gate_threshold', default=0.25)} "
          f"(shared by training, benchmark and live so all three agree)")
