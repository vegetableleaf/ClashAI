"""Batched self-play rollouts (plan1026 Pillar 4b, ticket S1): many matches stepped in lockstep by W CPU worker
processes, ONE forward per policy per decision round on one device (the GPU) for every worker's rows at once.

Engine-agnostic: matches are ``e1_eval.SelfPlayMatch`` on whatever env ``make_env`` builds (RoyaleSim's
RoyaleSelfPlayEnv today; crforge's facade plugs in the same way). Nothing here reads the engine.

One round, every worker in lockstep:
  1. worker: ``due()`` every live match (engine advance + landings), ``prepare()`` + the policy row of every deciding
     side (run_selfplay_batch's order: every side prepared before any acts) -> rows grouped by policy.
  2. server: per policy group ONE ``forward_batch`` over all workers' rows (enc stays on the device) -> each worker gets
     its slice of (gate, card logits, p, hand, g).
  3. worker: ``pre`` + the group's decide rule (``DECIDE`` = run_selfplay_batch's per-group rule, unchanged functions)
     on CPU with the side's own RNGs. The only device work a decide asks for, ``cell_logits``, goes through a stub:
     every decide runs in its own thread, the worker waits until each thread is blocked in ``cell_logits`` or done,
     and sends ONE request; the server answers every worker's requests of that wave with one cell call per policy.
  4. worker: ``apply`` in side order.
The rows a match records depend only on its own state and RNGs (run_selfplay_batch's contract), so the records equal
the actor path's up to float noise of the shared forward (identity check: speed/SPEED.md section d).

ticket B's unified decide(): replace ``DECIDE`` (one function, same arguments). ``run`` = ``run_selfplay_batch``'s
argument list minus ``n``, plus workers / in_flight / device."""
from __future__ import annotations

import contextlib
import copy
import multiprocessing as mp
import threading
import time
from typing import Optional

import numpy as np

from pipeline import e1_eval as E


def DECIDE(model, c: dict, enc, heads, p, allowed, stalled, sides) -> list[dict]:
    """``run_selfplay_batch``'s decide for one policy group (styled opponent / live / sample), verbatim."""
    from pipeline.decision_options import match_kwargs
    if "_opp_style" in c:
        from pipeline.adaptive_opponents import styled_decisions
        return styled_decisions(model, enc, heads, p, allowed, stalled, sides)
    if c["policy"] == "live":
        E.ability_decide(sides, enc, c)
        tau, kw = E.posture_live(sides, enc, c, c["tau"], match_kwargs(sides))
        return E.live_decide_batch(model, enc, heads, p, allowed, stalled, tau=tau, device=c["device"], **kw)
    return E.sample_decide_batch(model, enc, heads, p, allowed, stalled, sides, c)


def check_cfgs(cfg: dict, opponents: dict) -> None:
    """run_selfplay_batch's argument checks."""
    for c in [cfg] + [oc for _, oc in opponents.values()]:
        if c["policy"] not in ("live", "sample"):
            raise ValueError(f"self-play policies are live or sample, not {c['policy']!r}")
    if any(oc.get("record") for _, oc in opponents.values()):
        raise ValueError("a frozen opponent's side is never recorded")
    if cfg.get("record") and cfg["policy"] != "sample":
        raise ValueError("cfg['record'] needs policy 'sample' (no other policy records a row)")


def new_match(env, job, learner, opponents: dict, cfg: dict):
    """run_selfplay_batch's fill() for one job (i, spec, k[, overrides])."""
    i, spec, k, *rest = job
    over = dict(rest[0]) if rest and rest[0] else {}
    opp, ocfg = opponents[spec["opp"]["id"]]
    return E.SelfPlayMatch(env, spec, k, {**cfg, **over, "entry_index": i},
                           {**ocfg, **{x: v for x, v in over.items()
                                      if x not in ("obs_seed", "pipeline_decisions", "pipeline_tau_delta")},
                            "entry_index": i}, learner, opp)


