"""Chronological held-out evaluation; match-cluster paired bootstrap, no fitting on test/pros."""
import os
for variable in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"):
    os.environ[variable]="1"
import json
import collections
from pathlib import Path
import numpy as np
import torch
from build import HERE, ROOT, CKPT, digest
from fit import platt
from pipeline.live_phi import load, features
from pipeline.reward_shaping import trailing_mean

B=500
NAMES=("live_phi","value_phi","tower_crown")


def ci(point,values):
    a=np.asarray(values);a=a[np.isfinite(a)]
    return [float(point),*map(float,np.percentile(a,[2.5,97.5]))] if len(a) else [float(point),None,None]


def weighted_auc(groups,y,w):
    p=np.bincount(groups,w*y);n=np.bincount(groups,w*(1-y),minlength=len(p))
    den=p.sum()*n.sum()
    return float((p*(np.cumsum(n)-.5*n)).sum()/den) if den else np.nan


def smooth(data,x):
    out=np.zeros_like(x,dtype=float); trajectory=data.get("trajectory",data["match"])
    for mid in np.unique(trajectory):
        m=trajectory==mid;out[m]=trailing_mean(x[m],data["tick"][m],200)
    return out


def probabilities(model,x):
    with torch.no_grad():
        return np.concatenate([model.probability(torch.tensor(a,dtype=torch.float32)).numpy() for a in np.array_split(x,max(1,len(x)//4096))])


def sigmoid(x): return 1/(1+np.exp(-np.clip(x,-40,40)))


def predictions(data,model,maps=None,fit_mask=None):
    raw={"live_phi":2*probabilities(model,data["x"])-1,"value_phi":data["value"],"tower_crown":data["tc"]}
    scores={n:v for n,v in raw.items()}
    scores.update({n+"_10s":smooth(data,v) for n,v in raw.items()})
    if maps is None:
        maps={n:platt(v[fit_mask],data["y"][fit_mask]) for n,v in scores.items() if not n.startswith("live_phi")}
    probs={n:(v+1)/2 if n.startswith("live_phi") else sigmoid(maps[n][0]*v+maps[n][1]) for n,v in scores.items()}
    return scores,probs,maps


def masks(data):
    t=data["tick"]
    return {"all":np.ones(len(t),bool),"1x":t<2400,"2x":(t>=2400)&(t<4800),"3x":(t>=4800)&(t<6000),"first30s":t<600}


def table(data,scores,probs):
    result={}
    for label,mask in masks(data).items():
        y=data["y"][mask];_,r=np.unique(data["match"][mask],return_inverse=True);nrep=int(r.max()+1) if len(r) else 0
        gs={k:np.unique(v[mask],return_inverse=True)[1] for k,v in scores.items()}
        errors={k:(v[mask]-y)**2 for k,v in probs.items()}
        ones=np.ones(len(y));auc={k:weighted_auc(g,y,ones) for k,g in gs.items()};brier={k:float(e.mean()) for k,e in errors.items()}
        aa={k:[] for k in scores};bb={k:[] for k in probs};rng=np.random.default_rng(74012)
        for _ in range(B):
            w=np.bincount(rng.integers(nrep,size=nrep),minlength=nrep)[r]
            for k,g in gs.items():aa[k].append(weighted_auc(g,y,w))
            for k,e in errors.items():bb[k].append(float(w@e/w.sum()))
        entry={"rows":len(y),"matches":nrep,"win_rate":float(y.mean()),
               "auc":{k:ci(auc[k],aa[k]) for k in auc},"brier":{k:ci(brier[k],bb[k]) for k in brier},"paired":{}}
        for suffix in ("","_10s"):
            live="live_phi"+suffix
            for base in ("value_phi","tower_crown"):
                key=base+suffix
                entry["paired"][live+"-"+key]={"auc":ci(auc[live]-auc[key],np.array(aa[live])-aa[key]),
                    "brier":ci(brier[live]-brier[key],np.array(bb[live])-bb[key])}
        result[label]=entry
    return result


def calibration(data,probs):
    out={}
    for phase,m in masks(data).items():
        out[phase]={}
        for key,p in probs.items():
            p=p[m];y=data["y"][m];bins=np.minimum((p*10).astype(int),9); rows=[];ece=0
            for i in range(10):
                k=bins==i
                if not k.any():continue
                pp=float(p[k].mean()); yy=float(y[k].mean());ece+=k.mean()*abs(pp-yy)
                rows.append({"lo":i/10,"hi":(i+1)/10,"rows":int(k.sum()),"mean_prediction":pp,"observed_win_rate":yy})
            out[phase][key]={"ece":float(ece),"mean_probability":float(p.mean()),"win_rate":float(y.mean()),"bins":rows}
    return out


def jitter(data,scores):
    out={};trajectory=data.get("trajectory",data["match"])
    for name,s in scores.items():
        # Actual default potential: learned scalars x .5; tower_crown already weighted .3/.3.
        p=s if name.startswith("tower_crown") else .5*s
        diffs=[];per=[]
        for mid in np.unique(trajectory):
            m=trajectory==mid;d=np.diff(p[m]);diffs.extend(d.tolist())
            per.append({"trajectory":int(mid),"rows":int(m.sum()),"total_variation":float(np.abs(d).sum()),"step_std":float(d.std()) if len(d) else 0})
        tv=np.array([x["total_variation"] for x in per])
        out[name]={"step_delta_std":float(np.std(diffs)),"tv_mean":float(tv.mean()),"tv_median":float(np.median(tv)),"per_match":per}
    return out


def jitter_comparisons(data,scores):
    trajectory=data.get("trajectory",data["match"])
    clusters=np.unique(data["match"]);index={v:i for i,v in enumerate(clusters)};stats={}
    for name,s in scores.items():
        p=s if name.startswith("tower_crown") else .5*s
        # Counts, sum(delta), sum(delta^2), sum(TV), number of trajectories.
        a=np.zeros((len(clusters),5))
        for mid in np.unique(trajectory):
            mask=trajectory==mid;i=index[data["match"][mask][0]];d=np.diff(p[mask])
            a[i]+=[len(d),d.sum(),(d*d).sum(),np.abs(d).sum(),1]
        stats[name]=a
    def metric(a,w):
        n,s,ss,tv,nt=w@a
        return np.array([np.sqrt(max(0,ss/n-(s/n)**2)),tv/nt])
    points={k:metric(a,np.ones(len(clusters))) for k,a in stats.items()};boot={k:[] for k in stats}
    rng=np.random.default_rng(740)
    for _ in range(B):
        w=np.bincount(rng.integers(len(clusters),size=len(clusters)),minlength=len(clusters))
        for k,a in stats.items():boot[k].append(metric(a,w))
    out={"estimates":{k:{m:ci(points[k][i],np.array(boot[k])[:,i]) for i,m in enumerate(("step_std","tv_mean"))} for k in stats},"paired":{}}
    for suffix in ("","_10s"):
        live="live_phi"+suffix
        for base in ("value_phi","tower_crown"):
            key=base+suffix;delta=np.array(boot[live])-boot[key]
            out["paired"][live+"-"+key]={m:ci(points[live][i]-points[key][i],delta[:,i]) for i,m in enumerate(("step_std","tv_mean"))}
    return out


def bootmean(v,cluster):
    if not len(v):return [None,None,None]
    _,r=np.unique(cluster,return_inverse=True);n=r.max()+1;rng=np.random.default_rng(74)
    bs=[]
    for _ in range(B):
        w=np.bincount(rng.integers(n,size=n),minlength=n)[r];bs.append(float(w@v/w.sum()))
    return ci(float(np.mean(v)),bs)


def bootcontrast(v,cluster,left,right):
    """Difference of row means with the SAME resampled match weights in both groups."""
    left=left&np.isfinite(v);right=right&np.isfinite(v)
    if not left.any() or not right.any():return [None,None,None]
    _,r=np.unique(cluster,return_inverse=True);n=r.max()+1
    sums=np.stack([np.bincount(r[m],v[m],minlength=n) for m in (left,right)],axis=1)
    counts=np.stack([np.bincount(r[m],minlength=n) for m in (left,right)],axis=1)
    rng=np.random.default_rng(74012);bs=[]
    for _ in range(B):
        w=np.bincount(rng.integers(n,size=n),minlength=n);den=w@counts
        if (den>0).all():bs.append(float(np.diff((w@sums)/den)[0]*-1))
    return ci(float(v[left].mean()-v[right].mean()),bs)


def dependence(data,model,manifest):
    # Use every held-out decision for scalar PD; bootstrap at match level.
    x=data["x"].copy();r=data["match"];out={};values=[]
    for e in range(11):
        a=x.copy();a[:,3]=e/10;values.append(probabilities(model,a))
    arr=np.stack(values,1)
    out["own_elixir"]={"grid":list(range(11)),"mean_pwin":arr.mean(0).tolist(),
        "delta_5_to_10":bootmean(arr[:,10]-arr[:,5],r),"positive_row_fraction_5_to_10":float((arr[:,10]-arr[:,5]>1e-6).mean()),
        "by_phase":{k:bootmean((arr[:,10]-arr[:,5])[m],r[m]) for k,m in masks(data).items()}}
    for label,cols in (("own_tower_hp",range(7,10)),("enemy_tower_hp",range(10,13))):
        values=[]
        for fraction in (.05,.25,.5,.75,1):
            a=x.copy()
            for col in cols:
                alive=x[:,col+12]>.5;known=x[:,col+6]>.5;a[alive&known,col]=fraction
            values.append(probabilities(model,a))
        out[label]={"fractions":[.05,.25,.5,.75,1],"mean_pwin":[float(v.mean()) for v in values],
                    "delta_full_minus_low":bootmean(values[-1]-values[0],r)}
    # Remove actual troop tokens, retaining buildings, clock, elixir and towers.
    # This is a sensitivity diagnostic; it is not a legal transition simulation.
    from pipeline import vocab
    catalog=json.loads((ROOT/"research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json").read_text())["cards"]
    building_bases={vocab.base_key(vocab.engine_key(c["display_name"])) for c in catalog if c["type"]=="building"}
    building_ids={i for i,k in enumerate(vocab.UNIT_VOCAB) if vocab.base_key(k) in building_bases}
    batches=[];clusters=[]
    for rec in manifest["matches"]:
        if rec["split"]!=2:continue
        z=np.load(HERE/"shards"/(rec["file"]+".npz"));b={k:z["pd_"+k] for k in ("tok","mask","sc")}
        batches.append(b);clusters.extend([rec["match"]]*len(b["sc"]))
    b={k:torch.from_numpy(np.concatenate([a[k] for a in batches])) for k in batches[0]};r=np.array(clusters)
    own=(b["tok"][...,1]>.5)&b["mask"]&(b["tok"][...,13]<.5)&~torch.isin(b["tok"][...,0].long(),torch.tensor(sorted(building_ids)))
    curves=[];counts=[]
    for keep in (0,.5,1):
        altered={k:v.clone() for k,v in b.items()}
        for i in range(len(own)):
            ids=torch.where(own[i])[0];remove=ids[int(round(len(ids)*keep)):];altered["mask"][i,remove]=False
        curves.append(probabilities(model,features(altered).numpy()));counts.append(float((own&altered["mask"]).sum(1).float().mean()))
    out["own_troops_alive"]={"retained_fractions":[0,.5,1],"mean_counts":counts,"mean_pwin":[float(v.mean()) for v in curves],
                            "delta_all_minus_none":bootmean(curves[-1]-curves[0],r),"rows":len(r),"method":"remove observed own non-building, non-spell tokens; fixed other inputs"}
    return out


def behavior(data,scores):
    t=data["tick"];trajectory=data.get("trajectory",data["match"]);x=data["x"]
    if "cost" in data:cost=data["cost"]
    else:
        from pipeline.opp_elixir_count import card_cost
        ck=torch.load(CKPT,map_location="cpu",weights_only=False)
        lookup=np.array([card_cost(k) or 0 for k in ck["card_vocab"]]);cost=lookup[data["card"].astype(int)]
    el=x[:,3]*10;play=data["play"]>.5
    # The exact L73 strata: 30-second time x crown difference x tower advantage bins.
    alive=x[:,19:25]>.5;own=np.where(~alive[:,3],3,(~alive[:,4]).astype(int)+(~alive[:,5]));foe=np.where(~alive[:,0],3,(~alive[:,1]).astype(int)+(~alive[:,2]))
    hp=np.where(alive,np.where(x[:,13:19]>.5,x[:,7:13],1),0)
    tower=(hp[:,:3].sum(1)-hp[:,3:].sum(1))/3
    strata=(t//600)*100+(np.clip(own-foe,-2,2)+2)*10+np.digitize(tower,[-.2,-.05,.05,.2])
    _,g=np.unique(strata,return_inverse=True);o=2*data["y"]-1
    residual=o-np.bincount(g,o)[g]/np.bincount(g)[g]
    delta={k:np.full(len(t),np.nan) for k in scores}
    for mid in np.unique(trajectory):
        ids=np.where(trajectory==mid)[0];target=np.searchsorted(t[ids],t[ids]+200);valid=target<len(ids)
        for k,s in scores.items():delta[k][ids[valid]]=s[ids[target[valid]]]-s[ids[valid]]
    groups={"overspend_late_lt3":play&(t>=2400)&(el-cost<3),"kept_late_ge3":play&(t>=2400)&(el-cost>=3),
            "leak_wait_ge9_5":~play&(el>=9.5),"wait_below9_5":~play&(el<9.5)}
    out={}
    for name,m in groups.items():
        out[name]={"rows":int(m.sum()),"outcome_residual":bootmean(residual[m],data["match"][m]),"delta10s":{}}
        for k,d in delta.items():
            mm=m&np.isfinite(d);out[name]["delta10s"][k]=bootmean(d[mm],data["match"][mm])
    out["contrasts"]={}
    for name,left,right in (("overspend_minus_kept","overspend_late_lt3","kept_late_ge3"),
                            ("leak_minus_other_wait","leak_wait_ge9_5","wait_below9_5")):
        a,b=groups[left],groups[right]
        out["contrasts"][name]={"outcome_residual":bootcontrast(residual,data["match"],a,b),
            "delta10s":{k:bootcontrast(d,data["match"],a,b) for k,d in delta.items()}}
    out["note"]="L73 overspend (<3 after spend) and near-cap WAIT check; observational, not causal; no action becomes a model input. Includes only same-side +10s targets."
    return out


def main():
    model=load(HERE/"phi_live.pt");data=dict(np.load(HERE/"dataset.npz"));manifest=json.loads((HERE/"dataset_manifest.json").read_text())
    val=data["split"]==1;test=data["split"]==2
    if not np.isfinite(data["value"][val|test]).all():raise RuntimeError("missing calibration/test baseline predictions")
    scores,probs,maps=predictions(data,model,fit_mask=val)
    td={k:v[test] for k,v in data.items()};ts={k:v[test] for k,v in scores.items()};tp={k:v[test] for k,v in probs.items()}
    result={"bootstrap_draws":B,"bootstrap_unit":"match (pro replay, both sides together)","baseline_checkpoint_sha256":digest(CKPT),
        "phi_checkpoint_sha256":digest(HERE/"phi_live.pt"),"calibration_maps":maps,
        "live":{"table":table(td,ts,tp),"calibration":calibration(td,tp),"jitter":jitter(td,ts),"jitter_comparisons":jitter_comparisons(td,ts),"behavior":behavior(td,ts)},
        "dependence":dependence(td,model,manifest)}
    prior=float(data["y"][data["split"]==0].mean());result["live"]["prior_brier"]=float(((td["y"]-prior)**2).mean())
    pro=dict(np.load(HERE/"pro_dataset.npz"));ps,pp,_=predictions(pro,model,maps)
    result["pro"]={"table":table(pro,ps,pp),"calibration":calibration(pro,pp),"jitter":jitter(pro,ps),"jitter_comparisons":jitter_comparisons(pro,ps),"behavior":behavior(pro,ps)}
    gain=any(result["live"]["table"][k]["paired"]["live_phi-value_phi"]["auc"][1]>0 for k in ("all","1x"))
    cal=result["live"]["calibration"]["all"]["live_phi"]["ece"]<=.05 and result["live"]["table"]["all"]["brier"]["live_phi"][0]<=result["live"]["prior_brier"]
    bank=result["dependence"]["own_elixir"]["delta_5_to_10"][2]<=.01
    result["verdict"]={"decision":"candidate" if gain and cal and bank else "reject","auc_gate":gain,"calibration_gate":cal,"no_banking_gate":bank}
    result["pro_behavior_flags"]=[]
    for key in ("overspend_late_lt3","leak_wait_ge9_5"):
        b=result["pro"]["behavior"][key];r=b["outcome_residual"];d=b["delta10s"]["live_phi"]
        if r[2] is not None and d[1] is not None and r[2]<0 and d[1]>0: result["pro_behavior_flags"].append(key)
    for key,b in result["pro"]["behavior"]["contrasts"].items():
        r=b["outcome_residual"];d=b["delta10s"]["live_phi"]
        if r[2] is not None and d[1] is not None and r[2]<0 and d[1]>0:result["pro_behavior_flags"].append(key)
    if result["pro_behavior_flags"]:result["verdict"]["decision"]="reject"
    (HERE/"results.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    np.savez_compressed(HERE/"heldout_predictions.npz",**td,**{"score_"+k:v for k,v in ts.items()},**{"p_"+k:v for k,v in tp.items()})
    print("EVALUATION COMPLETE",result["verdict"],flush=True)


if __name__=="__main__":main()
