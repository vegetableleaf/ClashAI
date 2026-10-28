"""Asynchronous GPU decide server (plan1026 Pillar 4b, ticket S4): no per-step barrier.

Producers (crforge cohorts, RoyaleSim workers, a recorded stream) ``submit`` row blocks whenever they have them and get a
``Future`` of the block's decisions. One server thread repeatedly takes WHATEVER is queued (up to ``max_batch`` rows;
it waits at most ``wait_ms`` for a fuller batch), runs ONE forward for all of it, then the decide of plan1026 P1
(``decision_options.decide``, decode 'sample', each row drawing from its own rng) with the cell logits of the rows that
place computed from the same forward's encodings (one forward per decision). Results go back per block. A slow
producer never holds up the others; there is no cohort and no round.

The rows a block gets do not depend on which other blocks share its batch (each row draws only from its own rng; the
forward is per-row math), up to float noise of the batch composition -- ``tests/test_policy_server.py`` checks the
actions against the same decide run block by block.

Forward modes: eager; ``graphs`` = CUDA graphs captured per padded batch bucket (static buffers; padding rows are
copies of row 0 and are dropped); ``compile`` = torch.compile(mode="max-autotune-no-cudagraphs") of the same call.

``PolicyServer`` (LOOP-SRV, the fast loop's server; S4b's ``ProcServer`` is its one-model form): producer processes
decide; one server per GPU forwards SEVERAL models (the learner and the frozen opponent pool, any architecture or
feature version, each batched on its own), hot-swaps the learner's weight versions (every row is tagged with the
version that produced it) and answers cell / ability-head calls from the same batch's encodings and weights.
"""
from __future__ import annotations

import contextlib
import copy
import os
import queue
import threading
import time
from collections import deque
from concurrent.futures import Future
from pathlib import Path
from typing import Optional

import numpy as np
import torch

BUCKETS = (64, 128, 256, 512, 1024, 2048, 4096, 8192)
# PolicyServer: every batch is padded to one of these (a new shape costs ~210 ms on first use, SPEED.md j5); steps of
# 1/4-1/2 above 512 keep the padding waste low where the GPU is saturated
BUCKETS_FINE = (64, 128, 192, 256, 384, 512, 768, 1024, 1280, 1536, 1792, 2048, 2560, 3072, 3584, 4096)


def bucket(n: int, buckets=BUCKETS) -> int:
    for b in buckets:
        if n <= b:
            return b
    raise ValueError(f"batch {n} > {buckets[-1]}")


def configure(precision: str = "fp32", deterministic: bool = False):
    """Process-wide numerics. ``fp32`` (default, the identical path): no TF32 in matmuls NOR in cuDNN convolutions
    (cell_refine's convs: torch's cudnn.allow_tf32 defaults to True); ``tf32``: both on; ``bf16``: TF32 off, the
    Forward autocasts. ``deterministic``: deterministic algorithms + a fixed cuBLAS workspace (set before the first
    cuBLAS call of the process, i.e. before any forward)."""
    if precision not in ("fp32", "tf32", "bf16"):
        raise ValueError(precision)
    torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = precision == "tf32"
    if deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark = True, False


_TF_CONST: dict = {}


def _graph_safe_tower_features(sc):
    """tower_refine.tower_features with its two constant rows cached on the device (the original builds them with
    ``sc.new_tensor(list)``, a pageable host copy that CUDA-graph capture refuses). Same values, same ops after."""
    alive = sc[:, 64:70] > .5
    raw = sc[:, 52:58]
    known = (sc[:, 58:64] > .5) & alive & torch.isfinite(raw)
    hp = torch.where(known, raw, torch.zeros_like(raw))
    b = len(sc)
    key = (sc.device, sc.dtype)
    if key not in _TF_CONST:
        _TF_CONST[key] = (sc.new_tensor([0., 0, 0, 1, 1, 1]), sc.new_tensor([0., 1, 1, 0, 1, 1]))
    side, kind = (t.expand(b, -1) for t in _TF_CONST[key])
    return torch.stack([side, kind, hp, known.to(sc.dtype), alive.to(sc.dtype)], -1), alive


