"""Prove the value-only extraction equals encode_gen on a persisted real row batch."""
import json
import numpy as np
import torch
from build import HERE, CKPT, baseline
from pipeline.model_gen import load_model

model,_=load_model(CKPT,torch.device("cpu"));model.eval().requires_grad_(False)
z=np.load(next((HERE/"shards").glob("*.jsonl.npz")))
b={k[3:]:torch.from_numpy(z[k]) for k in z.files if k.startswith("pd_")}
with torch.no_grad():
    full=model.value_head(model.encode_gen(b)["g"]).softmax(-1)
    reference=(full[:,4:].sum(1)-full[:,:3].sum(1)).numpy()
    fast,_=baseline(model,b)
np.testing.assert_allclose(reference,fast,rtol=0,atol=1e-7)
(HERE/"baseline_parity.json").write_text(json.dumps({"rows":len(fast),"max_abs_value_error":float(np.max(np.abs(reference-fast)))},indent=2))
print("BASELINE PARITY VERIFIED")
