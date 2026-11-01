"""MGPU: data-parallel PPO learner (opt-in; absent = rl_royale's single-GPU learner, byte-identical).

Rank 0 is the learner process itself (Learner.one_update, league, logs, checkpoints, screens: untouched). Ranks 1.. are helper
replaces ``R.ppo_update``; per update it
  1. tells the helpers to start (an mp queue message: cfg, beta, the rng state, the loss options, the batch layout),
  2. broadcasts the learner's state (model, KL anchor, ability head weights + both Adam states) from rank 0 -- the helpers
     keep no state of their own between updates, so resume / restore / warm start need no special case,
  3. broadcasts the batch (the GPU tensors over the default group, the CPU memory tables over a gloo group),
  4. every rank then runs the SAME ``ppo_update(..., dp=DPCtx)``: each minibatch's micro-batches are dealt out (micro-batch j
     on rank j % world; ``rl_royale.accum_backward``), every rank backpropagates its own, the per-micro-batch losses and
     monitors are all-gathered and merged in micro-batch order (so the KL stop / nonfinite decisions are the single-GPU
     values on every rank), the ranks' gradients are summed IN RANK ORDER (``DPCtx.reduce_grads``: all-gather + a fixed-order
     sum, so every rank holds bit-identical gradients, the same for every run) and every rank takes the same clip + Adam step.
  5. a hash of the weights is compared across ranks after the update (a divergence raises).
What one update trains on is unchanged (same rows, same minibatch / micro-batch partition, same permutation: the helpers
get the learner's rng state); the only difference from single-GPU accumulation is the float32 summation order of the
gradient (sum over ranks of the sum over each rank's micro-batches) -- measured in pipeline/tests/test_learner_dp.py and
cf rows, ability head, ent_pair, mem_row_cache, split_attn, trunk_graph); anything else raises at the first update.
Backends: nccl (GPUs) / gloo (CPU tests; also works on CUDA tensors, slower).
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np
import torch
import torch.distributed as dist

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

TIMEOUT = datetime.timedelta(minutes=30)       # a collective that waits longer = a dead peer
LAZY_KEYS = {"x", "card_lp", "cell_lp", "play_pos", "kl_heads"}   # what Learner.one_update leaves in a LazyRef


# ------------------------------------------------------------------------------------------------------
# collectives
# ------------------------------------------------------------------------------------------------------
class DPCtx:
    """What the PPO steps see: this rank's place in the group + the two collectives they need."""

    def __init__(self, rank: int, world: int, group=None, cpu_group=None):
        self.rank, self.world, self.group, self.cpu_group = rank, world, group, cpu_group

    def owns(self, j: int) -> bool:
        """Micro-batch j of a minibatch is computed on this rank."""
        return j % self.world == self.rank

    def gather(self, obj) -> list:
        """Every rank's ``obj`` (picklable), in rank order, on every rank."""
        if self.world == 1:
            return [obj]
        out = [None] * self.world
        dist.all_gather_object(out, obj, group=self.cpu_group)
        return out

    def reduce_grads(self, params: list) -> None:
        """p.grad <- the sum over ranks, bit-identical on every rank (the ranks' flat gradients are all-gathered and added
        in rank order: independent of NCCL's reduction algorithm). A parameter no rank touched keeps grad None."""
        if self.world == 1 or not params:
            return
        dev = params[0].device
        if any(p.dtype != torch.float32 for p in params):
            raise RuntimeError("learner DP: gradients are summed as float32 (a parameter has another dtype)")
        parts = [(p.grad if p.grad is not None else torch.zeros_like(p)).reshape(-1) for p in params]
        flat = torch.cat(parts + [torch.tensor([p.grad is not None for p in params], dtype=torch.float32, device=dev)])
        bufs = [torch.empty_like(flat) for _ in range(self.world)]
        dist.all_gather(bufs, flat, group=self.group)
        tot = bufs[0]
        for b in bufs[1:]:
            tot = tot + b
        has = (tot[-len(params):] > 0).tolist()
        off = 0
        for p, h in zip(params, has):
            n = p.numel()
            p.grad = tot[off:off + n].view_as(p) if h else None
            off += n