# ---- the cell wave: decides in threads, their cell_logits calls answered together ---------------------------------
class _Need:
    __slots__ = ("gkey", "rows", "slot", "out")

    def __init__(self, gkey, rows, slot):
        self.gkey, self.rows, self.slot, self.out = gkey, rows, slot, None


class Waves:
    """Runs decide tasks in threads; ``cell(gkey, enc, slot)`` (called from a task) parks the thread until the next
    wave is answered. ``run(tasks, serve)``: ``serve([(gkey, rows, slot), ...]) -> [logits, ...]`` answers one wave."""

    def __init__(self):
        self.cv = threading.Condition()
        self.pending: list[_Need] = []
        self.done = 0

    def cell(self, gkey, enc, slot):
        import torch
        need = _Need(gkey, enc["_row"].numpy().copy(), slot.numpy().copy())
        with self.cv:
            self.pending.append(need)
            self.cv.notify_all()
            while need.out is None:
                self.cv.wait()
        return torch.from_numpy(need.out)

    def run(self, tasks, serve) -> list:
        n, res, err = len(tasks), [None] * len(tasks), []
        self.done = 0

        def body(j, f):
            try:
                res[j] = f()
            except BaseException as exc:              # noqa: BLE001 -- re-raised in the caller below
                err.append(exc)
            finally:
                with self.cv:
                    self.done += 1
                    self.cv.notify_all()
        th = [threading.Thread(target=body, args=(j, f), daemon=True) for j, f in enumerate(tasks)]
        for t in th:
            t.start()
        while True:
            with self.cv:
                while len(self.pending) + self.done < n:
                    self.cv.wait()
                wave, self.pending = self.pending, []
            if not wave:
                break
            outs = serve([(w.gkey, w.rows, w.slot) for w in wave])
            with self.cv:
                for w, o in zip(wave, outs):
                    w.out = np.asarray(o)
                self.cv.notify_all()
        for t in th:
            t.join()
        if err:
            raise err[0]
        return res


class CellStub:
    """The policy as a decide sees it in a worker: only ``cell_logits`` (-> the server, via the wave)."""

    def __init__(self, gkey, waves: Waves):
        self.gkey, self.waves = gkey, waves

    def cell_logits(self, enc, slot):
        return self.waves.cell(self.gkey, enc, slot)


def decide_groups(groups: dict, outs: dict, waves: Waves, serve) -> dict:
    """``groups`` {gkey: sides}, ``outs`` {gkey: (gate, card, card_hand, p, hand, g)} (numpy, this worker's rows) ->
    {gkey: (p, decisions)}. One task per non-styled group; styled groups one task per row (styled_decisions decodes
    each row on its own, so per-row calls equal the group call)."""
    import torch
    tasks, where = [], []
    for gkey, sides in groups.items():
        gate, card, card_hand, p, hand, g = outs[gkey]
        pre = [s.pre(hand[r]) for r, s in enumerate(sides)]
        allowed = np.stack([x[1] for x in pre])
        stalled = np.array([x[2] for x in pre], dtype=bool)
        c = sides[0].cfg
        rows = range(len(sides)) if "_opp_style" in c else [slice(0, len(sides))]
        for r in rows:
            sl = r if isinstance(r, slice) else slice(r, r + 1)
            idx = np.arange(len(sides))[sl]
            enc = {"g": torch.from_numpy(g[sl]), "_row": torch.from_numpy(idx)}
            heads = {"gate": torch.from_numpy(gate[sl]), "card": torch.from_numpy(card[sl]),
                     "card_hand": torch.from_numpy(card_hand[sl])}
            stub = CellStub(gkey, waves)
            tasks.append(lambda st=stub, c=c, e=enc, h=heads, pp=list(p[sl]), a=allowed[sl], z=stalled[sl],
                         ss=sides[sl]: DECIDE(st, c, e, h, pp, a, z, ss))
            where.append(gkey)
    res = waves.run(tasks, serve)
    out: dict = {}
    for gkey, d in zip(where, res):
        out.setdefault(gkey, []).extend(d)
    return {gkey: ([float(x) for x in outs[gkey][3]], out[gkey]) for gkey in groups}


