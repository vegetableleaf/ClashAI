"""Plan A S3 (scratchpad/gauntlet/L74/memory/PLAN_A.md): imitation warm-start of ONLY the match-memory adapter.

    python -m pipeline.train_memory --init CKPT --memory v1 --memory-tables gen_dataset_v32_fv5_memory_v1.npz \
        --data icebow/data/pipeline/gen_dataset_v32_fv5.npz --trainable memory --out-dir DIR [--epochs 2] [--amp bf16]

Lead 10-25: the init (an RL policy, e.g. CLXIII) keeps EVERY weight FROZEN; only the new memory parameters (model_gen
MemoryEncoder: event encoder, summary MLP, the zero-init output projection) learn, on the pro rows, how pros' decisions
depend on match history -- a residual on top of the init (S5 RL later fine-tunes everything). So:
  * model = model_gen.load_model(init, memory="v1") (a fresh zero-output encoder: step 0 = the init, asserted on the first
    val batch); requires_grad only for ``mem.*``; the optimizer holds only those (AdamW, linear warm-up + cosine);
  * the model stays in eval() mode the whole run: the frozen trunk runs exactly as in RL / live inference (no dropout);
    gradients still flow THROUGH the trunk to the adapter;
  * loss = train_gen.losses on gate / card / cell (train_gen's weights and masks; wait / value are reported, not trained:
    they are not policy heads), mirror p 0.5 (memory mirrored too: match_memory.mirror_ev);
  * memory inputs per batch: match_memory.rows_features over the per-match tables (dataset_gen memory_tables) at each row's
    tick -- identical to the pro replay's MatchMemory.features (tested), built on CPU in a prefetch thread;
  * after training every frozen tensor (parameters AND buffers) is asserted bit-identical to the init.
Val = the dataset's split 1 (by replay tag), a fixed seed-0 sample of --val-sample rows; every --val-every steps and at the
end: eval_gen.evaluate (the pro-agreement definitions) + the gate / card / cell val loss, each WITH memory, with the memory
inputs ZEROED (an empty memory, same weights) and for the init; best-by-val = lowest val loss with memory. Checkpoints: the
init's own checkpoint dict with the trained weights, ``memory: "v1"`` and an ``s3`` block (mem_best.pt, mem_latest.pt, and
mem_s{step}.pt every --ckpt-every steps). End: two association probes on the val rows of icebow-deck sides (``probes``).
``--head-rows N`` reads only the first N rows of --data (a streamed prefix: laptop tests; the full set needs a pod).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import queue
import threading
import time
import zipfile
from pathlib import Path

import numpy as np
import torch

from . import match_memory as MM
from .dataset_gen import checkpoint_gid, load_memory_tables
from .eval_gen import evaluate, val_rows
from .model_gen import load_model
from .train_gen import GenRows, losses

REPO = Path(__file__).resolve().parents[1]
HEADS = ("gate", "card", "cell")
PER_TOKEN = ("tok", "unit_form")
ICEBOW = ("x-bow", "tesla", "ice-wizard", "tornado", "rocket", "knight", "the-log", "skeletons")
REPEAT_T = 400                            # probe (b): "again within 20 s" of the card's last play (ticks)


def npz_head(path: Path, n: int) -> tuple[dict, dict]:
    """The first n rows of a dataset_gen npz (per-token members: their first off[n] tokens), decompressing only each
    member's prefix -- the full fv5 set does not fit a laptop (projectiles alone are 7.2 GB)."""
    z = zipfile.ZipFile(path)

    def read(name, rows):
        with z.open(name + ".npy") as f:
            ver = np.lib.format.read_magic(f)
            shape, fortran, dt = (np.lib.format.read_array_header_1_0(f) if ver == (1, 0)
                                  else np.lib.format.read_array_header_2_0(f))
            rows = shape[0] if rows is None else min(rows, shape[0])
            per = int(np.prod(shape[1:], dtype=np.int64))
            return np.frombuffer(f.read(rows * per * dt.itemsize), dt).reshape((rows,) + tuple(shape[1:])).copy()
    off = read("off", n + 1)
    arrs = {"off": off}
    for k in (i.filename[:-4] for i in z.infolist()):
        if k not in ("off", "meta", "tags"):
            arrs[k] = read(k, int(off[-1]) if k in PER_TOKEN else n)
    with z.open("meta.npy") as f:
        meta = json.loads(str(np.load(f)))
    return arrs, meta


