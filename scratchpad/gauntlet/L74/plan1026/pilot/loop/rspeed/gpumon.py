"""every 5 s: GPU util / memory + per-process GPU memory (nvidia-smi) -> one JSON line."""
import json, subprocess, sys, time
q = lambda a: subprocess.run(["nvidia-smi", a, "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip().splitlines()
with open(sys.argv[1], "a") as f:
    while True:
        g = [[x.strip() for x in l.split(",")] for l in q("--query-gpu=index,utilization.gpu,memory.used")]
        p = [[x.strip() for x in l.split(",")] for l in q("--query-compute-apps=pid,used_memory")]
        f.write(json.dumps({"t": time.time(), "gpu": g, "procs": p}) + "\n"); f.flush()
        time.sleep(5)
