"""Item-4 ratios per pair from pairs.sh's outputs: crforge / fin16 actor core-s, wall, rows over u0001-u0003.
    python pair_ratio.py DIR TAG NPAIRS"""
import re
import statistics as st
import sys
from pathlib import Path

D, TAG, N = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])


def run(name):
    upd = (D / f"upd_{name}.txt").read_text()
    cpu = sum(float(x) for x in re.findall(r"actors (\d+) core-s", upd))
    learn = sum(float(x) for x in re.findall(r"learner (\d+) core-s", upd))
    wall = sum(float(x) for x in re.findall(r"wall (\d+) s", upd))
    rows = [int(x) for x in re.findall(r"rows (\d+) wall", (D / f"{name}.log").read_text())]   # u0000..u0003
    return dict(cpu=cpu + learn, wall=wall, rows=sum(rows[1:4]), n=len(re.findall(r"^u\d+", upd, re.M)))


out = {}
for p in range(1, N + 1):
    try:
        cf, rs = run(f"{TAG}_p{p}_cf"), run(f"{TAG}_p{p}_rs")
    except (FileNotFoundError, ValueError) as e:
        print(f"pair {p}: missing ({e})")
        continue
    r = dict(cpu=cf["cpu"] / rs["cpu"], wall=cf["wall"] / rs["wall"],
             cpu_per_row=(cf["cpu"] / cf["rows"]) / (rs["cpu"] / rs["rows"]))
    out[p] = r
    print(f"pair {p}: cf {cf} | rs {rs} | crforge/fin16 cpu {r['cpu']:.3f} wall {r['wall']:.3f} cpu/row {r['cpu_per_row']:.3f}")
for k in ("cpu", "wall", "cpu_per_row"):
    v = [r[k] for r in out.values()]
    if v:
        print(f"{k}: mean {st.mean(v):.3f} min {min(v):.3f} max {max(v):.3f} (n={len(v)})")
