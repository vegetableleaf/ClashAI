"""Score the L60 prior-initialised bias-map heads (trained on v1 sim boards) on the v2 ENGINE-board val split.
Transfer test: does a head trained on sim boards hold up when the board comes from the real engine?"""
import importlib.util, sys, json
from pathlib import Path
import torch
HERE = Path(__file__).resolve().parent
L60 = HERE.parent / "L60"
sys.path.insert(0, str(L60))
import bc_coord as BC                       # HeadWrapper + K (v1 module)
spec = importlib.util.spec_from_file_location("kvb2", str(HERE / "knn_vs_bc_v2.py"))
K2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(K2)
dev = torch.device("cuda")
T, meta, deck, tr, va = K2.load_all(dev)
print("v2 val rows", len(va))
out = {}
for name in sys.argv[1:]:
    ck = torch.load(BC.MODELS / name, map_location="cpu")
    net = BC.PolicyNet(in_ch=int(ck["in_ch"]), n_cards=int(ck["n_cards"]), n_cells=int(ck["n_cells"]), threat_dim=int(ck["threat_dim"]))
    net.load_state_dict(ck["model"]); net = net.to(dev)
    ex = ck["bc_pro_extra"]["tensors"]
    m = BC.HeadWrapper(net, coord="cell_conv.0.weight_coord" in ex,
                       bias_init=ex["cell_bias_map"].to(dev) if "cell_bias_map" in ex else None).to(dev)
    if "cell_conv.0.weight_coord" in ex:
        with torch.no_grad(): m.net.cell_conv[0].weight[:, 96:] = ex["cell_conv.0.weight_coord"].to(dev)
    m.eval()
    o = BC.K.forward_all(m, T, va, want=("cells",))
    r, _, _ = BC.K.score(o["cells"], T["cell"][va], meta, va, name)
    print(name, "v1-val(ckpt)", ck["bc_pro"].get("val_top1"), "| v2-val", BC.K.fmt(r))
    out[name] = r
    if "cell_bias_map" in ex:   # the map alone on v2 (no convs): is the v1 prior still a prior on engine boards?
        cells = ex["cell_bias_map"].to(dev)[T["card"][va]]
        r0, _, _ = BC.K.score(cells, T["cell"][va], meta, va, name + "_maponly")
        print("   bias map alone on v2 val", BC.K.fmt(r0)); out[name + "_maponly"] = r0
json.dump(out, open(HERE / "rescore_bias_v2.json", "w"), indent=1, default=str)
