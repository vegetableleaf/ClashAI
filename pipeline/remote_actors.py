"""W16 distributed rollouts: one learner's actor jobs spread over the local ``ActorPool`` plus remote actor servers on
other pods (scratchpad/gauntlet/L74/distrib/DISTRIB.md). Opt-in: rl_royale ``remote_actors: <endpoints file>``;
absent = the plain ActorPool, unchanged.

Server, one per extra pod (binds 127.0.0.1; reach it through an SSH tunnel from the learner pod):

    python -m pipeline.remote_actors --port 5601 --workers 24

Sharding: with L local and W_r remote actors the update's job list is dealt ``jobs[a::N]`` over N = L + sum W_r global
actor slots -- exactly ActorPool's deal for ``n_actors = N`` -- slots 0..L-1 local, then each remote's block in endpoint
file order. Every slot's share runs as one ``actor_main`` message (same code, same in-flight batch), so the rows equal a
single-pod run with ``n_actors = N`` (measured: DISTRIB.md). A remote that fails / times out has its shares re-run by
local actors, one share per actor, same batches: never a partial update, never different rows. Transport:
``multiprocessing.connection`` (pickle) with the shared-token HMAC handshake (``RL_REMOTE_TOKEN`` or the gitignored
icebow/data/remote_actors.token); the server refuses a learner whose pipeline/*.py differ from its own.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pickle
import threading
import time
import traceback
from multiprocessing.connection import Client, Listener
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOKEN_FILE = REPO / "icebow" / "data" / "remote_actors.token"
CONNECT_S = 60          # TCP + HMAC handshake; a hung endpoint is skipped (retried every RETRY_EVERY updates)
READY_S = 1200          # the server's ActorPool startup (spawn + runtime import) after the hello
RETRY_EVERY = 5


def token() -> bytes:
    t = os.environ.get("RL_REMOTE_TOKEN") or (TOKEN_FILE.read_text(encoding="utf-8").strip() if TOKEN_FILE.is_file()
                                              else "")
    if len(t) < 16:
        raise SystemExit(f"remote actors need a shared token of >= 16 chars: env RL_REMOTE_TOKEN or {TOKEN_FILE}")
    return t.encode()


def code_hash() -> dict:
    """{pipeline-relative path: sha256} of every pipeline/**/*.py outside tests: the actor code both ends must share."""
    root = REPO / "pipeline"
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*.py")) if "tests" not in p.relative_to(root).parts}


_SHA: dict = {}


def file_sha(p: Path):
    """sha256 of a file (None = missing), cached on (size, mtime_ns)."""
    try:
        st = p.stat()
    except FileNotFoundError:
        return None
    k = (str(p), st.st_size, st.st_mtime_ns)
    if k not in _SHA:
        _SHA[k] = hashlib.sha256(p.read_bytes()).hexdigest()
    return _SHA[k]


def opp_files(kind: str, shares: list) -> dict:
    """{repo-relative path: sha256} of the frozen opponents a self-play share list loads (league snapshots are written
    on the learner pod during the run, so the remote may not have them yet)."""
    if kind != "selfplay":
        return {}
    paths = {j[1]["opp"]["path"] for sh in shares for j in sh}
    return {p: file_sha(REPO / p) for p in sorted(paths)}


def safe_rel(p: str) -> Path:
    q = Path(p)
    if q.is_absolute() or q.anchor or ".." in q.parts:
        raise ValueError(f"refusing to ship a file outside the repo: {p!r}")
    return REPO / q


def deal(jobs: list, n: int) -> list:
    """ActorPool's deal: slot a gets jobs[a::n]."""
    return [jobs[a::n] for a in range(n)]