def _bc(t: torch.Tensor, src: int, group) -> None:
    """In-place broadcast of one tensor from ``src`` (bool travels as uint8)."""
    if t.numel():
        dist.broadcast(t.view(torch.uint8) if t.dtype == torch.bool else t, src, group=group)


@torch.no_grad()
def bcast_tensors(ts: list, ctx: "DPCtx", src: int = 0) -> None:
    """Every tensor of ``ts`` (same shapes / dtypes on every rank, the same devices up to the rank's own GPU) takes rank
    """
    groups: dict = {}
    for t in ts:
        groups.setdefault((t.dtype, t.device.type), []).append(t)
    for (_, kind), lst in groups.items():
        flat = torch.cat([t.reshape(-1) for t in lst])
        _bc(flat, src, ctx.cpu_group if kind == "cpu" else ctx.group)
        off = 0
        for t in lst:
            n = t.numel()
            if ctx.rank != src:
                t.copy_(flat[off:off + n].view_as(t))
            off += n


def opt_params(opt) -> list:
    return [p for g in opt.param_groups for p in g["params"]]


def opt_layout(opt) -> dict:
    """What a helper needs to mirror rank 0's optimizer: the group hyper-parameters (lr moves with kl_lr_target), which
    parameters have state, their non-step state keys, the step counters."""
    ps = opt_params(opt)
    keys = [(i, k) for i, p in enumerate(ps) if p in opt.state for k in sorted(opt.state[p])
            if k != "step" and torch.is_tensor(opt.state[p][k])]
    steps = {i: (float(opt.state[p]["step"]), str(opt.state[p]["step"].dtype)) for i, p in enumerate(ps)
             if p in opt.state and "step" in opt.state[p]}
    return {"groups": [{k: v for k, v in g.items() if k != "params"} for g in opt.param_groups], "keys": keys, "steps": steps}


def opt_apply(opt, lay: dict) -> list:
    """Helper side: make ``opt`` the layout's shape (state cleared, zero tensors for every key, steps set); -> the state
    tensors in layout order, to be broadcast into."""
    for g, h in zip(opt.param_groups, lay["groups"]):
        g.update(h)
    ps = opt_params(opt)
    opt.state.clear()
    for i, (v, dt) in lay["steps"].items():
        opt.state[ps[i]]["step"] = torch.tensor(v, dtype=getattr(torch, dt.split(".")[1]))
    for i, k in lay["keys"]:
        opt.state[ps[i]][k] = torch.zeros_like(ps[i])
    return opt_state_tensors(opt, lay)


def opt_state_tensors(opt, lay: dict) -> list:
    ps = opt_params(opt)
    return [opt.state[ps[i]][k] for i, k in lay["keys"]]


def weights_hash(*mods) -> str:
    h = hashlib.sha1()
    for m in mods:
        for p in m.parameters():
            h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()[:16]


def _sync(dev: str) -> None:
    if dev.startswith("cuda"):
        torch.cuda.synchronize(torch.device(dev))


def _dtype(s: str):
    return getattr(torch, s.split(".")[1])


def batch_layout(B: dict) -> list:
    out = []
    for k, v in B.items():
        if k.startswith("_"):
            continue
        if torch.is_tensor(v):
            out.append((k, "t", str(v.dtype), tuple(v.shape)))
        elif isinstance(v, np.ndarray) and v.dtype != object:
            out.append((k, "n", v.dtype.str, tuple(v.shape)))
        else:
            raise RuntimeError(f"learner DP: batch key {k!r} is a {type(v).__name__}; only tensors / numeric arrays travel")
    return out


