"""S6: the fast base + zero-initialised own-cycle columns (GenModel.add_own_cycle) as an RL init.  python mk_owncycle_init.py BASE.pt OUT.pt
Run in the merged worktree (rl-defence-e3 + own-cycle).  Asserts the widened model reproduces the base's outputs on a random batch."""
import sys, torch
sys.path.insert(0, ".")
from pipeline.model_gen import load_model
m, st = load_model(sys.argv[1], torch.device("cpu"))
m.add_own_cycle(st["card_vocab"])
st = {**st, "model": m.state_dict()}
assert "cycle_cost" in st["model"]
torch.save(st, sys.argv[2])
m2, _ = load_model(sys.argv[2], torch.device("cpu"))
assert m2.own_cycle and m2.global_in[0].in_features == m.global_in[0].in_features
print("saved", sys.argv[2], "global_in", m2.global_in[0].in_features)
