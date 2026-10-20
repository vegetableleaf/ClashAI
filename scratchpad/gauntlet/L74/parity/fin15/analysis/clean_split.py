"""J2 / J3 / J6 on the fights J1 counts as clean (fights.is_clean, strict / core / all) vs every fight.
  python clean_split.py OUT_DIR"""
import json, glob, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

acc = {}
for f in glob.glob(sys.argv[1] + '/matches/*.json'):
    d = json.load(open(f))
    for fi in d.get('fights', []):
        jm = fi.get('jm') or {}
        if 'error' in fi:
            continue
        modes = ['every'] + [m for m in ('strict', 'core', 'all') if F.is_clean(fi, m)]
        for m in modes:
            a = acc.setdefault(m, {'j6': [0, 0], 'j6p': [0, 0], 'j2': [0, 0], 'j2t': [0, 0], 'j3': [0, 0]})
            for r in jm.get('j6', []):
                a['j6'][0] += r['agree']; a['j6'][1] += 1
                if r.get('both_alive') and not r.get('edge'):
                    a['j6p'][0] += r['agree']; a['j6p'][1] += 1
            for r in jm.get('j2', []):
                if 'err' in r:
                    a['j2'][0] += r['agree']; a['j2'][1] += 1
                    if r.get('spell') == 'Tornado':
                        a['j2t'][0] += r['agree']; a['j2t'][1] += 1
            for r in jm.get('j3', []):
                a['j3'][0] += r['agree']; a['j3'][1] += 1
for m, a in acc.items():
    print(m, {k: (round(v[0] / v[1], 3) if v[1] else None, v[1]) for k, v in a.items()})