def batch_xfer(lay: list, B, dev, group, cpu_group, src_side: bool) -> dict:
    """Rank 0 (``src_side``): broadcast B. Helper: allocate per ``lay`` and receive it. -> the batch dict."""
    out = {}
    for k, kind, dt, shape in lay:
        if kind == "t":
            t = B[k].contiguous() if src_side else torch.empty(shape, dtype=_dtype(dt), device=dev)
            _bc(t, 0, group)
            out[k] = t
        else:
            a = np.ascontiguousarray(B[k]) if src_side else np.empty(shape, dtype=np.dtype(dt))
            t = torch.from_numpy(a if a.flags.writeable else a.copy())
            _bc(t, 0, cpu_group)
            out[k] = t.numpy() if not src_side else a
    return out


def torch_flags() -> dict:
    """"""
    return {"deterministic": torch.are_deterministic_algorithms_enabled(), "benchmark": torch.backends.cudnn.benchmark,
            "cudnn_tf32": torch.backends.cudnn.allow_tf32, "matmul_tf32": torch.backends.cuda.matmul.allow_tf32,
            "cublas": os.environ.get("CUBLAS_WORKSPACE_CONFIG"), "threads": torch.get_num_threads()}


def apply_flags(f: dict) -> None:
    if f.get("cublas"):
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = f["cublas"]
    torch.use_deterministic_algorithms(bool(f["deterministic"]))
    torch.backends.cudnn.benchmark = bool(f["benchmark"])
    torch.backends.cudnn.allow_tf32 = bool(f["cudnn_tf32"])
    torch.backends.cuda.matmul.allow_tf32 = bool(f["matmul_tf32"])
    torch.set_num_threads(int(f["threads"]))


def init_group(backend: str, url: str, rank: int, world: int, dev: str):
    """Default group (backend) + a gloo group for objects / CPU tables (the same group on the gloo backend)."""
    kw = {"device_id": torch.device(dev)} if backend == "nccl" else {}
    dist.init_process_group(backend, init_method=url, rank=rank, world_size=world, timeout=TIMEOUT, **kw)
    cpu = dist.new_group(backend="gloo", timeout=TIMEOUT) if backend != "gloo" else dist.group.WORLD
    return dist.group.WORLD, cpu


