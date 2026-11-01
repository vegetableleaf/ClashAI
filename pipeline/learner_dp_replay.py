"""MGPU: replay a dumped ppo_update (pipeline.learner_dp.install_dump) on 1 and W GPUs, on the same records: the correctness
compare (weights, update record, steps / KL stop, run-to-run determinism) and the speed of the PPO steps.

        --mode policy --reps 2 --out result.json

value head only, ``critic_warmup_minibatch`` steps), ``policy`` = the same batch as a policy update (``vf.policy`` True, the
production minibatch / micro-batch recipe), ``warm`` = warm-up forced. ``--minibatch`` / ``--micro`` / ``--epochs`` override the
config for a smaller or larger run. Every (world, rep) restarts from the dumped state, so reps and worlds are comparable;
rep 0 is cold (graph capture, allocator), the later reps are the steady state.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MON = ("kl_gate", "kl_card", "kl_cell", "l_pg", "ratio_mean", "clip_frac", "grad_norm_mean", "l_v", "l_v_first", "l_ab")


def flags(deterministic: bool) -> None:
    """"""
    if deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False


def setup(d: dict, dev: str, mode: str, over: dict):
    """-> (model, opt, B, R, cfg, vf, ab, ent_ref, rng, beta): a fresh copy of the dumped call's state on ``dev``."""
    from pipeline import rl_royale as RL
    cfg = {**d["cfg"], **over}
    vf = dict(d["vf"]) if d["vf"] else None
    if vf is not None and mode in ("policy", "warm"):
        vf["policy"] = mode == "policy"
    model = copy.deepcopy(d["model"]).to(dev).eval()
    ref = copy.deepcopy(d["ref"]).to(dev).eval()
    for p in ref.parameters():
        p.requires_grad_(False)
    ent_ref = None if d["ent_ref"] is None else copy.deepcopy(d["ent_ref"]).to(dev).eval()
    opt = getattr(torch.optim, d["opt_cls"])(model.parameters(), lr=float(cfg["lr"]))
    opt.load_state_dict(copy.deepcopy(d["opt"]))
    ab = None
    if d["head"] is not None:
        head = copy.deepcopy(d["head"]).to(dev)
        hopt = torch.optim.Adam(head.parameters(), lr=1e-3)
        hopt.load_state_dict(copy.deepcopy(d["hopt"]))
        ab = {"head": head, "opt": hopt, "ent_coef": d["ab_ent_coef"]}
    B = {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in d["B"].items()}
    if cfg.get("mem_row_cache") and getattr(model, "mem", None) is not None and "mem_row_t" in B:
        B["_mem_cache"] = RL.MemRowCache(len(B["A"]))
    r = d["R"]
    R = RL.LazyRef(ref, B, r["tau"], r["T"], T_gate=r["T_gate"])
    if r["kl_heads"] is not None:
        R["kl_heads"] = tuple(r["kl_heads"])
    rng = np.random.default_rng()
    rng.bit_generator.state = d["rng"]
    return model, opt, B, R, cfg, vf, ab, ent_ref, rng, d["beta"]


def flat(*mods) -> np.ndarray:
    return np.concatenate([p.detach().cpu().numpy().astype(np.float64).reshape(-1) for m in mods for p in m.parameters()])


def summ(u: dict) -> dict:
    out = {k: u.get(k) for k in MON + ("steps", "nonfinite")}
    out["kl_stop"] = u.get("kl_stop")
    out["ent"] = u.get("ent")
    out["first"] = {k: v for k, v in (u.get("first") or {}).items() if isinstance(v, float)}
    return out


