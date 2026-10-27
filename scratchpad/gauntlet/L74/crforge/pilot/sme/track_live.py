"""Track one object's hp (or position) over ticks, recorded vs sim: python3 track_live.py RUNDIR MATCH SIDE X Y LO HI
Prints, per tick, the hp of the object at exactly (side, X, Y) in the sim and in the recorded frame (if any)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run, m = sys.argv[1], sys.argv[2]
side, x, y, lo, hi = map(int, sys.argv[3:8])
plan = json.load(open(os.path.join(run, m, 'plan.json')))
frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames', m + '.jsonl'))
o = run_batch([(runnable(plan), hi + 2, lo)], os.path.join(run, m, 'track'))[0]
for s in o:
    t = s['t']
    sh = [(e[2], e[6]) for e in s['E'] if e[3] == side and e[4] == x and e[5] == y]
    rh = [(e[3], e[4]) for e in frames[t]['E'] if e[0] == side and e[1] == x and e[2] == y] if t in frames else '-'
    fx = [e[2] for e in s['E'] if e[1] in 'AP' and abs(e[4] - x) < 4000 and abs(e[5] - y) < 4000]
    print(t, 'sim', sh, 'rec', rh, 'sim A/P near', fx[:4])
