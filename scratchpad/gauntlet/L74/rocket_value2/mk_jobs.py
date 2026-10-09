"""jobs.json for pod_driver.py.
  python mk_jobs.py base OUT.json [--censuses evo,lad,air] [--n 240]       stage A: BASE with every board logged (rv2_boards_s0.py)
  python mk_jobs.py arms OUT.json --seeds-dir DIR --arms a,b,c [--censuses ...]   stage B: each arm on DIR/<arm>_<census>.txt (mk_subsets.py)
  python mk_jobs.py full OUT.json --arms a,b [--censuses ...] [--n 240]    every seed (no subset trick)"""
import argparse, json, os

ap = argparse.ArgumentParser()
ap.add_argument('mode'); ap.add_argument('out')
ap.add_argument('--censuses', default='evo,lad,air'); ap.add_argument('--n', type=int, default=240)
ap.add_argument('--seeds-dir'); ap.add_argument('--arms', default='')
a = ap.parse_args()
cs = a.censuses.split(',')
jobs = []
if a.mode == 'base':
    jobs = [dict(arm='base', census=c, seeds=list(range(a.n)), wrap='scratchpad/gauntlet/L74/rocket_value2/rv2_boards_s0.py') for c in cs]
else:
    for arm in a.arms.split(','):
        for c in cs:
            if a.mode == 'full':
                seeds = list(range(a.n))
            else:
                f = os.path.join(a.seeds_dir, f'{arm}_{c}.txt')
                seeds = [int(x) for x in open(f).read().split(',') if x] if os.path.exists(f) else []
            if seeds:
                jobs.append(dict(arm=arm, census=c, seeds=seeds))
json.dump(jobs, open(a.out, 'w'))
print(len(jobs), 'jobs,', sum(len(j['seeds']) for j in jobs), 'games')
