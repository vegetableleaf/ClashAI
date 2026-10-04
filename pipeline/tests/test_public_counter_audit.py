import importlib.util
from pathlib import Path
import numpy as np

path=Path(__file__).resolve().parents[2]/'scratchpad/gauntlet/L70/gen_v31/audit_public_counter.py'
spec=importlib.util.spec_from_file_location('counter_audit',path)
audit=importlib.util.module_from_spec(spec)
import sys
sys.path.insert(0,str(path.parent));spec.loader.exec_module(audit)


def test_paired_error_aggregation_and_cluster_ci():
    rows=[dict(n=2,absolute_sum=[1.,4.],signed_sum=[-1.,4.],squared_sum=[.5,8.],over_one=[0,2])]*3
    result=audit.aggregate(rows)
    assert result['observations']==6
    assert result['mae']==[.5,2.]
    assert result['paired_mae_delta']==-1.5
    assert result['paired_mae_delta_ci95']==[-1.5,-1.5]


def test_truth_only_affects_error_not_observer_prediction():
    rec=dict(record_native=True,frames=[dict(tick=10,entities=[],projectiles=[],elixir=[6.,6.])])
    a=audit.evaluate(rec)
    rec['frames'][0]['elixir']=[2.,2.]
    b=audit.evaluate(rec)
    np.testing.assert_allclose(np.array(b['signed_sum'])-a['signed_sum'],[8.,8.])
