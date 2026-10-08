"""R4 CPU smoke: rl_royale --smoke (2 updates) with branch_kinds hold + card + xbow_class and FAKE labels.

The branch workers run the real ``branch_worker_main`` (real model, real fork selection ``fork_alt``) with T1/T2
replaced in the spawn child by test_rl_branch's fakes (pipeline.tests.test_branch_r4.r4_smoke_worker_main: a pair
sleeps R4_SMOKE_SLEEP s, labels +-0.5). Everything else is the real trainer.

    python scratchpad/gauntlet/L73/r4/smoke_r4.py --smoke --run <name> --config <yaml> key=value ...
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from pipeline import rl_royale as RL                       # noqa: E402
from pipeline.tests import test_branch_r4 as T4            # noqa: E402

RL.branch_worker_main = T4.r4_smoke_worker_main            # BranchPool's default target (resolved at construction)

if __name__ == "__main__":
    sys.exit(RL.main(sys.argv[1:]))