def freeze(model) -> dict:
    """Only ``mem.*`` trains; -> a copy of every other tensor (parameters + buffers) for the bit-identity check."""
    for k, p in model.named_parameters():
        p.requires_grad_(k.startswith("mem."))
    return {k: v.detach().clone() for k, v in model.state_dict().items() if not k.startswith("mem.")}


def frozen_unchanged(model, snap: dict) -> list:
    """The frozen tensors that differ from the snapshot (bitwise) -- must be []."""
    sd = model.state_dict()
    return [k for k, v in snap.items() if not torch.equal(sd[k], v)]


def batches(rows, perm, bs, prefetch):
    """rows.batch over ``perm`` in order, built ``prefetch`` batches ahead in a thread (CPU table features overlap the GPU)."""
    chunks = [perm[s:s + bs] for s in range(0, len(perm) - bs + 1, bs)]
    if prefetch <= 0:
        for c in chunks:
            yield rows.batch(c)
        return
    q: queue.Queue = queue.Queue(maxsize=prefetch)

    def work():
        try:
            for c in chunks:
                q.put(rows.batch(c))
        except BaseException as exc:                              # surfaced in the consumer
            q.put(exc)
        q.put(None)
    threading.Thread(target=work, daemon=True).start()
    while (b := q.get()) is not None:
        if isinstance(b, BaseException):
            raise b
        yield b


@torch.no_grad()
def val_loss(model, rows, bs=512, rocket_context_weight=1.0) -> dict:
    tot, parts, n = 0.0, {}, 0
    for s in range(0, len(rows.idx), bs):
        b = rows.batch(rows.idx[s:s + bs])
        loss, p = losses(model, b, mirror=False, grid=rows.grid, rocket_context_weight=rocket_context_weight, heads=HEADS)
        k = len(b["gate"])
        tot, n = tot + float(loss) * k, n + k
        for key, v in p.items():
            parts[key] = parts.get(key, 0.0) + v * k
    return {"loss": tot / max(n, 1), **{f"loss_{k}": v / max(n, 1) for k, v in parts.items()}}


def scores(model, base, rows, tables, rocket_context_weight=1.0) -> dict:
    """eval_gen.evaluate + val loss for: the memory model WITH memory, with the memory inputs ZEROED, and the init."""
    out = {}
    for name, net, mem in (("memory", model, tables), ("zeroed", model, "empty"), ("init", base, None)):
        rows.memory = mem
        out[name] = {**evaluate(net, rows, grid=rows.grid), **val_loss(net, rows, rocket_context_weight=rocket_context_weight)}
    rows.memory = tables
    return out


