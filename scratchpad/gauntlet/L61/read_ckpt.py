"""One read of a checkpoint against the IL instruments: pro-cell agreement on v1 (sim boards) and v2 (engine
boards) + the rails fraction. Usage: read_ckpt.py <path relative to icebow>"""
import importlib.util, sys, torch
from pathlib import Path
ROOT = Path("C:/Users/benpe/ClashBot"); ICEBOW = ROOT / "icebow"
def load(p, name):
    spec = importlib.util.spec_from_file_location(name, str(p)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
K1 = load(ROOT / "scratchpad/gauntlet/L60/knn_vs_bc.py", "kvb1"); K2 = load(ROOT / "scratchpad/gauntlet/L61/knn_vs_bc_v2.py", "kvb2")
ck_path = ICEBOW / sys.argv[1]; K1.CKPT = ck_path; K2.CKPT = ck_path
dev = torch.device("cuda")
for tag, K in (("v1 sim boards", K1), ("v2 engine boards", K2)):
    T, meta, deck, tr, va = K.load_all(dev); net, ck = K.load_net(dev)
    o = K.forward_all(net, T, va, want=("cells",)); r, _, _ = K.score(o["cells"], T["cell"][va], meta, va, tag)
    print(f"[{tag}] matches={ck.get('matches')} {K.fmt(r)}")
    if tag.startswith("v1"):
        raws = []
        with torch.no_grad():
            for i0 in range(0, len(va), 256):
                sl = torch.as_tensor(va[i0:i0+256], device=dev); fmap = net.features(K.batch_x(T, sl))
                z = net._embed(fmap, T["hands"][sl], T["nexts"][sl], T["elx"][sl], T["thr"][sl])
                sel = net._cell_logits(fmap, z)[torch.arange(len(sl)), T["card"][sl]]
                raws.append(sel[T["mask"][sl]].abs())
        r2 = torch.cat(raws); print(f"[rails] frac |raw|>8 = {(r2>8).float().mean():.3f}  p99 {r2.quantile(0.99):.1f}  mean {r2.mean():.1f}")
        bm = net.cell_bias_map.detach(); print(f"[bias map] max {bm.max():.2f} min {bm.min():.2f} |d| from init n/a (see native_bias_ckpt)")