# ------------------------------------------------------------------------------------------------------
# learner side
# ------------------------------------------------------------------------------------------------------
class Remote:
    def __init__(self, ep: str, conn, workers: int):
        self.ep, self.conn, self.workers = ep, conn, int(workers)

    def run(self, kind, update, sd, shares, timeout_s, log):
        need = opp_files(kind, shares)
        t0 = time.perf_counter()
        self.conn.send(("run", kind, int(update), sd, shares, need))
        t_send = time.perf_counter() - t0
        while True:
            if not self.conn.poll(timeout_s):
                raise TimeoutError(f"no answer in {timeout_s:.0f} s")
            t1 = time.perf_counter()
            buf = self.conn.recv_bytes()                 # = conn.recv(), with the reply's size and read time
            msg = pickle.loads(buf)
            if msg[0] == "files?":
                blob = {p: safe_rel(p).read_bytes() for p in msg[1]}
                log(f"[dist] {self.ep}: shipping {len(blob)} opponent file(s), "
                    f"{sum(map(len, blob.values())) / 2**20:.1f} MB: {sorted(blob)}")
                self.conn.send(("files", blob))
            elif msg[0] == "done":
                return msg[1], msg[2], msg[3], {"send_s": t_send, "mb": len(sd) / 2**20, "recv_mb": len(buf) / 2**20,
                                                "recv_s": time.perf_counter() - t1, "wall_s": time.perf_counter() - t0}
            elif msg[0] == "error":
                raise RuntimeError(f"remote error:\n{msg[1]}")
            else:
                raise RuntimeError(f"unexpected message {msg[0]!r}")

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def _open(ep: str, key: bytes, base: dict, code: dict) -> Remote:
    host, port = ep.rsplit(":", 1)
    conn = Client((host, int(port)), authkey=key)
    conn.send(("hello", base, code))
    if not conn.poll(READY_S):
        conn.close()
        raise TimeoutError(f"server not ready after {READY_S} s")
    msg = conn.recv()
    if msg[0] != "ready":
        conn.close()
        raise RuntimeError(f"server refused: {msg[1]}")
    return Remote(ep, conn, msg[1])


