"""LOOP-INT: cProfile of one producer's Python side (warm run of 2 x M jobs, then a profiled run of 2 x M jobs).
usage: same env as bench.sh; python prof.py MSG.pkl OUT.txt --matches M --threads T [--device cuda:0]"""
import argparse
import cProfile
import io
import pickle
import pstats
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[5]), str(HERE)]

ap = argparse.ArgumentParser()
ap.add_argument("msg")
ap.add_argument("out")
ap.add_argument("--matches", type=int, default=256)
ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--device", default="cuda:0")
a = ap.parse_args()
import os                                                   # noqa: E402
from bench import clone_jobs                                # noqa: E402
from producer import Producer                               # noqa: E402
base, update, sd, jobs = pickle.loads(Path(a.msg).read_bytes())
base = {**base, "actor_device": a.device}
P = Producer(base, a.matches, a.threads, a.device, Path(os.environ["CRFORGE_FACADE_BUILD"]))
P.run(update, sd, clone_jobs(jobs, 2 * a.matches, 0))
pr = cProfile.Profile()
pr.enable()
res, _, st = P.run(update, sd, clone_jobs(jobs, 2 * a.matches, 1))
pr.disable()
s = io.StringIO()
ps = pstats.Stats(pr, stream=s)
ps.sort_stats("cumulative").print_stats(45)
ps.sort_stats("tottime").print_stats(30)
Path(a.out).write_text(f"stats {st}\n" + s.getvalue())
print(st)
