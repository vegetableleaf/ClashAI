"""Per-head held-out NLL + top-1 + train/held-out gap + forward latency for one scale-curve checkpoint.
usage: scale_eval.py CODE_DIR CKPT DATA OUT_JSON   (run with the pod venv; GPU)"""
import sys, json, time, warnings, hashlib
import numpy as np, torch, torch.nn.functional as Fn
warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])
from pipeline.dataset import load as load_ds
from pipeline.eval_gen import GenRows, val_rows
from pipeline.model_gen import GenModel
from pipeline.model_v3 import cell_label, cell_index, tile_of_cell, GRID_X, GRID_Y

code, ck, data, out_json = sys.argv[1:5]
MODE = sys.argv[5] if len(sys.argv) > 5 else "all"   # all | nolat | latonly (latonly merges latency into an existing out_json)
dev = torch.device("cuda")
arrs, meta = load_ds(data)
st = torch.load(ck, map_location=dev)
a = st["args"]
model = GenModel(d=a["d"], layers=a["layers"], d_c=a["d_c"], n_cards=len(meta["card_vocab"]),
                 feature_version=a["feature_version"]).to(dev)
model.load_state_dict(st["model"]); model.eval()
n_params = sum(p.numel() for p in model.parameters())
grid = a["grid"]

tr_all = np.where(arrs["split"] == 0)[0]
sel = val_rows(arrs, a["val_sample"])                      # the rows the trainer used to pick the epoch
va_all = np.where(arrs["split"] == 1)[0]
va_clean = np.setdiff1d(va_all, sel)                       # held-out rows NOT used for epoch selection
v3 = np.where(arrs["v3val"] == 1)[0]
tr_sub = np.sort(np.random.default_rng(123).choice(tr_all, size=100000, replace=False))
rows = GenRows(arrs, np.arange(0), dev)

@torch.no_grad()
def nll(idx, bs=1024):
    s = dict(cell=0., card=0., wait=0., gate=0., value=0.); c = dict(play=0, wait=0, n=0)
    t1 = dict(cell_half=0, cell_tile=0, card=0, wait=0, gate_tp=0, gate_tn=0, value=0)
    nneg = npos = 0
    for i in range(0, len(idx), bs):
        ids = idx[i:i + bs]; b = rows.batch(ids)
        o = model(b, card=b["card"], form=b["form"])
        play = b["gate"] > 0.5; wt = ~play
        if play.any():
            lg = o["cell"][play]; xy = b["xy"][play]; th = cell_label(xy, grid)
            s["cell"] += float(Fn.cross_entropy(lg, th, reduction="sum"))
            pred = lg.argmax(-1); t1["cell_half"] += int((pred == th).sum())
            p = lg.softmax(-1).view(-1, GRID_Y // 2, 2, GRID_X // 2, 2).sum((2, 4)).flatten(1)
            tt = cell_index(xy, GRID_X // 2, GRID_Y // 2) if grid == "floor" else tile_of_cell(th)
            t1["cell_tile"] += int((p.argmax(-1) == tt).sum())
            ok = b["slot"][play] >= 0
            cl = o["card"][play][ok]; tg = b["slot"][play][ok]
            s["card"] += float(Fn.cross_entropy(cl, tg, reduction="sum")); t1["card"] += int((cl.argmax(-1) == tg).sum())
            c["play"] += int(play.sum()); c["card_n"] = c.get("card_n", 0) + int(ok.sum())
        ok = wt & (b["wait"] >= 0)
        if ok.any():
            wl = o["wait"][ok]; wg = b["wait"][ok]
            s["wait"] += float(Fn.cross_entropy(wl, wg, reduction="sum")); t1["wait"] += int((wl.argmax(-1) == wg).sum()); c["wait"] += int(ok.sum())
        s["gate"] += float(Fn.binary_cross_entropy_with_logits(o["gate"], b["gate"], reduction="sum"))
        gp = o["gate"] > 0; t1["gate_tp"] += int((gp & play).sum()); t1["gate_tn"] += int((~gp & wt).sum())
        npos += int(play.sum()); nneg += int(wt.sum())
        s["value"] += float(Fn.cross_entropy(o["value"], b["value"], reduction="sum")); t1["value"] += int((o["value"].argmax(-1) == b["value"]).sum())
        c["n"] += len(ids)
    P = max(c["play"], 1); K = max(c.get("card_n", 0), 1); W = max(c["wait"], 1); N = c["n"]
    return {"n": N, "n_play": c["play"],
            "nll_cell": s["cell"] / P, "nll_card": s["card"] / K, "nll_wait": s["wait"] / W,
            "nll_gate": s["gate"] / N, "nll_value": s["value"] / N,
            "nll_total": s["cell"] / P + s["card"] / K + .5 * s["wait"] / W + s["gate"] / N + .5 * s["value"] / N,
            "top1_cell_half": t1["cell_half"] / P, "top1_cell_tile": t1["cell_tile"] / P, "top1_card": t1["card"] / K,
            "top1_wait": t1["wait"] / W, "gate_bal_acc": .5 * (t1["gate_tp"] / max(npos, 1) + t1["gate_tn"] / max(nneg, 1)),
            "gate_acc": (t1["gate_tp"] + t1["gate_tn"]) / N, "value_acc": t1["value"] / N}

res = json.load(open(out_json)) if MODE == "latonly" else {"ckpt": ck, "sha256": hashlib.sha256(open(ck, "rb").read()).hexdigest(), "n_params": n_params, "d": a["d"],
       "layers": a["layers"], "epoch_selected": st["epoch"], "args": {k: a[k] for k in ("seed", "epochs", "bs", "lr", "amp", "grid", "feature_version")}}
if MODE != "latonly": res["heldout_clean"] = nll(va_clean); res["v3val"] = nll(v3); res["val_select_sample"] = nll(sel); res["train_sub100k"] = nll(tr_sub)
if MODE != "latonly": res["n_rows"] = {"train": len(tr_all), "val_all": len(va_all), "val_clean": len(va_clean), "sel": len(sel), "v3val": len(v3)}

# ---- forward latency (GPU only; pure model forward on an existing batch) ----
def lat(bs, amp, it):
    b = rows.batch(va_clean[:bs]); ts = []
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
        for k in range(it + 20):
            torch.cuda.synchronize(); t = time.perf_counter()
            model(b, card=b["card"], form=b["form"]); torch.cuda.synchronize()
            if k >= 20: ts.append((time.perf_counter() - t) * 1e3)
    ts = np.array(ts); return {"p50_ms": float(np.percentile(ts, 50)), "p99_ms": float(np.percentile(ts, 99))}
torch.cuda.reset_peak_memory_stats()
if MODE != "nolat": res["latency_ms"] = {f"bs{bs}_{'bf16' if amp else 'fp32'}": lat(bs, amp, it) for bs, it in ((1, 300), (1024, 40)) for amp in (False, True)}
if MODE != "nolat": res["latency_gpu_peak_mb_bs1024"] = round(torch.cuda.max_memory_allocated() / 2**20)
res["gpu"] = torch.cuda.get_device_name(0)
json.dump(res, open(out_json, "w"), indent=1)
print(json.dumps({k: res[k] for k in ("n_params", "epoch_selected")}), json.dumps(res["heldout_clean"]), json.dumps(res.get("latency_ms")))
