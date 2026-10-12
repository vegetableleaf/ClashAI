"""Fit only the public-state win predictor. Never imports the RL learner."""
import os
os.environ["CUDA_VISIBLE_DEVICES"]="-1"
os.environ["OMP_NUM_THREADS"]="1"
import copy
import json
from pathlib import Path
import sys
import time
import numpy as np
import torch
from torch.nn import functional as F
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]; sys.path.insert(0,str(ROOT))
from pipeline.live_phi import LivePhi, SCHEMA, FEATURE_DIM
torch.set_num_threads(1)


def date_split(records, fraction=.2):
    dates=sorted(set(r["file"][10:18] for r in records))
    if len(dates)<2: raise ValueError("need at least two dates")
    boundary=min(dates[1:],key=lambda d:abs(sum(r["file"][10:18]>=d for r in records)-fraction*len(records)))
    return boundary


def assemble():
    source=json.loads((HERE/"source_manifest.json").read_text())
    receipts=[HERE/"shards"/(n+".json") for n in source["files"]]
    if not all(p.exists() for p in receipts): raise RuntimeError("extraction incomplete")
    rs=[json.loads(p.read_text()) for p in receipts]
    good=[r for r in rs if not r["excluded"]]
    test_date=date_split(good)
    val_date=date_split([r for r in good if r["file"][10:18]<test_date])
    arrays={k:[] for k in ("x","value","tc","tick","play","cost","gate_logged","gate_rebuilt","y","match","split")}
    manifest=[]
    for i,r in enumerate(good):
        z=np.load(HERE/"shards"/(r["file"]+".npz")); n=len(z["x"])
        split=2 if r["file"][10:18]>=test_date else 1 if r["file"][10:18]>=val_date else 0
        arrays["x"].append(z["x"]); arrays["value"].append(z["value"]); arrays["tc"].append(z["tc"])
        for k,col in (("tick",0),("play",1),("cost",2),("gate_logged",3)): arrays[k].append(z["meta"][:,col])
        arrays["gate_rebuilt"].append(z["gate"])
        for k,v in (("y",r["label"]),("match",i),("split",split)): arrays[k].append(np.full(n,v))
        manifest.append(dict(r,match=i,split=split))
    data={k:np.concatenate(v) for k,v in arrays.items()}
    np.savez_compressed(HERE/"dataset.npz",**data)
    result={"matches":manifest,"excluded":[r for r in rs if r["excluded"]],"test_date":test_date,"validation_date":val_date,
            "selection":"phase_stats.read_live, since 20261008; exact final public tower scorecard label; draws dropped",
            "feature_schema":SCHEMA,"rows":len(data["y"])}
    (HERE/"dataset_manifest.json").write_text(json.dumps(result,indent=2))
    return data,result


def platt(x,y):
    # Positive-slope Platt fit preserves the baseline's ordering. Calibration only.
    x=torch.tensor(np.asarray(x),dtype=torch.float64); y=torch.tensor(np.asarray(y),dtype=torch.float64)
    theta=torch.tensor([0.,0.],dtype=torch.float64,requires_grad=True)
    opt=torch.optim.LBFGS([theta],max_iter=60,line_search_fn="strong_wolfe")
    def closure():
        opt.zero_grad(); loss=F.binary_cross_entropy_with_logits(theta[0].exp()*x+theta[1],y)+1e-6*theta.square().sum()
        loss.backward(); return loss
    opt.step(closure)
    return [float(theta[0].detach().exp()),float(theta[1].detach())]


def train(data,manifest):
    start=time.monotonic(); torch.manual_seed(74012); rng=np.random.default_rng(74012)
    X=torch.tensor(data["x"],dtype=torch.float32); y=torch.tensor(data["y"],dtype=torch.float32)
    tr=np.where(data["split"]==0)[0]; va=np.where(data["split"]==1)[0]
    model=LivePhi(32)
    with torch.no_grad():
        model.mean.copy_(X[tr].mean(0)); model.scale.copy_(X[tr].std(0).clamp_min(.05))
    opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    counts=np.bincount(data["match"][tr].astype(int)); weights=torch.tensor(1/counts[data["match"][tr].astype(int)],dtype=torch.float32)
    weights/=weights.mean(); best=float("inf"); state=None; hist=[]
    for epoch in range(30):
        order=rng.permutation(len(tr)); model.train()
        for st in range(0,len(order),1024):
            ix=order[st:st+1024]; ids=tr[ix]
            opt.zero_grad(); loss=(F.binary_cross_entropy_with_logits(model.logits(X[ids]),y[ids],reduction="none")*weights[ix]).mean()
            loss.backward(); opt.step()
            if time.monotonic()-start>=540:
                raise TimeoutError("CPU training deadline exceeded; no incomplete checkpoint accepted")
        model.eval()
        with torch.no_grad(): v=float(F.binary_cross_entropy_with_logits(model.logits(X[va]),y[va]))
        hist.append({"epoch":epoch+1,"validation_bce":v,"seconds":time.monotonic()-start})
        if v<best: best=v; state=copy.deepcopy(model.state_dict()); selected=epoch+1
    model.load_state_dict(state)
    with torch.no_grad(): logits=model.logits(X[va]).numpy()
    calibration=platt(logits,data["y"][va]); model.calibration.copy_(torch.tensor(calibration))
    duration=time.monotonic()-start
    if duration>=600: raise TimeoutError("training plus calibration exceeded ten minutes")
    ck={"schema":SCHEMA,"feature_dim":FEATURE_DIM,"feature_versions":[4,5,6],"hidden":32,
        "state_dict":model.state_dict(),"training_seconds":duration,"selected_epoch":selected,
        "seed":74012,"training_matches":[r["file"] for r in manifest["matches"] if r["split"]==0],
        "calibration_matches":[r["file"] for r in manifest["matches"] if r["split"]==1]}
    torch.save(ck,HERE/"phi_live.pt")
    (HERE/"training.json").write_text(json.dumps({"seconds":duration,"history":hist,"selected_epoch":selected,"calibration":calibration,
                                                "n_parameters":sum(p.numel() for p in model.parameters()),"threads":1},indent=2))
    print("PREDICTOR FIT COMPLETE",len(tr),len(va),round(duration,2),flush=True)


if __name__=="__main__":
    d,m=assemble(); train(d,m)