def compare(a: dict, b: dict, w0: np.ndarray, wa: np.ndarray, wb: np.ndarray) -> dict:
    """DP run ``b`` vs the single-GPU run ``a``: weights (max abs, relative to the size of the update itself) + monitors."""
    dw = wb - wa
    upd = np.linalg.norm(wa - w0)
    mon = {}
    for k in MON:
        x, y = a["summary"].get(k), b["summary"].get(k)
        if x is not None and y is not None:
            mon[k] = {"single": x, "dp": y, "rel": abs(y - x) / max(abs(x), 1e-12)}
    ks = (lambda r: None if r["summary"]["kl_stop"] is None else
          {q: r["summary"]["kl_stop"][q] for q in ("epoch", "minibatch", "steps")})
    return {"weights_max_abs": float(np.abs(dw).max()), "weights_rms": float(np.sqrt((dw ** 2).mean())),
            "update_norm": float(upd), "diff_over_update_norm": float(np.linalg.norm(dw) / max(upd, 1e-30)),
            "n_weights": int(len(w0)), "steps_equal": a["summary"]["steps"] == b["summary"]["steps"],
            "kl_stop_equal": ks(a) == ks(b), "kl_stop": [ks(a), ks(b)], "monitors": mon,
            "max_monitor_rel": max([m["rel"] for m in mon.values()] or [0.0])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("dump")
    ap.add_argument("--worlds", default="1,2,4")
    ap.add_argument("--devices", default="cuda:0,cuda:1,cuda:2,cuda:3")
    ap.add_argument("--backend", default=None, choices=("nccl", "gloo"))
    ap.add_argument("--mode", default="policy", choices=("dump", "policy", "warm"))
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--minibatch", type=int, default=None)
    ap.add_argument("--micro", type=int, default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--control", type=int, default=1, help="1 = also run single-GPU with micro_batch/2 (the float-noise scale)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    worlds = [int(x) for x in a.worlds.split(",")]
    devs = [x.strip() for x in a.devices.split(",") if x.strip()]
    if max(worlds) > len(devs):
        raise SystemExit(f"--worlds {worlds} needs {max(worlds)} devices, got {devs}")
    d = torch.load(a.dump, map_location="cpu", weights_only=False)
    flags(bool(d["cfg"].get("learner_deterministic")))
    if devs[0].startswith("cuda"):
        torch.cuda.set_device(torch.device(devs[0]))
    from pipeline import learner_dp as DP
    from pipeline import rl_royale as RL
    over = {k: v for k, v in (("minibatch", a.minibatch), ("micro_batch", a.micro), ("ppo_epochs", a.epochs)) if v}
    rows = len(d["B"]["A"])
    print(f"[replay] {a.dump}: call {d['call']}, {rows} rows, mode {a.mode}, cfg minibatch {d['cfg']['minibatch']} micro "
          f"{d['cfg'].get('micro_batch')} epochs {d['cfg']['ppo_epochs']}; worlds {worlds} on {devs}", flush=True)
    res = {"tag": a.tag, "dump": os.path.basename(a.dump), "rows": rows, "mode": a.mode, "devices": devs, "over": over,
           "torch": torch.__version__, "runs": [], "compare": [], "start_s": {}}
    W: dict = {}
    w_init = None
    for world in worlds:
        coord = None if world == 1 else DP.Coordinator(devs[:world], a.backend, log=lambda *x, **k: print(*x, flush=True))
        for rep in range(a.reps):
            model, opt, B, R, cfg, vf, ab, ent_ref, rng, beta = setup(d, devs[0], a.mode, over)
            if w_init is None:
                w_init = flat(model, *([ab["head"]] if ab else []))
            if devs[0].startswith("cuda"):
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats(torch.device(devs[0]))
            t0 = time.perf_counter()
            if coord is None:
                u = RL.ppo_update(model, opt, B, R, cfg, beta, rng, vf=vf, ability=ab, ent_ref=ent_ref)
            else:
                u = coord.ppo_update(RL.ppo_update, model, opt, B, R, cfg, beta, rng, vf=vf, ability=ab, ent_ref=ent_ref)
            if devs[0].startswith("cuda"):
                torch.cuda.synchronize()
            wall = time.perf_counter() - t0
            r = {"world": world, "rep": rep, "wall_s": wall, "summary": summ(u),
                 "gpu_peak_gb": (torch.cuda.max_memory_allocated(torch.device(devs[0])) / 2**30)
                 if devs[0].startswith("cuda") else None}
            if coord is not None:
                r["timing"] = coord.timing[-1]
                if rep == 0:
                    res["start_s"][str(world)] = coord.start_s
            W[(world, rep)] = flat(model, *([ab["head"]] if ab else []))
            res["runs"].append(r)
            print(f"[replay] world {world} rep {rep}: {wall:.1f} s, steps {u['steps']}, kl_stop {u.get('kl_stop')}, "
                  f"{r.get('timing', '')} gpu0 peak {r['gpu_peak_gb']}", flush=True)
            del model, opt, B, R, ab
        if coord is not None:
            coord.close()
    if a.control:                                             # float-noise scale: same math, the micro-batch sum re-associated
        model, opt, B, R, cfg, vf, ab, ent_ref, rng, beta = setup(d, devs[0], a.mode, over)
        half = {**over, "micro_batch": max(1, int(cfg["micro_batch"]) // 2)}
        del model, opt, B, R, ab
        model, opt, B, R, cfg, vf, ab, ent_ref, rng, beta = setup(d, devs[0], a.mode, half)
        u = RL.ppo_update(model, opt, B, R, cfg, beta, rng, vf=vf, ability=ab, ent_ref=ent_ref)
        res["runs"].append({"world": "ctrl", "rep": 0, "wall_s": None, "summary": summ(u)})
        W[("ctrl", 0)] = flat(model, *([ab["head"]] if ab else []))
        del model, opt, B, R, ab
    base = {(r["world"], r["rep"]): r for r in res["runs"]}
    for world in worlds:
        for rep in range(a.reps):
            if (world, rep) == (1, 0) or (1, rep) not in base:
                continue
            c = compare(base[(1, rep)], base[(world, rep)], w_init, W[(1, rep)], W[(world, rep)])
            res["compare"].append({"what": f"world {world} vs world 1, rep {rep}", **c})
    if a.control and (1, 0) in base:
        res["compare"].append({"what": "CONTROL single GPU micro_batch/2 vs micro_batch (re-associated sum, same math)",
                               **compare(base[(1, 0)], base[("ctrl", 0)], w_init, W[(1, 0)], W[("ctrl", 0)])})
    for world in worlds:                                      # run-to-run (same world, same start): identical?
        if a.reps > 1:
            res["compare"].append({"what": f"world {world}: rep 1 vs rep 0 bitwise equal",
                                   "equal": bool(np.array_equal(W[(world, 1)], W[(world, 0)]))})
    Path(a.out).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    for c in res["compare"]:
        print("[replay]", {k: (round(v, 9) if isinstance(v, float) else v) for k, v in c.items() if k != "monitors"}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
