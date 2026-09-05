import importlib.util, torch
from pathlib import Path
ROOT = Path("C:/Users/benpe/ClashBot"); ICEBOW = ROOT / "icebow"
def load(p, name):
    spec = importlib.util.spec_from_file_location(name, str(p)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
K1 = load(ROOT / "scratchpad/gauntlet/L60/knn_vs_bc.py", "kvb1"); K2 = load(ROOT / "scratchpad/gauntlet/L61/knn_vs_bc_v2.py", "kvb2")
dev = torch.device("cuda")
for tag, K in (("v1", K1), ("v2", K2)):
    K.CKPT = ICEBOW / "data/bc_pro/models/bc_bias_native_s0.pt"
    T, meta, deck, tr, va = K.load_all(dev); net, ck = K.load_net(dev)
    for sname, idx in (("TRAIN", tr), ("VAL", va)):
        o = K.forward_all(net, T, idx, want=("cells",)); s = o["cells"]; tgt = T["cell"][idx]
        bad = torch.isinf(s[torch.arange(len(idx)), tgt]) | torch.isnan(s[torch.arange(len(idx)), tgt])
        ok = ~bad; lp = torch.log_softmax(s[ok], 1); ce = -lp[torch.arange(ok.sum()), tgt[ok]].mean().item()
        p = lp.exp(); ent = -(p * lp.nan_to_num(neginf=0)).sum(1).mean().item()
        legal = torch.isfinite(s).sum(1).float()
        print(f"[{tag}] {sname}: n {len(idx)} target-masked {bad.sum().item()} ({100*bad.float().mean():.2f}%)  ce(legal) {ce:.3f}  H {ent:.2f}  legal cells mean {legal.mean():.0f} (uniform H {legal.log().mean():.2f})", flush=True)
