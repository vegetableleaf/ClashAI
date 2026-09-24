"""G2 acceptance 4: generalist rows vs S1's icebow s1_dataset.npz on the SAME (replay tag, side, tick, gate) rows.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/consistency_s1.py [GEN.npz] [S1.npz]
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from pipeline import vocab  # noqa: E402
from pipeline.obs_contract import load_deck  # noqa: E402

gen_p = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "icebow/data/pipeline/gen_dataset_starter.npz"
s1_p = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / "icebow/data/pipeline/s1_dataset.npz"
g, s = (lambda z: {k: z[k] for k in z.files})(np.load(gen_p)), (lambda z: {k: z[k] for k in z.files})(np.load(s1_p))  # materialise: NpzFile re-decompresses per access
gm = json.loads(str(g["meta"]))
voc = gm["card_vocab"]
deck = load_deck("icebow")
slot_key = [vocab.base_key(c).replace("_", "-") for c in deck.cards]


def keys(tags, rep, side, tick, gate):
    occ, out = Counter(), []
    for t, sd, tk, gt in zip(tags[rep], side, tick, gate):
        k = (str(t), int(sd), int(tk), int(gt))
        out.append(k + (occ[k],))
        occ[k] += 1
    return out


gk = {k: i for i, k in enumerate(keys(g["tags"], g["rep"], g["side"], g["tick"], g["y_gate"]))}
sk = keys(s["tags"], s["rep"], s["side"], s["tick"], s["y_gate"])
pairs = [(j, gk[k]) for j, k in enumerate(sk) if k in gk]
sj = np.asarray([p[0] for p in pairs])
gi = np.asarray([p[1] for p in pairs])
n_s1 = len(sk)
res = {"s1_rows": n_s1, "matched": len(pairs), "matched_pct": round(100 * len(pairs) / n_s1, 3)}

s1_card = np.asarray([slot_key[x] if x >= 0 else "<pad>" for x in s["y_slot"][sj]])
g_card = np.asarray([voc[x] for x in g["y_card"][gi]])
s1_wcard = np.asarray([slot_key[x] if x >= 0 else "<pad>" for x in s["y_wait_slot"][sj]])
g_wcard = np.asarray([voc[x] for x in g["y_wait_card"][gi]])
keep = np.ones(s["sc"].shape[1], bool)
keep[gm["sc_zeroed_cols"][0]:gm["sc_zeroed_cols"][1]] = False
s_hand = s["sc"][sj, 7:43].reshape(-1, 4, 9).argmax(-1)
s1_hand = np.asarray([[slot_key[x] if x < 8 else "<pad>" for x in h] for h in s_hand])
g_hand = np.asarray([[voc[x] for x in h] for h in g["hand_card"][gi]])
s1_past = np.asarray([[slot_key[int(x)] if x >= 0 else "<pad>" for x in p] for p in s["past"][sj, :, 0]])
g_past = np.asarray([[voc[int(x)] for x in p] for p in g["past"][gi, :, 0]])
tok_eq = np.asarray([np.array_equal(s["tok"][s["off"][a]:s["off"][a + 1]], g["tok"][g["off"][b]:g["off"][b + 1]])
                     for a, b in pairs])


def pct(x):
    return round(100 * float(np.mean(x)), 3)


res.update({
    "y_gate_equal_pct_of_s1": round(100 * len(pairs) / n_s1, 3),   # the key includes gate
    "y_card_vs_y_slot_pct": pct(s1_card == g_card),
    "y_xy_equal_pct": pct((s["y_xy"][sj] == g["y_xy"][gi]).all(1)),
    "y_wait_card_vs_y_wait_slot_pct": pct(s1_wcard == g_wcard),
    "y_wait_dt_equal_pct": pct(s["y_wait_dt"][sj] == g["y_wait_dt"][gi]),
    "y_crowns_equal_pct": pct((s["y_crowns"][sj] == g["y_crowns"][gi]).all(1)),
    "hand_identity_equal_pct": pct((s1_hand == g_hand).all(1)),
    "past_card_equal_pct": pct((s1_past == g_past).all(1)),
    "past_xydt_equal_pct": pct((s["past"][sj, :, 1:] == g["past"][gi, :, 2:]).all((1, 2))),
    "sc_nonslot_equal_pct": pct((s["sc"][sj][:, keep] == g["sc"][gi][:, keep]).all(1)),
    "tok_equal_pct": pct(tok_eq),
})
# v3 VAL selection: S1 split==1 rows vs the generalist's v3val flag
s_val = set(k for k, sp in zip(sk, s["split"]) if sp == 1)
g_val = set(k for k, i in gk.items() if g["v3val"][i] == 1)
res.update({"s1_v3val_rows": len(s_val), "gen_v3val_rows": len(g_val), "v3val_both": len(s_val & g_val),
            "v3val_s1_only": len(s_val - g_val), "v3val_gen_only": len(g_val - s_val),
            "gen_v3val_all_in_val_split": bool((g["split"][g["v3val"] == 1] == 1).all())})
unmatched = [k for k in sk if k not in gk]
res["unmatched_examples"] = [list(k) for k in unmatched[:5]]
res["unmatched_by_gate"] = dict(Counter(k[3] for k in unmatched))
print(json.dumps(res, indent=1))
