r"""`run.py sim-bench` -- measure simulator throughput on THIS machine.

Runs the real `train_sim` loop for a fixed wall-clock slice at several `--envs`
values and reports what actually comes out, so the setting is chosen from a
measurement instead of a guess.

It is the real training code, not a model of it: same env, same batched inference,
same replay and optimiser step. Only three things are overridden, none of which
touch throughput -- the checkpoint goes to `data/bench/` (your `policy_sim.pt` is
never written), the periodic benchmark eval is off (it would stall the clock), and
per-match logging is quiet.

Why "more parallel matches" is not simply "better"
--------------------------------------------------
Raising `--envs` does two opposite things at once:

  * matches/second RISES, because the one optimiser step per tick is amortised
    over more matches -- until the engine steps (which share a single core, the
    GIL) dominate and the curve flattens.
  * optimiser steps PER MATCH FALL, in direct proportion. At 8 envs a match is
    covered by roughly 30 gradient updates, at 64 by roughly 4. The same matches
    are then learned from far less often.

So the benchmark reports both, plus updates/second, and `--auto` stops climbing
when throughput stops improving instead of pushing the number as high as it goes.

Usage (from icebow/):
    .\.venv\Scripts\python.exe run.py sim-bench --auto --apply     # find + write it
    .\.venv\Scripts\python.exe run.py sim-bench --envs 8,16,32,64 --seconds 60
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .hardware import free_ram_bytes, probe, rss_bytes, suggest

SAFETY_RAM = 2 * 1024 ** 3          # keep this much free RAM; below it the search stops
MAX_ENVS = 256                      # hard ceiling for the automatic search
NEAR_PEAK = 0.97                    # settings within 3% of the peak count as equally fast


def _bench_config(cfg, tag: str):
    """A copy of the config that writes nowhere important and does not pause to eval."""
    from .config import Config
    data = copy.deepcopy(cfg.data)
    data.setdefault("train", {})["sim_checkpoint"] = f"data/bench/policy_bench_{tag}.pt"
    sim = data.setdefault("sim", {})
    sim["eval_every_matches"] = 0                 # an eval mid-slice would measure the eval, not training
    sim["save_every_matches"] = 10 ** 9
    sim["log_every_matches"] = 10 ** 9
    return Config(data=data, root=cfg.root)


def _run(cfg, k: int, seconds: float, seed: int) -> Optional[Dict[str, Any]]:
    from .train_sim import train_sim
    rss0 = rss_bytes() or 0
    res = train_sim(_bench_config(cfg, str(k)), matches=10 ** 9, seed=seed, envs=k,
                    time_limit_s=seconds, quiet=True)
    if not res:
        return None
    res["rss"] = rss_bytes()
    res["rss_delta"] = (res["rss"] - rss0) if res["rss"] else None
    res["free_ram"] = free_ram_bytes()
    res["matches_per_hour"] = res["mps"] * 3600.0
    res["updates_per_s"] = res["steps"] / max(1e-6, res["seconds"])
    res["updates_per_match"] = res["steps"] / max(1, res["matches"])
    return res


def _fmt(res: Dict[str, Any]) -> str:
    return (f"envs={res['envs']:<4} {res['mps']:5.2f} matches/s  "
            f"{res['matches_per_hour']:8,.0f}/h  "
            f"{res['updates_per_s']:6.1f} learning steps/s  "
            f"{res['updates_per_match']:6.1f} per match".replace(",", "."))


def sim_bench(cfg, envs: Optional[str] = None, seconds: float = 30.0, seed: int = 0,
              out: Optional[str] = None, warmup: float = 8.0, auto: bool = False,
              apply: bool = False) -> None:
    try:
        import torch
    except ImportError as exc:  # noqa: BLE001
        print(f"[sim-bench] PyTorch required ({exc}).")
        return

    info = probe()
    cur_envs = int(cfg.get("sim", "envs", default=8))
    sug = suggest(info, cur_envs)
    (cfg.path("data") / "bench").mkdir(parents=True, exist_ok=True)

    print(f"[sim-bench] {info['os']} | {info['cpu_logical']} CPU-Threads | "
          f"{(info['ram_total'] or 0) / 1024 ** 3:.0f} GB RAM | "
          f"{info.get('gpu') or 'keine CUDA-GPU'} | torch {info.get('torch')}", flush=True)

    if warmup > 0:
        print(f"[sim-bench] warm-up ({warmup:.0f}s, discarded) ...", flush=True)
        _run(cfg, 4, warmup, seed)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    results: List[Dict[str, Any]] = []
    stop_reason = ""

    if auto:
        # Climb by doubling until it stops paying off. Two consecutive rounds without a
        # real gain end it -- one flat step can be measurement noise, two is a plateau.
        print(f"[sim-bench] automatic search: doubling the number of parallel matches until it stops "
              f"getting faster ({seconds:.0f}s each, seed {seed})", flush=True)
        k, best, flat = 4, 0.0, 0
        while k <= MAX_ENVS:
            res = _run(cfg, k, seconds, seed)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if res is None:
                stop_reason = f"the run with {k} envs produced no result"
                break
            results.append(res)
            print("[sim-bench] " + _fmt(res), flush=True)
            gain = (res["mps"] / best - 1.0) if best > 0 else 1.0
            best = max(best, res["mps"])
            free = res.get("free_ram") or 0
            if free and free < SAFETY_RAM:
                stop_reason = (f"only {free / 1024 ** 3:.1f} GB of memory left, "
                               f"going further would be risky")
                break
            flat = flat + 1 if gain < 0.04 else 0
            if flat >= 2:
                stop_reason = "two doublings without a real gain"
                break
            k *= 2
        else:
            stop_reason = f"reached the {MAX_ENVS} limit"
        print(f"[sim-bench] search finished: {stop_reason}", flush=True)
    else:
        if envs:
            try:
                cand = sorted({int(x) for x in str(envs).replace(";", ",").split(",") if x.strip()})
            except ValueError:
                print(f"[sim-bench] --envs '{envs}' ist keine Liste von Zahlen (z.B. 8,16,32).")
                return
        else:
            cand = sorted(set(sug["bench_candidates"]) | {cur_envs})
        cand = [c for c in cand if 1 <= c <= MAX_ENVS]
        if not cand:
            print("[sim-bench] no valid values.")
            return
        print(f"[sim-bench] measuring {cand} envs, {seconds:.0f}s each (seed {seed}); "
              f"currently configured: {cur_envs}", flush=True)
        for k in cand:
            res = _run(cfg, k, seconds, seed)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if res is None:
                continue
            results.append(res)
            print("[sim-bench] " + _fmt(res), flush=True)

    if not results:
        print("[sim-bench] no measurements.")
        return

    peak = max(results, key=lambda r: r["mps"])
    # Among the settings that are equally fast (within 3% of the peak), take the SMALLEST
    # env count. They deliver the same matches per second, but the smaller one runs far
    # more gradient updates per match, so every match is learned from more often. Pushing
    # the number higher buys parallelism nobody benefits from and costs learning signal.
    near = [r for r in results if r["mps"] >= NEAR_PEAK * peak["mps"]]
    rec = min(near, key=lambda r: r["envs"])
    base = next((r for r in results if r["envs"] == cur_envs), None)

    print("")
    print(f"[sim-bench] fastest measurement: {peak['envs']} envs at {peak['mps']:.2f} matches/s",
          flush=True)
    if rec["envs"] != peak["envs"]:
        print(f"[sim-bench] recommendation: {rec['envs']} envs ({rec['mps']:.2f} matches/s). Practically "
              f"the same speed, but {rec['updates_per_match']:.1f} instead of "
              f"{peak['updates_per_match']:.1f} learning steps per match.", flush=True)
    else:
        print(f"[sim-bench] recommendation: {rec['envs']} envs", flush=True)
    if base:
        f = rec["mps"] / max(1e-9, base["mps"])
        print(f"[sim-bench] against the current setting ({cur_envs} envs, "
              f"{base['mps']:.2f} matches/s): factor {f:.2f}", flush=True)
    worst = min(results, key=lambda r: r["updates_per_match"])
    print(f"[sim-bench] for comparison: at {worst['envs']} envs only "
          f"{worst['updates_per_match']:.1f} learning steps per match are left. More parallel matches "
          f"do not automatically mean faster learning.", flush=True)

    payload = {
        "generated": time.time(), "seconds_per_run": seconds, "seed": seed, "auto": bool(auto),
        "hardware": info, "suggestion": sug, "current_envs": cur_envs,
        "results": results, "best_envs": rec["envs"], "best_mps": rec["mps"],
        "peak_envs": peak["envs"], "peak_mps": peak["mps"], "stop_reason": stop_reason,
        "applied": False,
    }

    if apply and rec["envs"] != cur_envs:
        from . import config_edit as editor
        try:
            r = editor.save_config_fields(cfg.path("config/config.yaml"),
                                          {"sim.envs": rec["envs"]},
                                          cfg.path("data/config_backups"))
            payload["applied"] = True
            payload["backup"] = r.get("backup")
            print(f"[sim-bench] sim.envs set from {cur_envs} to {rec['envs']} "
                  f"(backup: {Path(r['backup']).name})", flush=True)
        except Exception as exc:                        # noqa: BLE001
            print(f"[sim-bench] could not apply: {exc}", flush=True)
    elif apply:
        print("[sim-bench] the current setting is already the recommended one.", flush=True)

    out_path = Path(out) if out else cfg.path("data/sim_bench.json")
    if not out_path.is_absolute():
        out_path = cfg.path(str(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"[sim-bench] result written to {out_path}", flush=True)