class Forward:
    """``policy`` (an e1_eval.GenPolicy, or batched_rollout.LazyRefine of one) as one device call on a dict of numpy
    arrays -> (enc, heads, p [n] float64 or None for a model without a gate, hand bool [n, 8]); ``mode`` eager /
    graphs / compile. ``pad``: pad to ``buckets`` (default: every mode but eager); ``graph_max``: graphs mode replays
    a graph only up to this bucket (eager above); ``precision`` bf16 = autocast. ``last_graph``: the last call's
    outputs are a graph's static buffers (the next replay overwrites them)."""

    def __init__(self, policy, device: str = "cuda", mode: str = "eager", buckets=BUCKETS, pad: Optional[bool] = None,
                 graph_max: float = float("inf"), precision: str = "fp32", pool=None):
        from pipeline import e1_eval as E
        self.E, self.policy, self.device, self.mode = E, policy, device, mode
        self.keys = E.gen_row_keys(policy.model)
        self.graphs: dict = {}
        self.buckets, self.pad, self.graph_max = tuple(buckets), mode != "eager" if pad is None else pad, graph_max
        self.amp = (lambda: torch.autocast("cuda", dtype=torch.bfloat16)) if precision == "bf16" else contextlib.nullcontext
        self.last_graph = False
        self.pool = pool                # a graph memory pool shared with other Forwards (PolicyServer: one per server)
        if mode == "graphs":                                       # the one host copy inside the CLXIII forward
            from pipeline import tower_refine
            _graph_safe_tower_features(torch.zeros(1, 70, device=device))
            tower_refine.tower_features = _graph_safe_tower_features
        self.fn = policy.heads_t if not hasattr(policy, "pol") else self._lazy_heads
        if mode == "compile":
            self.fn = torch.compile(self.fn, mode="max-autotune-no-cudagraphs", dynamic=False)

    def _lazy_heads(self, b):
        """LazyRefine's forward without its own stacking (the cell-only features are added back in cell_logits)."""
        lz, m = self.policy, self.policy.model
        if getattr(lz, "fwd_pol", None) is not None:      # LazyRefine.split(): the refine-free copy, nothing swapped
            enc, heads = lz.fwd_pol.heads_t(b)
            if lz.cr is not None:
                enc["_xy"], enc["_mask"] = b["tok"][..., 4:6], b["mask"]
            if lz.tr is not None:
                enc["_sc"] = b["sc"]
            return enc, heads
        if lz.cr is not None:
            m.cell_refine = None
        if lz.tr is not None:
            lz.tr.use_cell = False
        try:
            enc, heads = lz.pol.heads_t(b)
        finally:
            if lz.cr is not None:
                m.cell_refine = lz.cr
            if lz.tr is not None:
                lz.tr.use_cell = True
        if lz.cr is not None:
            enc["_xy"], enc["_mask"] = b["tok"][..., 4:6], b["mask"]
        if lz.tr is not None:
            enc["_sc"] = b["sc"]
        return enc, heads

    def _post(self, enc, heads, b, n):
        E = self.E
        hs = b["hand_slot"][:n]
        hand = torch.zeros(n, E.N_SLOTS + 1, dtype=torch.bool, device=hs.device).scatter(1, hs, True)[:, :E.N_SLOTS]
        p = torch.sigmoid(heads["gate"][:n]).double() if "gate" in heads else None   # P2-OPP1 timing head: no gate
        return enc, heads, p, hand

    def __call__(self, arrs: dict, n: int):
        with torch.no_grad(), self.amp():
            B = bucket(n, self.buckets) if self.pad else n
            self.last_graph = self.mode == "graphs" and B <= self.graph_max
            if not self.last_graph:
                b = {k: torch.from_numpy(arrs[k][:n]).to(self.device, non_blocking=True) for k in self.keys}
                if B > n:                        # fixed shapes: pad to the bucket (rows = copies of row 0, dropped)
                    b = {k: torch.cat([v, v[:1].expand(B - n, *v.shape[1:])]) for k, v in b.items()}
                enc, heads = self.fn(b)
                return self._post(enc, heads, b, n)
            g = self.graphs.get(B)
            if g is None:
                g = self.graphs[B] = self._capture(arrs, B)
            stat, out = g["in"], g["out"]
            for k in self.keys:
                src = torch.from_numpy(arrs[k][:n])
                stat[k][:n].copy_(src, non_blocking=True)
                if B > n:
                    stat[k][n:].copy_(src[:1].expand(B - n, *src.shape[1:]), non_blocking=True)
            g["graph"].replay()
            return self._post(out[0], out[1], stat, n)

    def _capture(self, arrs: dict, B: int) -> dict:
        stat = {k: torch.from_numpy(np.repeat(arrs[k][:1], B, 0)).to(self.device) for k in self.keys}
        s = torch.cuda.Stream()
        s.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(s):
            for _ in range(3):                                   # warm-up on a side stream (cuBLAS workspaces)
                self.fn(stat)
        torch.cuda.current_stream().wait_stream(s)
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph, pool=self.pool, capture_error_mode="thread_local"):     # a server's other threads keep running
            out = self.fn(stat)
        return {"in": stat, "out": out, "graph": graph}

    def cell_logits(self, enc, n: int):
        """decide's cell_logits(ids, slots) on this forward's encodings (rows < n are real)."""
        from pipeline.decision_options import model_cell_logits
        return model_cell_logits(self.policy, enc, self.device)


class _Req:
    __slots__ = ("rows", "allowed", "stalled", "rngs", "tau_r", "n", "fut", "t")

    def __init__(self, rows, allowed, stalled, rngs, tau_r):
        self.rows, self.allowed, self.stalled, self.rngs, self.tau_r = rows, allowed, stalled, rngs, tau_r
        self.n, self.fut, self.t = len(allowed), Future(), time.perf_counter()


