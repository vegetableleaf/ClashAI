"""LEARNER-SCALE3: WHO makes the backward's memory-movement kernels (6b: fill_ / clone / copy_ / index_put_ ~42% of a
1,024-row step). One pilot minibatch_loss (pilot.yaml + mem_row_cache, ability head, lazy anchor) built under autograd
anomaly mode, so every backward node carries its forward traceback; the graph is walked from the loss and its nodes
are grouped by (node type, innermost pipeline/ source line), with the element count of the zero-filled gradient
buffer the node's backward allocates where the node saves its input size (Select / Index / Slice / ... Backward).
Device-independent (the graph is the same on CPU). Writes OUT (json) + a text table next to it.

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/glue_probe.py --config CFG --keep DIR \
        --T-gate 0.1 --mb 1024 --device cpu --out /workspace/lrn/prof/glue.json
"""
import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import loop_records as LR  # noqa: E402
from pipeline import loop_learner as LL  # noqa: E402
from rec_identity import collate_kw  # noqa: E402

FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\S+)\n\s*(.*)')


def site(tb):
    """innermost frame under pipeline/ (else the innermost frame) of an anomaly-mode traceback string."""
    fr = FRAME.findall("".join(tb) if isinstance(tb, list) else (tb or ""))
    mine = [f for f in fr if "/pipeline/" in f[0].replace("\\", "/") and "/tests/" not in f[0]]
    f = (mine or fr or [("?", "0", "?", "")])[-1]
    return f"{Path(f[0]).name}:{f[1]} {f[2]} | {f[3].strip()[:90]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--T-gate", type=float, required=True)
    ap.add_argument("--mb", type=int, default=1024)
    ap.add_argument("--max-matches", type=int, default=128)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    cfg = {**R.load_config(REPO / a.config, [], smoke=False), "T_gate": a.T_gate, "learner_device": a.device}
    run = f"lrn_glue_{int(time.time())}"
    for d in (R.RUN_ROOT / run, R.CKPT_ROOT / run):
        d.mkdir(parents=True, exist_ok=True)
    L = R.Learner(cfg, run, R.RUN_ROOT / run, R.CKPT_ROOT / run, R.Log(R.RUN_ROOT / run), False)
    LL.adopt_init_ability_head(L)
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))[:a.max_matches]]
    Bn, _ = R.collate(res, float(cfg["adv_clip"]), **collate_kw(cfg))
    del res
    B = R.to_device(Bn, L.dev)
    B["_mem_cache"] = R.MemRowCache(len(B["A"]))
    R.gae_batch(L.model, B, cfg)
    Rz = R.LazyRef(L.ref, B, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
    ac = R.adv_cfg(cfg)
    vf = {"coef": ac["vf_coef"], "clip": ac["vf_clip"], "policy": True, "trunk_grad": ac["vf_trunk_grad"]}
    abl = {"head": L.ability_head, "opt": L.ability_opt, "ent_coef": float(cfg["ability_ent_coef"])}
    N = len(B["A"])
    idx = torch.from_numpy(np.random.default_rng(0).choice(N, a.mb, replace=False)).to(L.dev)
    Rz.fill(idx)
    with torch.autograd.set_detect_anomaly(True, check_nan=False):
        loss, st = R.minibatch_loss(L.model, B, Rz, idx, tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=0.0,
                                    n_total=N, vf=vf, T_gate=cfg.get("T_gate"), ability=abl)
    groups = defaultdict(lambda: {"n": 0, "zero_elems": 0})
    seen, todo = set(), [loss.grad_fn]
    while todo:
        fn = todo.pop()
        if fn is None or fn in seen:
            continue
        seen.add(fn)
        todo.extend(f for f, _ in fn.next_functions)
        name = fn.name()
        if name == "torch::autograd::AccumulateGrad":
            continue
        g = groups[(name, site(fn.metadata.get("traceback_")))]
        g["n"] += 1
        sz = getattr(fn, "_saved_self_sym_sizes", None)
        if sz is not None:
            g["zero_elems"] += int(np.prod([int(s) for s in sz]))
    rows = sorted(({"node": k[0], "site": k[1], **v} for k, v in groups.items()), key=lambda r: (-r["zero_elems"], -r["n"]))
    a.out.write_text(json.dumps({"mb": a.mb, "rows": N, "nodes": len(seen), "groups": rows}, indent=1))
    txt = [f"{r['zero_elems'] / 1e6:9.2f}M {r['n']:5d}  {r['node']:32s} {r['site']}" for r in rows[:80]]
    a.out.with_suffix(".txt").write_text("\n".join(txt))
    print(f"nodes {len(seen)}; top:\n" + "\n".join(txt[:40]), flush=True)


if __name__ == "__main__":
    main()
