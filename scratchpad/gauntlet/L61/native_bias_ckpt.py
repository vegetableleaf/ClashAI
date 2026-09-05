"""Convert the L60 wrapper checkpoints (bc_pro_extra.cell_bias_map) into NATIVE PolicyNet checkpoints now that
model.py has `cell_bias_map`, then re-score them with the unmodified scorers on v1 (sim) and v2 (engine) val."""
import importlib.util, sys, json, torch
from pathlib import Path
ROOT = Path("C:/Users/benpe/ClashBot"); ICEBOW = ROOT / "icebow"; MODELS = ICEBOW / "data/bc_pro/models"
sys.path.insert(0, str(ICEBOW / "src"))
from clashrl.model import PolicyNet
def load(p):
    spec = importlib.util.spec_from_file_location(p.stem, str(p)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
K1 = load(ROOT / "scratchpad/gauntlet/L60/knn_vs_bc.py"); K2 = load(ROOT / "scratchpad/gauntlet/L61/knn_vs_bc_v2.py")
dev = torch.device("cuda"); out = {}
data = {"v1": K1.load_all(dev), "v2": K2.load_all(dev)}
for seed in (0, 1, 2):
    src = MODELS / f"bc_head_bias_s{seed}.pt"; ck = torch.load(src, map_location="cpu")
    ex = ck.pop("bc_pro_extra"); assert set(ex["tensors"]) == {"cell_bias_map"}
    ck["model"] = dict(ck["model"]); ck["model"]["cell_bias_map"] = ex["tensors"]["cell_bias_map"].clone()
    ck["bc_pro"]["native_cell_bias_map"] = True
    dst = MODELS / f"bc_bias_native_s{seed}.pt"; torch.save(ck, dst)
    net = PolicyNet(in_ch=int(ck["in_ch"]), n_cards=int(ck["n_cards"]), n_cells=int(ck["n_cells"]), threat_dim=int(ck["threat_dim"]))
    net.load_state_dict(torch.load(dst, map_location="cpu")["model"]); net = net.to(dev).eval()   # strict
    for name, K in (("v1", K1), ("v2", K2)):
        T, meta, deck, tr, va = data[name]
        o = K.forward_all(net, T, va, want=("cells",)); r, _, _ = K.score(o["cells"], T["cell"][va], meta, va, f"native_s{seed}_{name}")
        print(f"native s{seed} {name}: {r['top1']:.2f} / {r['top5']:.2f}   (wrapper val_top1 {ck['bc_pro']['val_top1']:.2f})"); out[f"s{seed}_{name}"] = (r["top1"], r["top5"])
json.dump(out, open(ROOT / "scratchpad/gauntlet/L61/native_bias_ckpt.json", "w"), indent=1)
