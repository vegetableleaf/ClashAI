"""10-14 experiment: graft ONLY CellRefine + TowerRefine from LIVE.pt onto ARM.pt, KEEPING the arm's own (RL-trained)
projectile_target_* input layers (graft_generic.py overwrites them with LIVE's).
    python graft_heads_only.py ARM.pt LIVE.pt OUT.pt"""
import sys, torch
arm, live = torch.load(sys.argv[1], map_location="cpu"), torch.load(sys.argv[2], map_location="cpu")
heads = {k: v for k, v in live["model"].items() if k.startswith(("cell_refine.", "tower_refine."))}
extra = {k: v for k, v in live["model"].items() if k.startswith("projectile_target_") and k not in arm["model"]}
assert live["card_vocab"] == arm["card_vocab"], "card vocab differs"
arm["model"] = {**arm["model"], **heads, **extra}
arm["grafted_heads_from"] = sys.argv[2]
arm["graft_mode"] = "heads_only_keep_own_projectile_target"
torch.save(arm, sys.argv[3])
print("grafted", len(heads), "head tensors +", len(extra), "missing projectile tensors ->", sys.argv[3])