# ---- worker ---------------------------------------------------------------------------------------------------------
def _worker(wid: int, conn, make_env, learner, opponents: dict, cfg: dict, jobs: list, in_flight: int, pol_ix: dict,
            skip, fast=(), nice: int = 0) -> None:
    import os
    import torch
    torch.set_num_threads(1)
    if nice:                                           # the server's launch-bound forward first when cores are short
        os.nice(nice)
    if "cue" in fast:                                  # pipeline.fast_obs: same rows, fewer Battle.save() calls
        from pipeline import fast_obs
        fast_obs.install(("cue",))
    T = {k: 0.0 for k in ("due", "prepare_row", "decide", "apply", "wait_fwd", "wait_cell", "reset")}
    jobs_it, free, live = iter(jobs), [make_env() for _ in range(in_flight)], []
    results, skipped, rounds = [], [], 0
    waves = Waves()

    def fill():
        t = time.perf_counter()
        while free:
            job = next(jobs_it, None)
            if job is None:
                break
            env = free.pop()
            try:
                live.append(new_match(env, job, learner, opponents, cfg))
            except skip as exc:
                free.append(env)
                skipped.append({"tag": job[1]["tag"], "why": str(exc)})
        T["reset"] += time.perf_counter() - t

    def serve(reqs):
        t = time.perf_counter()
        conn.send(("cell", reqs))
        r = conn.recv()
        T["wait_cell"] += time.perf_counter() - t
        return r

    try:
        fill()
        while live:
            t = time.perf_counter()
            due = []
            for m in list(live):
                ds = m.due()
                if ds:
                    due += ds
                else:
                    live.remove(m)
                    free.append(m.env)
                    results.append(m.result())
            T["due"] += time.perf_counter() - t
            fill()
            if not due:
                continue
            t = time.perf_counter()
            for s in due:
                s.prepare()
            groups: dict = {}
            for s in due:
                key = (pol_ix[id(s.model)], "_opp_style" in s.cfg)   # = run_selfplay_batch's grouping
                groups.setdefault(key, []).append(s)
            rows = {k: [s.gen_row(s.model) if isinstance(s.model, E.GenPolicy) else s._obs for s in ss]
                    for k, ss in groups.items()}
            T["prepare_row"] += time.perf_counter() - t
            t = time.perf_counter()
            conn.send(("fwd", rows))
            outs = conn.recv()
            T["wait_fwd"] += time.perf_counter() - t
            t = time.perf_counter()
            dec = decide_groups(groups, outs, waves, serve)
            conn.send(("cell", None))                  # this round's decides are done
            T["decide"] += time.perf_counter() - t
            t = time.perf_counter()                    # every decision of the round before any acts, in group order
            todo = [(s, dec[k][0][r], dec[k][1][r]) for k, ss in groups.items() for r, s in enumerate(ss)]
            for s, pr, d in todo:
                s.apply(pr, d)
            T["apply"] += time.perf_counter() - t
            rounds += 1
        T["decide"] -= T["wait_cell"]
        conn.send(("end", results, skipped, {"rounds": rounds, "time_s": {k: round(v, 3) for k, v in T.items()}}))
    except BaseException:
        import traceback
        conn.send(("error", traceback.format_exc()))
    finally:
        conn.close()


# ---- server ---------------------------------------------------------------------------------------------------------
def _device_policy(pol, device: str):
    """A copy of ``pol`` (GenPolicy or S1Model) whose network lives on ``device``."""
    if isinstance(pol, E.GenPolicy):
        q = copy.copy(pol)
        q.model = copy.deepcopy(pol.model).to(device).eval()
        return q
    return copy.deepcopy(pol).to(device).eval()


