r"""`run.py sim-bench` -- measure simulator throughput on THIS machine.

Runs the real `train_sim` loop for a fixed wall-clock slice at several `--envs`
values and reports matches/second for each, so the setting is chosen from a
measurement instead of a guess.

It is the real training code, not a model of it: same env, same batched inference,
same replay and optimiser step. Only three things are overridden, none of which
touch throughput -- the checkpoint goes to `data/bench/` (your `policy_sim.pt` is
never written), the periodic benchmark eval is off (it would stall the clock), and
per-match logging is quiet.

Read the numbers as EARLY-training throughput: within a short slice, self-play has
not ramped in yet, so a long run sits somewhat lower once league opponents (which
run their own network) start appearing.

Usage (from icebow/):
    .\.venv\Scripts\python.exe run.py sim-bench
    .\.venv\Scripts\python.exe run.py sim-bench --envs 8,16,32,64 --seconds 60
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .hardware import probe, suggest


def _bench_config(cfg, tag: str):
    """A copy of the config that writes nowhere important and does not pause to eval."""
    from ..config import Config
    data = copy.deepcopy(cfg.data)
    data.setdefault("train", {})["sim_checkpoint"] = f"data/bench/policy_bench_{tag}.pt"
    sim = data.setdefault("sim", {})
    sim["eval_every_matches"] = 0                 # an eval mid-slice would measure the eval, not training
    sim["save_every_matches"] = 10 ** 9
    sim["log_every_matches"] = 10 ** 9
    return Config(data=data, root=cfg.root)


def sim_bench(cfg, envs: Optional[str] = None, seconds: float = 45.0, seed: int = 0,
              out: Optional[str] = None, warmup: float = 8.0) -> None:
    try:
        import torch
    except ImportError as exc:  # noqa: BLE001
        print(f"[sim-bench] PyTorch required ({exc}).")
        return
    from ..train_sim import train_sim

    info = probe()
    cur_envs = int(cfg.get("sim", "envs", default=8))
    sug = suggest(info, cur_envs)
    if envs:
        try:
            cand = sorted({int(x) for x in str(envs).replace(";", ",").split(",") if x.strip()})
        except ValueError:
            print(f"[sim-bench] --envs '{envs}' ist keine Liste von Zahlen (z.B. 8,16,32).")
            return
    else:
        cand = sorted(set(sug["bench_candidates"]) | {cur_envs})
    cand = [c for c in cand if 1 <= c <= 128]
    if not cand:
        print("[sim-bench] keine gültigen Env-Zahlen.")
        return

    (cfg.path("data") / "bench").mkdir(parents=True, exist_ok=True)
    print(f"[sim-bench] {info['os']} | {info['cpu_logical']} CPU-Threads | "
          f"{(info['ram_total'] or 0) / 1024 ** 3:.0f} GB RAM | "
          f"{info.get('gpu') or 'keine CUDA-GPU'} | torch {info.get('torch')}", flush=True)
    print(f"[sim-bench] messe {cand} Envs à {seconds:.0f}s (Seed {seed}); "
          f"aktuell konfiguriert: envs={cur_envs}", flush=True)

    if warmup > 0:
        print(f"[sim-bench] Aufwärmen ({warmup:.0f}s, wird verworfen -- CUDA-Kontext + Caches) ...",
              flush=True)
        train_sim(_bench_config(cfg, "warmup"), matches=10 ** 9, seed=seed,
                  envs=min(cand), time_limit_s=warmup, quiet=True)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    results: List[Dict[str, Any]] = []
    for k in cand:
        print(f"[sim-bench] envs={k} ...", flush=True)
        t0 = time.time()
        res = train_sim(_bench_config(cfg, str(k)), matches=10 ** 9, seed=seed, envs=k,
                        time_limit_s=seconds, quiet=True)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if not res:
            continue
        res["wall"] = time.time() - t0
        res["matches_per_hour"] = res["mps"] * 3600.0
        results.append(res)
        print(f"[sim-bench] envs={k:<3} -> {res['mps']:.2f} Matches/s "
              f"({res['matches']} Matches in {res['seconds']:.0f}s, "
              f"{res['matches_per_hour']:,.0f}/h)".replace(",", "."), flush=True)

    if not results:
        print("[sim-bench] keine Messwerte.")
        return
    best = max(results, key=lambda r: r["mps"])
    base = next((r for r in results if r["envs"] == cur_envs), None)
    print("")
    print(f"[sim-bench] SCHNELLSTE Einstellung: envs={best['envs']} mit {best['mps']:.2f} Matches/s "
          f"({best['matches_per_hour']:,.0f} Matches/Stunde)".replace(",", "."), flush=True)
    if base and base["envs"] != best["envs"]:
        print(f"[sim-bench] gegenüber der aktuellen Einstellung (envs={cur_envs}, "
              f"{base['mps']:.2f} m/s): Faktor {best['mps'] / max(1e-9, base['mps']):.2f}x", flush=True)
    elif base:
        print("[sim-bench] die aktuelle Einstellung ist bereits die schnellste gemessene.", flush=True)

    payload = {
        "generated": time.time(), "seconds_per_run": seconds, "seed": seed,
        "hardware": info, "suggestion": sug, "current_envs": cur_envs,
        "results": results, "best_envs": best["envs"], "best_mps": best["mps"],
    }
    out_path = Path(out) if out else cfg.path("data/sim_bench.json")
    if not out_path.is_absolute():
        out_path = cfg.path(str(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"[sim-bench] -> {out_path}", flush=True)
