"""L60 Measurement 2 -- can the cell head learn the static per-card map once it has coordinates?

Head-only BC recipe from knn_vs_bc.cmd_bc (rail repair --rescale_p99 6, Adam 1e-3 on cell_ctx + cell_conv, batch 128,
<= 60 epochs, EARLY STOP ON VAL CE patience 8, seed 0), with a wrapper module around the unmodified PolicyNet:
  --variant coord : two constant coordinate channels (x, y in [-1, 1]) concatenated to the cell_conv INPUT at the fmap
                    resolution (12 x 8 for the 96 x 64 obs). cell_conv[0] = Conv2d(64+32 -> 48, 1x1) becomes
                    Conv2d(98 -> 48, 1x1): weight[:, :96] copied from the source, weight[:, 96:98] = 0, bias copied,
                    so epoch 0 == the (rescaled) baseline exactly (asserted).
  --variant bias  : a learnable per-card bias map [n_cards, 432] added to the cell logits (before the +/-8 tanh cap),
                    initialised to log(train_count + 1) (Laplace-1 log prior; NOT centred, as specified). Epoch 0 =
                    rescaled baseline logits + log prior (reported; log prior alone = control 13.65/40.04).
  --variant both  : the two together (extra, for reference).
Checkpoint: the source dict layout (`model` strict-loadable into PolicyNet) can NOT represent either wrapper
(cell_conv.0.weight would be [48,98,1,1]; a [10,432] bias map does not fold into cell_conv.4.bias [10] because the map is
bilinearly upsampled from 12x8 and the bias is per channel), so the file keeps `model` = the strict-loadable part (wrapper
extras stripped) and adds `bc_pro_extra` with the extra tensors + a description; the policy code would need the wrapper.
Usage (cwd icebow): PYTHONPATH=src PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L60/bc_coord.py --variant coord
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
import knn_vs_bc as K  # noqa: E402  (unmodified; imported)
from clashrl.model import PolicyNet, _LOGIT_CAP  # noqa: E402

MODELS = K.MODELS
GW, GH, NC = K.GW, K.GH, K.GW * K.GH


class HeadWrapper(nn.Module):
    """Holds the unmodified PolicyNet; re-implements _cell_logits with (optional) coordinate channels and a
    per-card bias map. Exposes features / _embed / _cell_logits / forward the way knn_vs_bc.forward_all uses them."""

    def __init__(self, net: PolicyNet, coord: bool, bias_init: torch.Tensor | None):
        super().__init__()
        self.net = net
        self.coord = coord
        if coord:
            old = net.cell_conv[0]
            assert isinstance(old, nn.Conv2d) and old.kernel_size == (1, 1) and old.in_channels == 96
            new = nn.Conv2d(old.in_channels + 2, old.out_channels, 1)
            with torch.no_grad():
                new.weight.zero_()
                new.weight[:, :old.in_channels] = old.weight
                new.bias.copy_(old.bias)
            net.cell_conv[0] = new.to(old.weight.device)
        self.bias_map = nn.Parameter(bias_init.clone()) if bias_init is not None else None
        self._coord_cache = {}

    def coords(self, h, w, device):
        key = (h, w, str(device))
        if key not in self._coord_cache:
            ys = torch.linspace(-1, 1, h, device=device)[:, None].expand(h, w)
            xs = torch.linspace(-1, 1, w, device=device)[None, :].expand(h, w)
            self._coord_cache[key] = torch.stack([xs, ys])[None]           # [1,2,h,w]
        return self._coord_cache[key]

    def features(self, x):
        return self.net.features(x)

    def _embed(self, *a, **k):
        return self.net._embed(*a, **k)

    def _cell_logits(self, fmap, z):
        net = self.net
        ctx = net.cell_ctx(z)[:, :, None, None].expand(-1, -1, fmap.shape[2], fmap.shape[3])
        inp = torch.cat([fmap, ctx], dim=1)
        if self.coord:
            inp = torch.cat([inp, self.coords(fmap.shape[2], fmap.shape[3], fmap.device).expand(fmap.shape[0], -1, -1, -1)], 1)
        m = net.cell_conv(inp)
        gw, gh = net.grid_wh
        cells = F.interpolate(m, size=(gh, gw), mode="bilinear", align_corners=False).flatten(2)
        if not net.cell_per_card:
            cells = cells.expand(-1, net.n_cards, -1)
        if self.bias_map is not None:
            cells = cells + self.bias_map[None]
        return cells

    def forward(self, x, hand, nxt=None, elx=None, thr=None):
        fmap = self.features(x)
        z = self._embed(fmap, hand, nxt, elx, thr)
        cards = _LOGIT_CAP * torch.tanh(self.net.card_head(z) / _LOGIT_CAP)
        cells = _LOGIT_CAP * torch.tanh(self._cell_logits(fmap, z) / _LOGIT_CAP)
        return cards, cells

    def head_params(self):
        ps = list(self.net.cell_ctx.parameters()) + list(self.net.cell_conv.parameters())
        if self.bias_map is not None:
            ps.append(self.bias_map)
        return ps


def main(args):
    dev = torch.device(args.device)
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    T, meta, deck, tr, va = K.load_all(dev)
    net, ck = K.load_net(dev)
    # rail repair, identical to knn_vs_bc.cmd_bc
    with torch.no_grad():
        raws = []
        for i0 in range(0, len(tr), 256):
            sl = torch.as_tensor(tr[i0:i0 + 256], device=dev)
            fmap = net.features(K.batch_x(T, sl))
            z = net._embed(fmap, T["hands"][sl], T["nexts"][sl], T["elx"][sl], T["thr"][sl])
            sel = net._cell_logits(fmap, z)[torch.arange(len(sl)), T["card"][sl]]
            raws.append(sel[T["mask"][sl]].abs())
        p99 = float(torch.quantile(torch.cat(raws), 0.99))
        rescale = p99 / args.rescale_p99
        net.cell_conv[4].weight.div_(rescale); net.cell_conv[4].bias.div_(rescale)
    print(f"[rescale] p99 {p99:.2f} -> cell_conv.4 / {rescale:.2f}")
    base = K.forward_all(net, T, va, want=("cells",))
    rbase, _, _ = K.score(base["cells"], T["cell"][va], meta, va, "rescaled_baseline")
    print("rescaled baseline", K.fmt(rbase))

    bias_init = None
    if args.variant in ("bias", "both"):
        hist = torch.zeros(10, NC, device=dev)
        hist.index_put_((T["card"][tr], T["cell"][tr]), torch.ones(len(tr), device=dev), accumulate=True)
        bias_init = torch.log(hist + 1.0)
        # what the bias map alone scores through this pipeline (should be the Laplace-1 control, 13.65/40.04)
        sc = (_LOGIT_CAP * torch.tanh(bias_init[T["card"][va]] / _LOGIT_CAP)).masked_fill(~T["mask"][va], float("-inf"))
        rp, _, _ = K.score(sc, T["cell"][va], meta, va, "log_prior_alone"); print(K.fmt(rp))
    model = HeadWrapper(net, coord=args.variant in ("coord", "both"), bias_init=bias_init).to(dev)
    for p in model.net.parameters():
        p.requires_grad_(False)
    hp = [model.bias_map] if args.bias_only else model.head_params()     # --bias_only: convs frozen, only the map trains
    for p in hp:
        p.requires_grad_(True)
    opt = torch.optim.Adam(hp, lr=args.head_lr)
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    okv = T["mask"][va][torch.arange(len(va)), T["cell"][va]]

    def evaluate(tag):
        model.eval()
        out = K.forward_all(model, T, va, want=("cells",))
        res, _, _ = K.score(out["cells"], T["cell"][va], meta, va, tag)
        res["entropy_nats"] = K.masked_entropy(out["cells"])
        res["val_ce"] = float(F.cross_entropy(out["cells"][okv], T["cell"][va][okv]))
        return res

    r0 = evaluate(f"M2_{args.variant}_ep0")
    print(f"ep 0 val top1 {r0['top1']:.2f} top5 {r0['top5']:.2f} ce {r0['val_ce']:.3f} H {r0['entropy_nats']:.2f}")
    if args.variant == "coord":
        assert abs(r0["top1"] - rbase["top1"]) < 1e-9 and abs(r0["top5"] - rbase["top5"]) < 1e-9, "epoch 0 != baseline"
        print("[check] epoch 0 == rescaled baseline (zero-init coordinate weights)")
    curve = [(0, r0["top1"], r0["top5"], r0["val_ce"], r0["entropy_nats"], None)]
    best_ce, best_ep, bad = r0["val_ce"] if not args.skip_epoch0 else 1e9, 0, 0
    best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    for ep in range(1, args.epochs + 1):
        model.train()
        perm = torch.randperm(len(tr), generator=gen).numpy()
        tot, n = 0.0, 0
        for i0 in range(0, len(tr), args.bs):
            sl = torch.as_tensor(tr[perm[i0:i0 + args.bs]], device=dev)
            _, cells = model(K.batch_x(T, sl), T["hands"][sl], T["nexts"][sl], T["elx"][sl], T["thr"][sl])
            sel = cells[torch.arange(len(sl)), T["card"][sl]].masked_fill(~T["mask"][sl], float("-inf"))
            ok = T["mask"][sl][torch.arange(len(sl)), T["cell"][sl]]
            loss = F.cross_entropy(sel[ok], T["cell"][sl][ok])
            opt.zero_grad(); loss.backward(); opt.step()
            tot += loss.item() * len(sl); n += len(sl)
        r = evaluate(f"M2_{args.variant}")
        curve.append((ep, r["top1"], r["top5"], r["val_ce"], r["entropy_nats"], tot / n))
        print(f"ep {ep} train_ce {tot/n:.3f} val top1 {r['top1']:.2f} top5 {r['top5']:.2f} ce {r['val_ce']:.3f} H {r['entropy_nats']:.2f}", flush=True)
        if r["val_ce"] < best_ce - 1e-9:
            best_ce, best_ep, bad = r["val_ce"], ep, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= args.patience:
                print(f"early stop at ep {ep}, best ep {best_ep} val_ce {best_ce:.3f}")
                break
    model.load_state_dict(best_state)
    rb = evaluate(f"M2_{args.variant}_best"); rb["best_epoch"] = best_ep; rb["curve"] = curve
    rb["rescaled_baseline"] = {"top1": rbase["top1"], "top5": rbase["top5"]}
    print("BEST", K.fmt(rb), "ce", rb["val_ce"], "entropy", rb["entropy_nats"])
    # what the strict-loadable part alone scores (bias map stripped / coordinate weights dropped)
    if args.variant in ("bias", "both"):
        bm = model.bias_map
        model.bias_map = None
        rs = evaluate("strict_part_without_bias_map"); rb["without_bias_map"] = {"top1": rs["top1"], "top5": rs["top5"], "val_ce": rs["val_ce"]}
        print("strict-loadable convs WITHOUT the bias map:", K.fmt(rs))
        model.bias_map = bm
    # save: source dict layout + extras
    sd = {k[len("net."):]: v for k, v in best_state.items() if k.startswith("net.")}
    extra = {}
    if args.variant in ("coord", "both"):
        w = sd["cell_conv.0.weight"]
        extra["cell_conv.0.weight_coord"] = w[:, 96:].clone()      # [48,2,1,1] : x, y channel weights
        sd["cell_conv.0.weight"] = w[:, :96].clone()               # strict-loadable slice (NOT equivalent on its own)
    if args.variant in ("bias", "both"):
        extra["cell_bias_map"] = best_state["bias_map"].clone()    # [10,432]
    ck2 = dict(ck); ck2["model"] = sd
    ck2["bc_pro"] = {"mode": f"head+{args.variant}", "seed": args.seed, "best_epoch": best_ep, "val_top1": rb["top1"],
                     "val_top5": rb["top5"], "val_ce": rb["val_ce"], "source": str(K.CKPT), "head_rescale_div": rescale,
                     "stop_on": "val_ce", "epoch0": curve[0]}
    ck2["bc_pro_extra"] = {"tensors": extra, "note": (
        "The `model` entry is strict-loadable into PolicyNet but is NOT the evaluated model: the wrapper adds "
        + ("two constant coordinate channels (x,y in [-1,1] at the 12x8 fmap resolution) as cell_conv input channels 96:98 "
           "(weights in cell_conv.0.weight_coord); " if args.variant in ("coord", "both") else "")
        + ("a per-card bias map [n_cards,432] added to the pre-tanh cell logits (cell_bias_map); " if args.variant in ("bias", "both") else "")
        + "see scratchpad/gauntlet/L60/bc_coord.py HeadWrapper.")}
    outp = MODELS / (args.out or f"bc_head_{args.variant}_s{args.seed}.pt")
    torch.save(ck2, outp)
    # verify: the strict part loads; the wrapper rebuilt from the file reproduces the val number
    ck3 = torch.load(outp, map_location="cpu")
    net2 = PolicyNet(in_ch=int(ck3["in_ch"]), n_cards=int(ck3["n_cards"]), n_cells=int(ck3["n_cells"]), threat_dim=int(ck3["threat_dim"]))
    net2.load_state_dict(ck3["model"]); net2 = net2.to(dev)
    ex = ck3["bc_pro_extra"]["tensors"]
    m2 = HeadWrapper(net2, coord="cell_conv.0.weight_coord" in ex,
                     bias_init=ex["cell_bias_map"].to(dev) if "cell_bias_map" in ex else None).to(dev)
    if "cell_conv.0.weight_coord" in ex:
        with torch.no_grad():
            m2.net.cell_conv[0].weight[:, 96:] = ex["cell_conv.0.weight_coord"].to(dev)
    m2.eval()
    out2 = K.forward_all(m2, T, va, want=("cells",))
    r2, _, _ = K.score(out2["cells"], T["cell"][va], meta, va, "reload")
    assert abs(r2["top1"] - rb["top1"]) < 1e-6, (r2["top1"], rb["top1"])
    rb["saved"] = str(outp); rb["reload_ok"] = True
    print("saved+reloaded (via wrapper)", outp, "top1", r2["top1"])
    json.dump(rb, open(MODELS / (args.json or f"M2_{args.variant}_s{args.seed}.json"), "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="coord", choices=["coord", "bias", "both"])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--bs", type=int, default=128)
    ap.add_argument("--rescale_p99", type=float, default=6.0)
    ap.add_argument("--head_lr", type=float, default=1e-3)
    ap.add_argument("--skip_epoch0", action="store_true")
    ap.add_argument("--bias_only", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    torch.set_num_threads(2)
    t0 = time.time()
    main(a)
    print(f"done {time.time()-t0:.0f}s")
