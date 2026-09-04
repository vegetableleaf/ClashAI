"""Offline stage timer for the live decision path (HANDOFF §5be.5.1 spec, built §5bl).

Times every stage the live act loop pays per decision, on RECORDED frames, without touching
play.py / env.py / train_rl.py and without the game. The live loop already accounts for these
stages per match (`env.py` `_cad`, dumped as `cadence` in data/reward_stats/live_*.jsonl) -- this
tool breaks the two coarse buckets that dominate there (`reads` and the trainer residual) into
their parts, on a box whose load you control.

    .venv/Scripts/python.exe tools/latency_stage_timer.py --video data/sessions/20260815_222309/video.mp4 \
        --frames 120 --stride 6 --json scratchpad/gauntlet/L12/stage_timer.json

Stages (env side, per frame): detect_state, tower.step, tower_hp.step, enemy_mass, read_elixir_frac,
clock.update, recognize_hand(+multihot), threat_tracker.update (colour), detector pass (yolo, if the
weights load), vision.observe.  Trainer side (synthetic batch, real net + real shapes): policy forward
(batch 1), DDQN optimise-equivalent (batch 64 forward online+target + backward + step) -- the same
work train_rl.optimise() does synchronously after EVERY live decision.

Prints per-stage median / p90 in ms and the box load it ran under. A number from a contended box is
an UPPER BOUND, not a measurement -- the tool records the load so nobody compares across loads.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from clashrl.config import Config          # noqa: E402


def _q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))] if v else float("nan")


def _box_load():
    """Free RAM (GB) and a 1 s CPU sample, so the record says what the box was doing."""
    out = {}
    try:
        import psutil
        out["free_gb"] = round(psutil.virtual_memory().available / 2**30, 2)
        out["cpu_pct"] = psutil.cpu_percent(interval=1.0)
    except Exception:                                   # noqa: BLE001
        out["free_gb"] = None
        out["cpu_pct"] = None
    try:
        import torch
        out["cuda"] = bool(torch.cuda.is_available())
        if out["cuda"]:
            free, total = torch.cuda.mem_get_info()
            out["vram_free_gb"] = round(free / 2**30, 2)
    except Exception:                                   # noqa: BLE001
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="data/sessions/20260815_222309/video.mp4")
    ap.add_argument("--frames", type=int, default=120, help="in-match frames to time")
    ap.add_argument("--stride", type=int, default=6, help="decode every k-th frame (12 fps video)")
    ap.add_argument("--start", type=int, default=0, help="first frame index")
    ap.add_argument("--json", default=None)
    ap.add_argument("--no-net", action="store_true", help="skip the trainer-side timings")
    ap.add_argument("--net-iters", type=int, default=50)
    args = ap.parse_args()

    os.chdir(_ROOT)
    cfg = Config.load()
    load_before = _box_load()
    print(f"[timer] box before: {load_before}")

    import cv2
    from clashrl.vision import Vision
    from clashrl.reward import TowerTracker, enemy_mass
    from clashrl.tower_hp import TowerHpTracker
    from clashrl.clock import ElixirClock
    from clashrl.threats import ThreatTracker
    from clashrl.states import GameState

    vision = Vision(cfg)
    tower = TowerTracker(cfg)
    tower_hp = TowerHpTracker(cfg)
    clock = ElixirClock(cfg, vision)
    threat = ThreatTracker(cfg)
    detector = None
    det_err = None
    try:
        from clashrl.replay_mine import load_detector
        detector = load_detector(cfg)
    except Exception as e:                              # noqa: BLE001
        det_err = repr(e)

    stages = {k: [] for k in ("decode", "detect_state", "tower_step", "tower_hp_step", "enemy_mass",
                              "read_elixir", "clock_update", "hand", "threat_colour", "detector",
                              "observe")}
    cap = cv2.VideoCapture(str(_ROOT / args.video))
    if not cap.isOpened():
        print(f"[timer] cannot open {args.video}")
        return 2
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.start)
    fi = args.start
    n_match = 0
    obs = None
    n_seen = 0
    t_wall0 = time.perf_counter()
    while n_match < args.frames:
        t0 = time.perf_counter()
        ok, frame = cap.read()
        if not ok:
            break
        fi += 1
        n_seen += 1
        if (n_seen - 1) % args.stride:
            continue
        stages["decode"].append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        state = vision.detect_state(frame)
        stages["detect_state"].append(time.perf_counter() - t0)
        if state != GameState.IN_MATCH:
            continue
        n_match += 1

        def _t(name, fn):
            t = time.perf_counter()
            try:
                r = fn()
            except Exception as e:                       # noqa: BLE001
                stages.setdefault(name + "_err", []).append(repr(e)[:120])
                return None
            stages[name].append(time.perf_counter() - t)
            return r

        _t("tower_step", lambda: tower.step(frame))
        _t("tower_hp_step", lambda: tower_hp.step(frame))
        _t("enemy_mass", lambda: enemy_mass(frame, cfg))
        _t("read_elixir", lambda: vision.read_elixir_frac(frame))
        _t("clock_update", lambda: clock.update(frame))
        _t("hand", lambda: vision.hand_multihot(vision.recognize_hand(frame)))
        _t("threat_colour", lambda: threat.update(frame, time.time()).vector())
        if detector is not None:
            _t("detector", lambda: detector.detect(frame) if hasattr(detector, "detect") else detector(frame))
        obs = _t("observe", lambda: vision.observe(frame))
    wall = time.perf_counter() - t_wall0
    cap.release()

    print(f"[timer] {n_match} in-match frames of {n_seen} decoded (stride {args.stride}), "
          f"{wall:.1f} s wall")
    if detector is None:
        print(f"[timer] detector NOT timed: {det_err}")
    rep = {"video": args.video, "frames": n_match, "stride": args.stride, "box_before": load_before,
           "stages_ms": {}, "errors": {}}
    env_sum_med = 0.0
    for k, v in stages.items():
        if k.endswith("_err"):
            rep["errors"][k[:-4]] = v[:3]
            continue
        if not v:
            continue
        ms = [1000.0 * x for x in v]
        rep["stages_ms"][k] = {"n": len(ms), "p50": round(_q(ms, .5), 1), "p90": round(_q(ms, .9), 1),
                               "mean": round(st.mean(ms), 1)}
        if k != "decode":
            env_sum_med += _q(ms, .5)
        print(f"  {k:14s} n={len(ms):4d}  p50 {_q(ms, .5):7.1f} ms  p90 {_q(ms, .9):7.1f} ms  "
              f"mean {st.mean(ms):7.1f} ms")
    for k, v in rep["errors"].items():
        print(f"  {k:14s} ERROR {v[0]}")
    print(f"  env stages, sum of medians (excl. decode): {env_sum_med:.1f} ms")
    rep["env_sum_of_medians_ms"] = round(env_sum_med, 1)

    if not args.no_net:
        try:
            import torch
            from clashrl.train_rl import _build_net, _pick_device
            from clashrl.detect_obs import obs_in_channels
            rl_path = cfg.path(cfg.get("train", "rl_checkpoint", default="data/policy_rl.pt"))
            if not rl_path.exists():
                rl_path = cfg.path("data/policy_sim_ppo.pt")
            ckpt = torch.load(rl_path, map_location="cpu")
            n_cards, n_cells = int(ckpt["n_cards"]), int(ckpt["n_cells"])
            threat_dim = int(ckpt.get("threat_dim", 14))
            in_ch = obs_in_channels(cfg)
            device = torch.device(_pick_device(cfg))
            net = _build_net(cfg, device, n_cards, n_cells, threat_dim, in_ch)
            try:
                net.policy.load_state_dict(ckpt["model"])
            except Exception as e:                       # noqa: BLE001
                print(f"[timer] net weights not loaded ({repr(e)[:80]}); timing random weights, same shapes")
            target = _build_net(cfg, device, n_cards, n_cells, threat_dim, in_ch)
            target.load_state_dict(net.state_dict())
            H, W = (obs.shape[0], obs.shape[1]) if obs is not None else (int(cfg.get("env", "obs_size", default=96)),) * 2
            print(f"[timer] net: {rl_path.name} on {device}, obs {in_ch}x{H}x{W}, cards {n_cards}, cells {n_cells}")

            def _mk(b):
                x = torch.rand(b, in_ch, H, W, device=device)
                hand = torch.rand(b, n_cards, device=device)
                nxt = torch.rand(b, n_cards, device=device)
                elx = torch.rand(b, 1, device=device)
                thr = torch.rand(b, threat_dim, device=device)
                return x, hand, nxt, elx, thr

            def _sync():
                if device.type == "cuda":
                    torch.cuda.synchronize()

            fwd = []
            net.eval()
            with torch.no_grad():
                for _ in range(5):
                    net(*_mk(1)); _sync()
                for _ in range(args.net_iters):
                    a = _mk(1); _sync(); t = time.perf_counter(); net(*a); _sync()
                    fwd.append(1000.0 * (time.perf_counter() - t))
            rep["stages_ms"]["net_forward_b1"] = {"n": len(fwd), "p50": round(_q(fwd, .5), 1),
                                                   "p90": round(_q(fwd, .9), 1), "mean": round(st.mean(fwd), 1)}
            print(f"  {'net_forward_b1':14s} n={len(fwd):4d}  p50 {_q(fwd, .5):7.1f} ms  p90 {_q(fwd, .9):7.1f} ms")

            # DDQN optimise-equivalent: batch-64 online forward, target forward (no grad), huber loss,
            # backward, clip, step. Same net, same shapes as train_rl.optimise(); the loss target is
            # synthetic, which changes nothing about the cost.
            import torch.nn.functional as F
            net.train()
            opt = torch.optim.Adam(net.parameters(), lr=1e-5)
            bs = int(cfg.get("train", "batch_size", default=64))
            opt_ms = []
            for i in range(5 + args.net_iters):
                a = _mk(bs); b = _mk(bs)
                _sync(); t = time.perf_counter()
                cq, ceq, gq = net(*a)
                with torch.no_grad():
                    cq2, ceq2, gq2 = target(*b)
                    y = gq2.max(1).values
                q = gq.max(1).values + cq.flatten(1).mean(1) * 0.0 + ceq.flatten(1).mean(1) * 0.0
                loss = F.smooth_l1_loss(q, y)
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 10.0); opt.step(); _sync()
                if i >= 5:
                    opt_ms.append(1000.0 * (time.perf_counter() - t))
            rep["stages_ms"]["ddqn_optimise_b%d" % bs] = {"n": len(opt_ms), "p50": round(_q(opt_ms, .5), 1),
                                                          "p90": round(_q(opt_ms, .9), 1), "mean": round(st.mean(opt_ms), 1)}
            print(f"  {'ddqn_optimise':14s} n={len(opt_ms):4d}  p50 {_q(opt_ms, .5):7.1f} ms  p90 {_q(opt_ms, .9):7.1f} ms  (batch {bs}, {device})")
            rep["net"] = {"ckpt": rl_path.name, "device": str(device), "obs": [in_ch, H, W]}
        except Exception as e:                           # noqa: BLE001
            print(f"[timer] trainer-side timing unavailable: {e!r}")
            rep["errors"]["net"] = repr(e)[:200]

    rep["box_after"] = _box_load()
    print(f"[timer] box after: {rep['box_after']}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rep, indent=1))
        print(f"[timer] wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