class AsyncPolicyServer:
    """``submit(rows, allowed, stalled, rngs, tau_r=None) -> Future[list of decide dicts]``; ``rows`` = dict of numpy
    arrays [n, ...] with the policy's gen_row keys. ``cfg``: tau, T, T_gate (decode 'sample', SAMPLE_RULES at their
    defaults). ``decide=False``: the future holds (gate z, card logits, p) only -- the forward-only throughput mode.
    ``pipelined`` (eager / compile, off by default): the decide of batch k runs in a second thread while batch k+1 is
    forwarded. Measured SLOWER on the 4090 (12.3k vs 14.3k rows/s: the decide and the forward launches share the GIL),
    and refused for a policy with refine layers (LazyRefine swaps them out during a forward, which a concurrent cell
    call would see). Graphs mode reuses its output buffers, so it is always serial.
    ``stats``: batches, rows, seconds in stack / forward / decide / waiting, batch-size histogram."""

    def __init__(self, policy, cfg: dict, device: str = "cuda", max_batch: int = 4096, wait_ms: float = 1.0,
                 mode: str = "eager", decide: bool = True, pipelined: bool = False, forward: Optional[Forward] = None):
        self.fwd = forward or Forward(policy, device, mode)            # a shared Forward keeps one set of graphs
        self.cfg, self.device, self.max_batch, self.wait = cfg, device, int(max_batch), wait_ms / 1000.0
        self.decide_on = decide
        self.q: "queue.Queue[Optional[_Req]]" = queue.Queue()
        self.stats = {"batches": 0, "rows": 0, "stack_s": 0.0, "forward_s": 0.0, "decide_s": 0.0, "idle_s": 0.0,
                      "sizes": []}
        self._buf: dict = {}
        self._stop = False
        self.pipelined = bool(pipelined and decide and mode != "graphs")
        lz = self.fwd.policy
        if self.pipelined and (getattr(lz, "cr", None) is not None or getattr(lz, "tr", None) is not None):
            raise ValueError("pipelined decide with refine layers: a cell call would race the forward's swap")
        self._dq: "queue.Queue" = queue.Queue(maxsize=2)
        self.th = threading.Thread(target=self._loop, daemon=True)
        self.th.start()
        if self.pipelined:
            self.th2 = threading.Thread(target=self._decide_loop, daemon=True)
            self.th2.start()

    def submit(self, rows: dict, allowed, stalled, rngs, tau_r=None) -> Future:
        r = _Req(rows, np.asarray(allowed, bool), np.asarray(stalled, bool), list(rngs), tau_r)
        self.q.put(r)
        return r.fut

    def close(self):
        self._stop = True
        self.q.put(None)
        self.th.join(timeout=30)
        if self.pipelined:
            self._dq.put(None)
            self.th2.join(timeout=30)

    def _take(self) -> list:
        t = time.perf_counter()
        first = self.q.get()
        self.stats["idle_s"] += time.perf_counter() - t
        if first is None:
            return []
        got, n = [first], first.n
        deadline = time.perf_counter() + self.wait
        while n < self.max_batch:
            try:
                r = self.q.get(timeout=max(0.0, deadline - time.perf_counter())) if self.wait else self.q.get_nowait()
            except queue.Empty:
                break
            if r is None:
                self._stop = True
                break
            if n + r.n > self.max_batch:                       # keep it for the next batch
                self.q.put(r)
                break
            got.append(r)
            n += r.n
        return got

    def _stack(self, reqs: list, n: int) -> dict:
        out = {}
        for k in self.fwd.keys:
            a0 = reqs[0].rows[k]
            buf = self._buf.get(k)
            if buf is None or buf.shape[0] < self.max_batch:
                buf = self._buf[k] = torch.empty((self.max_batch, *a0.shape[1:]),
                                                 dtype=torch.from_numpy(a0[:1]).dtype).pin_memory().numpy()
            o = 0
            for r in reqs:
                buf[o:o + r.n] = r.rows[k]
                o += r.n
            out[k] = buf
        return out

    def _decide(self, reqs, n, enc, heads, pn):
        from pipeline.decision_options import DecisionOptions, decide, sample_rules
        c = self.cfg
        tau, T = float(c["tau"]), float(c.get("T", 0.5))
        allowed = np.concatenate([r.allowed for r in reqs])
        stalled = np.concatenate([r.stalled for r in reqs])
        rngs = [g for r in reqs for g in r.rngs]
        tau_r = (np.concatenate([np.broadcast_to(np.asarray(tau if r.tau_r is None else r.tau_r, np.float64), (r.n,))
                                 for r in reqs]) if any(r.tau_r is not None for r in reqs) else None)
        hd = {k: v[:n] for k, v in heads.items()}
        out = decide(hd, pn, allowed, stalled, tau=tau, options=sample_rules(DecisionOptions()), rngs=[None] * n,
                     decode="sample", sampler={"tau_r": tau_r, "T": T, "T_gate": float(c.get("T_gate") or T),
                                               "heads": frozenset(("gate", "card", "cell")), "rngs": rngs},
                     cell_logits=self.fwd.cell_logits(enc, n))
        o = 0
        for r in reqs:
            r.fut.set_result(out[o:o + r.n])
            o += r.n

    def _decide_loop(self):
        while True:
            item = self._dq.get()
            if item is None:
                return
            reqs, n, enc, heads, pn = item
            t = time.perf_counter()
            try:
                self._decide(reqs, n, enc, heads, pn)
            except BaseException as exc:                       # noqa: BLE001 -- every waiting producer gets it
                for r in reqs:
                    if not r.fut.done():
                        r.fut.set_exception(exc)
            self.stats["decide_s"] += time.perf_counter() - t

    def _loop(self):
        while not self._stop:
            reqs = self._take()
            if not reqs:
                break
            try:
                n = sum(r.n for r in reqs)
                t0 = time.perf_counter()
                arrs = self._stack(reqs, n)
                t1 = time.perf_counter()
                enc, heads, p, hand = self.fwd(arrs, n)
                if not self.decide_on:
                    z, card, pp = (heads["gate"][:n].float().cpu().numpy(), heads["card"][:n].float().cpu().numpy(),
                                   p.cpu().numpy())
                    t2 = t3 = time.perf_counter()
                    o = 0
                    for r in reqs:
                        r.fut.set_result((z[o:o + r.n], card[o:o + r.n], pp[o:o + r.n]))
                        o += r.n
                else:
                    pn = p.cpu().numpy()                       # the sync: this batch's host copies are done
                    t2 = time.perf_counter()
                    if self.pipelined:
                        self._dq.put((reqs, n, enc, heads, pn))
                        t3 = t2
                    else:
                        self._decide(reqs, n, enc, heads, pn)
                        t3 = time.perf_counter()
                S = self.stats
                S["batches"] += 1
                S["rows"] += n
                S["stack_s"] += t1 - t0
                S["forward_s"] += t2 - t1
                S["decide_s"] += t3 - t2
                S["sizes"].append(n)
            except BaseException as exc:                       # noqa: BLE001 -- every waiting producer gets it
                for r in reqs:
                    if not r.fut.done():
                        r.fut.set_exception(exc)


# ---- S4b + LOOP-SRV: decide in the producers; the server forwards one or more models and swaps weight versions --------
AUTHKEY = b"loopsrv"


