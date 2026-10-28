# D2-G test harness (not pipeline code), active only under its env switches:
#   D2_DET_CUDA=1  every Python process of the run (learner + spawned actors) turns on torch's deterministic algorithms
#                  before rl_royale imports anything; CUBLAS_WORKSPACE_CONFIG is set by run3.sh.
#   D2_SAMPLE=dir  spawned actor processes (argv[0] '-c') run d2sample's 10 ms stack sampler -> dir/<pid>.json.
import os
import sys

if os.environ.get("D2_DET_CUDA"):
    import torch
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False

if os.environ.get("D2_SAMPLE") and sys.argv[:1] == ["-c"]:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import d2sample
    d2sample.start(os.environ["D2_SAMPLE"])
