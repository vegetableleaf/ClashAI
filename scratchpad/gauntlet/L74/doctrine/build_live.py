"""Cache the live logs L74/doctrine needs into L74/habits/cache (same format as habits/build_cache.py, which only takes
'ICEBOW Mark X:' names; cue_ab2 has no registry Mark yet).  python build_live.py   (run at idle priority)"""
import json
import pickle
import sys
from pathlib import Path

HAB = Path(__file__).resolve().parents[1] / 'habits'
sys.path.insert(0, str(HAB))
import build_cache as B  # noqa: E402

WANT = ('ICEBOW Mark CXXIV:', 'ICEBOW Mark CXXXVIII:', 'ICEBOW Mark CLIII:', 'rlarm_gae_cue_ab2_')
idx = json.load(open(HAB / 'index.json'))
todo = [(n, v) for n, v in sorted(idx.items()) if v['mark'].startswith(WANT) and not (HAB / 'cache' / (Path(n).stem + '.pkl')).exists()]
print(len(todo), 'to build', flush=True)
for n, v in todo:
    try:
        m = B.livelog.read(B.LOGS / n)
    except Exception as e:  # noqa: BLE001
        print('FAIL', n, repr(e)[:200], flush=True)
        continue
    if m is None:
        print('NOFRAMES', n, flush=True)
        continue
    tmp = HAB / 'cache' / (Path(n).stem + '.tmp')
    pickle.dump(B.compact(m, dict(v, log=n)), open(tmp, 'wb'))
    tmp.replace(tmp.with_suffix('.pkl'))
print('done', flush=True)