class DistPool:
    """ActorPool's interface (``run``, ``close``, ``pids``, ``n``) over the local pool + the endpoints listed in
    ``endpoints`` (one ``host:port`` per line, ``#`` comments; re-read every run, so pods can be added or removed
    mid-run -- N changes then, logged)."""

    def __init__(self, local, endpoints: Path, base: dict, log, timeout_s: float):
        self.local, self.file, self.base, self.log, self.timeout_s = local, Path(endpoints), base, log, float(timeout_s)
        self.key, self.code = token(), code_hash()
        self.remotes: dict = {}                  # ep -> Remote (connected, ready)
        self.failed: dict = {}                   # ep -> runs left before the next connect attempt
        self.last_n = None
        self._connect()

    @property
    def pids(self):
        return self.local.pids

    @property
    def n(self):
        return self.local.n + sum(r.workers for r in self.remotes.values())

    def endpoints(self) -> list:
        lines = self.file.read_text(encoding="utf-8").splitlines()
        return [x.split("#", 1)[0].strip() for x in lines if x.split("#", 1)[0].strip()]

    def _drop(self, ep: str, why: str) -> None:
        r = self.remotes.pop(ep, None)
        if r is not None:
            r.close()
        self.failed[ep] = RETRY_EVERY
        self.log(f"[dist] REMOTE {ep} DROPPED: {why}")

    def _connect(self) -> None:
        try:
            eps = self.endpoints()
        except OSError as exc:
            self.log(f"[dist] WARNING endpoints file unreadable ({exc}); keeping {sorted(self.remotes)}")
            eps = list(self.remotes)
        for ep in [e for e in self.remotes if e not in eps]:
            self.remotes.pop(ep).close()
            self.log(f"[dist] remote {ep} removed (no longer in {self.file})")
        todo = []
        for ep in eps:
            if ep in self.remotes:
                continue
            if self.failed.get(ep, 0) > 0:
                self.failed[ep] -= 1
                continue
            todo.append(ep)
        got: dict = {}

        def go(ep):
            try:
                got[ep] = _open(ep, self.key, self.base, self.code)
            except BaseException as exc:            # noqa: BLE001 -- any failure = skip this endpoint for now
                got[ep] = exc
        ths = {ep: threading.Thread(target=go, args=(ep,), daemon=True) for ep in todo}
        for t in ths.values():
            t.start()
        t_end = time.time() + CONNECT_S + READY_S
        for ep, t in ths.items():
            t.join(max(0.0, t_end - time.time()))
            r = got.get(ep)
            if isinstance(r, Remote):
                self.remotes[ep] = r
                self.failed.pop(ep, None)
                self.log(f"[dist] remote {ep} connected: {r.workers} workers")
            else:
                self.failed[ep] = RETRY_EVERY
                self.log(f"[dist] WARNING remote {ep} unavailable ({r if r is not None else 'connect timed out'}); "
                         f"retry in {RETRY_EVERY} runs")
        self.remotes = {ep: self.remotes[ep] for ep in eps if ep in self.remotes}   # endpoint file order = slot order

    def run(self, kind: str, update: int, sd: bytes, jobs: list):
        self._connect()
        L = self.local.n
        rem = list(self.remotes.values())
        N = L + sum(r.workers for r in rem)
        if N != self.last_n:
            self.log(f"[dist] {N} actor slots: local {L} + " + (", ".join(f"{r.ep} {r.workers}" for r in rem) or "none"))
            self.last_n = N
        shares = deal(jobs, N)
        plan, off = [], L
        for r in rem:
            plan.append((r, off, shares[off:off + r.workers]))
            off += r.workers
        out: dict = {}

        def go(r, sh):
            try:
                out[r.ep] = r.run(kind, update, sd, sh, self.timeout_s, self.log)
            except BaseException as exc:            # noqa: BLE001 -- reported + re-run locally below
                out[r.ep] = exc
        ths = [(r, threading.Thread(target=go, args=(r, sh), daemon=True)) for r, _, sh in plan if any(sh)]
        for _, t in ths:
            t.start()
        t0 = time.perf_counter()
        results, skipped, stats = self.local.run(kind, update, sd, jobs,
                                                 shares={a: shares[a] for a in range(L)})
        t_local = time.perf_counter() - t0
        for r, t in ths:
            t.join(self.timeout_s + 60)
        notes = [f"local {t_local:.0f}s"]
        for r, o, sh in plan:
            if not any(sh):
                continue
            got = out.get(r.ep)
            if isinstance(got, tuple):
                res, sk, st, tx = got
                results += res
                skipped += sk
                stats.update({o + int(a): s for a, s in st.items()})
                notes.append(f"{r.ep} {tx['wall_s']:.0f}s (send {tx['mb']:.1f} MB in {tx['send_s']:.1f}s, rows "
                             f"{tx['recv_mb']:.0f} MB read in {tx['recv_s']:.1f}s)")
                continue
            why = f"{type(got).__name__}: {got}" if got is not None else "thread still running past the timeout"
            self._drop(r.ep, why)
            self.log(f"[dist] FAILOVER u{update} {kind}: re-running {r.ep}'s {sum(map(len, sh))} jobs "
                     f"({len(sh)} shares) on the local actors, one share per actor (same rows)")
            t1 = time.perf_counter()
            for c in range(0, len(sh), L):
                chunk = sh[c:c + L]
                res, sk, st = self.local.run(kind, update, sd, jobs, shares=dict(enumerate(chunk)))
                results += res
                skipped += sk
                stats.update({o + c + int(a): s for a, s in st.items()})
            notes.append(f"{r.ep} FAILED -> local re-run {time.perf_counter() - t1:.0f}s")
        if len(results) + len(skipped) != len(jobs):     # never a silent partial update
            raise RuntimeError(f"[dist] u{update} {kind}: {len(results)} rows + {len(skipped)} skipped != "
                               f"{len(jobs)} jobs")
        from pipeline.rl_royale import row_key
        results.sort(key=row_key)                       # ActorPool.run's order
        self.log(f"[dist] u{update} {kind} {len(jobs)} jobs over {N} slots: " + "; ".join(notes))
        return results, skipped, stats

    def close(self) -> None:
        for r in self.remotes.values():
            r.close()
        self.local.close()


