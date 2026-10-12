"""Load the exact L73 pro row IDs and recompute the requested OLD value head.

Streaming extraction avoids loading the multi-GB expanded source into RAM.
Inference is resumable in bounded chunks, at most four CPU threads.
"""
import argparse
import json
import time
import zipfile
from pathlib import Path
import numpy as np
import torch
from build import HERE, ROOT, CKPT, baseline, features, tower_crown, digest
from pipeline.eval_gen import GenRows
from pipeline.model_gen import load_model
from numpy.lib import format as NF


class Stream:
    def __init__(self,z,key):
        self.f=z.open(key+".npy"); ver=NF.read_magic(self.f)
        self.shape,order,self.dtype=(NF.read_array_header_1_0 if ver==(1,0) else NF.read_array_header_2_0)(self.f)
        if order: raise ValueError("unexpected Fortran array")
        self.row=int(np.prod(self.shape[1:]))*self.dtype.itemsize
    def read(self,n):
        return np.frombuffer(self.f.read(n*self.row),self.dtype).reshape((n,)+tuple(self.shape[1:]))


def prepare():
    saved=np.load(HERE.parent.parent/"L73/phi_eval/phi_v32.npz")
    src=ROOT/"icebow/data/pipeline/gen_dataset_v32_fv5.npz"
    wanted=saved["idx"]; data=np.load(src)
    metadata=json.loads(str(data["meta"]))
    checkpoint=torch.load(CKPT,map_location="cpu",weights_only=False)
    assert metadata["feature_version"]==5
    assert metadata["card_vocab"]==checkpoint["card_vocab"]
    off=data["off"]; n=len(off)-1; z=zipfile.ZipFile(src)
    keys=("tok","unit_form","sc","past","hand_card","hand_form","next_card","next_form","deck_card","deck_form",
          "opp_past","opp_cycle","projectiles","effects","own_ability","y_gate","y_hand_pos","y_wait_card","y_card","y_xy","y_crowns")
    keys=[k for k in keys if k+".npy" in z.namelist()]
    streams={k:Stream(z,k) for k in keys}; parts={k:[] for k in keys}; lengths=[]
    for start in range(0,n,20000):
        end=min(start+20000,n); lo,hi=int(off[start]),int(off[end])
        chunk={k:s.read(hi-lo if k in ("tok","unit_form") else end-start) for k,s in streams.items()}
        ix=wanted[(wanted>=start)&(wanted<end)]
        if not len(ix): continue
        uid=np.concatenate([np.arange(off[j]-lo,off[j+1]-lo) for j in ix]).astype(int)
        for k,v in chunk.items(): parts[k].append(v[uid] if k in ("tok","unit_form") else v[ix-start])
        lengths.extend((off[ix+1]-off[ix]).tolist())
    sub={k:np.concatenate(v) for k,v in parts.items()}
    sub["off"]=np.r_[0,np.cumsum(lengths)]
    np.testing.assert_allclose(sub["sc"][:,saved["sc_cols"]],saved["sc"],atol=0,rtol=0)
    np.testing.assert_array_equal(sub["y_crowns"],saved["y_crowns"])
    for k in ("idx","rep","side","tick","y_crowns","y_gate","y_card"): sub[k]=saved[k]
    np.savez_compressed(HERE/"pro_inputs.npz",**sub)
    (HERE/"pro_source.json").write_text(json.dumps({"path":str(src.relative_to(ROOT)),"sha256":digest(src),
        "l73_path":"scratchpad/gauntlet/L73/phi_eval/phi_v32.npz","rows":len(wanted),"exact_sc_and_label_parity":True,
        "feature_version":5,"checkpoint_vocab_equal":True},indent=2))
    print("PRO ROWS LOADED",len(wanted),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--prepare",action="store_true");ap.add_argument("--seconds",type=float,default=240)
    ap.add_argument("--threads",type=int,choices=(1,2,4),default=4)
    a=ap.parse_args();torch.set_num_threads(a.threads)
    if a.prepare: prepare(); return
    arr=dict(np.load(HERE/"pro_inputs.npz")); rows=GenRows(arr,np.arange(len(arr["sc"])),torch.device("cpu"))
    model,_=load_model(CKPT,torch.device("cpu")); model.eval().requires_grad_(False)
    dest=HERE/"pro_shards";dest.mkdir(exist_ok=True); t0=time.monotonic()
    for start in range(0,len(arr["sc"]),1024):
        p=dest/f"{start:06d}.npz"
        if p.exists(): continue
        xs=[];values=[]
        for i in range(start,min(start+1024,len(arr["sc"])),64):
            b=rows.batch(np.arange(i,min(i+64,start+1024,len(arr["sc"]))))
            v,_=baseline(model,b); values.append(v); xs.append(features(b).numpy())
        temp=p.with_suffix(".tmp.npz")
        np.savez_compressed(temp,x=np.concatenate(xs),value=np.concatenate(values),start=start)
        temp.replace(p)
        print("PRO",start+len(np.concatenate(xs)),"/",len(arr["sc"]),"seconds",round(time.monotonic()-t0,1),flush=True)
        if time.monotonic()-t0>a.seconds: return
    xs=[];values=[]
    for p in sorted(p for p in dest.glob("*.npz") if p.stem.isdigit()):
        z=np.load(p);xs.append(z["x"]);values.append(z["value"])
    rep=arr["rep"];side=arr["side"]
    d=arr["y_crowns"][:,0]-arr["y_crowns"][:,1]; keep=(d!=0)&(arr["tick"]<6000)
    keys=dict(x=np.concatenate(xs),value=np.concatenate(values),tc=tower_crown(arr["sc"]),tick=arr["tick"],
              y=(d>0).astype(int),match=rep,trajectory=rep.astype(np.int64)*2+side,play=arr["y_gate"],card=arr["y_card"])
    order=np.lexsort((keys["tick"][keep],keys["trajectory"][keep]))
    np.savez_compressed(HERE/"pro_dataset.npz",**{k:v[keep][order] for k,v in keys.items()})
    print("PRO DATASET COMPLETE",int(keep.sum()),flush=True)


if __name__=="__main__": main()
