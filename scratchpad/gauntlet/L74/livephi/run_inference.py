"""Sequential short inference jobs on at most four of this laptop's 16 logical CPUs."""
import os
os.environ["OPENBLAS_NUM_THREADS"]="1"
import subprocess
import sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]


def run(script):
    for attempt in range(40):
        print("INFERENCE JOB",script,attempt+1,flush=True)
        p=subprocess.run([sys.executable,str(HERE/script),"--seconds","240","--threads","4"],cwd=ROOT)
        if p.returncode:raise SystemExit(p.returncode)
        if script=="baselines.py":
            with np.load(HERE/"dataset.npz") as z:
                if np.isfinite(z["value"][z["split"]>0]).all():return
        elif (HERE/"pro_dataset.npz").exists():return
    raise RuntimeError("bounded job count exceeded; inspect progress")


if __name__=="__main__":
    run("baselines.py");run("pro.py");print("ALL FROZEN INFERENCE COMPLETE",flush=True)
