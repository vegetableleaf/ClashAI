"""ARGMAX-CELL DIVERSITY -- the sim-to-real blindness metric from 5cdf867, as a runnable command.

5cdf867 justified domain randomization with a hand measurement: the same trained net produced **2
distinct argmax cells on real frames** (input-insensitive -- the placement collapsed to one corner
regardless of what was on the board) against **11 varied cells on sim obs**. That number was measured
by hand and never committed, so it could not be re-run to check whether a change actually helped.
This module makes it reproducible.

WHAT IS MEASURED. For a set of observations, run the policy and take the cell head's argmax -- masked
to DEPLOYABLE cells exactly as `play` / `train_sim` mask it, so the number describes placements the bot
would really make, not unreachable ones. Then report, per world:

  distinct    how many different cells the net chose across the sampled frames. This is 5cdf867's
              number. Low = the trunk is not responding to the board.
  top_share   fraction of frames that landed on the single most popular cell. This is the sharper
              signal: "collapsed to one corner" is exactly top_share near 1.0. `distinct` can look
              healthy while 90% of frames still pile onto one cell.
  entropy     normalized Shannon entropy of the cell distribution (0 = always one cell, 1 = uniform
              over the cells actually used). Robust to sample size in a way `distinct` is not.

READ IT AS A COMPARISON, NOT AN ABSOLUTE. A good policy SHOULD concentrate placements -- there are only
a handful of correct X-Bow tiles -- so high diversity is not itself the goal. The diagnosis is the GAP:
sim diversity high while real diversity collapses means the trunk works on synthetic input and is blind
on real input. Closing that gap is what the semantic raster is for.

THE IMAGE BRANCH IS ISOLATED. `next` and `threat` are zeroed on BOTH sides. The trunk is what is under
test, and feeding the sim its real threat vector while real frames got zeros would let the sim look more
responsive purely because it had a varying side-channel. `hand` and `elixir` stay real on both sides,
because they drive the card choice, which selects the deployable mask the cell argmax is taken under.

CAVEAT ON SAMPLING. Real frames are sampled from recorded sessions and scored INDEPENDENTLY (each frame
gets a fresh tracker), while sim frames come from a rollout, which visits correlated boards. The rollout
therefore steps with RANDOM affordable actions rather than the policy's own choices -- otherwise a good
policy would walk one narrow trajectory and understate its own diversity. Use `--frames` large enough (a
few hundred) that neither side is sample-starved, and compare like with like.

Usage, from icebow/:
    .\\.venv\\Scripts\\python.exe run.py obs-diversity --ckpt data/policy_sim_best.pt
    .\\.venv\\Scripts\\python.exe run.py obs-diversity --ckpt data/policy_sim_best.pt --mode rgb
"""
from __future__ import annotations

import math
import random
from collections import Counter
from pathlib import Path
from typing import List, Optional

import numpy as np


def _stats(cells: List[int], n_cells: int) -> dict:
    if not cells:
        return {"n": 0, "distinct": 0, "top_share": float("nan"), "entropy": float("nan"), "top_cell": None}
    c = Counter(cells)
    n = len(cells)
    top_cell, top_n = c.most_common(1)[0]
    probs = [v / n for v in c.values()]
    ent = -sum(p * math.log(p) for p in probs)
    denom = math.log(len(c)) if len(c) > 1 else 0.0
    return {"n": n, "distinct": len(c), "top_share": top_n / n,
            "entropy": ent / denom if denom > 0 else 0.0, "top_cell": top_cell}


def _fmt(label: str, s: dict, gw: int) -> str:
    if not s["n"]:
        return f"[obs-diversity] {label:<5}: no frames scored"
    tc = s["top_cell"]
    return (f"[obs-diversity] {label:<5}: {s['distinct']:4d} distinct cells over {s['n']:4d} frames"
            f"   top_share {s['top_share']:.2f} (cell {tc} = col {tc % gw}, row {tc // gw})"
            f"   entropy {s['entropy']:.2f}")


