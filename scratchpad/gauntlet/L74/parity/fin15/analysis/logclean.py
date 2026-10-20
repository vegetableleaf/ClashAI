"""Log J2 on strict-clean fights: per victim, agreement split ground / air, and the signed SIM - live end offset along the Log's
roll direction (positive = the SIM pushed further).  python logclean.py OUT_DIR"""
import json, glob, os, sys, statistics as S
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
g = defaultdict(list)
for f in glob.glob(sys.argv[1] + '/matches/*.json'):
    d = json.load(open(f))
    for fi in d.get('fights', []):
        jm = fi.get('jm') or {}
        if 'error' in fi or not F.is_clean(fi, 'strict') or jm.get('spell') != 'Log':
            continue
        fwd = 1 if fi['anchor']['side'] == 0 else -1
        for r in jm.get('j2', []):
            if 'err' in r:
                g[(r['victim'], r['flying'])].append((r['agree'], (r['sim_end'][1] - r['live_end'][1]) * fwd))
air = [a for (v, fl), xs in g.items() if fl for a, _ in xs]
grd = [a for (v, fl), xs in g.items() if not fl for a, _ in xs]
print('Log clean: ground', round(sum(grd) / len(grd), 3), len(grd), '| air', round(sum(air) / len(air), 3), len(air))
for (v, fl), xs in sorted(g.items(), key=lambda kv: -sum(1 - a for a, _ in kv[1]))[:12]:
    fails = [o for a, o in xs if not a]
    print(f"{v:28s} air {int(fl)} n {len(xs):4d} agree {sum(a for a, _ in xs)/len(xs):.2f}  fails' SIM-live along the roll: median {S.median(fails) if fails else 0:.0f}  "
          f"sim further {sum(o > 0 for o in fails)} / less {sum(o < 0 for o in fails)}")