def _layout(spec: dict, block_max: int, base: int = 0):
    """A model's region of a producer's shared-memory segment: {key: (byte offset, shape, dtype)} (64-byte aligned)
    from ``base``, and the region's end."""
    out, o = {}, base
    for k, (shape, dt) in spec.items():
        out[k] = (o, (block_max, *shape), np.dtype(dt))
        o += -(-int(np.prod((block_max, *shape))) * np.dtype(dt).itemsize // 64) * 64
    return out, o


def _layouts(table) -> tuple:
    """Every model's region, one after the other: ([layout per model], segment size)."""
    out, o = [], 0
    for _, spec, block_max, _ in table:
        lay, o = _layout(spec, block_max, o)
        out.append(lay)
    return out, max(o, 1)


def _views(buf, layout: dict) -> dict:
    return {k: np.ndarray(shape, dtype=dt, buffer=buf, offset=o) for k, (o, shape, dt) in layout.items()}


def row_spec(rows: dict, keys) -> dict:
    """{key: (trailing shape, dtype str)} of a producer's row block (numpy arrays [n, ...])."""
    return {k: (tuple(rows[k].shape[1:]), rows[k].dtype.str) for k in keys}


class Fwd:
    """One block's forward, as a producer sees it: ``heads`` {name: numpy [n, ...]} (every head the model's heads_t
    returns), ``p`` = sigmoid(gate) float64 (None without a gate), ``ver`` = the weight version that produced them."""
    __slots__ = ("mi", "bid", "ver", "heads", "p")

    def __init__(self, mi, bid, ver, heads, p):
        self.mi, self.bid, self.ver, self.heads, self.p = mi, bid, ver, heads, p


class Client:
    """A producer's end (``PolicyServer.clients[i]`` passed to a spawned process, or ``connect(address)``; use it in
    ONE process). ``forward([(model, rows, n), ...])`` writes each block into its model's shared-memory region, sends
    them all, and returns their ``Fwd``s; ``cells`` / ``ability`` answer a decide's playing rows / pressable buttons
    from the SAME batch (encodings and weights); ``done`` frees the batches. ``decide`` = S4b's P1 decide on top
    (one block, decode 'sample'); every decide dict gets ``wver``."""

    def __init__(self, name: str, table: list, conn, foreign: bool = False):
        self.name, self.table, self.conn, self.foreign = name, table, conn, foreign
        self.models = {t[0]: i for i, t in enumerate(table)}
        self._shm, self.view = None, None

    def _attach(self):
        from multiprocessing import resource_tracker, shared_memory
        self._shm = shared_memory.SharedMemory(name=self.name)
        if self.foreign:              # not a child of the server: its own tracker would unlink the server's segment
            resource_tracker.unregister(self._shm._name, "shared_memory")
        self.view = [_views(self._shm.buf, lay) for lay in _layouts(self.table)[0]]

    def _mi(self, model) -> int:
        return model if isinstance(model, int) else self.models[model]

    def _recv(self):
        msg = self.conn.recv()
        if isinstance(msg, tuple) and msg and msg[0] == "err":
            raise RuntimeError(f"policy server: {msg[1]}")
        return msg

    def forward(self, blocks) -> list:
        """``blocks`` = [(model name or index, rows dict, n)], at most one per model -> [Fwd] in the same order. All
        are sent before any answer is awaited, so the server batches them with the other producers' blocks."""
        if self.view is None:
            self._attach()
        mis = [self._mi(m) for m, _, _ in blocks]
        if len(set(mis)) != len(mis):
            raise ValueError("one block per model per forward() (one shared-memory region per model)")
        for mi, (_, rows, n) in zip(mis, blocks):
            if n > self.table[mi][2]:
                raise ValueError(f"block of {n} rows > block_max {self.table[mi][2]} ({self.table[mi][0]})")
            for k, v in self.view[mi].items():
                v[:n] = rows[k][:n]
            self.conn.send(("fwd", mi, int(n)))
        got = {}
        for _ in mis:
            _, mi, bid, ver, heads, p = self._recv()
            got[mi] = Fwd(mi, bid, ver, heads, p)
        return [got[mi] for mi in mis]

    def cells(self, f: Fwd, ids, slots) -> np.ndarray:
        """decide's ``cell_logits(ids, slots)`` for rows ``ids`` of block ``f`` -> float32 [len(ids), N_CELLS]."""
        self.conn.send(("cell", f.bid, np.asarray(ids, np.int64), np.asarray(slots, np.int64)))
        return self._recv()

    def ability(self, f: Fwd, ids, feat) -> np.ndarray:
        """rl_royale's ability head (B6) on rows ``ids`` of block ``f``: z = head(g[ids], feat) -> float64 [len(ids)]
        (e1_eval.ability_decide's z), from the version that produced ``f``."""
        self.conn.send(("ab", f.bid, np.asarray(ids, np.int64), np.asarray(feat, np.float32)))
        return self._recv()

    def done(self, fs):
        for f in fs:
            self.conn.send(("done", f.bid))

    def decide(self, rows: dict, allowed, stalled, rngs, tau_r=None, model=0) -> list:
        (f,) = self.forward([(model, rows, len(allowed))])
        try:
            return self.decide_fwd(f, allowed, stalled, rngs, tau_r)
        finally:
            self.done([f])

    def decide_fwd(self, f: Fwd, allowed, stalled, rngs, tau_r=None) -> list:
        """S4b's P1 decide (decision_options.decide, decode 'sample', the model's cfg) on forward ``f``'s heads, its
        cell logits from the same batch; every dict tagged ``wver`` = f.ver. The caller sends ``done``."""
        from pipeline.decision_options import DecisionOptions, decide, sample_rules
        n = len(allowed)
        c = self.table[f.mi][3]
        tau, T = float(c["tau"]), float(c.get("T", 0.5))
        out = decide({k: torch.from_numpy(v) for k, v in f.heads.items()}, f.p, np.asarray(allowed, bool),
                     np.asarray(stalled, bool), tau=tau, options=sample_rules(DecisionOptions()), rngs=[None] * n,
                     decode="sample", sampler={"tau_r": tau_r, "T": T, "T_gate": float(c.get("T_gate") or T),
                                               "heads": frozenset(("gate", "card", "cell")), "rngs": list(rngs)},
                     cell_logits=lambda ids, slots: torch.from_numpy(self.cells(f, ids, slots)))
        for d in out:
            d["wver"] = f.ver
        return out

    def close(self):
        try:
            self.conn.send(("bye",))
        except (BrokenPipeError, OSError):
            pass
        if self._shm is not None:
            self.view = None
            self._shm.close()


def connect(address, authkey: bytes = AUTHKEY) -> Client:
    """A producer's Client for a running ``PolicyServer(listen=...)`` (any process on the machine)."""
    from multiprocessing.connection import Client as _connect
    conn = _connect(address, authkey=authkey)
    _, name, table = conn.recv()
    return Client(name, table, conn, foreign=True)


class _Copy:
    """One weight copy of a served model: the (split) policy, its Forward (own graphs), version, batches in flight,
    and the ability head once a push carried one."""

    def __init__(self, policy, fwd_kw: dict, version):
        self.pol, self.version, self.refs, self.ability = policy, version, 0, None
        self.dst: dict = {}                     # id(model) -> its state_dict tensors (aliases of the parameters)
        self.fwd = Forward(policy, **fwd_kw)


class PolicyServer:
    """The forward-only GPU server (S4b + LOOP-SRV). ``models`` = [{name, policy (GenPolicy / LazyRefine), spec
    (row_spec of its rows), cfg (Client.decide's tau / T / T_gate; optional), block_max (default ``block_max``),
    version (default 0), swap (a second weight copy for ``push``; implied by watch), watch (a directory: the learner's
    weight files, see ``_watch_loop``; the model serves nothing until its first version arrives)}].

    Producers: ``clients[i]`` (``n_clients`` pre-wired, passed to spawned processes) and/or ``connect(self.address)``
    (``listen`` True or an address). Each has one shared-memory segment with a region per model. Threads:
      - receiver: fwd -> the model's queue; cell / ab -> the cell queue; done -> release the batch;
      - forward (double-buffered): the model whose oldest request waited longest; its queued blocks up to
        ``max_batch`` rows (waiting up to ``wait_ms`` from that request's arrival) -> pad to a bucket -> ONE forward of
        the active weight copy -> each producer gets its rows' heads + the copy's version; the batch keeps its
        encodings AND its copy until every block of it says done;
      - cell: cell / ability calls on the batch's own encodings and copy, on a separate CUDA stream;
      - watch (per watched model) and accept (``listen``).
    ``push(name, version, state_dict)`` loads the spare copy IN PLACE (graph addresses stay valid) once no batch
    holds it, then flips: a decide's forward and its cell / ability calls always use one version.
    ``stats``: stack / forward / cell / idle / push seconds, batches, rows, pushes, per model rows / batches / padding."""

    def __init__(self, models: list, n_clients: int = 0, block_max: int = 512, device: str = "cuda",
                 max_batch: int = 2048, wait_ms: float = 1.0, mode: str = "eager", buckets=BUCKETS_FINE,
                 graph_max: int = 512, precision: str = "fp32", deterministic: bool = False, listen=None,
                 authkey: bytes = AUTHKEY):
        if device.startswith("cuda"):
            configure(precision, deterministic)
        self.device, self.max_batch, self.wait, self.mode = device, int(max_batch), wait_ms / 1000.0, mode
        if self.max_batch > buckets[-1]:
            raise ValueError(f"max_batch {max_batch} > the largest bucket {buckets[-1]}")
        # ONE graph memory pool for every graph of the server: replays are serial on one stream and each batch's
        # outputs are copied / cloned right after its replay, so a later replay may reuse the memory (private pools
        # per graph filled the 4090's 24 GB with 8 models x 6 buckets)
        pool = torch.cuda.graph_pool_handle() if mode == "graphs" and device.startswith("cuda") else None
        self.fwd_kw = dict(device=device, mode=mode, buckets=buckets, pad=True, graph_max=graph_max,
                           precision=precision, pool=pool)
        self.models = []
        for m in models:
            m = dict(m)
            m.setdefault("block_max", block_max)
            if m["block_max"] > self.max_batch:
                raise ValueError(f"{m['name']}: block_max {m['block_max']} > max_batch {max_batch}")
            m["swap"] = bool(m.get("swap") or m.get("watch"))
            self.models.append(m)
        self.table = [(m["name"], m["spec"], m["block_max"], m.get("cfg")) for m in self.models]
        self._names = {m["name"]: i for i, m in enumerate(self.models)}
        self._lay, self._size = _layouts(self.table)
        self._shm, self.views, self.conns, self.clients = [], [], [], []
        self._lock = threading.Lock()                       # conns / batches / copies' refs and the active flips
        for _ in range(n_clients):
            import multiprocessing as mp
            a, b = mp.Pipe()
            self.clients.append(Client(self._new_client(a), self.table, b))
        self._listener, self.address = None, None
        if listen:
            from multiprocessing.connection import Listener
            self._listener = Listener(None if listen is True else listen, authkey=authkey)
            self.address, self._authkey = self._listener.address, authkey
        self.stats = {"batches": 0, "rows": 0, "stack_s": 0.0, "forward_s": 0.0, "cell_s": 0.0, "cell_calls": 0,
                      "idle_s": 0.0, "pushes": 0, "push_s": 0.0,
                      "per_model": {m["name"]: {"rows": 0, "batches": 0, "pad_rows": 0} for m in self.models}}
        self._stop = False

    def _new_client(self, conn) -> str:
        """A producer's segment (one region per model) on server end ``conn`` -> the segment's name."""
        from multiprocessing import shared_memory
        s = shared_memory.SharedMemory(create=True, size=self._size)
        with self._lock:
            self._shm.append(s)
            self.views.append([_views(s.buf, lay) for lay in self._lay])
            self.conns.append(conn)
        return s.name

    def start(self, warm: Optional[dict] = None):
        """Build the weight copies (two for a swapped model) and start the threads. ``warm`` {model name: rows dict
        [k, ...]}: run every bucket up to max_batch through each copy first (pays the first-use cost of each shape and
        captures the graphs now, not mid-run)."""
        from pipeline import batched_rollout as BR
        self._cuda = self.device.startswith("cuda")
        for m in self.models:
            pol = m["policy"] if hasattr(m["policy"], "pol") else BR.LazyRefine(m["policy"])
            pol.split()                 # refine layers: a refine-free forward copy, so cell calls never race a forward
            watched = bool(m.get("watch"))
            v0 = None if watched else m.get("version", 0)
            m["copies"] = [_Copy(pol, self.fwd_kw, v0)] + ([_Copy(copy.deepcopy(pol), self.fwd_kw, v0)]
                                                           if m["swap"] else [])
            m["active"] = None if watched else 0
            m["slot"] = 0
            m["bufs"] = [{k: torch.empty((self.max_batch, *shape), dtype=torch.from_numpy(np.zeros(1, dt)).dtype)
                          .pin_memory().numpy() if self._cuda else np.empty((self.max_batch, *shape), dtype=np.dtype(dt))
                          for k, (shape, dt) in m["spec"].items()} for _ in range(2)]       # double-buffered
            m["push_lock"] = threading.Lock()
            if warm and m["name"] in warm:
                self._warm(m, warm[m["name"]])
        self._bid = 0
        self._cs = torch.cuda.Stream() if self._cuda else None
        self._fq = [deque() for _ in self.models]
        self._cv = threading.Condition()
        self._cq: "queue.Queue" = queue.Queue()
        self._batches: dict = {}
        self._dead: set = set()
        loops = [self._recv_loop, self._fwd_loop, self._cell_loop] + ([self._accept_loop] if self._listener else [])
        self.th = [threading.Thread(target=f, daemon=True) for f in loops]
        self.th += [threading.Thread(target=self._watch_loop, args=(mi,), daemon=True)
                    for mi, m in enumerate(self.models) if m.get("watch")]
        for t in self.th:
            t.start()
        return self

    def _warm(self, m, rows):
        k = len(next(iter(rows.values())))
        for c in m["copies"]:
            for B in self.fwd_kw["buckets"]:
                if B > self.max_batch:
                    break
                arr = {key: np.ascontiguousarray(rows[key][np.arange(B) % k]) for key in m["spec"]}
                if self._cuda:
                    arr = {key: torch.from_numpy(v).pin_memory().numpy() for key, v in arr.items()}
                out = c.fwd(arr, B)
                (out[2] if out[2] is not None else next(iter(out[1].values()))).cpu()

    def close(self):
        self._stop = True
        if self._listener is not None:                  # wake a blocked accept(), then close
            from multiprocessing.connection import Client as _connect
            with contextlib.suppress(Exception):
                _connect(self.address, authkey=self._authkey).close()
            with contextlib.suppress(OSError):
                self._listener.close()
        if hasattr(self, "_cv"):
            with self._cv:
                self._cv.notify_all()
        for t in getattr(self, "th", []):
            t.join(timeout=30)
        self.views = []
        for s in self._shm:
            s.close()
            with contextlib.suppress(FileNotFoundError):
                s.unlink()

    # ---- weight versions ----------------------------------------------------------------------------------------
    def version(self, name) -> Optional[int]:
        m = self.models[self._names.get(name, name) if not isinstance(name, int) else name]
        return None if m["active"] is None else m["copies"][m["active"]].version

    def push(self, name, version: int, state_dict: dict, timeout: float = 120.0):
        """Load ``state_dict`` (strict, the model's own keys; rl_royale's actor message: the ability head's tensors
        under ``rl_royale.ABILITY_SD``) as weight ``version`` (> the current one) and make it the active copy. Waits
        until no batch still holds the spare copy."""
        mi = name if isinstance(name, int) else self._names[name]
        m = self.models[mi]
        t0 = time.perf_counter()
        with m["push_lock"]:
            cur = self.version(mi)
            if cur is not None and int(version) <= cur:
                raise ValueError(f"{m['name']}: version {version} is not newer than {cur}")
            tgt = 0 if m["active"] is None else 1 - m["active"]
            if tgt >= len(m["copies"]):
                raise ValueError(f"{m['name']}: not swappable (start it with swap=True or watch=DIR)")
            c = m["copies"][tgt]
            while True:
                with self._lock:
                    if c.refs == 0:
                        break
                if time.perf_counter() - t0 > timeout:
                    raise TimeoutError(f"{m['name']}: the spare copy is still held by {c.refs} batch(es)")
                time.sleep(0.001)
            t1 = time.perf_counter()
            self.stats["push_wait_s"] = self.stats.get("push_wait_s", 0.0) + t1 - t0
            self._load(c, state_dict)
            if self._cuda:
                torch.cuda.synchronize(self.device)
            c.version = int(version)
            with self._cv:
                with self._lock:
                    m["active"] = tgt
                self._cv.notify_all()
        self.stats["pushes"] += 1
        self.stats["push_s"] += time.perf_counter() - t0

    def _load(self, c: _Copy, sd: dict):
        sd = dict(sd)
        asd = {}
        if any(k.startswith("__ability__.") for k in sd):
            from pipeline.rl_royale import ABILITY_SD, AbilityHead, pop_prefix
            asd = pop_prefix(sd, ABILITY_SD)
        def copy_in(model, keys):
            """Strict, in place (graph addresses unchanged), as ONE foreach call on the copy's cached state tensors: a
            per-tensor load_state_dict took up to 7 s while the server's other threads held the GIL."""
            dst = c.dst.get(id(model))
            if dst is None:
                dst = c.dst[id(model)] = model.state_dict()
            if set(dst) != set(keys):
                raise KeyError(f"state dict mismatch: missing {sorted(set(dst) - set(keys))[:5]}, "
                               f"unexpected {sorted(set(keys) - set(dst))[:5]}")
            torch._foreach_copy_(list(dst.values()), [sd[k] for k in dst])

        with torch.no_grad():
            copy_in(c.pol.model, list(sd))
            fp = getattr(c.pol, "fwd_pol", None)
            if fp is not None:                                           # the split forward copy: no cell_refine
                fk = list(fp.model.state_dict())
                extra = set(sd) - set(fk)
                if any(not k.startswith("cell_refine.") for k in extra):
                    raise KeyError(f"forward copy lacks {sorted(extra)[:5]}")
                copy_in(fp.model, fk)
            if asd:
                if c.ability is None:
                    w = asd["net.0.weight"]
                    d_g = c.pol.model.value_head.in_features
                    c.ability = AbilityHead(d_g, int(w.shape[0]), int(w.shape[1]) - d_g).to(self.device).eval()
                c.ability.load_state_dict(asd)

    def _watch_loop(self, mi: int):
        """The learner's weight files: DIR/{name}.v{V:08d}.pt = {"version": V, "state_dict": SD} and DIR/{name}.latest
        = "V" (each written to a .tmp, then os.replace). Polled every 0.2 s; a newer V is pushed. A file already
        removed by the writer -> latest is read again."""
        m = self.models[mi]
        d = Path(m["watch"])
        while not self._stop:
            try:
                v = int((d / f"{m['name']}.latest").read_text().strip())
                cur = self.version(mi)
                if cur is None or v > cur:
                    obj = torch.load(d / f"{m['name']}.v{v:08d}.pt", map_location="cpu")
                    self.push(mi, int(obj.get("version", v)), obj["state_dict"])
                    continue
            except (FileNotFoundError, ValueError):
                pass
            time.sleep(0.2)

    # ---- threads ------------------------------------------------------------------------------------------------
    def _accept_loop(self):
        while not self._stop:
            try:
                conn = self._listener.accept()
            except (OSError, EOFError):
                if self._stop:
                    return
                continue
            if self._stop:
                return
            conn.send(("hello", self._new_client(conn), self.table))

    def _release(self, bid, i):
        """Producer ``i`` is done with batch ``bid`` (caller holds _lock); the last one frees encodings and copy."""
        b = self._batches.get(bid)
        if b is not None:
            b["left"].discard(i)
            if not b["left"]:
                del self._batches[bid]
                b["c"].refs -= 1

    def _recv_loop(self):
        """Every producer message: fwd -> its model's queue, cell / ab -> the cell queue, done -> release the batch."""
        from multiprocessing.connection import wait as mp_wait
        while not self._stop:
            with self._lock:
                live = {id(c): (i, c) for i, c in enumerate(self.conns) if i not in self._dead}
            if not live:
                time.sleep(0.01)
                continue
            for c in mp_wait([c for _, c in live.values()], timeout=0.05):
                i = live[id(c)][0]
                try:
                    msg = c.recv()
                except (EOFError, OSError):
                    msg = ("bye",)
                if msg[0] == "fwd":
                    with self._cv:
                        self._fq[msg[1]].append((i, int(msg[2]), time.perf_counter()))
                        self._cv.notify()
                elif msg[0] in ("cell", "ab"):
                    self._cq.put((msg[0], msg[1], i, msg[2], msg[3]))
                elif msg[0] == "done":
                    with self._lock:
                        self._release(msg[1], i)
                elif msg[0] == "bye":
                    with self._lock:
                        self._dead.add(i)
                        for bid in list(self._batches):
                            self._release(bid, i)

    def _take(self, block: bool):
        """-> (model index, [(client, n)], n) or None: the model whose oldest queued block arrived first (and has an
        active version); its queued blocks up to max_batch rows, waiting until ``wait_ms`` after that block's arrival
        for more. ``block`` False: None at once when nothing is ready."""
        with self._cv:
            while True:
                ready = [mi for mi, q in enumerate(self._fq) if q and self.models[mi]["active"] is not None]
                if ready or not block or self._stop:
                    break
                self._cv.wait(0.05)
            if not ready:
                return None
            mi = min(ready, key=lambda j: self._fq[j][0][2])
            q = self._fq[mi]
            deadline = q[0][2] + self.wait
            take, n = [], 0
            while True:
                while q and n + q[0][1] <= self.max_batch:
                    i, k, _ = q.popleft()
                    take.append((i, k))
                    n += k
                rem = deadline - time.perf_counter()
                if q or n >= self.max_batch or rem <= 0 or self._stop:      # full, or the wait is over
                    break
                self._cv.wait(rem)
        return mi, take, n

    def _launch(self, mi, take, n):
        """Stack ``take`` into the model's pinned buffer set, launch the forward of its active copy and the
        device->host copies of every head (non-blocking, an event after them) -> the in-flight batch."""
        m = self.models[mi]
        buf = m["bufs"][m["slot"]]
        m["slot"] ^= 1
        with self._lock:
            c = m["copies"][m["active"]]
            c.refs += 1
        try:
            t0 = time.perf_counter()
            off, o = {}, 0
            for i, k in take:
                off[i] = o
                for key, v in self.views[i][mi].items():
                    buf[key][o:o + k] = v[:k]
                o += k
            t1 = time.perf_counter()
            enc, heads, p, _ = c.fwd(buf, n)
        except BaseException:
            with self._lock:
                c.refs -= 1
            raise
        if c.fwd.last_graph:                     # static graph outputs: the next replay overwrites them
            enc = {k: v[:n].clone() if torch.is_tensor(v) else v for k, v in enc.items()}
        host = {k: torch.empty((n, *x.shape[1:]), dtype=torch.float32, pin_memory=self._cuda) for k, x in heads.items()}
        for k, x in heads.items():
            host[k].copy_(x[:n].float(), non_blocking=True)
        if p is not None:
            host["_p"] = torch.empty(n, dtype=torch.float64, pin_memory=self._cuda)
            host["_p"].copy_(p[:n], non_blocking=True)
        ev = torch.cuda.Event() if self._cuda else None
        if ev is not None:
            ev.record()
        self.stats["stack_s"] += t1 - t0
        return {"mi": mi, "c": c, "take": take, "n": n, "off": off, "enc": enc, "host": host, "ev": ev, "t": t1,
                "B": bucket(n, self.fwd_kw["buckets"])}

    def _finish(self, f):
        """Wait for an in-flight batch's heads, register its encodings + copy for cell calls, answer its producers."""
        S = self.stats
        if f["ev"] is not None:
            f["ev"].synchronize()
        h = {k: v.numpy() for k, v in f["host"].items()}
        p = h.pop("_p", None)
        c = f["c"]
        with self._lock:
            bid = self._bid
            self._bid += 1
            left = {i for i, _ in f["take"] if i not in self._dead}
            if left:
                self._batches[bid] = {"enc": f["enc"], "n": f["n"], "off": f["off"], "left": left, "c": c}
            else:
                c.refs -= 1
        for i, k in f["take"]:
            s0 = f["off"][i]
            with contextlib.suppress(BrokenPipeError, OSError):
                self.conns[i].send(("heads", f["mi"], bid, c.version, {kk: v[s0:s0 + k] for kk, v in h.items()},
                                    None if p is None else p[s0:s0 + k]))
        S["batches"] += 1
        S["rows"] += f["n"]
        S["forward_s"] += time.perf_counter() - f["t"]
        pm = S["per_model"][self.models[f["mi"]]["name"]]
        pm["rows"] += f["n"]
        pm["batches"] += 1
        pm["pad_rows"] += f["B"] - f["n"]

    def _fail(self, take, exc):
        import traceback
        traceback.print_exception(exc)
        for i, _ in take:
            with contextlib.suppress(BrokenPipeError, OSError):
                self.conns[i].send(("err", repr(exc)))

    def _fwd_loop(self):
        """Double-buffered: batch k+1 is stacked and launched while batch k is still on the GPU; k is answered once its
        heads are on the host."""
        S, inflight = self.stats, None
        while not self._stop:
            t = time.perf_counter()
            got = self._take(block=inflight is None)
            if inflight is None:
                S["idle_s"] += time.perf_counter() - t
            nxt = None
            if got:
                try:
                    nxt = self._launch(*got)
                except BaseException as exc:                   # noqa: BLE001 -- every waiting producer gets it
                    self._fail(got[1], exc)
            if inflight is not None:
                self._finish(inflight)
            inflight = nxt
        if inflight is not None:
            self._finish(inflight)

    def _cell_loop(self):
        S = self.stats
        while not self._stop:
            try:
                reqs = [self._cq.get(timeout=0.05)]
            except queue.Empty:
                continue
            while True:
                try:
                    reqs.append(self._cq.get_nowait())
                except queue.Empty:
                    break
            t0 = time.perf_counter()
            by: dict = {}
            for kind, bid, i, x, y in reqs:
                by.setdefault((kind, bid), []).append((i, x, y))
            for (kind, bid), rr in by.items():
                try:
                    with self._lock:
                        b = self._batches[bid]
                    ids = np.concatenate([x + b["off"][i] for i, x, _ in rr])
                    stream = torch.cuda.stream(self._cs) if self._cs is not None else contextlib.nullcontext()
                    with torch.no_grad(), stream:
                        c = b["c"]
                        if kind == "cell":
                            out = c.fwd.cell_logits(b["enc"], b["n"])(ids, np.concatenate([y for _, _, y in rr]))
                            out = out.float().cpu().numpy()
                        elif c.ability is None:
                            raise RuntimeError("ability call: this weight version carried no ability head")
                        else:
                            g = b["enc"]["g"]
                            out = c.ability(g[torch.as_tensor(ids, device=g.device)],
                                            torch.as_tensor(np.concatenate([y for _, _, y in rr]), device=g.device))
                            out = out.double().cpu().numpy()
                except BaseException as exc:                   # noqa: BLE001 -- the waiting producers get it
                    for i, _, _ in rr:
                        with contextlib.suppress(BrokenPipeError, OSError):
                            self.conns[i].send(("err", repr(exc)))
                    continue
                S["cell_calls"] += 1
                o = 0
                for i, x, _ in rr:
                    with contextlib.suppress(BrokenPipeError, OSError):
                        self.conns[i].send(out[o:o + len(x)])
                    o += len(x)
            S["cell_s"] += time.perf_counter() - t0


def ProcServer(policy, spec: dict, n_clients: int, block_max: int, cfg: dict, device: str = "cuda",
               max_batch: int = 2048, wait_ms: float = 1.0, mode: str = "eager", **kw) -> PolicyServer:
    """S4b's one-model server: ``clients[i].decide(rows, allowed, stalled, rngs)`` (model 0, version 0)."""
    return PolicyServer([{"name": "policy", "policy": policy, "spec": spec, "cfg": cfg}], n_clients, block_max, device,
                        max_batch, wait_ms, mode, **kw)
