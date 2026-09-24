"""Idle-GPU throughput of train_gen / eval_gen on gen_dataset_v1 (L68 G3 follow-up, item 1 + 3).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/throughput_v1.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from pipeline import eval_gen as EG, train_gen as TG, train_s1 as T1  # noqa: E402
from pipeline.dataset import load as load_ds  # noqa: E402
from pipeline.model_gen import GenModel  # noqa: E402


def sync():
    torch.cuda.synchronize()


def old_batch(self, ids):                                         # the pre-follow-up GenRows.batch (S1's row loop)
    b = T1.Rows.batch(self, ids)
    t = torch.from_numpy(np.asarray(ids)).to(self.dev)
    b.update({k: v[t].long() for k, v in self.ident.items()})
    b["card"], b["form"] = self.card[t].long(), self.form[t].long()
    return b


def timed(fn):
    sync(); t = time.time(); r = fn(); sync()
    return time.time() - t, r


res = {"gpu": torch.cuda.get_device_name(0)}
t0 = time.time()
arrs, meta = load_ds(REPO / "icebow/data/pipeline/gen_dataset_v1.npz")
res["load_s"] = round(time.time() - t0, 1)
tr_all = np.where(arrs["split"] == 0)[0]
res["rows"], res["train_rows"], res["val_rows"], res["v3val_rows"] = (len(arrs["split"]), len(tr_all),
                                                                     int((arrs["split"] == 1).sum()), int(arrs["v3val"].sum()))
dev = torch.device("cuda")
torch.cuda.reset_peak_memory_stats()
t0 = time.time()
rows = EG.GenRows(arrs, tr_all, dev)
sync()
res["rows_to_gpu_s"] = round(time.time() - t0, 1)
res["gpu_mb_data"] = round(torch.cuda.memory_allocated() / 2 ** 20)
rng = np.random.default_rng(0)
sub = np.sort(rng.choice(tr_all, 50_000, replace=False))
torch.manual_seed(0)
model = GenModel(n_cards=len(meta["card_vocab"])).to(dev)

# item 1: eval before / after vectorising batch(), 20k rows, eval bs 512 (train_gen's)
new_batch = EG.GenRows.batch
v20 = rows.view(sub[:20_000])
for name, fn in (("new", new_batch), ("old", old_batch), ("new_again", new_batch)):
    EG.GenRows.batch = fn
    ids = v20.idx
    tb, _ = timed(lambda: [v20.batch(ids[s:s + 512]) for s in range(0, len(ids), 512)])
    te, _ = timed(lambda: EG.evaluate(model, v20, bs=512, grid="lattice"))
    res[f"eval20k_{name}"] = {"eval_s": round(te, 2), "batch_only_s": round(tb, 2), "rows_per_s": round(20_000 / te)}
    print(json.dumps({name: res[f"eval20k_{name}"]}), flush=True)
EG.GenRows.batch = new_batch

# item 3: eval throughput on the 50k subset, bs 256 and 512
v50 = rows.view(sub)
for bs in (256, 512):
    te, _ = timed(lambda: EG.evaluate(model, v50, bs=bs, grid="lattice"))
    res[f"eval50k_bs{bs}_rows_per_s"] = round(50_000 / te)

# item 3: training throughput on the 50k subset, bs 256 (train_gen's loop body: mirror p 0.5, AdamW, clip)
model.train()
opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)
perm = rng.permutation(sub)
bs = 256
def steps(lo, hi):
    for s in range(lo * bs, hi * bs, bs):
        b = rows.batch(perm[s:s + bs])
        loss, _ = TG.losses(model, b, mirror=rng.random() < 0.5, grid="lattice")
        opt.zero_grad(set_to_none=True); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        float(loss.detach())
n_steps = len(perm) // bs
timed(lambda: steps(0, 10))                                       # warm-up
tt, _ = timed(lambda: steps(10, n_steps))
res["train_rows_per_s"] = round((n_steps - 10) * bs / tt)
res["gpu_peak_mb"] = round(torch.cuda.max_memory_allocated() / 2 ** 20)

# projection: --epochs 4 on the full v1 train split, --val-sample 30000 + full v3val each epoch, final 20k train eval
ev_rate = res["eval50k_bs512_rows_per_s"]
ep_train = res["train_rows"] / res["train_rows_per_s"]
ep_eval = (30_000 + res["v3val_rows"]) / ev_rate
total = res["load_s"] + res["rows_to_gpu_s"] + 4 * (ep_train + ep_eval) + 20_000 / ev_rate
res["projection_epochs4"] = {"train_s_per_epoch": round(ep_train), "eval_s_per_epoch": round(ep_eval),
                             "total_h": round(total / 3600, 2)}
out = Path(__file__).with_name("throughput_v1.json")
out.write_text(json.dumps(res, indent=1))
print(json.dumps(res))
