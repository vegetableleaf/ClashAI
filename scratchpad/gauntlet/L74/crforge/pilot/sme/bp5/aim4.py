"""aim4.py RUNDIR LIB OUTDIR M1,M2,... -- A2c-BP5: AimRun4 traces (probe events + characters with state/z/timers + PA) of some matches"""
import json, os, subprocess, sys
run, lib, wd, only = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(",")
os.makedirs(wd, exist_ok=True)
res = {json.loads(l)["match"]: json.loads(l) for l in open(os.path.join(run, "results.jsonl"))}
jobs = []
for m in sorted(res):
    if not any(m.endswith(o) for o in only): continue
    p = json.load(open(os.path.join(run, m, "plan.json")))
    p["cmds"] = [{k: v for k, v in c.items() if k != "_src"} for c in p["cmds"]]
    json.dump(p, open(os.path.join(wd, m + ".plan.json"), "w"))
    jobs.append("%s %d %s 0" % (os.path.join(wd, m + ".plan.json"), res[m]["live_end"] + 2, os.path.join(wd, m + ".o.jsonl")))
open(os.path.join(wd, "jobs.txt"), "w").write("\n".join(jobs) + "\n")
cp = os.environ.get("CP", "/workspace/pilot/bp4/build_aim4")
r = subprocess.run(["java", "-Xmx32g"] + os.environ.get("JOPT", "").split() + [ "-cp", lib + "/*:" + cp, os.environ.get("CLS", "AimRun4"), "/workspace/crforge_cache/tables/16.402.22", os.path.join(wd, "jobs.txt"), "8"], capture_output=True, text=True)
print(r.stdout.strip()[-400:], r.stderr[-800:])
