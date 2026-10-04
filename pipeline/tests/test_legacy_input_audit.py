import importlib.util
from pathlib import Path
import sys
import numpy as np
import tempfile

path=Path(__file__).resolve().parents[2]/'scratchpad/gauntlet/L70/gen_v31/audit_legacy_inputs.py'
sys.path.insert(0,str(path.parent))
spec=importlib.util.spec_from_file_location('legacy_audit',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_full_scalar_scan_and_masked_negative_control():
    with tempfile.TemporaryDirectory(dir=path.parents[4]/'.foreman/codex_autopilot/runs') as directory:
        p=Path(directory)/'sample.npz';a=np.zeros((17000,7),np.float32);a[-1,5:7]=[.5,1]
        np.savez_compressed(p,sc=a)
        r=m.scalar_inventory(p)
        assert r['rows']==17000 and r['opponent_known_rows']==1
        assert r['status']=='RECORDED_OPPONENT_ELIXIR_IN_LEGACY_MODEL_INPUT'
        a[:]=0;np.savez_compressed(p,sc=a)
        assert m.scalar_inventory(p)['opponent_known_rows']==0
