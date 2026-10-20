"""J2 failures on strict-clean fights, by spell and victim.  python j2clean.py OUT_DIR"""
import json, glob, os, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
n, bad, tot = Counter(), Counter(), Counter()
for f in glob.glob(sys.argv[1] + '/matches/*.json'):
    for fi in json.load(open(f)).get('fights', []):
        if 'error' in fi or not F.is_clean(fi, 'strict'):
            continue
        for r in (fi.get('jm') or {}).get('j2', []):
            if 'err' not in r:
                continue
            tot[r['spell']] += 1
            if not r['agree']:
                bad[(r['spell'], r['victim'])] += 1; n[r['spell']] += 1
print('fails by spell (of n):', [(s, n[s], tot[s]) for s in sorted(n, key=lambda s: -n[s])][:10])
print('fails by spell x victim:', bad.most_common(25))
