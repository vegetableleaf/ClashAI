# LOOP-INT (run.sh NOTF32=1): every process of an A/B arm (learner, actors, producers) runs with TF32 off (lead ruling
# 10-28: no TF32 in a forward that produces or recomputes log-probs), so both arms of a correctness test share numerics.
try:
    import torch
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
except Exception:
    pass
