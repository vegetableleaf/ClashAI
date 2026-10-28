"""SME-FRESH diagnostics (no fitting): run a results plan.json once and print, per frame in [LO, HI], the comparator diff
(canon_live vs sim_canon, as sme_live.analyse) plus the sim rows whose name contains NAME.
    (runF.sh env) python3 diagF.py PLAN.json FRAMES.jsonl SIDE LO HI [NAME] [EVERY]"""
import json, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', '/workspace/pilot/fresh/sme10f'))
import sme_live  # noqa: E402
from sme import run_batch, diff  # noqa: E402
plan, fp, side, lo, hi = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
name = sys.argv[6] if len(sys.argv) > 6 else None
every = int(sys.argv[7]) if len(sys.argv) > 7 else 1
frames = sme_live.load_frames(fp)
o = run_batch([(sme_live.runnable(json.load(open(plan))), max(frames) + 3, 0)], '/tmp/diagF_%d' % os.getpid())[0]
by = {x['t']: x for x in o}
an = sme_live.analyse(o, frames, side)
for t in sorted(frames):
    if not (lo <= t <= hi) or t not in by or (t - lo) % every and an['cls'].get(t) == 'exact':
        continue
    r = sme_live.canon_live(frames[t], side)
    s = sme_live.sim_canon(by[t], side)
    if sme_live.HP_PH:
        r = sme_live.fill_placeholder(r, s)
    d = diff(r, s)
    rows = [u for u in by[t].get('U', []) + by[t].get('T', []) if name and name in json.dumps(u)] if name else []
    print(t, an['cls'].get(t), json.dumps(d)[:600], ('SIM ' + json.dumps(rows)[:400]) if rows else '')
