"""VM check after syncing pipeline/tower_refine.py + the model_gen.py hook: the live checkpoint loads with NO tower_refine and
gives the same outputs as the pre-sync model_gen (backup imported as a separate module); the folded checkpoints load
fv6 + CellRefine + TowerRefine. Synthetic batch, CPU, 2 threads.  Run from ~/ClashBot: python ~/probe_rocket/vm_verify.py"""
import importlib.util, os, sys, torch
sys.path.insert(0, os.path.expanduser("~/ClashBot")); torch.set_num_threads(2)
from pipeline.model_gen import load_model
CK = "icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt"
import importlib.machinery as IM
_p = os.path.expanduser("~/probe_rocket/model_gen.py.bak_pre_towerrefine")
spec = importlib.util.spec_from_file_location("pipeline.model_gen_old", _p, loader=IM.SourceFileLoader("pipeline.model_gen_old", _p))
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
torch.manual_seed(0); B = 8
b = {"tok": torch.rand(B, 64, 14), "mask": torch.zeros(B, 64, dtype=torch.bool), "unit_form": torch.zeros(B, 64, dtype=torch.long),
     "sc": torch.rand(B, 70), "past": torch.zeros(B, 3, 5), "hand_card": torch.randint(1, 50, (B, 4)), "hand_form": torch.zeros(B, 4, dtype=torch.long),
     "next_card": torch.ones(B, dtype=torch.long), "next_form": torch.zeros(B, dtype=torch.long), "deck_card": torch.randint(1, 50, (B, 8)),
     "deck_form": torch.zeros(B, 8, dtype=torch.long), "opp_past": torch.zeros(B, 3, 5), "opp_cycle": torch.zeros(B, 8, 4),
     "projectiles": torch.zeros(B, 64, 8), "effects": torch.zeros(B, 32, 6), "own_ability": torch.zeros(B, 8, 7)}
b["tok"][..., 0] = torch.randint(0, 200, (B, 64)).float(); b["mask"][:, :10] = True
c = torch.full((B,), 5)
with torch.no_grad():
    m_new, _ = load_model(CK, torch.device("cpu")); m_old, _ = old.load_model(CK, torch.device("cpu"))
    assert getattr(m_new, "tower_refine", None) is None
    a, o = m_new.eval()(b, card=c), m_old.eval()(b, card=c)
    for k in ("gate", "card", "cell", "wait", "value"): assert torch.equal(a[k], o[k]), k
    print("live checkpoint: hooked loader byte-identical to pre-sync model_gen")
    for w in ("w1", "w2"):
        m, _ = load_model(os.path.expanduser(f"~/probe_rocket/rseries_r3c_u0030_barrel2k_cellref_towerref_{w}.pt"), torch.device("cpu")); m.eval()
        assert m.tower_refine is not None and m.cell_refine is not None and m.feature_version >= 6
        r = m(b, card=c); print(w, "loads fv6+CellRefine+TowerRefine; card diff vs base", float((r["card"] - a["card"]).abs().max()))