# ------------------------------------------------------------------------------------------------------
# the PPO call, on every rank
# ------------------------------------------------------------------------------------------------------
def run_ppo(RL, ctx: DPCtx, dev: str, state: dict, msg: dict, B=None, orig=None, tm=None):
    """One update's collective sequence + ppo_update, identical on rank 0 (``B`` given, ``orig`` = the real ppo_update) and the
    helpers (B received). ``state``: model / ref / ref_init / ability head + opts of THIS rank."""
    model, ref, head = state["model"], state["ref"], state.get("head")
    opt, hopt = state["opt"], state.get("hopt")
    tensors = list(model.state_dict().values()) + list(ref.state_dict().values())
    if head is not None:
        tensors += list(head.state_dict().values())
    side0 = ctx.rank == 0
    t0 = time.perf_counter()
    if not side0:                                              # helpers: mirror the optimizers' shape first
        tensors += opt_apply(opt, msg["opt"]) + (opt_apply(hopt, msg["hopt"]) if hopt is not None else [])
    else:
        tensors += opt_state_tensors(opt, msg["opt"]) + (opt_state_tensors(hopt, msg["hopt"]) if hopt is not None else [])
    bcast_tensors(tensors, ctx)
    _sync(dev)
    t1 = time.perf_counter()
    Bd = batch_xfer(msg["batch"], B, dev, ctx.group, ctx.cpu_group, side0)
    _sync(dev)
    t2 = time.perf_counter()
    if side0:
        Bd = B
    else:
        if msg["cfg"].get("mem_row_cache") and getattr(model, "mem", None) is not None and "mem_row_t" in Bd:
            Bd["_mem_cache"] = RL.MemRowCache(len(Bd["A"]))
    r = msg["R"]
    R = msg["R_obj"] if side0 else RL.LazyRef(ref, Bd, r["tau"], r["T"], T_gate=r["T_gate"])
    if not side0 and r["kl_heads"] is not None:
        R["kl_heads"] = tuple(r["kl_heads"])
    ab = None if head is None else {"head": head, "opt": hopt, "ent_coef": msg["ab_ent_coef"]}
    if side0:
        ab = msg["ability"]
    rng = msg["rng_obj"] if side0 else np.random.default_rng()
    if not side0:
        rng.bit_generator.state = msg["rng"]
    vf = msg["vf"]
    fn = orig if side0 else RL.ppo_update
    ent_ref = msg["ent_ref_obj"] if side0 else (state["ref_init"] if msg["ent_ref"] else None)
    out = fn(model, opt, Bd, R, msg["cfg"], msg["beta"], rng, vf=vf, ability=ab, ent_ref=ent_ref, dp=ctx)
    _sync(dev)
    t3 = time.perf_counter()
    hs = ctx.gather(weights_hash(model, *([head] if head is not None else [])))
    if len(set(hs)) != 1:                                      # every rank sees the same hs, so every rank takes this branch
        per = ctx.gather([hashlib.sha1(p.detach().cpu().numpy().tobytes()).hexdigest()[:8] for p in model.parameters()])
        bad = [n for (n, _), *hh in zip(model.named_parameters(), *per) if len(set(hh)) > 1]
        raise RuntimeError(f"learner DP: the ranks' weights diverged after the update: {hs}; parameters that differ: {bad[:6]}")
    if tm is not None:                                         # seconds: state sync, batch broadcast, the PPO steps, the check
        tm.update(sync=t1 - t0, batch=t2 - t1, ppo=t3 - t2, check=time.perf_counter() - t3)
    return out


# ------------------------------------------------------------------------------------------------------
# helper processes
# ------------------------------------------------------------------------------------------------------
def _parent_watch() -> None:
    import multiprocessing as mp
    parent = mp.parent_process()

    def loop():
        while True:
            time.sleep(5)
            if parent is not None and not parent.is_alive():
                os._exit(1)
    threading.Thread(target=loop, daemon=True).start()


def worker_main(rank: int, world: int, url: str, backend: str, devices: list, flags: dict, model, ref_init, head, opt_cls,
                opt_kw: dict, hopt_cls, hopt_kw, in_q, out_q) -> None:
    """A helper rank for the whole run: waits for ("ppo", msg) on ``in_q``, None = exit."""
    import queue
    try:
        _parent_watch()
        dev = devices[rank]
        if dev.startswith("cuda"):
            torch.cuda.set_device(torch.device(dev))
        apply_flags(flags)
        from pipeline import rl_royale as RL
        group, cpu_group = init_group(backend, url, rank, world, dev)
        model = copy.deepcopy(model).to(dev).eval()           # a PRIVATE copy: the spawn args of every helper share one set of
        ref = copy.deepcopy(model).eval()                    # shared-memory CPU tensors (CPU ranks would step on each other)
        for p in ref.parameters():
            p.requires_grad_(False)
        state = {"model": model, "ref": ref, "opt": opt_cls(model.parameters(), **opt_kw),
                 "ref_init": None if ref_init is None else copy.deepcopy(ref_init).to(dev).eval()}
        if head is not None:
            state["head"] = copy.deepcopy(head).to(dev)
            state["hopt"] = hopt_cls(state["head"].parameters(), **hopt_kw)
        ctx = DPCtx(rank, world, group, cpu_group)
        out_q.put(("ready", rank, os.getpid()))
    except BaseException:
        out_q.put(("error", rank, traceback.format_exc()))
        os._exit(1)
    while True:
        try:
            msg = in_q.get(timeout=30)
        except queue.Empty:
            continue
        if msg is None:
            break
        try:
            run_ppo(RL, ctx, dev, state, msg[1])
            state["model"].zero_grad(set_to_none=True)
        except BaseException:
            out_q.put(("error", rank, traceback.format_exc()))
            os._exit(1)
    try:
        dist.destroy_process_group()
    except Exception:
        pass
    os._exit(0)


