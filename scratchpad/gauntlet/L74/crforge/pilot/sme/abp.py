# ability / play run-tick sweep near an onset: python3 abp.py RUN M:t0 ...   (run env)
import json,sys,os
sys.path.insert(0,"/workspace/pilot/sme")
from sme import run_batch
from sme_live import load_frames, runnable, analyse
ME={json.loads(l)["match"]:json.loads(l)["my_side"] for l in open("/workspace/pilot/inputs_v2/inputs_rngfree.jsonl")}
run=sys.argv[1]
for arg in sys.argv[2:]:
    m,t0=arg.split(":"); m="live_play_"+m; t0=int(t0)
    plan=json.load(open(os.path.join(run,m,"plan.json")))
    fr=load_frames("/workspace/pilot/sme_live/frames2/"+m+".jsonl")
    ks=[i for i,c in enumerate(plan["cmds"]) if c["kind"]!="skip" and t0-130<=c["run"]<=t0]
    jobs=[];meta=[]
    for k in ks:
        for dR in (-3,-2,-1,1,2,3):
            p=json.loads(json.dumps(plan)); p["cmds"][k]["run"]+=dR; p["cmds"][k]["given"]+=dR
            jobs.append((runnable(p), t0+400, 0)); meta.append((k,dR))
    outs=run_batch(jobs,"/tmp/a2c4/abp")
    best={}
    for (k,dR),o in zip(meta,outs):
        f=analyse(o,fr,ME[m],0,t0+400)["first"] if o else -1
        if f is None or (f>t0): best.setdefault(k,[]).append((dR,f))
    for k,v in best.items():
        c=plan["cmds"][k]; card=c.get("card") or ("abil:"+plan["cmds"][int(c["unit"][3:].split("_")[0])]["card"])
        print(m[10:],t0,"cmd",k,card,"side",c["side"],"R",c["run"],"win",c["_src"]["lo"],c["_src"]["hi"],c["_src"]["source"],"better:",v,flush=True)
    if not best: print(m[10:],t0,"no single-command shift in -3..+3 helps",flush=True)
