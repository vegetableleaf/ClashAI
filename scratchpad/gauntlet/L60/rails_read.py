"""Rails read: fraction of masked raw cell logits with |raw| > 8 (+ mean/min) on the val split, for a checkpoint.
usage: rails_read.py <ckpt path relative to icebow>"""
import sys, importlib.util, torch, numpy as np
from pathlib import Path
spec = importlib.util.spec_from_file_location("kvb", str(Path(__file__).with_name("knn_vs_bc.py")))
kvb = importlib.util.module_from_spec(spec); spec.loader.exec_module(kvb)
kvb.CKPT = kvb.ICEBOW / sys.argv[1]
dev = "cuda"
T, meta, deck, tr, va = kvb.load_all(dev)
net, ck = kvb.load_net(dev)
raws = []
with torch.no_grad():
    for i0 in range(0, len(va), 256):
        sl = torch.as_tensor(va[i0:i0 + 256], device=dev)
        fmap = net.features(kvb.batch_x(T, sl))
        z = net._embed(fmap, T["hands"][sl], T["nexts"][sl], T["elx"][sl], T["thr"][sl])
        sel = net._cell_logits(fmap, z)[torch.arange(len(sl)), T["card"][sl]]
        raws.append(sel[T["mask"][sl]].float().cpu())
r = torch.cat(raws)
print(f"{sys.argv[1]}: masked raw cell logits n={len(r)} frac|raw|>8 = {(r.abs()>8).float().mean():.3f} mean {r.mean():.1f} min {r.min():.1f} max {r.max():.1f} p99|raw| {r.abs().quantile(0.99):.1f}")
