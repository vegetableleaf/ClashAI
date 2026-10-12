"""Artifact checks, independent numerical checks, and success-only gate markers."""
import hashlib
import json
import sys
import numpy as np
import torch
from build import HERE, ROOT, PS, public_events, rebuild, tensor_batch, features, outcome, CKPT


def dataset():
    m=json.loads((HERE/"dataset_manifest.json").read_text());d=dict(np.load(HERE/"dataset.npz"))
    src=json.loads((HERE/"source_manifest.json").read_text())
    assert len(m["matches"])+len(m["excluded"])==len(src["files"])
    assert len(set(r["file"] for r in m["matches"]))==len(m["matches"])
    assert len(d["x"])==m["rows"] and np.isfinite(d["x"]).all()
    assert d["x"].shape[1]==35 and set(np.unique(d["y"]))=={0,1}
    sets=[{r["file"][10:18] for r in m["matches"] if r["split"]==i} for i in range(3)]
    assert max(sets[0])<min(sets[1]) and max(sets[1])<min(sets[2])
    old=json.loads((HERE.parent/"phase_stats/report.json").read_text());old_by={r["id"]:r for r in old["matches"]}
    matched=0
    for r in m["matches"]:
        q=d["match"]==r["match"]
        assert q.sum()==r["rows"] and sum(r["phase_counts"].values())==r["rows"]
        assert set(d["split"][q])=={r["split"]} and set(d["y"][q])=={r["label"]}
        assert (np.diff(d["tick"][q])>=0).all() and (d["tick"][q]<6000).all()
        assert r["input_sha_verified"]
        if r["file"] in old_by and old_by[r["file"]]["sha256"]==r["sha256"]:
            assert r["label"]==int(old_by[r["file"]]["outcome"]=="wins");matched+=1
    assert matched>0
    ck=torch.load(CKPT,map_location="cpu",weights_only=False);gid={k:i for i,k in enumerate(ck["card_vocab"])}
    for split in range(3):
        r=next(a for a in m["matches"] if a["split"]==split);path=PS.LIVE/r["file"]
        live,reason=PS.read_live(path);assert reason is None and outcome(live)==r["label"]
        rows,meta=rebuild(list(public_events(path)),gid)
        x=features(tensor_batch(rows)).numpy();np.testing.assert_array_equal(x,d["x"][d["match"]==r["match"]])
    print("DATASET VERIFIED",len(m["matches"]),m["rows"],"phase_stats overlap",matched)


def independent_auc(y,p):
    # Rank-sum implementation, separate from evaluate.weighted_auc.
    order=np.argsort(p,kind="stable");ranks=np.empty(len(p),float);i=0
    while i<len(order):
        j=i+1
        while j<len(order) and p[order[j]]==p[order[i]]:j+=1
        ranks[order[i:j]]=(i+1+j)/2;i=j
    n=int(y.sum());return (ranks[y==1].sum()-n*(n+1)/2)/(n*(len(y)-n))


def evaluation():
    from pipeline.live_phi import load
    from evaluate import probabilities
    r=json.loads((HERE/"results.json").read_text());tr=json.loads((HERE/"training.json").read_text())
    assert tr["seconds"]<600 and tr["threads"]==1
    z=dict(np.load(HERE/"heldout_predictions.npz"));model=load(HERE/"phi_live.pt")
    manifest=json.loads((HERE/"dataset_manifest.json").read_text())
    full=dict(np.load(HERE/"dataset.npz"))
    for rec in manifest["matches"]:
        if rec["split"]==0:continue
        pred=np.load(HERE/"shards"/(rec["file"]+".pred.npz"))
        assert int(pred["input_revision"])==3
        np.testing.assert_array_equal(full["value"][full["match"]==rec["match"]],pred["value"])
    from build import baseline
    from pipeline.model_gen import load_model
    old,_=load_model(CKPT,torch.device("cpu"));old.eval().requires_grad_(False)
    for split in (1,2):
        rec=next(a for a in manifest["matches"] if a["split"]==split)
        shard=np.load(HERE/"shards"/(rec["file"]+".npz"))
        b={k[6:]:torch.from_numpy(shard[k][:2]) for k in shard.files if k.startswith("batch_")}
        current,_=baseline(old,b)
        np.testing.assert_allclose(current,full["value"][full["match"]==rec["match"]][:2],atol=2e-6,rtol=0)
        from pipeline import rl_royale as RL
        learner=object.__new__(RL.Learner);learner.dev=torch.device("cpu")
        learner.cfg={"advantage":"gae","shaping":"live_phi","critic_warmup_updates":1}
        learner.phi_net=learner._load_phi_net({"args":{"feature_version":6}})
        actual=learner._phi_values({k:b[k].numpy() for k in ("tok","mask","sc")})
        expected=2*probabilities(model,features(b).numpy())-1
        np.testing.assert_allclose(actual,expected,atol=1e-7,rtol=0)
    np.testing.assert_allclose(probabilities(model,z["x"]),z["p_live_phi"],atol=1e-7)
    for key in ("live_phi","value_phi","tower_crown"):
        auc=independent_auc(z["y"],z["score_"+key]);brier=float(((z["p_"+key]-z["y"])**2).mean())
        assert abs(auc-r["live"]["table"]["all"]["auc"][key][0])<1e-10
        assert abs(brier-r["live"]["table"]["all"]["brier"][key][0])<1e-10
    for source in ("live","pro"):
        assert set(r[source]["table"])=={"all","1x","2x","3x","first30s"}
        for ph,entry in r[source]["table"].items():
            assert entry["rows"]>0 and entry["matches"]>1
            for suffix in ("","_10s"):
                for key in ("live_phi","value_phi","tower_crown"):
                    for metric in ("auc","brier"):
                        a,lo,hi=entry[metric][key+suffix];assert 0<=a<=1 and 0<=lo<=hi<=1
                assert entry["paired"]["live_phi"+suffix+"-value_phi"+suffix]["auc"][1] is not None
        assert r[source]["jitter"] and r[source]["behavior"] and r[source]["calibration"]
    assert set(r["dependence"])=={"own_elixir","own_tower_hp","enemy_tower_hp","own_troops_alive"}
    v=r["verdict"]
    expected=all(v[k] for k in ("auc_gate","calibration_gate","no_banking_gate")) and not r["pro_behavior_flags"]
    assert (v["decision"]=="candidate")==expected
    untouched=json.loads((HERE/"untouched_sources.json").read_text())
    for path,sha in untouched.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    print("EVALUATION VERIFIED",v["decision"])


if __name__=="__main__":
    {"dataset":dataset,"evaluation":evaluation}[sys.argv[1]]()
