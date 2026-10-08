"""Fold a trained offline TowerRefine (tr_wX.pt, wrapper format) into a full checkpoint loadable by pipeline.model_gen
(opt-in by the tower_refine.* keys), and verify on 256 real chip rows:
  main     : MAIN-checkout pipeline -> outputs of the live checkpoint and of the offline wrapper (reference)        -> ref.npz
  worktree : WORKTREE pipeline (hooked model_gen) -> live checkpoint must load WITHOUT tower_refine and match the main
             outputs exactly; the folded checkpoint must load fv6 target branch + CellRefine + TowerRefine together and
             match the wrapper.
  python convert_and_verify.py main tr_w2.pt ; python convert_and_verify.py worktree tr_w2.pt"""
import os, sys, pickle
import numpy as np, torch
HERE = os.path.dirname(os.path.abspath(__file__))
MODE, TR = sys.argv[1], sys.argv[2]
WT = os.path.abspath(os.path.join(HERE, "../../../.."))
ROOT = "C:/Users/benpe/ClashBot" if MODE == "main" else WT
sys.path.insert(0, ROOT); sys.path.insert(1, HERE)
os.chdir(ROOT)
import pipeline
assert os.path.dirname(pipeline.__file__).replace("\\", "/").startswith(ROOT.replace("\\", "/")), pipeline.__file__
from common import load_rows, CK
from pipeline.eval_gen import GenRows
from pipeline.model_gen import load_model
torch.set_num_threads(2)
rows = sorted(r["row"] for r in pickle.load(open(os.path.join(HERE, "chip_rows.pkl"), "rb")) if r["kind"] == "chip")[:256]
sub, meta = load_rows(np.array(rows)); dev = torch.device("cpu")
b = GenRows(sub, np.arange(len(rows)), dev).batch(np.arange(len(rows)))
RK = torch.full((len(rows),), meta["card_vocab"].index("rocket"))


def outs(m):
    with torch.no_grad():
        o = m(b, card=RK, form=torch.zeros_like(RK))
    return {k: o[k].float().numpy() for k in ("gate", "card", "cell")}


tr_path = os.path.join(HERE, TR); folded = os.path.join(HERE, "rseries_r3c_u0030_barrel2k_cellref_towerref_" + TR.split("_")[1])
if MODE == "main":
    import tower_refine as offline
    live, _ = load_model(CK["live"], dev); live.eval()
    w, _ = offline.load(tr_path, dev)
    np.savez(os.path.join(HERE, "ref.npz"), **{"live_" + k: v for k, v in outs(live).items()}, **{"wrap_" + k: v for k, v in outs(w).items()})
    s = torch.load(tr_path, map_location="cpu", weights_only=False); st = torch.load(CK["live"], map_location="cpu", weights_only=False)
    cfg = s["cfg"]
    tr_sd = {"tower_refine." + k: v for k, v in s["tower_refine"].items()}
    tr_sd["tower_refine.cfg"] = torch.tensor([32, 4, 128, int(cfg["card"]), int(cfg["cell"])])
    st["model"] = {**st["model"], **tr_sd}
    st["tower_refine"] = {"source": TR, "w_chip": s["w_chip"], "steps": s["steps"], "base": CK["live"], "eval": s["eval"], "eval_base": s["eval_base"]}
    torch.save(st, folded); print("folded ->", folded)
else:
    ref = np.load(os.path.join(HERE, "ref.npz"))
    live, _ = load_model(CK["live"], dev); live.eval()
    assert getattr(live, "tower_refine", None) is None and live.cell_refine is not None and live.feature_version >= 6
    for k, v in outs(live).items(): assert np.array_equal(v, ref["live_" + k]), ("live changed", k)
    m, _ = load_model(folded, dev); m.eval()
    assert m.tower_refine is not None and m.cell_refine is not None and m.feature_version >= 6
    for k, v in outs(m).items():
        d = float(np.abs(v - ref["wrap_" + k]).max()); print(k, "max |folded - wrapper|", d); assert d < 1e-4, k
    d = outs(m)
    print("live checkpoint byte-identical under the hooked loader; folded = fv6 + CellRefine + TowerRefine == offline wrapper")