@torch.no_grad()
def probes(model, base, rows, tables, arrs, gid, bs=512) -> dict:
    """Two association probes on ``rows`` (val rows; restricted here to icebow-deck sides), for the init, the memory model
    with its memory and with the memory zeroed:
      (a) X-Bow propensity: on PLAY rows whose side has >= 2 FAILED own reach X-Bows earlier in the match (the memory
          summary at the row), mean P(card = X-Bow) (the model's hand-position softmax mass on the X-Bow; 0 if not in
          hand) vs the pros' rate of playing it; the same for rows with 0 failures (contrast);
      (b) repeat after a bad outcome: per own card c, on rows where c is in hand and c's LAST own play (visible at the row)
          is resolved, tower-swing known and played <= 20 s ago: the per-row play propensity of c -- model P(gate) x
          P(card = c), pro 1[played c] -- split by that play's swing < 0 (bad) vs >= 0.
    Per-decision-row rates (wait rows every 40 ticks + play rows), not per-episode probabilities; association only."""
    ice = sorted(gid[k] for k in ICEBOW)
    idx = np.asarray(rows.idx)
    sel = idx[np.all(np.sort(arrs["deck_card"][idx].astype(np.int64), 1) == np.asarray(ice), 1)] if len(idx) else idx
    res = {"rows_icebow": int(len(sel))}
    if not len(sel):
        return res
    xb = gid["x-bow"]
    packed, row_tab, row_t = tables
    E = MM.gather_rows(packed, np.asarray(row_tab)[sel])
    t = np.asarray(row_t)[sel].astype(np.int64)[:, None]
    vals, tick, res1 = E["vals"], E["tick"].astype(np.int64), E["res"][..., 1].astype(np.int64)
    own = (vals[..., MM._COL["is_play"]] == 1) & (vals[..., MM._COL["mine"]] == 1) & (t >= E["vis"])
    fails = np.round(MM.rows_features(packed, row_tab, row_t, arrs["deck_card"], sel)["mem_summary"][:, 3] * 10)
    hand = arrs["hand_card"][sel].astype(np.int64)
    play = arrs["y_gate"][sel] == 1
    ycard = arrs["y_card"][sel].astype(np.int64)
    outs = {}
    for name, net, mem in (("init", base, None), ("memory", model, tables), ("zeroed", model, "empty")):
        rows.memory = mem
        g, pc = [], []
        for s in range(0, len(sel), bs):
            b = rows.batch(sel[s:s + bs])
            o = net(b)
            g.append(torch.sigmoid(o["gate"]).double().cpu().numpy())
            pc.append(torch.softmax(o["card"].double(), -1).cpu().numpy())
        outs[name] = (np.concatenate(g), np.concatenate(pc))
    rows.memory = tables
    p_xb = {k: (pc * (hand == xb)).sum(1) for k, (_, pc) in outs.items()}
    for grp, m in (("fails_ge2", play & (fails >= 2)), ("fails_0", play & (fails == 0))):
        res[f"xbow_{grp}"] = {"n": int(m.sum()), "pro": float((ycard[m] == xb).mean()) if m.any() else None,
                              **{k: float(v[m].mean()) if m.any() else None for k, v in p_xb.items()}}
    rep = {}
    for c in ice:
        mine = own & (E["card"].astype(np.int64) == c)
        last = np.where(mine, np.arange(mine.shape[1])[None], -1).max(1)
        ok = last >= 0
        li = np.maximum(last, 0)[:, None]
        lt = np.take_along_axis(tick, li, 1)[:, 0]
        known = np.take_along_axis(vals[..., MM._COL["out_tower_known"]], li, 1)[:, 0] == 1
        swing = np.take_along_axis(E["swing"], li, 1)[:, 0]
        inhand = (hand == c).any(1)
        base_m = ok & inhand & known & (t[:, 0] >= np.take_along_axis(res1, li, 1)[:, 0]) & (t[:, 0] - lt <= REPEAT_T)
        name = next(k for k, v in gid.items() if v == c)
        rep[name] = {}
        for grp, m in (("bad", base_m & (swing < 0)), ("not_bad", base_m & (swing >= 0))):
            pro = play & (ycard == c)
            rep[name][grp] = {"n": int(m.sum()), "pro": float(pro[m].mean()) if m.any() else None,
                              **{k: float((g * (pc * (hand == c)).sum(1))[m].mean()) if m.any() else None
                                 for k, (g, pc) in outs.items()}}
    res["repeat_after_bad"] = rep
    return res


