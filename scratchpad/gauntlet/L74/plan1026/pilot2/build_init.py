"""PILOT2 init: B0-full v2 (MEM_FULL.md s5) + ZERO target layers (GenModel.add_target_in), then the u0 identity vs CLXIII
NOLEAK = MEM_FULL's G-mem-0 recipe (recorded val rows, memory at e_max 256 + snapshot, CPU) run three ways per batch:
random target rows, all-none target rows, and no target keys. Every gate / card / cell / value output and card / cell
log-prob must equal CLXIII's (max |diff| < 1e-6), the three tgt tensors must be exactly 0, and rl.ability_head (the IW
press head ability_head_from_init keeps) must be CLXIII's tensor for tensor.

    python build_init.py --b0full B0FULL.pt --clxiii CLXIII.pt --tables snap_full.npz --out OUT.pt [--data DATA.npz] [--rows 10000]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))
B0FULL_SHA = "fc1caf14cca0c89a7b2ed22d615e5ed5c0f06b5162b30cc828c77aae197d5eb0"
TGT = ("tgt_in.", "tgt_out.", "tgt_back.")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    for k in ("b0full", "clxiii", "tables", "out"):
        ap.add_argument("--" + k, type=Path, required=True)
    ap.add_argument("--data", type=Path, default=REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz")
    ap.add_argument("--rows", type=int, default=10000)
    a = ap.parse_args()
    from pipeline.model_gen import load_model
    assert sha(a.b0full) == B0FULL_SHA, "not B0-full v2"
    ck = torch.load(a.b0full, map_location="cpu", weights_only=False)
    cl = torch.load(a.clxiii, map_location="cpu", weights_only=False)
    assert not any(k.startswith(TGT) for k in ck["model"]), "B0-full already has target layers"
    m = load_model(a.b0full, torch.device("cpu"))[0]
    m.add_target_in()
    tgt = {k: v.detach().clone() for k, v in m.state_dict().items() if k.startswith(TGT)}
    assert len(tgt) == 3 and all(not v.any() for v in tgt.values()), tgt.keys()
    out = {**ck, "model": {**ck["model"], **tgt},
           "pilot2": {"base": str(a.b0full), "base_sha256": B0FULL_SHA, "added": sorted(tgt),
                      "builder": "scratchpad/gauntlet/L74/plan1026/pilot2/build_init.py"}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".tmp")
    torch.save(out, tmp)
    tmp.replace(a.out)
    chk = torch.load(a.out, map_location="cpu", weights_only=False)
    assert all(torch.equal(chk["model"][k], v) for k, v in ck["model"].items()) and len(chk["model"]) == len(ck["model"]) + 3
    sc = cl["model"]
    assert all(torch.equal(chk["model"][k], sc[k]) for k in sc), "a CLXIII tensor changed"
    ah, ah0 = chk["rl"]["ability_head"], cl["rl"]["ability_head"]
    ab_same = ah.keys() == ah0.keys() and all(torch.equal(ah[k], ah0[k]) for k in ah0)
    assert ab_same, "rl.ability_head differs from CLXIII's"
    print(f"init {a.out} sha256 {sha(a.out)}: {len(sc)} CLXIII tensors + {len(chk['model']) - len(sc) - 3} memory + 3 zero "
          f"target tensors; rl.ability_head == CLXIII ({len(ah0)} tensors)", flush=True)

    # ---- u0 identity (G-mem-0 + target rows) ----
    from pipeline.dataset import load as load_ds
    from pipeline.dataset_gen import checkpoint_gid, load_memory_tables
    from pipeline.target_obs import TGT_N
    from pipeline.train_gen import GenRows as Rows
    from pipeline.train_memory import table_val_rows
    dev = torch.device("cpu")
    arrs, meta = load_ds(a.data)
    packed, row_tab, _ = load_memory_tables(a.tables)
    row_tab = row_tab[:len(arrs["y_gate"])]
    new = load_model(a.out, dev)[0].eval()
    base = load_model(a.clxiii, dev)[0].eval()
    assert new.tgt_in is not None and getattr(base, "tgt_in", None) is None
    va = table_val_rows(arrs, row_tab, a.rows)
    rows = Rows(arrs, va, dev)
    rows.memory, rows.memory_version, rows.memory_gid = (packed, row_tab, arrs["tick"]), "v2", checkpoint_gid(meta["card_vocab"])
    rows.memory_e_max, rows.memory_n_f = int(new.mem.e_max), new.mem.ev_in.in_features
    rows.grid = "lattice"
    g = torch.Generator().manual_seed(1031)
    worst, n_long, n_edges = {}, 0, 0
    with torch.no_grad():
        for s in range(0, len(va), 256):
            b = rows.batch(va[s:s + 256])
            n_long += int((b["mem_mask"].bool().sum(-1) > 128).sum())
            B, U = b["tok"].shape[:2]
            idx = torch.randint(-1, U, (B, U), generator=g)
            n_edges += int((idx >= 0).sum())
            o0 = base(b, card=b["card"], form=b["form"])
            for tag, extra in (("rand", {"tgt": torch.randn(B, U, TGT_N, generator=g), "tgt_idx": idx}),
                               ("none", {"tgt": torch.zeros(B, U, TGT_N), "tgt_idx": torch.full((B, U), -1)}),
                               ("nokeys", {})):
                o1 = new({**b, **extra}, card=b["card"], form=b["form"])
                for k in ("gate", "card", "value", "cell"):
                    f = torch.isfinite(o0[k])
                    assert torch.equal(f, torch.isfinite(o1[k])), f"{tag} {k}: finite masks differ"
                    if f.any():
                        worst[f"{tag}_{k}"] = max(worst.get(f"{tag}_{k}", 0.0), float((o1[k][f] - o0[k][f]).abs().max()))
                    if k in ("card", "cell"):
                        l1, l0 = torch.log_softmax(o1[k], -1), torch.log_softmax(o0[k], -1)
                        m0 = torch.isfinite(l0)
                        key = f"{tag}_logp_{k}"
                        worst[key] = max(worst.get(key, 0.0), float((l1[m0] - l0[m0]).abs().max()))
    res = {"rows": int(len(va)), "rows_gt128": n_long, "random_target_edges": n_edges, "max_diff": worst,
           "pass": max(worst.values()) < 1e-6 and ab_same, "ability_head_equal": ab_same, "init_sha256": sha(a.out),
           "clxiii_sha256": sha(a.clxiii)}
    print("G-pilot2-0", json.dumps(res), flush=True)
    Path(str(a.out) + ".id.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    sys.exit(0 if res["pass"] else 1)


if __name__ == "__main__":
    main()
