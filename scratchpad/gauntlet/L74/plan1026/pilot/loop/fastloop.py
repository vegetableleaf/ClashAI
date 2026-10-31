"""LOOP-INT (plan1026 pilot): the fast crforge training loop's orchestrator. The learner IS rl_royale's (``main``:
config, PPO math, league, screens, checkpoints, STOP, logs all unchanged); only its self-play rollouts are served by
K producer processes (loop/producer.py: an in-process JVM with N CfTrain matches on T threads, production per-side
code, the policy forward on the producer's GPU) instead of ActorPool's actors. Screens / proagree / warm starts stay on
ActorPool (n_actors of the config).

usage (pod, env as LOOP-OPS' launcher sets it: ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux CRFORGE_LIB ...):
  python -u scratchpad/gauntlet/L74/plan1026/pilot/loop/fastloop.py --producers 4 --matches 64 --threads 4 \
      --devices cuda:0,cuda:1 [--server eager|graphs] [--build DIR] [--out RUN_DIR] -- --run RUN --config CFG.yaml [k=v ...]
Per update: one line in <rl run dir>/throughput.jsonl (and --out/throughput.jsonl): matches/h, rows/s, per-stage time.
--server: the forwards run on one LOOP-SRV serve.py per device (started at the first rollout with that update's opponent
checkpoints; the learner's weights of each update are pushed to its watch dir), producers on CPU; the learner rows then
carry the server's v_old / wver (rl_royale stored_values). Without it: in-process forwards on each producer's device.
A top-level ``fastloop:`` block in the config (pilot.yaml) is stripped before rl_royale loads it (rl_royale refuses
unknown keys); this script's own flags decide the loop shape.
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


def producer_main(aid, base: dict, n: int, threads: int, device: str, build: str, in_q, out_q, server=None,
                  local: bool = False) -> None:
    """aid = (producer index, generation). FASTLOOP_CRASH_TEST=p (recovery test only): each run, with probability p,
    the process kills itself with SIGSEGV after its first round (the libtorch-in-JVM failure RX-X23 saw)."""
    try:
        sys.path.insert(0, str(HERE))
        from producer import Producer
        # --local-forward: the forwards that stay in-process with --server (timing heads, 'live' seats) on ``device``
        P = Producer(base, n, threads, device if (local or not server) else "cpu", Path(build), aid[0], server=server)
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
        update, sd, jobs, ver = msg
        try:
            out_q.put(("done", aid, P.run(update, sd, jobs, ver)))
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
        self.restarts = self.prefetch_miss = 0
        self.servers, self.srv_root = [], Path(f"/dev/shm/fastloop_{os.getpid()}")
        self.started = False

    def _start(self, jobs) -> None:
        """At the first rollout: the servers (opponents = this update's checkpoints), then the producers."""
        a = self.a
        if a.server:
            sys.path.insert(0, str(HERE))
            from bench import start_servers
            import torch
            torch.backends.cudnn.allow_tf32 = torch.backends.cuda.matmul.allow_tf32 = False
            self.servers = start_servers({**self.base, "init_path": a.init, "mem_full": a.mem_full}, -1, None, jobs, self.devs, a.server,
                                         a.matches, str(self.srv_root), push=False)
        for k in range(a.producers):
            self._spawn(k)
        self._wait_ready(set(range(a.producers)))
        self.started = True
        self.log(f"[fastloop] {a.producers} producers x {a.matches} matches x {a.threads} threads on {self.devs}"
                 + (f", forwards on {len(self.servers)} serve.py ({a.server})" if a.server else ""))

    def _push(self, ver: int, sd: bytes) -> None:
        """Learner weights of version ``ver`` (updates done) -> the servers' watch dir (serve.py loads learner.vN +
        learner.latest; an equal version is not reloaded). Called only between waves: no producer is mid-share, so
        every wave sees ONE version (policy_server.push flips its copies atomically besides)."""
        import torch
        from pipeline import rl_royale as R
        wd = self.srv_root / "weights"
        wd.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(HERE))
        from producer import server_version
        msd, _ = R.split_actor_sd(sd, "cpu")             # the ability head's tensors ride along (policy_server._load)
        v = server_version(ver, any(k.startswith(R.ABILITY_SD) for k in msd))
        tmp = wd / f".learner.v{v:08d}.pt"
        torch.save({"version": v, "state_dict": msd}, tmp)
        os.replace(tmp, wd / f"learner.v{v:08d}.pt")
        (wd / "learner.latest").write_text(str(v))
        for old in sorted(wd.glob("learner.v*.pt"))[:-2]:
            old.unlink(missing_ok=True)

    def _spawn(self, k: int) -> None:
        """(Re)start producer k with a fresh queue and generation: messages of a dead generation are ignored."""
        self.gen[k] += 1
        q = self.ctx.Queue()
        srv = f"{self.srv_root}/srv{k % len(self.devs)}.sock" if self.a.server else None
        p = self.ctx.Process(target=producer_main, args=((k, self.gen[k]), self.base, self.a.matches, self.a.threads,
                                                         self.devs[k % len(self.devs)], self.a.build, q, self.out_q, srv,
                                                         bool(self.a.local_forward)),
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

    def _restart(self, k: int, why: str, share, update: int, sd: bytes, tries: dict, ver: int) -> None:
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
        self.in_qs[k].put((update, sd, share, ver))

    def run(self, update: int, sd: bytes, jobs: list):
        return self.collect(self.submit(update, sd, jobs, update))

    def submit(self, update: int, sd: bytes, jobs: list, ver: int) -> dict:
        """Start one wave, non-blocking: ``update``'s jobs (their seeds) played with the learner weights ``sd`` of weight
        version ``ver`` (= updates done when ``sd`` was taken: ``update`` itself, or update - 1 for an --overlap
        prefetch). One wave at a time. -> the handle for ``collect``."""
        if getattr(self, "busy", False):
            raise RuntimeError("FastPool.submit: a wave is still in flight (collect it first)")
        t0 = time.perf_counter()
        if os.environ.get("FASTLOOP_DUMP"):                   # compare.py's input: the exact actor message
            import pickle
            out = Path(self.a.rl_dir, f"fast_msg_u{update:04d}.pkl")
            if out.exists():                                  # a 2nd message of one update (B6 warm start, then u0000)
                out = out.with_name(f"fast_msg_u{update:04d}_{time.time_ns()}.pkl")
            out.write_bytes(pickle.dumps((self.base, update, sd, jobs)))
        if self.a.server:
            self._push(ver, sd)
        if not self.started:
            self._start(jobs)
        shares = {k: jobs[k::len(self.in_qs)] for k in range(len(self.in_qs)) if jobs[k::len(self.in_qs)]}
        for k, js in shares.items():
            self.in_qs[k].put((update, sd, js, ver))
        self.busy = True
        return {"update": update, "sd": sd, "jobs": jobs, "ver": ver, "shares": shares, "t0": t0}

    def collect(self, h: dict):
        """Wait for the wave ``h`` (restarting dead producers, replaying their share) -> ActorPool.run's triple."""
        from pipeline.rl_royale import row_key
        update, sd, ver, shares, t0 = h["update"], h["sd"], h["ver"], h["shares"], h["t0"]
        tw = time.perf_counter()
        results, skipped, stats, tries = [], [], {}, {}
        while len(stats) < len(shares):
            try:
                msg = self.out_q.get(timeout=10)
            except queue.Empty:
                for k in [k for k in shares if k not in stats and not self.procs[k].is_alive()]:
                    self._restart(k, f"process exited {self.procs[k].exitcode}", shares[k], update, sd, tries, ver)
                continue
            (k, g) = msg[1]
            if g != self.gen[k] or k in stats:
                continue                                          # a replaced producer's message
            if msg[0] == "error":
                self._restart(k, msg[2], shares[k], update, sd, tries, ver)
                continue
            if msg[0] != "done":
                continue
            r, s, st = msg[2]
            results += r
            skipped += s
            stats[k] = st
        self.busy = False
        results.sort(key=row_key)
        for r in results:                                     # every row's server weight version = the one sent (LOOP-SRV)
            w = (r.get("traj") or {}).get("wver")
            if w is not None and len(w) and any(int(x) != int(ver) for x in set(w.tolist())):
                raise RuntimeError(f"u{update:04d} {r.get('tag')}: rows at wver {sorted(set(w.tolist()))}, sent v{ver}")
        label = any(bool(r["traj"]["ab_cand"].any()) for r in results if "ab_cand" in (r.get("traj") or {}))
        if os.environ.get("FASTLOOP_RECORDS") and not label:   # LOOP-LRN: this update's rollout (traj: lp_*, v_old, wver);
            import pickle                                     # not the B6 warm start's label rollouts (no PPO rows)
            rd = Path(os.environ["FASTLOOP_RECORDS"])
            rd.mkdir(parents=True, exist_ok=True)
            out = rd / f"records_u{update:04d}.pkl"
            if out.exists():                                  # the B6 warm start's call, then u0000's
                out = out.with_name(f"records_u{update:04d}_{time.time_ns()}.pkl")
            out.write_bytes(pickle.dumps({"update": int(update), "results": results, "skipped": skipped},
                                         protocol=pickle.HIGHEST_PROTOCOL))
        wall = time.perf_counter() - t0
        rows = sum(st["rows"] for st in stats.values())
        line = {"update": int(update), "t": time.time(), "matches": len(results), "skipped": len(skipped), "wall_s": wall,
                "producer_restarts_total": self.restarts,
                "matches_per_h": len(results) / wall * 3600 if wall else None, "rows": rows,
                "rows_per_s": rows / wall if wall else None,
                "per_stage_s": {k: sum(st["time"].get(k, 0.0) for st in stats.values()) for k in ("java", "fill", "decide")},
                "java_engine_core_s": sum(st["java_engine_core_s"] for st in stats.values()),
                "java_obs_core_s": sum(st["java_obs_core_s"] for st in stats.values()),
                **({"behaviour_ver": int(ver), "staleness": int(update) - int(ver),
                    "wait_s": time.perf_counter() - tw, "wave_s": max((st["wall_s"] for st in stats.values()), default=0.0),
                    "prefetch_miss": self.prefetch_miss} if self.a.overlap is not None else {}),
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
            if q is not None:
                q.put(None)
        for s in self.servers:
            s.kill()


def match_rng(cfg: dict, u: int):
    """--overlap: update u's matchup stream, a function of (seed, u) only -- the learner's rng then draws only minibatch
    orders, and the wave of u+1 can be drawn before update u's PPO steps (their count varies with kl_stop)."""
    import zlib
    import numpy as np
    return np.random.default_rng(zlib.crc32(f"overlap:{int(cfg['seed'])}:{int(u)}".encode()))


def install(R, a, state: dict, pool=FastPool) -> None:
    """Route rl_royale's self-play rollouts to ``pool`` (FastPool): ActorPool.run('selfplay') -> pool.collect(pool.submit).
    --overlap (OVERLAP.md): Learner.rollout(u) draws u's matchups from match_rng(u) (production's rollout code itself,
    its rng swapped for the call), and with --overlap 1, right after it returns (league ratings updated), submits update
    u+1's wave with the CURRENT weights (version u) -- it plays while one_update(u) learns. rollout(u+1)'s own actors.run
    then collects that wave if its jobs are the ones it asks for, else drains it and plays the asked jobs now
    (prefetch_miss; e.g. a league snapshot taken by update u). Absent: the alternating loop, unchanged."""
    orig_init, orig_run, orig_rollout = R.ActorPool.__init__, R.ActorPool.run, R.Learner.rollout
    stop = (lambda: (Path(a.rl_dir) / "STOP").exists() or bool(a.out and (Path(a.out) / "STOP").exists()))

    def init(self, base, n, log, *args, **kw):
        orig_init(self, base, n, log, *args, **kw)
        if "fast" not in state:
            state["fast"] = pool(base, a, log)

    def run(self, kind, update, sd, jobs, shares=None):
        if kind == "selfplay" and "fast" in state:
            if a.out and (Path(a.out) / "STOP").exists() and not (Path(a.rl_dir) / "STOP").exists():
                (Path(a.rl_dir) / "STOP").write_text("from --out STOP\n")   # rl_royale stops after this update
            fp, pend = state["fast"], state.pop("pending", None)
            if pend is not None:
                if pend["update"] == update and pend["jobs"] == jobs:
                    return fp.collect(pend)                    # the overlapped wave: played with version pend["ver"]
                fp.collect(pend)                               # not the jobs asked for: drained and dropped
                fp.prefetch_miss += 1
                fp.log(f"[fastloop] overlap: prefetched wave u{pend['update']:04d} dropped (asked u{update:04d}, jobs "
                       f"{'equal' if pend['jobs'] == jobs else 'differ'}); prefetch_miss {fp.prefetch_miss}")
            return fp.collect(fp.submit(update, sd, jobs, update))
        return orig_run(self, kind, update, sd, jobs, shares)

    def rollout(self, u):
        cfg = self.cfg
        if getattr(self, "league", None) is None:
            raise SystemExit("--overlap: league self-play only (the fast loop serves 'selfplay')")
        if a.overlap == 1 and not (a.server and cfg.get("stored_values")):
            raise SystemExit("--overlap 1 needs --server and stored_values (the behaviour lp_old / v_old / wver rows)")
        if a.overlap == 1 and cfg.get("kl_stop_prev") is not None and cfg.get("kl_ref_refresh_every") != 1:
            raise SystemExit("--overlap 1 with kl_stop_prev needs kl_ref_refresh_every 1 (KL stop to the update-start policy)")
        rng, self.rng = self.rng, match_rng(cfg, u)
        try:
            out = orig_rollout(self, u)
        finally:
            self.rng = rng
        if a.overlap == 1 and u + 1 < int(cfg["max_updates"]) and not stop():
            specs = R.sample_matchups(match_rng(cfg, u + 1), int(cfg["E"]), u + 1, self.league["snapshots"], cfg,
                                      self.census, self.census_p,     # = production rollout's call (a miss is caught)
                                      **({"league_state": self.league} if cfg.get("league_pfsp") == "hard" else {}),
                                      exploiters=getattr(self, "exploiters", None))
            jobs = [(i, sp, g) for i, sp in enumerate(specs) for g in range(int(cfg["G"]))]
            state["pending"] = state["fast"].submit(u + 1, self._actor_bytes(), jobs, int(self.update))
        return out

    R.ActorPool.__init__, R.ActorPool.run = init, run
    if a.overlap is not None:
        R.Learner.rollout = rollout


def start_mps(d: str) -> None:
    """A private MPS control daemon: only processes with this CUDA_MPS_PIPE_DIRECTORY (this one and its children) join;
    other CUDA users of the machine are untouched. Quit at exit."""
    import atexit
    import subprocess
    pipe, logd = Path(d, "pipe"), Path(d, "log")
    pipe.mkdir(parents=True, exist_ok=True)
    logd.mkdir(parents=True, exist_ok=True)
    os.environ["CUDA_MPS_PIPE_DIRECTORY"], os.environ["CUDA_MPS_LOG_DIRECTORY"] = str(pipe), str(logd)
    subprocess.run(["nvidia-cuda-mps-control", "-d"], check=True)
    # quit WITHOUT waiting: "quit" blocks until every client is gone, and this process is one of them (31892 rs_full3:
    # a blocking quit at exit hung fastloop for 15 min after its last update)
    atexit.register(lambda: subprocess.Popen(["sh", "-c", "echo quit | nvidia-cuda-mps-control"], start_new_session=True))
    print(f"[fastloop] CUDA MPS daemon started (pipe {pipe})", flush=True)


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
    ap.add_argument("--server", default=None, help="eager | graphs: forwards on LOOP-SRV serve.py, one per device")
    ap.add_argument("--local-forward", action="store_true",
                    help="with --server: the producers' in-process forwards (timing-head / 'live' groups, which never go to "
                         "serve.py) run on the producer's --devices entry instead of its CPU (absent = CPU, as before)")
    ap.add_argument("--overlap", type=int, choices=(0, 1), default=None,
                    help="OVERLAP.md: 1 = the next wave plays while the learner trains (one version stale); 0 = its "
                         "synchronous control (same matchup stream); absent = production's alternating loop")
    ap.add_argument("--mps", default=None, metavar="DIR",
                    help="ROLLOUT-SPEED: start a private CUDA MPS daemon (pipe / log dirs under DIR) before any CUDA use; "
                         "every process of the run (learner, serve.py, producers) shares the GPU through it, quit at exit. "
                         "31892: 3.5k -> 9.5k rows/s per GPU (LOOP_INT STATUS). Absent = no MPS, as before")
    a = ap.parse_args(argv[:cut])
    rl_argv = argv[cut + 1:]
    if a.mps:
        start_mps(a.mps)
    from pipeline import rl_royale as R
    run_name = rl_argv[rl_argv.index("--run") + 1]
    import yaml
    ci = rl_argv.index("--config") + 1
    cfg = yaml.safe_load(Path(rl_argv[ci]).read_text())
    a.init = cfg["init"]                                  # the server's learner architecture (weights come per update)
    em, sn = cfg.get("memory_e_max"), cfg.get("memory_board_snap")   # MEM-FULL: rl_royale widens the init (serve.py too)
    a.mem_full = f"{em or 128},{int(bool(sn))}" if em is not None or sn else ""
    if "fastloop" in cfg:                                 # pilot.yaml's block: this script's business, not rl_royale's
        stripped = Path(a.out or R.RUN_ROOT) / f"{run_name}.fastloop_stripped.yaml"
        stripped.parent.mkdir(parents=True, exist_ok=True)
        stripped.write_text(yaml.safe_dump({k: v for k, v in cfg.items() if k != "fastloop"}, sort_keys=False))
        print(f"[fastloop] config {rl_argv[ci]}: fastloop block {cfg['fastloop']} stripped -> {stripped}", flush=True)
        rl_argv[ci] = str(stripped)
    a.rl_dir = str(R.RUN_ROOT / run_name)
    state = {}
    install(R, a, state)
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