class LazyRefine:
    """Server-side GenPolicy whose forward skips the features only the cell head reads (``cell_refine`` per-cell
    features, ``tower_refine``'s cell features: [B, 2304, C] for EVERY row) and whose ``cell_logits`` computes them for
    the requested rows only (about 3% of rows place a card). Same math per row as ``GenPolicy``; ``stats`` = stack /
    device seconds of the forwards."""

    def __init__(self, pol):
        self.pol, self.model = pol, pol.model
        self.cr = getattr(pol.model, "cell_refine", None)
        tr = getattr(pol.model, "tower_refine", None)
        self.tr = tr if tr is not None and tr.use_cell else None
        self.stats = {"stack_s": 0.0, "device_s": 0.0}
        self.fwd_pol = None

    def split(self):
        """A separate forward copy of the network with the cell-only features switched off for good, so a cell call
        (on the original, refine layers in place) can run while a forward runs (S4b: no swap to race with)."""
        if self.fwd_pol is None and (self.cr is not None or self.tr is not None):
            q = copy.copy(self.pol)
            q.model = copy.deepcopy(self.model)
            q.model.cell_refine = None
            if self.tr is not None:
                q.model.tower_refine.use_cell = False
            self.fwd_pol = q
        return self

    def forward_batch(self, rows, device: str = "cpu"):
        import torch
        m = self.model
        t = time.perf_counter()
        with torch.no_grad():
            b = {k: torch.from_numpy(np.ascontiguousarray(np.stack([r[k] for r in rows]))).to(device)
                 for k in E.gen_row_keys(m)}
            t1 = time.perf_counter()
            if self.cr is not None:
                m.cell_refine = None
            if self.tr is not None:
                self.tr.use_cell = False
            try:
                enc, heads = self.pol.heads_t(b)
            finally:
                if self.cr is not None:
                    m.cell_refine = self.cr
                if self.tr is not None:
                    self.tr.use_cell = True
            if self.cr is not None:
                enc["_xy"], enc["_mask"] = b["tok"][..., 4:6], b["mask"]
            if self.tr is not None:
                enc["_sc"] = b["sc"]
            B = heads["card"].shape[0]
            hand = torch.zeros(B, E.N_SLOTS + 1, dtype=torch.bool, device=heads["card"].device)
            hand = hand.scatter(1, b["hand_slot"], True)[:, :E.N_SLOTS]
            p = torch.sigmoid(heads["gate"]).cpu().tolist()
        self.stats["stack_s"] += t1 - t
        self.stats["device_s"] += time.perf_counter() - t1
        return enc, heads, p, hand.cpu().numpy()

    def cell_logits(self, enc: dict, slot):
        enc = dict(enc)
        xy, mask, sc = enc.pop("_xy", None), enc.pop("_mask", None), enc.pop("_sc", None)
        if self.cr is not None:
            enc["cell_feat"] = self.cr.features(enc["u"], xy, mask)
        if self.tr is not None:
            enc["tower_cell_feat"] = self.tr.cell_feat(sc)
        return self.pol.cell_logits(enc, slot)


_HEADS_CLS: list = []


def _HeadsT(pol):
    """torch.func target: ``GenPolicy.heads_t`` as a module call (functional_call swaps the parameters in). One class
    for every policy (stack_module_state needs equal classes)."""
    import torch
    if not _HEADS_CLS:
        class HeadsT(torch.nn.Module):
            def __init__(self, pol):
                super().__init__()
                self.model = pol.model
                self.pol = copy.copy(pol)

            def forward(self, b):
                self.pol.model = self.model
                return self.pol.heads_t(b)
        _HEADS_CLS.append(HeadsT)
    return _HEADS_CLS[0](pol)


