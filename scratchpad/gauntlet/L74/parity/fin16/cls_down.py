"""cls_down.py MOVED.json DIR -- cls.py args: w19/cls.py (live vs SIM first-divergence classifier, K = 0) restricted to the
moved fights with direction DIR (down / up) of down_dossier.py's MOVED.json. Run with CLS_ALL=1 so a fight that PASSES on that
SIM (the base arm, for a down fight) is classified too. Engine / exports by env as for fights.py (one chunk per call)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'w19'))
assert os.environ.get('CLS_ALL') == '1', 'set CLS_ALL=1'
import cls  # noqa: E402

moved, d = sys.argv[1], sys.argv[2]
want = {(x['key'].split('@')[0], int(x['key'].split('@')[1].split(' ')[0])) for x in json.load(open(moved)) if x['dir'] == d}
_failing = cls.failing


def failing(base, stamped=True, mode='strict'):
    out = {}
    for m, v in _failing(base, stamped, mode).items():
        keep = [f for f in v if (m[10:], f[0]) in want]
        if keep:
            out[m] = keep
    return out


cls.failing = failing
sys.argv = [sys.argv[0]] + sys.argv[3:]
cls.main()
