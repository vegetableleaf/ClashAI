"""Rebuild validation/test baseline history with public frames and Hero deduplication.

The trained board projection must remain bit-identical. This repair changes no
labels, splits, model weights, live sources or policy. Old scored outputs are
invalidated by baselines.py's input_revision=3 requirement.
"""
import collections
import json
import numpy as np
import torch
from build import HERE, CKPT, PS, rebuild, public_events, tensor_batch, features

ck=torch.load(CKPT,map_location="cpu",weights_only=False);gid={k:i for i,k in enumerate(ck["card_vocab"])}
manifest=json.loads((HERE/"dataset_manifest.json").read_text());changed=collections.Counter();done=0
for rec in manifest["matches"]:
    if rec["split"]==0:continue
    path=HERE/"shards"/(rec["file"]+".npz");old=dict(np.load(path))
    if "input_revision" in old and int(old["input_revision"])==3:continue
    rows,meta=rebuild(list(public_events(PS.LIVE/rec["file"])),gid);b=tensor_batch(rows)
    np.testing.assert_array_equal(features(b).numpy(),old["x"])
    samples=np.linspace(0,len(rows)-1,min(4,len(rows))).astype(int)
    for k,v in b.items():
        field="batch_"+k;arr=v.numpy()
        changed[k]+=int(np.count_nonzero(old[field]!=arr))
        old[field]=arr;old["pd_"+k]=arr[samples]
    old["value"]=np.full(len(rows),np.nan,np.float32);old["gate"]=np.full(len(rows),np.nan,np.float32)
    old["input_revision"]=np.array(3)
    np.savez_compressed(path,**old);done+=1
    if done%20==0:print("REPAIRED",done,flush=True)
data=dict(np.load(HERE/"dataset.npz"));data["value"][data["split"]>0]=np.nan;data["gate_rebuilt"][data["split"]>0]=np.nan
np.savez_compressed(HERE/"dataset.npz",**data)
(HERE/"baseline_input_repair.json").write_text(json.dumps({"matches":done,"changed_elements":dict(changed),
    "training_features_bit_identical":True,"input_revision":3},indent=2))
print("BASELINE INPUTS REPAIRED",done,{k:v for k,v in changed.items() if v},flush=True)
