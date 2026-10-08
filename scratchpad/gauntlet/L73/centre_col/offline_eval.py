"""Offline before/after for the CellRefine module (L73 centre column). Teacher-forced on pro play rows of
gen_dataset_v32_fv5, lattice labels.
    python offline_eval.py OUT.json CKPT [CKPT ...]
Row sets: VAL = every val play row; SUB = play rows among the first 250k rows (head_res.py's set, train + val).
Per ckpt: head_res.py's tables (exact / x1 inside vs across patch / y1 / other, by split x unit|spell; centre-column
same vs OTHER column), cell top-1 / top-3 / NLL on VAL, and the h2 LANE CONSISTENCY of the model's own centre-column
picks (defensive Knight/IceWizard/Skeletons/Tesla rows, own half, nearest enemy body in a lane: share on the enemy's
side of centre; the pro's own rate on the same rows is reported beside it). Card logits of every ckpt are compared
to the FIRST ckpt's (max |diff| over VAL) -- the refine module must leave the card head bit-identical."""
import collections, json, sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline.dataset import load
from pipeline.model_gen import load_model
from pipeline.model_v3 import cell_label
from pipeline.train_gen import GenRows

DATA = "C:/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz"
SPELL = {"the-log", "tornado", "rocket", "fireball", "arrows", "zap", "goblin-barrel", "poison", "earthquake", "freeze",
         "lightning", "giant-snowball", "barbarian-barrel", "royal-delivery", "graveyard", "rage", "clone", "void", "vines"}
H2 = {"knight", "ice-wizard", "skeletons", "tesla"}
out_path, ckpts = sys.argv[1], sys.argv[2:]
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
arrs, meta = load(DATA)
play = arrs["y_gate"] == 1
rows_all = np.where(play & ((arrs["split"] == 1) | (np.arange(len(play)) < 250000)))[0]
rows = GenRows(arrs, rows_all, dev)
lab = arrs["y_xy"]; split = arrs["split"]; side = arrs["side"]; card = arrs["y_card"]; tok = arrs["tok"]; off = arrs["off"]
voc = meta["card_vocab"]
LC = cell_label(torch.from_numpy(lab[rows_all].astype(np.float32)), "lattice").numpy()

# nearest enemy body for the h2 rows (pro card in H2, own half); model frame, tiles
h2 = {}
for k, r in enumerate(rows_all):
    if voc[card[r]] not in H2:
        continue
    LX, LY = LC[k] % 36 / 2, 32 - LC[k] // 36 / 2
    if LY >= 15:
        continue
    t = tok[off[r]:off[r + 1]]
    en = t[(t[:, 2] == 1) & (t[:, 13] == 0)]
    if not len(en):
        continue
    ex, ey = en[:, 4] * 18, (1 - en[:, 5]) * 32
    j = int(np.argmin(np.hypot(ex - LX, ey - LY)))
    h2[k] = float(ex[j])

res, card0 = {}, None
for ck in ckpts:
    model, st = load_model(ck, dev); model.eval()
    pred, top3, nll, cards = [], [], [], []
    with torch.no_grad():
        for s in range(0, len(rows_all), 512):
            ids = rows_all[s:s + 512]
            b = rows.batch(ids)
            o = model(b, card=b["card"], form=b["form"])
            t = cell_label(b["xy"], "lattice")
            lp = o["cell"].float().log_softmax(-1)
            pred.append(lp.argmax(-1).cpu()); nll.append(-lp.gather(1, t[:, None])[:, 0].cpu())
            top3.append((lp.topk(3, -1).indices == t[:, None]).any(-1).cpu()); cards.append(o["card"].float().cpu())
    pred, top3, nll, cards = torch.cat(pred).numpy(), torch.cat(top3).numpy(), torch.cat(nll).numpy(), torch.cat(cards)
    card_diff = None if card0 is None else float(torch.nan_to_num(cards - card0, nan=0.0, posinf=0, neginf=0).abs().max())
    same_inf = None if card0 is None else bool(torch.equal(torch.isinf(cards), torch.isinf(card0)))
    if card0 is None:
        card0 = cards
    c, cen, lane = collections.Counter(), collections.Counter(), collections.Counter()
    for k, r in enumerate(rows_all):
        sets = (["val"] if split[r] else []) + (["sub_" + ("val" if split[r] else "train")] if r < 250000 else [])
        L, m = LC[k], pred[k]
        LX, LY, MX, MY = L % 36 / 2, 32 - L // 36 / 2, m % 36 / 2, 32 - m // 36 / 2
        kind = "spell" if voc[card[r]] in SPELL else "unit"
        if (MX, MY) == (LX, LY): cls = "exact"
        elif MY == LY and abs(MX - LX) == 1: cls = "x1-inside" if int(LX // 2) == int(MX // 2) else "x1-across"
        elif MX == LX and abs(MY - LY) == 1: cls = "y1-inside" if int((32 - LY) // 2) == int((32 - MY) // 2) else "y1-across"
        else: cls = "other"
        for sp in sets:
            c[f"{sp}|{kind}|{cls}"] += 1
            if kind == "unit" and LX in (8.5, 9.5) and LY < 15 and MX in (8.5, 9.5) and MY == LY:
                cen[f"{sp}|side{int(side[r])}|{'same' if MX == LX else 'OTHER'}"] += 1
            if k in h2 and abs(h2[k] - 9) >= 1:
                eX = h2[k]
                if MX in (8.5, 9.5):
                    lane[f"{sp}|side{int(side[r])}|model|{'enemy_side' if (MX - 9) * (eX - 9) > 0 else 'far_side'}"] += 1
                if LX in (8.5, 9.5):
                    lane[f"{sp}|side{int(side[r])}|pro|{'enemy_side' if (LX - 9) * (eX - 9) > 0 else 'far_side'}"] += 1
    va = split[rows_all] == 1
    res[ck] = {"val_n_play": int(va.sum()), "val_cell_top1": float((pred[va] == LC[va]).mean()),
               "val_cell_top3": float(top3[va].mean()), "val_cell_nll": float(nll[va].mean()),
               "val_card_top1": float((cards[torch.from_numpy(va)].argmax(-1).numpy() == arrs["y_hand_pos"][rows_all][va]).mean()),
               "card_logit_max_abs_diff_vs_first": card_diff, "card_inf_pattern_equal": same_inf,
               "has_cell_refine": getattr(model, "cell_refine", None) is not None,
               "miss": dict(sorted(c.items())), "centre": dict(sorted(cen.items())), "lane": dict(sorted(lane.items()))}
    print(json.dumps({ck: {k: v for k, v in res[ck].items() if k not in ("miss",)}}, indent=1), flush=True)
Path(out_path).write_text(json.dumps(res, indent=1))