# ------------------------------------------------------------------------------------------------------
# server side
# ------------------------------------------------------------------------------------------------------
def _log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def _serve_conn(conn, st: dict, workers: int, timeout_s: float, code: dict) -> None:
    from pipeline import rl_royale as RL
    while True:
        msg = conn.recv()
        if msg[0] == "hello":
            _, base, lcode = msg
            diff = sorted(k for k in set(code) | set(lcode) if code.get(k) != lcode.get(k))
            if diff:
                conn.send(("refuse", f"pipeline code differs from the learner's: {diff[:12]}"))
                _log(f"REFUSED a learner: code differs {diff[:12]}")
                return
            if st["pool"] is None or st["base"] != base:
                if st["pool"] is not None:
                    st["pool"].close()
                st["pool"], st["base"] = None, None
                t = time.perf_counter()
                st["pool"] = RL.ActorPool(base, workers, _log, timeout_s)
                st["base"] = base
                _log(f"ActorPool of {workers} ready in {time.perf_counter() - t:.0f}s")
            conn.send(("ready", workers))
        elif msg[0] == "run":
            _, kind, update, sd, shares, need = msg
            miss = [p for p, h in need.items() if file_sha(safe_rel(p)) != h]
            if miss:
                conn.send(("files?", miss))
                tag, blob = conn.recv()
                for p, b in blob.items():
                    dst = safe_rel(p)
                    if hashlib.sha256(b).hexdigest() != need[p]:
                        raise RuntimeError(f"shipped {p} does not match its sha")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dst.with_name(dst.name + ".w16tmp")
                    tmp.write_bytes(b)
                    os.replace(tmp, dst)                 # a new inode: never writes through a hard link
                _log(f"received {len(blob)} file(s): {sorted(blob)}")
            t = time.perf_counter()
            try:
                res, sk, sts = st["pool"].run(kind, update, sd, [], shares=dict(enumerate(shares)))
            except Exception:
                tb = traceback.format_exc()
                st["pool"].close()
                st["pool"], st["base"] = None, None
                conn.send(("error", tb))
                _log(f"u{update} {kind}: ERROR, pool closed\n{tb}")
                return
            conn.send(("done", res, sk, sts))
            _log(f"u{update} {kind}: {sum(map(len, shares))} jobs in {time.perf_counter() - t:.0f}s")
        else:
            raise RuntimeError(f"unexpected message {msg[0]!r}")


def serve(port: int, workers: int, timeout_s: float, host: str = "127.0.0.1") -> None:
    from multiprocessing import AuthenticationError
    key, code = token(), code_hash()
    st = {"pool": None, "base": None}               # kept across learner connections (a reconnect is instant)
    with Listener((host, int(port)), authkey=key) as ls:
        _log(f"remote actor server on {host}:{port}, {workers} workers, code {hashlib.sha256(repr(code).encode()).hexdigest()[:12]}")
        while True:
            try:
                conn = ls.accept()
            except (AuthenticationError, OSError, EOFError) as exc:
                _log(f"rejected a connection: {type(exc).__name__}: {exc}")
                continue
            _log("learner connected")
            try:
                _serve_conn(conn, st, workers, timeout_s, code)
            except (EOFError, OSError) as exc:
                _log(f"learner gone ({type(exc).__name__})")
            except Exception:
                _log(traceback.format_exc())
            finally:
                conn.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="W16 remote actor server")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--workers", type=int, required=True)
    ap.add_argument("--timeout-s", type=float, default=3600.0, help="per-actor timeout (rl_royale actor_timeout_s)")
    ap.add_argument("--host", default="127.0.0.1", help="bind address; default loopback = SSH-tunnel only")
    a = ap.parse_args(argv)
    serve(a.port, a.workers, a.timeout_s, a.host)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
