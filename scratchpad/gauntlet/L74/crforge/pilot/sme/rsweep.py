import json,sys,os
sys.path.insert(0,"/workspace/pilot/sme")
from sme import run_batch
from sme_live import load_frames, runnable, analyse
ME={json.loads(l)["match"]:json.loads(l)["my_side"] for l in open("/workspace/pilot/inputs_v2/inputs_rngfree.jsonl")}
for arg in sys.argv[1:]:
    m,k=arg.split(":"); m="live_play_"+m; k=int(k)
    plan=json.load(open("/workspace/pilot/sme_live/run17/%s/plan.json"%m)); fr=load_frames("/workspace/pilot/sme_live/frames2/"+m+".jsonl")
    jobs=[]
    for dR in range(-14,1):
        p=json.loads(json.dumps(plan)); p["cmds"][k]["run"]+=dR; p["cmds"][k]["given"]+=dR; jobs.append((runnable(p),max(fr)+3,0))
    outs=run_batch(jobs,"/tmp/a2c4/rs")
    print(m[10:],"R",plan["cmds"][k]["run"],[(dR,(lambda a:(a["first"],a["counts"].get("exact")))(analyse(o,fr,ME[m]))) for dR,o in zip(range(-14,1),outs) if o],flush=True)
