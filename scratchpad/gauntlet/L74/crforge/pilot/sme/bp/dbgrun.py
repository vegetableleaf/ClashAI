import json, sys, subprocess
sys.path.insert(0, "/workspace/pilot/sme")
from sme_live import runnable
plan = runnable(json.load(open(sys.argv[1])))
json.dump(plan, open("work/dbg/p.json", "w"))
open("work/dbg/jobs.txt", "w").write("work/dbg/p.json %s work/dbg/o.jsonl %s\n" % (sys.argv[2], sys.argv[3]))
r = subprocess.run(["java", "-Ddbgxy=" + sys.argv[4], "-cp", "/workspace/pilot/bp2/lib_dbg/*:/workspace/pilot/sme/build_008aa626", "SmeRun",
                    "/workspace/crforge_cache/tables/16.402.22", "work/dbg/jobs.txt", "1"], capture_output=True, text=True)
print("\n".join(l for l in r.stderr.splitlines() if "DBG" in l))