def obs_diversity(cfg, ckpt_path: Optional[str] = None, frames: int = 200, session=None,
                  mode: Optional[str] = None, conf: Optional[float] = None, seed: int = 0) -> None:
    try:
        import torch
    except ImportError as exc:  # noqa: BLE001
        print(f"[obs-diversity] PyTorch required ({exc}). Install the CUDA build (see README).")
        return
    import cv2

    from . import semantic
    from .actions import ActionSpace
    from .cards import CardDB
    from .model import PolicyNet
    from .train_rl import _pick_device

    if mode:                                   # score a checkpoint in ITS mode without editing config.yaml
        cfg.data.setdefault("observation", {})["obs_mode"] = mode
    obs_mode = semantic.obs_mode(cfg)
    in_ch = semantic.obs_channels(cfg)

    path = cfg.path(ckpt_path) if ckpt_path else cfg.path(
        cfg.get("train", "sim_checkpoint", default="data/policy_sim.pt"))
    if not path.exists():
        print(f"[obs-diversity] no checkpoint at {path} -- train one first (run.py train-sim).")
        return
    ck = torch.load(path, map_location="cpu")
    n_cards, n_cells = int(ck["n_cards"]), int(ck["n_cells"])
    threat_dim = int(ck.get("threat_dim", 14))
    ck_mode, ck_ch = ck.get("obs_mode", "rgb"), int(ck.get("in_ch", 3))
    if ck_mode != obs_mode or ck_ch != in_ch:
        print(f"[obs-diversity] checkpoint/observation MISMATCH -- {path.name} was trained on "
              f"obs_mode={ck_mode} ({ck_ch} ch), scoring at {obs_mode} ({in_ch} ch).")
        print(f"[obs-diversity] re-run with --mode {ck_mode} to score it in the mode it was trained on.")
        return

    device = _pick_device(cfg)
    net = PolicyNet(in_ch, n_cards, n_cells, threat_dim=threat_dim).to(device)
    net.load_state_dict(ck["model"])
    net.eval()

    actions = ActionSpace(cfg)
    gw = int(actions.gw)
    db = CardDB(cfg)
    deck_keys = db.deck_identities()

    def _base(k):
        return k[:-4] if str(k).endswith("_evo") else str(k)

    anywhere_ids = {i for i, k in enumerate(deck_keys) if _base(k) in ("rocket", "miner")}
    yourhalf = torch.tensor(actions.deployable_mask(False), dtype=torch.bool, device=device)
    allcells = torch.ones(n_cells, dtype=torch.bool, device=device)

    def cell_argmax(obs, hand_vec, next_vec, elx, thr_vec) -> Optional[int]:
        """The cell the policy would actually place -- greedy, hand-masked, DEPLOYABLE-masked, exactly
        as play.py and train_sim's greedy path do it."""
        x = torch.from_numpy(np.ascontiguousarray(obs)).float().permute(2, 0, 1).unsqueeze(0).to(device) / 255.0
        hv = torch.from_numpy(np.asarray(hand_vec, np.float32)).unsqueeze(0).to(device)
        nv = torch.from_numpy(np.asarray(next_vec, np.float32)).unsqueeze(0).to(device)
        ev = torch.tensor([[float(elx)]], dtype=torch.float32, device=device)
        tv = torch.from_numpy(np.asarray(thr_vec, np.float32)).unsqueeze(0).to(device)
        with torch.no_grad():
            z = net.features_vec(x, hv, nv, ev, tv)
            cq, ceq = net.card_head(z), net.cell_head(z)
        cq = cq.masked_fill(hv < 0.5, float("-inf"))
        if not bool(torch.isfinite(cq).any()):
            return None
        ci = int(cq.argmax(1).item())
        cmask = allcells if ci in anywhere_ids else yourhalf
        return int(ceq.masked_fill(~cmask.unsqueeze(0), float("-inf")).argmax(1).item())

    # ---- SIM: a greedy rollout over the simulator -----------------------------------------------
    from .sim.env import SimMatchEnv

    sim_env = SimMatchEnv(cfg, seed=seed)
    if sim_env.threat_dim != threat_dim:
        print(f"[obs-diversity] threat_dim mismatch: checkpoint {threat_dim} vs env {sim_env.threat_dim}. "
              "The observation.use_detector / use_interactions gates must match the checkpoint.")
        return
    # ISOLATE THE IMAGE BRANCH. The question is whether the CONV TRUNK responds to the board, so the
    # non-image inputs are held constant across BOTH worlds: `next` and `threat` are zeroed on each side.
    # (Feeding the sim its real threat vector while real frames got zeros would let the sim look more
    # responsive purely because it had a varying side-channel -- measuring the wrong thing.) `hand` and
    # `elixir` stay real on both sides because they drive the card choice, which selects the deployable
    # mask the cell argmax is taken under.
    zero_next = np.zeros(n_cards, np.float32)
    zero_thr = np.zeros(threat_dim, np.float32)

    sim_cells: List[int] = []
    obs = sim_env.reset()
    for _ in range(frames):
        c = cell_argmax(obs, sim_env.hand_vec, zero_next, sim_env.elixir_vec[0], zero_thr)
        if c is not None:
            sim_cells.append(c)
        # step with a RANDOM affordable action so the rollout visits varied boards instead of walking
        # the policy's own narrow trajectory (which would understate diversity for a good policy)
        hand = [i for i, v in enumerate(sim_env.hand_vec) if v > 0.5]
        affordable = [i for i in hand if sim_env.specs[i].elixir <= sim_env.elixir]
        act = ((1, random.choice(affordable), random.randrange(n_cells))
               if affordable and random.random() < 0.5 else (0, 0, 0))
        obs, _r, done, _i = sim_env.step(act)
        if done:
            obs = sim_env.reset()

    # ---- REAL: recorded in-match frames, observed exactly as `play` observes them ----------------
    from .vision import Vision
    from .reward import TowerTracker
    from .tower_hp import TowerHpTracker
    from .states import GameState

    vision = Vision(cfg)
    tower = TowerTracker(cfg)
    hp = TowerHpTracker(cfg)
    ow, oh = cfg.get("observation", "arena_size", default=[64, 96])
    sem_live = None
    detector = None
    team_tracker = None
    real_blocked = None                      # why the REAL half could not be scored (reported at the end)
    if obs_mode != "rgb":
        from .replay_mine import load_detector, TeamTracker
        det = load_detector(cfg)
        detector = det if det.available else None
        if detector is None:
            # The SIM half is still worth reporting -- it is the reference the real number is compared
            # against, and it needs nothing but a checkpoint.
            real_blocked = ("no trained board detector, so the REAL semantic channels would be all-zero "
                            "(train it: python tools/detect/train.py)")
        else:
            sem_live = semantic.LiveRaster(cfg, db)
            team_tracker = TeamTracker()
    det_conf = float(conf if conf is not None else cfg.get("observation", "detector_conf", default=0.5))

    root = Path(cfg.path(cfg.get("record", "out_dir", default="data/sessions")))
    if session and Path(session).exists():
        sessions = [Path(session)]
    elif session:
        sessions = [root / session]
    elif root.exists():
        sessions = sorted(d for d in root.iterdir() if (d / "meta.json").exists())
    else:
        sessions = []
    videos = [next((s / n for n in ("video.mp4", "video.avi") if (s / n).exists()), None) for s in sessions]
    videos = [v for v in videos if v is not None]

    real_cells: List[int] = []
    if not videos and real_blocked is None:
        real_blocked = (f"no recorded session videos under {root} (record one: run.py record, "
                        "or pass --session)")
    if real_blocked is None:
        rng = random.Random(seed)
        tries = 0
        while len(real_cells) < frames and tries < frames * 20:
            tries += 1
            vid = rng.choice(videos)
            cap = cv2.VideoCapture(str(vid))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, rng.randrange(max(1, total)))
            ok, frame = cap.read()
            cap.release()
            if not ok or frame is None or vision.detect_state(frame) != GameState.IN_MATCH:
                continue
            hand_ids = vision.recognize_hand(frame)
            hand_vec = vision.hand_multihot(hand_ids)
            if hand_vec.sum() == 0:                 # unreadable tray -> the policy could not act either
                continue
            tower.reset(); hp.reset()               # frames are sampled independently, so is tracker state
            tower.step(frame); hp.step(frame)
            rgb = vision.observe(frame) if obs_mode != "semantic" else None
            sem = None
            if sem_live is not None:
                dets = detector.detect(frame, conf=det_conf)
                team_tracker.tag(dets, tries * 1.0)
                sem = sem_live.render(dets, hp.my_hp, hp.my_full, tower.mine_alive,
                                      hp.enemy_hp, hp.full, tower.enemy_alive, int(oh), int(ow))
            o = semantic.compose(obs_mode, rgb, sem)
            c = cell_argmax(o, hand_vec, zero_next, vision.read_elixir(frame) / 10.0, zero_thr)
            if c is not None:
                real_cells.append(c)

    s_sim = _stats(sim_cells, n_cells)
    s_real = _stats(real_cells, n_cells)
    print(f"[obs-diversity] checkpoint {path.name}  obs_mode={obs_mode} ({in_ch} ch)  "
          f"grid {gw}x{int(actions.gh)} = {n_cells} cells")
    print(_fmt("SIM", s_sim, gw))
    if real_blocked is not None:
        print(f"[obs-diversity] REAL : NOT SCORED -- {real_blocked}")
        print("[obs-diversity] the sim-vs-real GAP is the whole metric, so this run is only half of it.")
    else:
        print(_fmt("REAL", s_real, gw))
    if s_sim["n"] and s_real["n"]:
        ratio = s_real["distinct"] / max(1, s_sim["distinct"])
        print(f"[obs-diversity] REAL/SIM distinct-cell ratio {ratio:.2f} "
              f"(1.00 = the trunk responds to real frames as well as to sim frames; "
              f"5cdf867 measured 2/11 = 0.18 on the RGB observation)")
