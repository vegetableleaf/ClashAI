"""MEM-RETRAIN recipe step 3: B0-full = B0 (CLXIII NOLEAK 141 tensors unchanged + memory encoder, coupling 0) with its
mem.* / mem_aux.* tensors REPLACED by a retrained full-history encoder (train_memory --e-max 256 --snap --mem-warm B0), then
gate G-mem-0: B0-full (memory inputs at e_max 256 + snapshot) vs CLXIII NOLEAK on N recorded val rows, CPU, max |diff| of the
gate / card / cell / value outputs and of the card / cell log-probs must be < 1e-6 (coupling mem.out = 0 makes it exact).

    python build_b0_full.py --b0 B0.pt --enc mem_best.pt --clxiii CLXIII.pt --tables snap_full.npz --data DATA.npz --out OUT.pt
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))
MEM = ("mem.", "mem_aux.")
HEADS = ("cell_refine.", "tower_refine.", "projectile_target_")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    for k in ("b0", "enc", "clxiii", "tables", "out"):
        ap.add_argument("--" + k, type=Path, required=True)
    ap.add_argument("--data", type=Path, default=REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz")
    ap.add_argument("--rows", type=int, default=10000)
    a = ap.parse_args()
    b0 = torch.load(a.b0, map_location="cpu", weights_only=False)
    e = torch.load(a.enc, map_location="cpu", weights_only=False)
    cl = torch.load(a.clxiii, map_location="cpu", weights_only=False)
    sb, se, sc = b0["model"], e["model"], cl["model"]
    assert all(torch.equal(sb[k], sc[k]) for k in sc), "B0 non-memory tensors differ from CLXIII"
    # the encoder file was trained on the RAW net: its trunk must equal CLXIII's on every non-head tensor
    bad = [k for k in sc if not k.startswith(HEADS + MEM) and not torch.equal(sc[k], se[k])]
    assert not bad, f"encoder file trunk differs from CLXIII: {bad[:5]}"
    mem = {k: v for k, v in se.items() if k.startswith(MEM)}
    assert mem["mem.out.weight"].abs().max() == 0 and mem["mem.out.bias"].abs().max() == 0, "coupling mem.out is not zero"
    assert "mem.full" in mem and [int(x) for x in mem["mem.full"]] == [256, 1], "encoder is not the 256 + snap one"
    model = {k: v for k, v in sb.items() if not k.startswith(MEM)}
    model.update(mem)
    out = {**b0, "model": model}
    for k in ("memory", "memory_aux", "s3"):
        out[k] = e[k]
    assert e.get("memory_v2") in (None, b0["memory_v2"]), "memory_v2 meta differs between B0 and the encoder file"
    out["b0"] = {**b0["b0"], "mem_full": {"encoder": str(a.enc), "encoder_sha256": sha(a.enc), "e_max": 256, "snap": True,
                                          "tables": str(a.tables), "base_b0": str(a.b0), "base_b0_sha256": sha(a.b0),
                                          "builder": "scratchpad/gauntlet/L74/memory/full/build_b0_full.py"}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".tmp")
    torch.save(out, tmp)
    tmp.replace(a.out)
    chk = torch.load(a.out, map_location="cpu", weights_only=False)["model"]
    assert all(torch.equal(chk[k], sc[k]) for k in sc) and all(torch.equal(chk[k], mem[k]) for k in mem)
    print(f"B0-full {a.out} sha256 {sha(a.out)}: {len(sc)} CLXIII tensors + {len(mem)} memory tensors", flush=True)

    # ---- G-mem-0 ----
    from pipeline.dataset import load as load_ds
    from pipeline.dataset_gen import checkpoint_gid, load_memory_tables
    from pipeline.model_gen import load_model
    from pipeline.train_gen import GenRows as Rows
    from pipeline.train_memory import table_val_rows
    dev = torch.device("cpu")
    arrs, meta = load_ds(a.data)
    packed, row_tab, _ = load_memory_tables(a.tables)
    row_tab = row_tab[:len(arrs["y_gate"])]
    gid = checkpoint_gid(meta["card_vocab"])
    new = load_model(a.out, dev)[0].eval()
    base = load_model(a.clxiii, dev)[0].eval()
    va = table_val_rows(arrs, row_tab, a.rows)
    rows = Rows(arrs, va, dev)
    rows.memory, rows.memory_version, rows.memory_gid = (packed, row_tab, arrs["tick"]), "v2", gid
    rows.memory_e_max, rows.memory_n_f = int(new.mem.e_max), new.mem.ev_in.in_features
    rows.grid = "lattice"
    worst = {}
    n_long = 0
    with torch.no_grad():
        for s in range(0, len(va), 256):
            b = rows.batch(va[s:s + 256])
            n_long += int((b["mem_mask"].bool().sum(-1) > 128).sum())
            o1, o0 = new(b, card=b["card"], form=b["form"]), base(b, card=b["card"], form=b["form"])
            for k in ("gate", "card", "value", "cell"):
                f = torch.isfinite(o0[k])
                assert torch.equal(f, torch.isfinite(o1[k])), f"{k}: finite masks differ"
                if f.any():
                    worst[k] = max(worst.get(k, 0.0), float((o1[k][f] - o0[k][f]).abs().max()))
                if k in ("card", "cell"):
                    l1, l0 = torch.log_softmax(o1[k], -1), torch.log_softmax(o0[k], -1)
                    g = torch.isfinite(l0)
                    worst["logp_" + k] = max(worst.get("logp_" + k, 0.0), float((l1[g] - l0[g]).abs().max()))
    res = {"rows": int(len(va)), "rows_gt128": n_long, "max_diff": worst, "pass": max(worst.values()) < 1e-6,
           "b0_full_sha256": sha(a.out)}
    print("G-mem-0", json.dumps(res), flush=True)
    Path(str(a.out) + ".gmem0.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
