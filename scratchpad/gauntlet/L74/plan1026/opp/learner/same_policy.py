"""same_policy.py INIT.pt RUN_CKPT.pt -- OPP-PUSH arm 2: prove a critic-only warm-up left the policy untouched. Compares every
tensor of the two checkpoints' model state dicts; prints the tensors that differ (expected: value-head tensors only) and the max
abs difference of all the others (expected: exactly 0)."""
import sys

import torch


def sd(path):
    ck = torch.load(path, map_location="cpu", weights_only=False)
    for k in ("model", "state_dict", "net"):
        if isinstance(ck.get(k), dict):
            return ck[k], sorted(ck)
    return {k: v for k, v in ck.items() if torch.is_tensor(v)}, sorted(ck)


a, ka = sd(sys.argv[1])
b, kb = sd(sys.argv[2])
print("init keys", ka[:12], "| run keys", kb[:12])
common = sorted(set(a) & set(b))
diff = [k for k in common if not torch.equal(a[k], b[k])]
print(f"tensors: init {len(a)} run {len(b)} common {len(common)}; only init {sorted(set(a) - set(b))[:5]}; only run {sorted(set(b) - set(a))[:5]}")
print("differ:", diff)
same = [k for k in common if k not in diff]
print("identical tensors:", len(same), "max |d| over them:", max((float((a[k].float() - b[k].float()).abs().max()) for k in same), default=0.0))
