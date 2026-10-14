"""Fold an offline TowerRefine (L73/chip_rocket/train_tower_refine.py output, wrapper format) into a full checkpoint that
pipeline.model_gen loads (opt-in by the tower_refine.* keys). The same fold as L73/chip_rocket/convert_and_verify.py
'main' (lines 40-46), without its two-checkout verification.
    python fold_tower_refine.py BASE_WITH_CELLREF.pt TR.pt OUT.pt
    python fold_tower_refine.py --check       (fold tr_w2.pt onto the old base == the old live checkpoint's tower head)"""
import sys
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[4]


def fold(base_path, tr_path, out_path):
    s = torch.load(tr_path, map_location="cpu", weights_only=False)
    st = torch.load(base_path, map_location="cpu", weights_only=False)
    cfg = s["cfg"]
    tr_sd = {"tower_refine." + k: v for k, v in s["tower_refine"].items()}
    tr_sd["tower_refine.cfg"] = torch.tensor([32, 4, 128, int(cfg["card"]), int(cfg["cell"])])
    st["model"] = {**st["model"], **tr_sd}
    st["tower_refine"] = {"source": str(tr_path), "w_chip": s["w_chip"], "steps": s["steps"], "base": str(base_path),
                          "eval": s["eval"], "eval_base": s["eval_base"]}
    torch.save(st, out_path)
    return st


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        bench = ROOT / "icebow/data/bench/rl_royale/rseries_r3c"
        tmp = Path(__file__).with_name("_fold_check.pt")
        st = fold(bench / "rseries_r3c_u0030_barrel2k_cellref.pt", ROOT / "scratchpad/gauntlet/L73/chip_rocket/tr_w2.pt", tmp)
        live = torch.load(bench / "rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt", map_location="cpu", weights_only=False)
        keys = sorted(k for k in live["model"] if k.startswith("tower_refine."))
        same = keys == sorted(k for k in st["model"] if k.startswith("tower_refine.")) and \
            all(torch.equal(live["model"][k], st["model"][k]) for k in keys)
        tmp.unlink()
        print(f"FOLD_CHECK {'OK' if same else 'MISMATCH'}: {len(keys)} tower_refine tensors")
        sys.exit(0 if same else 1)
    fold(*sys.argv[1:4])
    sys.path.insert(0, str(ROOT))
    from pipeline.model_gen import load_model
    m, _ = load_model(sys.argv[3], torch.device("cpu"))
    assert getattr(m, "cell_refine", None) is not None and getattr(m, "tower_refine", None) is not None, "heads not loaded"
    print("folded + loads with cell_refine and tower_refine ->", sys.argv[3])
