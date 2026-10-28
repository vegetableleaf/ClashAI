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


def producer_main(aid, base: dict, n: int, threads: int, device: str, build: str, in_q, out_q) -> None:
    """aid = (producer index, generation). FASTLOOP_CRASH_TEST=p (recovery test only): each run, with probability p,
    the process kills itself with SIGSEGV after its first round (the libtorch-in-JVM failure RX-X23 saw)."""
    try:
        sys.path.insert(0, str(HERE))
        from producer import Producer
        P = Producer(base, n, threads, device, Path(build), aid[0])
        out_q.put(("ready", aid, os.getpid()))
    except Exception:
        out_q.put(("error", aid, traceback.format_exc()))
        return
    p_crash = float(os.environ.get("FASTLOOP_CRASH_TEST", 0) or 0)
    if p_crash:
        import random
        import signal
        rnd = random.Random(os.getpid())

        def maybe_die(matches, rows, state={"n": 0}):
            state["n"] += 1
            if state["n"] == 50 and rnd.random() < p_crash:
                os.kill(os.getpid(), signal.SIGSEGV)
        P.progress = maybe_die
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

    MAX_RESTARTS = 3                                          # per share and update; then the update fails loudly

    def __init__(self, base: dict, a, log):
        self.log, self.a, self.base = log, a, base
        self.ctx = mp.get_context("spawn")
        self.devs = a.devices.split(",")
        self.out_q = self.ctx.Queue()
        self.in_qs, self.procs, self.gen = [None] * a.producers, [None] * a.producers, [0] * a.producers
        self.restarts = 0
        for k in range(a.producers):
            self._spawn(k)
        self._wait_ready(set(range(a.producers)))
        log(f"[fastloop] {a.producers} producers x {a.matches} matches x {a.threads} threads on {self.devs}")

    def _spawn(self, k: int) -> None:
        """(Re)start producer k with a fresh queue and generation: messages of a dead generation are ignored."""
        self.gen[k] += 1
        q = self.ctx.Queue()
        p = self.ctx.Process(target=producer_main, args=((k, self.gen[k]), self.base, self.a.matches, self.a.threads,
                                                         self.devs[k % len(self.devs)], self.a.build, q, self.out_q),
                             daemon=True)
        p.start()
        self.in_qs[k], self.procs[k] = q, p

    def _wait_ready(self, ks: set) -> None:
        t0 = time.time()
        while ks:
            if time.time() - t0 > 900:
                raise RuntimeError(f"producers {sorted(ks)} not ready after 900 s")
            try:
                msg = self.out_q.get(timeout=10)
            except queue.Empty:
                continue
            (k, g) = msg[1]
            if g != self.gen[k]:
                continue
            if msg[0] == "error":
                raise RuntimeError(f"producer {k} failed to start:\n{msg[2]}")
            if msg[0] == "ready":
                ks.discard(k)

    def _restart(self, k: int, why: str, share, update: int, sd: bytes, tries: dict) -> None:
        """A dead / failed producer: its partial matches are gone with it (a producer returns only whole matches, at the
        end of its share); restart it and replay the whole share (per-match deterministic: the same results)."""
        tries[k] = tries.get(k, 0) + 1
        self.restarts += 1
        self.log(f"[fastloop] producer {k} restart {tries[k]} ({why[-400:]})")
        if tries[k] > self.MAX_RESTARTS:
            raise RuntimeError(f"producer {k} failed {tries[k]} times this update: {why}")
        if self.procs[k].is_alive():
            self.procs[k].kill()
        self._spawn(k)
        self._wait_ready({k})
        self.in_qs[k].put((update, sd, share))

    def run(self, update: int, sd: bytes, jobs: list):
        from pipeline.rl_royale import row_key
        t0 = time.perf_counter()
        if os.environ.get("FASTLOOP_DUMP"):                   # compare.py's input: the exact actor message
            import pickle
            Path(self.a.rl_dir, f"fast_msg_u{update:04d}.pkl").write_bytes(pickle.dumps((self.base, update, sd, jobs)))
        shares = {k: jobs[k::len(self.in_qs)] for k in range(len(self.in_qs)) if jobs[k::len(self.in_qs)]}
        for k, js in shares.items():
            self.in_qs[k].put((update, sd, js))
        results, skipped, stats, tries = [], [], {}, {}
        while len(stats) < len(shares):
            try:
                msg = self.out_q.get(timeout=10)
            except queue.Empty:
                for k in [k for k in shares if k not in stats and not self.procs[k].is_alive()]:
                    self._restart(k, f"process exited {self.procs[k].exitcode}", shares[k], update, sd, tries)
                continue
            (k, g) = msg[1]
            if g != self.gen[k] or k in stats:
                continue                                          # a replaced producer's message
            if msg[0] == "error":
                self._restart(k, msg[2], shares[k], update, sd, tries)
                continue
            if msg[0] != "done":
                continue
            r, s, st = msg[2]
            results += r
            skipped += s
            stats[k] = st
        results.sort(key=row_key)
        wall = time.perf_counter() - t0
        rows = sum(st["rows"] for st in stats.values())
        line = {"update": int(update), "t": time.time(), "matches": len(results), "skipped": len(skipped), "wall_s": wall,
                "producer_restarts_total": self.restarts,
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
