"""Bounded value-head inference for only validation/test; no gradients or policy updates."""
import argparse
import json
import time
import numpy as np
import torch
from build import HERE, CKPT, baseline
from pipeline.model_gen import load_model


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--seconds",type=float,default=240)
    ap.add_argument("--threads",type=int,choices=(1,2,4),default=4);a=ap.parse_args();torch.set_num_threads(a.threads)
    manifest=json.loads((HERE/"dataset_manifest.json").read_text())
    model,_=load_model(CKPT,torch.device("cpu"));model.eval().requires_grad_(False);t0=time.monotonic()
    todo=[r for r in manifest["matches"] if r["split"] in (1,2)]
    for ix,r in enumerate(todo):
        path=HERE/"shards"/(r["file"]+".npz");dst=HERE/"shards"/(r["file"]+".pred.npz")
        if dst.exists():
            with np.load(dst) as previous:
                if "input_revision" in previous and int(previous["input_revision"])==3:continue
        z=np.load(path)
        if np.isfinite(z["value"]).all(): continue
        b={k[6:]:z[k] for k in z.files if k.startswith("batch_")}
        values=[];gates=[]
        for i in range(0,len(b["sc"]),64):
            v,g=baseline(model,{k:torch.from_numpy(x[i:i+64]) for k,x in b.items()});values.append(v);gates.append(g)
        temp=dst.with_suffix(".tmp.npz")
        np.savez_compressed(temp,value=np.concatenate(values),gate=np.concatenate(gates),input_revision=3)
        temp.replace(dst)
        print("BASELINE",ix+1,"/",len(todo),round(time.monotonic()-t0,1),flush=True)
        if time.monotonic()-t0>a.seconds:return
    data=dict(np.load(HERE/"dataset.npz"))
    for r in todo:
        dst=HERE/"shards"/(r["file"]+".pred.npz")
        if dst.exists():
            z=np.load(dst)
            assert int(z["input_revision"])==3
            m=data["match"]==r["match"];data["value"][m]=z["value"];data["gate_rebuilt"][m]=z["gate"]
    assert np.isfinite(data["value"][data["split"]>0]).all()
    np.savez_compressed(HERE/"dataset.npz",**data)
    print("BASELINES COMPLETE",flush=True)


if __name__=="__main__":main()
