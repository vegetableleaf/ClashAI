"""Record the PRE-WIRING per-step reward sequence (L59 regression reference).
    cd icebow && PYTHONHASHSEED=0 .venv/Scripts/python.exe ../scratchpad/gauntlet/L59/reward_ref.py
"""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
ICEBOW = HERE.parents[2] / "icebow"
# The PRE-EDIT source: `git archive HEAD icebow/src/clashrl` unpacked (read-only) into L59/_head, imported
# BEFORE the test module so its own `../src` path insert cannot shadow it (modules are cached).
HEAD_SRC = HERE / "_head" / "icebow" / "src"
sys.path.insert(0, str(HEAD_SRC))
import clashrl.sim.env as _E   # noqa: E402
assert Path(_E.__file__).resolve().is_relative_to(HEAD_SRC.resolve()), _E.__file__
assert not hasattr(_E.SimMatchEnv, "_geo_credit"), "not the pre-edit env"
sys.path.insert(0, str(ICEBOW / "tests"))
import test_geometry_wiring as W   # noqa: E402
assert W.SimMatchEnv is _E.SimMatchEnv
# the HEAD copy's Config resolves its project root to L59/_head/icebow (no config/, no data/): load the
# REAL icebow/config/config.yaml and point the root at the real icebow so the card DB etc. resolve
from clashrl.config import Config as _C   # noqa: E402
_orig_load = _C.load.__func__
def _load(cls, path=None):
    cfg = _orig_load(cls, path or ICEBOW / "config" / "config.yaml")
    cfg.root = ICEBOW
    return cfg
_C.load = classmethod(_load)
assert W.Config is _C
print("recording against", _E.__file__)

rewards, ledgers = W.run_matches(W.make_cfg(False))
arr = np.empty(len(rewards), dtype=object)
for i, r in enumerate(rewards):
    arr[i] = r
np.save(W.REF, arr, allow_pickle=True)
for i, r in enumerate(rewards):
    print(f"match {i} seed {W.SEEDS[i]}: {len(r)} steps, non-trade reward sum {r.sum():+.4f}, "
          f"plays {ledgers[i]['plays']}, terms {len(ledgers[i]['terms'])}")
print("saved", W.REF)
