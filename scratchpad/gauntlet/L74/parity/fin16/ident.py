"""ident.py BASE_DIR ARM_DIR [FROM=20261019_0600]: identity of each match result (DIR/matches/*.json) between two J1 runs, split
by capture stamp (before / from FROM). Raw bytes can never match across two runtime dirs: summary.stamp.path and every
fight's stamp.path name the SIM directory, and summary.seconds is wall time. So each pair is compared twice: raw bytes, and
canonical JSON with only those three fields removed (NORMALISED). A normalised difference counts the fights that differ."""
import json
import sys
from pathlib import Path


def norm(m):
    m['summary'].pop('seconds', None); m['summary'].pop('stamp', None)
    for f in m.get('fights', []):
        if isinstance(f.get('stamp'), dict):
            f['stamp'].pop('path', None)
    return m


base, arm = Path(sys.argv[1]) / 'matches', Path(sys.argv[2]) / 'matches'
cut = sys.argv[3] if len(sys.argv) > 3 else '20261019_0600'
names = sorted({p.name for p in base.glob('*.json')} | {p.name for p in arm.glob('*.json')})
t = {e: dict(raw_same=0, norm_same=0, norm_diff=0, missing=0, fights=0, fights_diff=0) for e in ('pre', 'post')}
pre_diffs = []
for n in names:
    e = 'post' if n[10:23] >= cut else 'pre'
    a, b = base / n, arm / n
    if not (a.exists() and b.exists()):
        t[e]['missing'] += 1; pre_diffs.append((e, n, 'missing'))
        continue
    ra, rb = a.read_bytes(), b.read_bytes()
    t[e]['raw_same'] += ra == rb
    ja, jb = norm(json.loads(ra)), norm(json.loads(rb))
    fa, fb = ja.get('fights', []), jb.get('fights', [])
    nf = sum(x != y for x, y in zip(fa, fb)) + abs(len(fa) - len(fb))
    t[e]['fights'] += max(len(fa), len(fb)); t[e]['fights_diff'] += nf
    if json.dumps(ja, sort_keys=True) == json.dumps(jb, sort_keys=True):
        t[e]['norm_same'] += 1
    else:
        t[e]['norm_diff'] += 1
        if e == 'pre':
            pre_diffs.append((e, n, f'fights differing {nf}/{max(len(fa), len(fb))}'))
for e in ('pre', 'post'):
    print(f'{e} {cut}:', t[e])
for e, n, why in pre_diffs:
    print('PRE-PATCH DIFF', n, why)
