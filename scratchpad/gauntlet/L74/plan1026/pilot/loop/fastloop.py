"""LOOP-INT (plan1026 pilot): the fast crforge training loop's orchestrator. The learner IS rl_royale's (``main``:
config, PPO math, league, screens, checkpoints, STOP, logs all unchanged); only its self-play rollouts are served by
K producer processes (loop/producer.py: an in-process JVM with N CfTrain matches on T threads, production per-side
code, the policy forward on the producer's GPU) instead of ActorPool's actors. Screens / proagree / warm starts stay on
ActorPool (n_actors of the config).

usage (pod, env as LOOP-OPS' launcher sets it: ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux CRFORGE_LIB ...):
  python -u scratchpad/gauntlet/L74/plan1026/pilot/loop/fastloop.py --producers 4 --matches 64 --threads 4 \
      --devices cuda:0,cuda:1 [--build DIR] [--out RUN_DIR] -- --run RUN --config CFG.yaml [k=v ...]
Per update: one line in <rl run dir>/throughput.jsonl (and --out/throughput.jsonl): matches/h, rows/s, per-stage time.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import queue
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
sys.path.insert(0, str(REPO))


def producer_main(aid: int, base: dict, n: int, threads: int, device: str, build: str, in_q, out_q) -> None:
    try:
        sys.path.insert(0, str(HERE))
        from producer import Producer
        P = Producer(base, n, threads, device, Path(build), aid)
        out_q.put(("ready", aid, os.getpid()))
    except Exception:
        out_q.put(("error", aid, traceback.format_exc()))
        return
    while True:
        msg = in_q.get()
        if msg is None:
            return
        update, sd, jobs = msg
        try:
            out_q.put(("done", aid, P.run(update, sd, jobs)))
        except Exception:
            out_q.put(("error", aid, traceback.format_exc()))


class FastPool:
    """K producer processes; ``run`` = ActorPool.run's contract for kind 'selfplay' (results sorted by row_key)."""

    def __init__(self, base: dict, a, log):
        self.log, self.a, self.base = log, a, base
        ctx = mp.get_context("spawn")
        devs = a.devices.split(",")
        self.out_q = ctx.Queue()
        self.in_qs, self.procs = [], []
        for k in range(a.producers):
            q = ctx.Queue()
            p = ctx.Process(target=producer_main, args=(k, base, a.matches, a.threads, devs[k % len(devs)], a.build, q,
                                                         self.out_q), daemon=True)
            p.start()
            self.in_qs.append(q)
            self.procs.append(p)
        ready = 0
        while ready < a.producers:
            msg = self.out_q.get(timeout=900)
            if msg[0] == "error":
                raise RuntimeError(f"producer {msg[1]} failed to start:\n{msg[2]}")
            ready += 1
        log(f"[fastloop] {a.producers} producers x {a.matches} matches x {a.threads} threads on {devs}")

    def run(self, update: int, sd: bytes, jobs: list):
        from pipeline.rl_royale import row_key
        t0 = time.perf_counter()
        if os.environ.get("FASTLOOP_DUMP"):                   # compare.py's input: the exact actor message
            import pickle
            Path(self.a.rl_dir, f"fast_msg_u{update:04d}.pkl").write_bytes(pickle.dumps((self.base, update, sd, jobs)))
        shares = {k: jobs[k::len(self.in_qs)] for k in range(len(self.in_qs)) if jobs[k::len(self.in_qs)]}
        for k, js in shares.items():
            self.in_qs[k].put((update, sd, js))
        results, skipped, stats = [], [], {}
        while len(stats) < len(shares):
            try:
                msg = self.out_q.get(timeout=30)
            except queue.Empty:
                dead = [k for k in shares if not self.procs[k].is_alive()]
                if dead:
                    raise RuntimeError(f"producers {dead} died")
                continue
            if msg[0] == "error":
                raise RuntimeError(f"producer {msg[1]}:\n{msg[2]}")
            r, s, st = msg[2]
            results += r
            skipped += s
            stats[msg[1]] = st
        results.sort(key=row_key)
        wall = time.perf_counter() - t0
        rows = sum(st["rows"] for st in stats.values())
        line = {"update": int(update), "t": time.time(), "matches": len(results), "skipped": len(skipped), "wall_s": wall,
                "matches_per_h": len(results) / wall * 3600 if wall else None, "rows": rows,
                "rows_per_s": rows / wall if wall else None,
                "per_stage_s": {k: sum(st["time"].get(k, 0.0) for st in stats.values()) for k in ("java", "fill", "decide")},
                "java_engine_core_s": sum(st["java_engine_core_s"] for st in stats.values()),
                "java_obs_core_s": sum(st["java_obs_core_s"] for st in stats.values()),
                "producers": stats}
        for d in {self.a.rl_dir, self.a.out} - {None}:
            Path(d).mkdir(parents=True, exist_ok=True)
            with open(Path(d) / "throughput.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(line, default=str) + "\n")
        self.log(f"[fastloop] u{update:04d} {len(results)} matches in {wall:.1f} s = {line['matches_per_h']:.0f} /h, "
                 f"{rows} rows ({line['rows_per_s']:.0f}/s), skipped {len(skipped)}")
        # one_update reads ActorPool's per-actor stats (wall_s, matches, gpu_peak_mb)
        return results, skipped, {f"p{k}": {"wall_s": st["wall_s"], "matches": st["matches"], "gpu_peak_mb": None}
                                  for k, st in stats.items()}

    def close(self):
        for q in self.in_qs:
            q.put(None)


def main() -> int:
    argv = sys.argv[1:]
    cut = argv.index("--") if "--" in argv else len(argv)
    ap = argparse.ArgumentParser()
    ap.add_argument("--producers", type=int, default=2)
    ap.add_argument("--matches", type=int, default=64, help="matches in flight per producer")
    ap.add_argument("--threads", type=int, default=4, help="Java threads per producer")
    ap.add_argument("--devices", default="cuda:0")
    ap.add_argument("--build", default=str(HERE / "jbuild"))
    ap.add_argument("--out", default=None, help="extra dir for throughput.jsonl / STOP / FINAL (LOOP-OPS)")
    a = ap.parse_args(argv[:cut])
    rl_argv = argv[cut + 1:]
    from pipeline import rl_royale as R
    run_name = rl_argv[rl_argv.index("--run") + 1]
    a.rl_dir = str(R.RUN_ROOT / run_name)
    state = {}
    orig_init, orig_run = R.ActorPool.__init__, R.ActorPool.run

    def init(self, base, n, log, *args, **kw):
        orig_init(self, base, n, log, *args, **kw)
        if "fast" not in state:
            state["fast"] = FastPool(base, a, log)

    def run(self, kind, update, sd, jobs, shares=None):
        if kind == "selfplay" and "fast" in state:
            if a.out and (Path(a.out) / "STOP").exists() and not (Path(a.rl_dir) / "STOP").exists():
                (Path(a.rl_dir) / "STOP").write_text("from --out STOP\n")   # rl_royale stops after this update
            return state["fast"].run(update, sd, jobs)
        return orig_run(self, kind, update, sd, jobs, shares)

    R.ActorPool.__init__, R.ActorPool.run = init, run
    try:
        rc = R.main(rl_argv)
    finally:
        if "fast" in state:
            state["fast"].close()
    if a.out:
        ck = sorted((R.CKPT_ROOT / run_name).glob(f"{run_name}_u*.pt"))
        Path(a.out, "FINAL").write_text((str(ck[-1]) if ck else "none") + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