# ------------------------------------------------------------------------------------------------------
# rank 0
# ------------------------------------------------------------------------------------------------------
class Coordinator:
    def __init__(self, devices: list, backend: str | None = None, log=print):
        self.devices = [str(d) for d in devices]
        self.world = len(self.devices)
        self.backend = backend or ("nccl" if self.devices[0].startswith("cuda") else "gloo")
        self.log = log
        self.procs, self.qs, self.ctx = [], [], None
        self.out_q = None
        self.sig = None
        self.timing = []                                          # per update: sync / batch / ppo / check seconds (rank 0)
        self.start_s = None                                       # seconds the helpers took to come up

    # -- startup -----------------------------------------------------------------------------------
    def _start(self, model, opt, ability, ent_ref) -> None:
        import torch.multiprocessing as tmp
        dev0 = next(model.parameters()).device
        if dev0.type != self.devices[0].split(":")[0] or (dev0.type == "cuda" and dev0.index != int(self.devices[0].split(":")[1])):
            raise SystemExit(f"learner DP: rank 0's model is on {dev0}, the first learner device is {self.devices[0]}")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            url = f"tcp://127.0.0.1:{s.getsockname()[1]}"
        mp_ctx = tmp.get_context("spawn")
        self.out_q = mp_ctx.Queue()
        self._ready = 0
        okw = {k: v for k, v in opt.defaults.items() if v is not None}
        head = None if ability is None else copy.deepcopy(ability["head"]).cpu()
        hkw = None if ability is None else {k: v for k, v in ability["opt"].defaults.items() if v is not None}
        mcpu = copy.deepcopy(model).cpu()
        icpu = None if ent_ref is None else copy.deepcopy(ent_ref).cpu()
        for r in range(1, self.world):
            q = mp_ctx.Queue()
            p = mp_ctx.Process(target=worker_main, args=(r, self.world, url, self.backend, self.devices, torch_flags(), mcpu,
                                                         icpu, head, type(opt), okw,
                                                         None if ability is None else type(ability["opt"]), hkw, q,
                                                         self.out_q), daemon=True)
            p.start()
            self.procs.append(p)
            self.qs.append(q)
        t0 = time.time()
        threading.Thread(target=self._watch, daemon=True).start()      # a helper dying before the group forms must not hang us
        group, cpu_group = init_group(self.backend, url, 0, self.world, self.devices[0])
        self.ctx = DPCtx(0, self.world, group, cpu_group)
        ready = 0
        while ready < self.world - 1:
            self._drain(raise_error=True)
            ready = self._ready
            if time.time() - t0 > 900:
                raise RuntimeError("learner DP: helpers not ready after 900 s")
            time.sleep(0.2)
        self.start_s = time.time() - t0
        self.log(f"[dp] learner data-parallel: {self.world} ranks on {self.devices} ({self.backend}), helpers pids "
                 f"{[p.pid for p in self.procs]}, started in {self.start_s:.0f} s")

    def _drain(self, raise_error: bool) -> None:
        import queue
        while True:
            try:
                m = self.out_q.get_nowait()
            except queue.Empty:
                return
            if m[0] == "ready":
                self._ready += 1
            elif m[0] == "error":
                self.log(f"[rl] CRASH: learner DP helper rank {m[1]} failed:\n{m[2]}")
                if raise_error:
                    raise RuntimeError(f"learner DP helper rank {m[1]} failed:\n{m[2]}")

    def _watch(self) -> None:
        """A dead helper leaves rank 0 blocked in a collective for the whole timeout: stop the run at once instead (the chain
        sees '[rl] CRASH' in the log and resumes from the last checkpoint)."""
        while self.procs:
            time.sleep(5)
            for r, p in enumerate(self.procs, 1):
                if not p.is_alive():
                    self._drain(raise_error=False)
                    self.log(f"[rl] CRASH: learner DP helper rank {r} (pid {p.pid}) exited {p.exitcode}")
                    sys.stdout.flush()
                    sys.stderr.flush()
                    os._exit(3)

    # -- one update ---------------------------------------------------------------------------------
    def ppo_update(self, orig, model, opt, B, R, cfg, beta, rng, vf=None, posture=None, ability=None, ent_ref=None, th_ref=None):
        from pipeline import rl_royale as RL
        if self.world == 1:                                       # no peers: the dp path of one rank (tests)
            return orig(model, opt, B, R, cfg, beta, rng, vf=vf, posture=posture, ability=ability, ent_ref=ent_ref,
                        th_ref=th_ref, dp=DPCtx(0, 1))
        if not isinstance(R, RL.LazyRef) or set(R) - LAZY_KEYS or posture is not None or th_ref is not None \
                or (vf or {}).get("ctx_head") is not None:
            raise SystemExit("learner DP supports the stored_values learner only (LazyRef anchor; no posture / critic_ctx / "
                             "timing-head options)")
        sig = (ability is not None, ent_ref is not None, type(opt).__name__)
        if self.procs and sig != self.sig:                        # the helpers were built for another option set: rebuild them
            self.close()
        if not self.procs:
            self._start(model, opt, ability, ent_ref)
            self.sig = sig
        self._drain(raise_error=True)
        msg = {"cfg": cfg, "beta": beta, "rng": rng.bit_generator.state, "vf": vf, "ent_ref": ent_ref is not None,
               "R": {"tau": R.tau, "T": R.T, "T_gate": R.T_gate, "kl_heads": R.get("kl_heads")},
               "opt": opt_layout(opt), "hopt": None if ability is None else opt_layout(ability["opt"]),
               "ab_ent_coef": None if ability is None else ability["ent_coef"], "batch": batch_layout(B)}
        for q in self.qs:
            q.put(("ppo", msg))
        local = {"model": model, "ref": R.ref, "opt": opt, "head": None if ability is None else ability["head"],
                 "hopt": None if ability is None else ability["opt"]}
        tm = {}
        out = run_ppo(RL, self.ctx, self.devices[0], local, {**msg, "R_obj": R, "rng_obj": rng, "ability": ability,
                                                             "ent_ref_obj": ent_ref}, B=B, orig=orig, tm=tm)
        self._drain(raise_error=True)
        self.timing.append(tm)
        return out

    def close(self) -> None:
        procs, self.procs = self.procs, []
        for q in self.qs:
            try:
                q.put(None)
            except Exception:
                pass
        for p in procs:
            p.join(20)
            if p.is_alive():
                p.terminate()
                p.join(5)
        if self.ctx is not None:
            try:
                dist.destroy_process_group()
            except Exception:
                pass
            self.ctx = None
        self.qs = []