def merge_key(pol):
    """Policies with equal keys can share one vmapped forward: plain GenModels (no cue / refine / memory layers)
    with the same parameter names and shapes. None = not mergeable."""
    if not isinstance(pol, E.GenPolicy):
        return None
    m = pol.model
    if any(getattr(m, a, None) is not None for a in ("cue_in", "cell_refine", "tower_refine", "mem", "mem_aux")):
        return None
    return (int(getattr(m, "feature_version", 1)),) + tuple((n, tuple(v.shape)) for n, v in m.state_dict().items())


class Merged:
    """K same-architecture policies (``merge_key``) in ONE GPU call: ``torch.func.stack_module_state`` +
    ``vmap(functional_call)``, each member's rows padded to the largest member's count with copies of its first row
    (padding rows are dropped from the outputs). Per member the outputs are ``GenPolicy.forward_batch``'s (enc, heads,
    p, hand) up to float noise (merge_probe.py: max abs diff 1.3e-5 on card logits)."""

    def __init__(self, pols: list, device: str):
        import torch
        from torch.func import stack_module_state
        self.pols = pols
        mods = [_HeadsT(p) for p in pols]
        self.params, self.buffers = stack_module_state(mods)
        self.base = copy.deepcopy(mods[0]).to("meta").eval()
        self.keys = E.gen_row_keys(pols[0].model)
        self.torch = torch

    def forward(self, members: list, rows_list: list, device: str) -> list:
        torch = self.torch
        from torch.func import functional_call
        n = [len(r) for r in rows_list]
        B = max(n)
        b = {k: torch.from_numpy(np.ascontiguousarray(np.stack([np.stack([r[k] for r in rows] + [rows[0][k]] * (B - len(rows)))
                                                                for rows in rows_list]))).to(device) for k in self.keys}
        ix = torch.as_tensor(members, device=device)
        pr = {a: v.index_select(0, ix) for a, v in self.params.items()}
        bu = {a: v.index_select(0, ix) for a, v in self.buffers.items()}
        with torch.no_grad():
            enc, heads = torch.vmap(lambda p_, b_, x: functional_call(self.base, (p_, b_), (x,)))(pr, bu, b)
            out = []
            for j, nj in enumerate(n):
                e = {a: v[j, :nj] for a, v in enc.items()}
                h = {a: v[j, :nj] for a, v in heads.items()}
                hs = b["hand_slot"][j, :nj]
                hand = torch.zeros(nj, E.N_SLOTS + 1, dtype=torch.bool, device=hs.device).scatter(1, hs, True)[:, :E.N_SLOTS]
                out.append((e, h, torch.sigmoid(h["gate"]).cpu().tolist(), hand.cpu().numpy()))
        return out


def _forward(pol, rows: list, device: str):
    if isinstance(pol, (E.GenPolicy, LazyRefine)):
        return pol.forward_batch(rows, device)
    return E.model_forward_batch(pol, *zip(*rows), device=device)


