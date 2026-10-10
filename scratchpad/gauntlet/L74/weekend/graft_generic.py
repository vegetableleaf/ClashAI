"""Graft the live model's CellRefine + TowerRefine + projectile_target_* add-ons (42 tensors) onto an RL arm checkpoint.
    python graft_generic.py ARM.pt LIVE.pt OUT.pt      (graft_heads.py with paths as arguments)"""
import sys, torch
arm, live = torch.load(sys.argv[1], map_location="cpu"), torch.load(sys.argv[2], map_location="cpu")
heads = {k: v for k, v in live["model"].items() if k.startswith(("cell_refine.", "tower_refine.", "projectile_target_"))}
assert live["card_vocab"] == arm["card_vocab"], "card vocab differs"
arm["model"] = {**arm["model"], **heads}
arm["grafted_heads_from"] = sys.argv[2]
torch.save(arm, sys.argv[3])
print("grafted", len(heads), "tensors ->", sys.argv[3])
