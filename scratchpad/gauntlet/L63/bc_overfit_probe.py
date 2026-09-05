"""Owner premise test: does the BC init OVERFIT? Score bc_bias_native_s0 on TRAIN vs VAL rows (v1 sim boards, v2 engine
boards) on the same instrument as read_ckpt.py. Also the split size and a per-match-count summary."""
import importlib.util, sys, json, torch, numpy as np
from pathlib import Path
ROOT = Path("C:/Users/benpe/ClashBot"); ICEBOW = ROOT / "icebow"
def load(p, name):
    spec = importlib.util.spec_from_file_location(name, str(p)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
K1 = load(ROOT / "scratchpad/gauntlet/L60/knn_vs_bc.py", "kvb1"); K2 = load(ROOT / "scratchpad/gauntlet/L61/knn_vs_bc_v2.py", "kvb2")
ck_path = ICEBOW / (sys.argv[1] if len(sys.argv) > 1 else "data/bc_pro/models/bc_bias_native_s0.pt"); K1.CKPT = ck_path; K2.CKPT = ck_path
dev = torch.device("cuda")
for tag, K in (("v1 sim boards", K1), ("v2 engine boards", K2)):
    T, meta, deck, tr, va = K.load_all(dev); net, ck = K.load_net(dev)
    for sname, idx in (("TRAIN", tr), ("VAL", va)):
        o = K.forward_all(net, T, idx, want=("cells",)); r, _, _ = K.score(o["cells"], T["cell"][idx], meta, idx, f"{tag} {sname}")
        # cross-entropy of the pro cell under the policy, as a second overfit signal
        with torch.no_grad():
            lp = torch.log_softmax(o["cells"], dim=1); ce = -lp[torch.arange(len(idx)), T["cell"][idx]].mean().item()
            ent = -(lp.exp() * lp).sum(1).mean().item()
        print(f"[{tag}] {sname}: {K.fmt(r)}  ce {ce:.3f} H {ent:.2f}", flush=True)
    try:
        print(f"[{tag}] split sizes train {len(tr)} val {len(va)}; meta cols: {list(meta.columns)[:12] if hasattr(meta,'columns') else type(meta)}")
    except Exception as e: print("meta:", e)