def run(make_env, learner, opponents: dict, jobs, cfg: dict, on_result, on_skip=None, skip=(), *, workers: int = 8,
        in_flight: Optional[int] = None, device: str = "cuda", cohorts: int = 2, amp: Optional[str] = None,
        fast=(), worker_nice: int = 0) -> dict:
    """Play ``jobs`` ((i, spec, k[, overrides]) as run_selfplay_batch) on ``workers`` processes, each with up to
    ``in_flight`` matches (default: all of its share at once). ``learner`` / ``opponents`` / ``cfg``: as
    run_selfplay_batch (CPU policies; the forked workers use them for rows and decides, the server copies them to
    ``device`` for the forward). ``on_result(line)`` per finished match (worker order), ``on_skip(spec, exc_str)``.
    ``cohorts``: the workers split into this many groups (worker index mod cohorts), each in lockstep on its own and
    served in turn, so one cohort's CPU work overlaps the server's forward for the other (1 = one lockstep).
    ``amp`` "bf16": the server's forward and cell calls under bf16 autocast (NOT the actors' fp32: the sampled
    actions / log-probs then differ from the actor path's; a throughput option, off by default).
    ``fast`` (opt-in, each identity-checked in speed/SPEED.md f): "refine" = ``LazyRefine`` on the server; "cue" =
    ``pipeline.fast_obs.sim_cue_rows`` in the workers; "merge" = same-architecture policies share one vmapped forward
    (``Merged``). ``worker_nice``: os.nice for the workers (the server forward is CPU-launch-bound: 321 kernel launches
    per call; it ran 2x slower under a full worker load than alone, server_prof.py).
    -> stats: rounds, server time split (forward / cell / waiting for workers), per-worker time split."""
    import torch
    check_cfgs(cfg, opponents)
    jobs = list(jobs)
    pols = [learner] + [p for p, _ in opponents.values()]
    pol_ix: dict = {}
    for p in pols:
        pol_ix.setdefault(id(p), len(pol_ix))
    by_ix = {ix: next(p for p in pols if id(p) == pid) for pid, ix in pol_ix.items()}
    shares = [jobs[w::workers] for w in range(workers)]
    ctx = mp.get_context("fork")                       # the workers inherit the policies, cfgs and make_env as is
    conns, procs = [], []
    for w, share in enumerate(shares):
        if not share:
            continue
        a, b = ctx.Pipe()
        pr = ctx.Process(target=_worker, args=(w, b, make_env, learner, opponents, cfg, share,
                                               in_flight or len(share), pol_ix, skip, tuple(fast),
                                               int(worker_nice)), daemon=True)
        pr.start()
        b.close()
        conns.append(a)
        procs.append(pr)
    dev = {ix: _device_policy(p, device) for ix, p in by_ix.items()}   # after the fork: no CUDA state in workers
    merged: dict = {}                                  # pol_ix -> (Merged, member index)
    if "merge" in fast:
        by_key: dict = {}
        for ix, p in dev.items():
            mk = merge_key(p)
            if mk is not None:
                by_key.setdefault(mk, []).append(ix)
        for ixs in by_key.values():
            if len(ixs) > 1:
                grp = Merged([dev[i] for i in ixs], device)
                merged.update({i: (grp, j) for j, i in enumerate(ixs)})
    if "refine" in fast:
        dev = {ix: LazyRefine(p) if isinstance(p, E.GenPolicy) and ix not in merged else p for ix, p in dev.items()}
    autocast = (lambda: torch.autocast("cuda", dtype=torch.bfloat16)) if amp == "bf16" else contextlib.nullcontext
    S = {"forward_s": 0.0, "cell_s": 0.0, "wait_s": 0.0, "rows": 0, "forwards": 0, "cell_calls": 0, "rounds": 0}
    wstats, lines = [], [[] for _ in conns]
    t_all = time.perf_counter()

    def recv_all(ws):
        t = time.perf_counter()
        got = {w: conns[w].recv() for w in ws}
        S["wait_s"] += time.perf_counter() - t
        for w, msg in got.items():
            if msg[0] == "error":
                raise RuntimeError(f"batched_rollout worker {w} failed:\n{msg[1]}")
        return got

    def one_round(active: list) -> list:
        """One lockstep round of the workers ``active`` -> the ones still playing."""
        got = recv_all(active)
        fwd = []
        for w, msg in got.items():
            if msg[0] == "end":
                lines[w], st = msg[1], msg[3]
                wstats.append(st)
                for sk in msg[2]:
                    if on_skip:
                        on_skip({"tag": sk["tag"]}, sk["why"])
            else:
                fwd.append(w)
        if not fwd:
            return fwd
        S["rounds"] += 1
        t = time.perf_counter()
        keys = sorted({k for w in fwd for k in got[w][1]})
        enc_of, outs = {}, {w: {} for w in fwd}
        off: dict = {}
        rows_of: dict = {}
        for k in keys:
            rows, o = [], 0
            for w in fwd:
                r = got[w][1].get(k)
                if r:
                    off[(w, k)] = o
                    rows += r
                    o += len(r)
            rows_of[k] = rows
        res: dict = {}
        for grp in {id(merged[k[0]][0]): merged[k[0]][0] for k in keys if k[0] in merged}.values():
            ks = [k for k in keys if k[0] in merged and merged[k[0]][0] is grp]
            if len(ks) > 1:
                with autocast():
                    res.update(zip(ks, grp.forward([merged[k[0]][1] for k in ks], [rows_of[k] for k in ks], device)))
                S["merged_calls"] = S.get("merged_calls", 0) + 1
        for k in keys:
            rows = rows_of[k]
            if k in res:
                enc, heads, p, hand = res[k]
            else:
                with autocast():
                    enc, heads, p, hand = _forward(dev[k[0]], rows, device)
                S["forwards"] += 1
            enc_of[k] = enc
            cpu = lambda x: x.detach().float().cpu().numpy()    # noqa: E731
            gate, card = cpu(heads["gate"]), cpu(heads["card"])
            ch = cpu(heads["card_hand"]) if "card_hand" in heads else np.zeros((len(rows), 0), np.float32)
            g = cpu(enc["g"])
            p = np.asarray(p, np.float64)
            for w in fwd:
                if (w, k) in off:
                    s0, n = off[(w, k)], len(got[w][1][k])
                    outs[w][k] = (gate[s0:s0 + n], card[s0:s0 + n], ch[s0:s0 + n], p[s0:s0 + n], hand[s0:s0 + n],
                                  g[s0:s0 + n])
            S["rows"] += len(rows)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        S["forward_s"] += time.perf_counter() - t
        for w in fwd:
            conns[w].send(outs[w])
        waiting = list(fwd)                        # cell waves until every worker reports its decides done
        while waiting:
            got = recv_all(waiting)
            t = time.perf_counter()
            reqs = {w: m[1] for w, m in got.items() if m[1] is not None}
            waiting = list(reqs)
            per_k: dict = {}
            for w, rq in reqs.items():
                for j, (k, rows, slot) in enumerate(rq):
                    per_k.setdefault(k, []).append((w, j, rows + off[(w, k)], slot))
            ans = {w: [None] * len(rq) for w, rq in reqs.items()}
            with torch.no_grad(), autocast():
                for k, items in per_k.items():
                    rows = np.concatenate([x[2] for x in items])
                    slot = np.concatenate([x[3] for x in items])
                    ix = torch.as_tensor(rows, device=device)
                    sub = {a: v[ix] for a, v in enc_of[k].items()}
                    lg = dev[k[0]].cell_logits(sub, torch.as_tensor(slot, device=device)).detach().float().cpu().numpy()
                    S["cell_calls"] += 1
                    o = 0
                    for w, j, r, _ in items:
                        ans[w][j] = lg[o:o + len(r)]
                        o += len(r)
            S["cell_s"] += time.perf_counter() - t
            for w in reqs:
                conns[w].send(ans[w])
        return fwd

    try:
        groups = [list(range(c, len(conns), max(1, cohorts))) for c in range(max(1, cohorts))]
        while any(groups):
            groups = [one_round(g) if g else g for g in groups]
        for w in range(len(conns)):
            for line in lines[w]:
                on_result(line)
    finally:
        for pr in procs:
            pr.join(timeout=30)
            if pr.is_alive():
                pr.terminate()
    S["wall_s"] = time.perf_counter() - t_all
    for k in ("stack_s", "device_s"):
        if any(isinstance(p, LazyRefine) for p in dev.values()):
            S[f"forward_{k}"] = sum(p.stats[k] for p in dev.values() if isinstance(p, LazyRefine))
    S["workers"] = wstats
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in S.items()}
