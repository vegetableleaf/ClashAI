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
"""
from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import Future
from typing import Optional

import numpy as np
import torch

BUCKETS = (64, 128, 256, 512, 1024, 2048, 4096, 8192)


def bucket(n: int) -> int:
    for b in BUCKETS:
        if n <= b:
            return b
    raise ValueError(f"batch {n} > {BUCKETS[-1]}")


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
    arrays -> (enc, heads, p [n] float64, hand bool [n, 8]); ``mode`` eager / graphs / compile."""

    def __init__(self, policy, device: str = "cuda", mode: str = "eager"):
        from pipeline import e1_eval as E
        self.E, self.policy, self.device, self.mode = E, policy, device, mode
        self.keys = E.gen_row_keys(policy.model)
        self.graphs: dict = {}
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
        p = torch.sigmoid(heads["gate"][:n]).double()
        return enc, heads, p, hand

    def __call__(self, arrs: dict, n: int):
        with torch.no_grad():
            if self.mode != "graphs":
                b = {k: torch.from_numpy(arrs[k][:n]).to(self.device, non_blocking=True) for k in self.keys}
                if self.mode == "compile":       # fixed shapes: pad to the bucket (dynamic=False recompiles per shape)
                    B = bucket(n)
                    b = {k: torch.cat([v, v[:1].expand(B - n, *v.shape[1:])]) if B > n else v for k, v in b.items()}
                enc, heads = self.fn(b)
                return self._post(enc, heads, b, n)
            B = bucket(n)
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
        with torch.cuda.graph(graph):
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
