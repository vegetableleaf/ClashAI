"""S3 step 3 projection (b): matches/h per pod = min(CPU bound, GPU bound).

CPU bound = the measured loop rate (cf_loop.py result: Java engine + our main token tensors + legality + the Python
server thread, CPU-only stand-in policy) scaled to the pod's vCPU (linear in threads: (b) past 48 threads, which needs
several JVMs, measured 12 x 4 > 1 x 48 for the engine) and slowed by the CPU work the prototype does not do yet
(--extra-core-s). GPU bound = SPEED.md's rows/s on one RTX 4090 (B >= 1,024, CLXIII inputs; 10 M = the 288 x 8 row)
x GPUs / policy rows per match.

usage: python -I project.py results/loop_n2048_c2_t24.json --extra-core-s 0.05 --rows-per-match 706
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# rows/s on one 4090 (SPEED.md sections a3 and c; (a) measured unless marked (b))
GPU = {
    "1.76 M as today, fp32": 9527,
    "1.76 M lazy refine, fp32": 18794,
    "1.76 M lazy refine + bf16": 44524,
    "10 M as today, fp32": 4378,
    "10 M lazy refine + bf16 (b: CLXIII's x4.67)": round(4378 * 44524 / 9527),
}
PODS = {"54 vCPU + 1x 4090": (54, 1), "128 vCPU + 2x 4090": (128, 2)}


def table(loop: dict, extra: float, rows: float, reserve: int) -> list[str]:
    threads = loop["cohorts"] * loop["threads_per_cohort"]
    core = loop["core_s_per_match"]
    out = ["| pod | model, GPU path | CPU-bound matches/h | GPU-bound matches/h | **matches/h** | 300k | 1 M |",
           "|---|---|---:|---:|---:|---|---|"]
    for pod, (vcpu, gpus) in PODS.items():
        cpu_h = loop["matches_per_h"] * (vcpu - reserve) / threads * core / (core + extra)
        for name, rps in GPU.items():
            gpu_h = rps * gpus / rows * 3600
            best = min(cpu_h, gpu_h)
            out.append(f"| {pod} | {name} | {cpu_h:,.0f} | {gpu_h:,.0f} | **{best:,.0f}** | "
                       f"{'yes' if best >= 3e5 else 'no'} | {'yes' if best >= 1e6 else 'no'} |")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("loop", help="a cf_loop.py result JSON")
    ap.add_argument("--rows-per-match", type=float, default=706.0, help="policy rows per match (both seats)")
    ap.add_argument("--extra-core-s", type=float, default=0.0, help="CPU per match the prototype does not do yet")
    ap.add_argument("--reserve", type=int, default=2, help="vCPU kept for the server thread and the OS")
    a = ap.parse_args()
    loop = json.loads(Path(a.loop).read_text())
    print(f"loop {loop['matches_per_h']:,.0f}/h on {loop['cohorts'] * loop['threads_per_cohort']} threads, "
          f"{loop['core_s_per_match']:.3f} core-s per match + extra {a.extra_core_s:.3f}; {a.rows_per_match:.0f} rows/match")
    print("\n".join(table(loop, a.extra_core_s, a.rows_per_match, a.reserve)))


def _demo():
    loop = dict(cohorts=2, threads_per_cohort=24, core_s_per_match=0.2, matches_per_h=720000)
    t = table(loop, 0.0, 706.0, 6)          # 48 usable vCPU on the 54 pod: the CPU bound is the measured rate
    assert "| 720,000 |" in t[2], t[2]
    assert t[4].endswith("| **227,035** | no | no |"), t[4]  # 1.76 M lazy + bf16, 1 GPU: min(720k, 227k)
    assert t[9].endswith("| yes | no |"), t[9]               # the same on 2 GPUs: 454k
    return t


if __name__ == "__main__":
    main()