def save(path: Path, init_ck: dict, model, info: dict) -> None:
    ck = dict(init_ck, model={k: v.detach().cpu() for k, v in model.state_dict().items()}, memory=MM.VERSION, s3=info)
    tmp = path.with_name(path.name + ".tmp")
    torch.save(ck, tmp)
    tmp.replace(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--init", type=Path, required=True, help="a feature_version >= 4 generalist checkpoint (e.g. CLXIII)")
    ap.add_argument("--memory", choices=("v1",), required=True)
    ap.add_argument("--memory-tables", type=Path, required=True, help="dataset_gen memory_tables' file for --data")
    ap.add_argument("--data", type=Path, default=REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz")
    ap.add_argument("--trainable", choices=("memory",), required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--steps", type=int, default=0, help="> 0 overrides --epochs")
    ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--wd", type=float, default=0.01)
    ap.add_argument("--warmup", type=int, default=500)
    ap.add_argument("--amp", choices=("none", "bf16"), default="none")
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--val-sample", type=int, default=30000)
    ap.add_argument("--val-every", type=int, default=2000)
    ap.add_argument("--ckpt-every", type=int, default=2000)
    ap.add_argument("--prefetch", type=int, default=4)
    ap.add_argument("--head-rows", type=int, default=0, help="read only the first N rows of --data (laptop tests)")
    ap.add_argument("--limit-rows", type=int, default=0, help="a seeded random N of the train rows")
    ap.add_argument("--probe-rows", type=int, default=0, help="cap the val rows the probes read (0 = every val row)")
    ap.add_argument("--rocket-context-weight", type=float, default=None)
    ap.add_argument("--rocket-context-artifact", type=Path, default=None)
    ap.add_argument("--device", default=None)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    t0 = time.time()
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    dev = torch.device(a.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    if a.head_rows:
        arrs, meta = npz_head(a.data, a.head_rows)
    else:
        from .dataset import load as load_ds
        arrs, meta = load_ds(a.data)
    if int(meta.get("feature_version", 1)) < 4:
        raise SystemExit("memory v1 needs a feature_version >= 4 dataset")
    packed, row_tab, mmeta = load_memory_tables(a.memory_tables)
    if mmeta["card_vocab"] != meta["card_vocab"]:
        raise SystemExit("--memory-tables were built for another dataset (card_vocab differs)")
    n = len(arrs["y_gate"])
    if len(row_tab) < n or (not a.head_rows and len(row_tab) != n):
        raise SystemExit(f"--memory-tables hold {len(row_tab)} rows, --data {n}: not this dataset")
    row_tab = row_tab[:n]
    rcw = a.rocket_context_weight or 1.0
    if a.rocket_context_artifact is not None:
        from .rocket_context import load_weight_artifact
        arrs["rocket_context_probability"], meta["rocket_context"] = load_weight_artifact(a.rocket_context_artifact, a.data)
    elif rcw != 1.0:
        raise SystemExit("--rocket-context-weight > 1 needs --rocket-context-artifact")
    init_ck = torch.load(a.init, map_location="cpu", weights_only=False)
    if list(init_ck["card_vocab"]) != list(meta["card_vocab"]):
        raise SystemExit("the init's card_vocab differs from the dataset's: card ids would not line up")
    grid = str(init_ck["args"].get("grid", "lattice"))
    model = load_model(a.init, dev, memory=a.memory)[0].eval()
    base = load_model(a.init, dev)[0].eval()
    if getattr(base, "mem", None) is not None:
        raise SystemExit("--init already has memory weights: S3 starts from a model without them")
    snap = freeze(model)
    for p in base.parameters():
        p.requires_grad_(False)
    gid = checkpoint_gid(meta["card_vocab"])
    tables = (packed, row_tab, arrs["tick"])
    tr = np.flatnonzero(arrs["split"] == 0)
    if a.limit_rows and a.limit_rows < len(tr):
        tr = np.sort(rng.choice(tr, size=a.limit_rows, replace=False))
    va_idx = val_rows(arrs, a.val_sample)
    rows = GenRows(arrs, tr, dev)
    rows.memory, rows.grid = tables, grid
    va = rows.view(va_idx)
    params = [p for k, p in model.named_parameters() if k.startswith("mem.")]
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=a.wd)
    if len(tr) < a.bs:
        raise SystemExit(f"{len(tr)} train rows < one batch of {a.bs}")
    per_epoch = len(tr) // a.bs
    steps = a.steps if a.steps > 0 else max(int(round(a.epochs * per_epoch)), 1)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(a.warmup, 1)) * 0.5 * (
        1 + math.cos(math.pi * min(s, steps) / steps)))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    info = {"init": str(a.init), "init_sha256": hashlib.sha256(a.init.read_bytes()).hexdigest(),
            "memory_tables": str(a.memory_tables), "data": str(a.data), "head_rows": a.head_rows, "train_rows": int(len(tr)),
            "val_rows": int(len(va_idx)), "steps": steps, "bs": a.bs, "lr": a.lr, "wd": a.wd, "warmup": a.warmup,
            "heads": list(HEADS), "mirror": not a.no_mirror, "amp": a.amp, "rocket_context_weight": rcw,
            "trainable": "memory", "n_trainable": int(sum(p.numel() for p in params)), "seed": a.seed}
    log = (a.out_dir / "s3_log.jsonl").open("a", encoding="utf-8")

    def emit(rec):
        print(json.dumps(rec), flush=True)
        log.write(json.dumps(rec) + "\n")
        log.flush()
    if len(va_idx):                                       # step 0: the memory model IS the init (zero-output encoder)
        b = va.batch(va_idx[:min(256, len(va_idx))])
        with torch.no_grad():
            o1, o0 = model(b, card=b["card"], form=b["form"]), base(b, card=b["card"], form=b["form"])
        diff = max(float((o1[k] - o0[k]).abs().max()) for k in ("gate", "card", "value", "cell"))
        if diff > 1e-6:
            raise SystemExit(f"step-0 identity failed: max |diff| {diff}")
        emit({"step": 0, "identity_max_diff": diff})
    amp = a.amp == "bf16" and dev.type == "cuda"
    best, step, ep, hist = math.inf, 0, 0, []
    tl, sl = time.time(), 0
    while step < steps:
        perm = rng.permutation(tr)
        for b in batches(rows, perm, a.bs, a.prefetch):
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                loss, parts = losses(model, b, mirror=(not a.no_mirror) and rng.random() < 0.5, grid=grid,
                                     rocket_context_weight=rcw, heads=HEADS)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            gn = float(torch.nn.utils.clip_grad_norm_(params, 1.0))
            opt.step()
            sched.step()
            step += 1
            if step % 50 == 0 or step == steps:
                emit({"step": step, "epoch": ep, "loss": float(loss.detach()), **{f"p_{k}": round(v, 5) for k, v in parts.items()},
                      "grad_norm": round(gn, 4), "lr": sched.get_last_lr()[0],
                      "s_per_step": round((time.time() - tl) / (step - sl), 4)})
                tl, sl = time.time(), step
            if len(va_idx) and (step % a.val_every == 0 or step == steps):
                sc = scores(model, base, va, tables, rcw)
                hist.append({"step": step, **sc})
                emit({"step": step, "val": {k: {m: round(v[m], 5) for m in ("loss", "card_top1", "cell_tile_top1",
                                                                             "cell_half_top1", "gate_bal_acc") if m in v}
                                            for k, v in sc.items()}})
                if sc["memory"]["loss"] < best:
                    best = sc["memory"]["loss"]
                    save(a.out_dir / "mem_best.pt", init_ck, model, {**info, "step": step, "val": sc})
            if step % a.ckpt_every == 0:
                save(a.out_dir / f"mem_s{step}.pt", init_ck, model, {**info, "step": step})
                tl = time.time()                          # (validation / saving time is not step time)
                sl = step
            if step >= steps:
                break
        ep += 1
    save(a.out_dir / "mem_latest.pt", init_ck, model, {**info, "step": step})
    bad = frozen_unchanged(model, snap)
    if bad:
        raise SystemExit(f"FROZEN WEIGHTS CHANGED: {bad[:5]} (+{max(0, len(bad) - 5)})")
    pidx = val_rows(arrs, 0)                              # the probes read EVERY val row (the >= 2 failures group is rare)
    pv = va.view(pidx if not a.probe_rows else pidx[:a.probe_rows])
    pr = probes(model, base, pv, tables, arrs, gid) if len(pidx) else {}
    final = {"FINAL": True, "steps": step, "frozen_tensors_unchanged": len(snap), "best_val_loss": best, "probes": pr,
             "hist": hist, "seconds": round(time.time() - t0, 1), **info}
    (a.out_dir / "s3_final.json").write_text(json.dumps(final, indent=1), encoding="utf-8")
    emit({k: v for k, v in final.items() if k != "hist"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
