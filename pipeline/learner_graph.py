"""LEARNER-SPEED ticket B, first cut (``trunk_graph: n``, learner-only, opt-in, CUDA): the generalist trunk forward +
backward of an n-row minibatch replayed as CUDA graphs.

A pilot PPO step at 256 rows is half GPU-idle: ~3,900 small kernels, launch-bound (SCALE.md 7e). The trunk
(GenPolicy.heads_t = encode_gen + heads_gen + the card scatter) has a FIXED shape at a fixed row count, so
torch.cuda.make_graphed_callables captures its forward and backward once and replays them. Everything with a
data-dependent shape stays eager and unchanged: the played-row cell head, the losses, the monitors (and their syncs),
the lazy anchor, the entropy pair, clip and Adam; minibatches of another size (an epoch's tail) run eager.

Same kernels at the same shapes -> the same values; the one possible difference is the ORDER in which a gradient that
reaches a tensor from inside AND outside the graph is summed (e.g. g: gate / card heads inside, cell / value heads
outside), i.e. the last bits (tests: pipeline/tests/test_learner_graph.py; real records: lrn/lspeed/graph_gate.py).

Graphs are cached per model (weakly) and per (rows, input layout, requires_grad pattern): the critic warm-up (trunk
frozen) runs eager. Nothing on the actor or live path imports this file.
"""
from __future__ import annotations

import contextlib
import weakref

import torch
import torch.nn as nn

_CACHE: "weakref.WeakKeyDictionary[nn.Module, dict]" = weakref.WeakKeyDictionary()


@contextlib.contextmanager
def _capture_safe(sc):
    """tower_refine.tower_features builds its two constant rows with sc.new_tensor([...]) -- a host-to-device copy, which
    graph capture refuses. During the capture only, the same function with the constants made on the device beforehand
    (checked bitwise against the original on ``sc`` first; replays run no Python). Yields the constants: the caller keeps
    them alive as long as the graph (freed, their memory is reused and the graph reads garbage)."""
    from pipeline import tower_refine as TR
    orig = TR.tower_features
    side = sc.new_tensor([0., 0, 0, 1, 1, 1])
    kind = sc.new_tensor([0., 1, 1, 0, 1, 1])

    def tower_features(sc):
        alive = sc[:, 64:70] > .5
        raw = sc[:, 52:58]
        known = (sc[:, 58:64] > .5) & alive & torch.isfinite(raw)
        hp = torch.where(known, raw, torch.zeros_like(raw))
        b = len(sc)
        return torch.stack([side.expand(b, -1), kind.expand(b, -1), hp, known.to(sc.dtype), alive.to(sc.dtype)], -1), alive
    a, b = orig(sc), tower_features(sc)
    if not (torch.equal(a[0], b[0]) and torch.equal(a[1], b[1])):
        raise RuntimeError("learner_graph: tower_refine.tower_features changed; update _capture_safe")
    TR.tower_features = tower_features
    try:
        yield side, kind
    finally:
        TR.tower_features = orig


class _Trunk(nn.Module):
    """heads_t as a module of flat tensors (make_graphed_callables needs a Module to see the parameters)."""

    def __init__(self, pol, keys):
        super().__init__()
        self.m, self.keys, self.out_keys = pol.model, keys, None
        self._pol = [pol]                                     # not a submodule

    def forward(self, *xs):
        enc, heads = self._pol[0].heads_t(dict(zip(self.keys, xs)))
        flat = [("e", k, v) for k, v in enc.items()] + [("h", k, v) for k, v in heads.items()]
        self.out_keys = [(s, k) for s, k, _ in flat]
        return tuple(v for _, _, v in flat)


def _fresh_grads(grad_inputs, grad_outputs):
    """Post-hook on the graphed backward node: its parameter gradients are views of the graph's STATIC buffers, and
    AccumulateGrad would adopt them as p.grad when p.grad is None; the next replay (micro_batch's next micro-batch) then
    overwrites p.grad in place and the accumulation double-counts (caught by test_learner_graph's composition test:
    gradient off by 3.2x relative). One fused foreach x 1.0 (exact) hands autograd fresh tensors instead."""
    i = [j for j, gr in enumerate(grad_inputs) if gr is not None]
    out = list(grad_inputs)
    for j, t in zip(i, torch._foreach_mul([grad_inputs[j] for j in i], 1.0)):
        out[j] = t
    return tuple(out)


def heads_t(pol, b: dict):
    """GenPolicy.heads_t(b), through a CUDA graph of the model's ``trunk_graph`` row count when it applies (grad on, CUDA,
    that row count, the trunk trainable); else pol.heads_t(b) itself."""
    model = pol.model
    n = getattr(model, "trunk_graph", None)
    keys = sorted(b)
    xs = [b[k] for k in keys]
    if (not n or not torch.is_grad_enabled() or xs[0].device.type != "cuda" or len(xs[0]) != n
            or not next(model.encoder.parameters()).requires_grad):   # the trunk frozen (critic warm-up): eager
        return pol.heads_t(b)
    key = (tuple((k, tuple(x.shape), x.dtype) for k, x in zip(keys, xs)), tuple(p.requires_grad for p in model.parameters()))
    cache = _CACHE.setdefault(model, {})
    if key not in cache:
        tr = _Trunk(pol, keys)
        with _capture_safe(b["sc"]) as consts:
            g = torch.cuda.make_graphed_callables(tr, tuple(x.clone() for x in xs), allow_unused_input=True)
        cache[key] = (g, tr, consts)                         # consts: the graph reads them; they must outlive it
    g, tr, _ = cache[key]
    out = g(*xs)
    node = next((o.grad_fn for o in out if o.grad_fn is not None), None)
    if node is not None:
        node.register_hook(_fresh_grads)
    enc, heads = {}, {}
    for (s, k), v in zip(tr.out_keys, out):
        (enc if s == "e" else heads)[k] = v
    return enc, heads
