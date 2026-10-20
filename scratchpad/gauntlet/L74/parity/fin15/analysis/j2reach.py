"""J2 with H-J2-REACH applied post hoc (no air victim under the Log / Barbarian Barrel), every fight and strict-clean fights.
  python j2reach.py OUT_DIR"""
import json, glob, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.metrics.replay_metrics import boot  # noqa: E402
GROUND_ONLY = {'Log', 'BarbLog'}
for mode in ('every', 'strict'):
    items, logi = [], []
    for f in glob.glob(sys.argv[1] + '/matches/*.json'):
        d = json.load(open(f))
        for fi in d.get('fights', []):
            if 'error' in fi or (mode == 'strict' and not F.is_clean(fi, 'strict')):
                continue
            for r in (fi.get('jm') or {}).get('j2', []):
                if 'err' not in r or (r['flying'] and r['spell'] in GROUND_ONLY):
                    continue
                items.append((d['summary']['match'], r['agree']))
                if r['spell'] == 'Log':
                    logi.append((d['summary']['match'], r['agree']))
    mean = lambda xs: sum(xs) / len(xs)
    v, ci = boot(items, mean); lv, lci = boot(logi, mean)
    print(mode, f'J2 {v:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] n {len(items)} | Log {lv:.3f} [{lci[0]:.3f}, {lci[1]:.3f}] n {len(logi)}')