def install(R, devices: list, backend: str | None = None, log=print) -> Coordinator:
    """Route rl_royale's PPO steps through ``Coordinator`` (module global lookup: Learner.one_update calls ``ppo_update`` by
    """
    coord = Coordinator(devices, backend, log)
    orig = R.ppo_update

    def ppo_update(model, opt, B, Rr, cfg, beta, rng, vf=None, posture=None, ability=None, ent_ref=None, th_ref=None):
        return coord.ppo_update(orig, model, opt, B, Rr, cfg, beta, rng, vf, posture, ability, ent_ref, th_ref)
    R.ppo_update = ppo_update
    return coord


def parse_gpus(s: str | None) -> list | None:
    """'0,1,2,3' -> [0, 1, 2, 3]; None / '' -> None."""
    return [int(x) for x in s.split(",") if x.strip() != ""] if s else None


# ------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------
def _cpu(x):
    if torch.is_tensor(x):
        return x.detach().cpu().clone()
    if isinstance(x, dict):
        return {k: _cpu(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return type(x)(_cpu(v) for v in x)
    return x


def install_dump(R, out_dir, calls=(0,), log=print) -> None:
    """Before the real ppo_update calls numbered ``calls`` (0 = the first), write ``<out_dir>/dump_c<k>.pt``: everything the
    call reads (learner + anchor + ability head weights, both Adam states, the batch, cfg, beta, rng state, loss options), so
    ``learner_dp_replay`` can run the SAME update on 1 or W GPUs without the engine, the league or the actors. The call goes
    on unchanged. Install it before or after ``install``: the inputs are the same."""
    orig, n = R.ppo_update, [0]
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    def ppo_update(model, opt, B, Rr, cfg, beta, rng, vf=None, posture=None, ability=None, ent_ref=None, th_ref=None, **kw):
        k, n[0] = n[0], n[0] + 1
        if k in calls:
            if not isinstance(Rr, R.LazyRef) or posture is not None or th_ref is not None:
                raise SystemExit("learner dump: stored_values learners only")
            d = {"model": copy.deepcopy(model).cpu(), "ref": copy.deepcopy(Rr.ref).cpu(),
                 "ent_ref": None if ent_ref is None else copy.deepcopy(ent_ref).cpu(),
                 "head": None if ability is None else copy.deepcopy(ability["head"]).cpu(),
                 "opt": _cpu(opt.state_dict()), "opt_cls": type(opt).__name__,
                 "hopt": None if ability is None else _cpu(ability["opt"].state_dict()),
                 "ab_ent_coef": None if ability is None else ability["ent_coef"],
                 "B": {kk: (_cpu(v) if torch.is_tensor(v) else v) for kk, v in B.items() if not kk.startswith("_")},
                 "cfg": cfg, "beta": beta, "rng": rng.bit_generator.state, "vf": vf,
                 "R": {"tau": Rr.tau, "T": Rr.T, "T_gate": Rr.T_gate, "kl_heads": Rr.get("kl_heads")}, "call": k}
            path = Path(out_dir) / f"dump_c{k}.pt"
            torch.save(d, str(path) + ".tmp")
            os.replace(str(path) + ".tmp", path)
            log(f"[dp] dumped ppo_update call {k} to {path} ({path.stat().st_size / 2**20:.0f} MB, {len(B['A'])} rows)")
        return orig(model, opt, B, Rr, cfg, beta, rng, vf=vf, posture=posture, ability=ability, ent_ref=ent_ref, th_ref=th_ref, **kw)
    R.ppo_update = ppo_update


def main(argv=None) -> int:
    """
    """
    import argparse
    argv = sys.argv[1:] if argv is None else list(argv)
    cut = argv.index("--") if "--" in argv else len(argv)
    ap = argparse.ArgumentParser()
    ap.add_argument("--devices", default=None)
    ap.add_argument("--backend", default=None, choices=("nccl", "gloo"))
    ap.add_argument("--dump", default=None)
    ap.add_argument("--dump-calls", default="0")
    a = ap.parse_args(argv[:cut])
    from pipeline import rl_royale as R
    coord = None
    devs = [x.strip() for x in a.devices.split(",") if x.strip()] if a.devices else []
    if len(devs) > 1:
        if devs[0].startswith("cuda"):
            torch.cuda.set_device(torch.device(devs[0]))
        coord = install(R, devs, a.backend)
    if a.dump:
        install_dump(R, a.dump, tuple(int(x) for x in a.dump_calls.split(",")))
    try:
        return R.main(argv[cut + 1:])
    finally:
        if coord is not None:
            coord.close()


if __name__ == "__main__":
    raise SystemExit(main())
