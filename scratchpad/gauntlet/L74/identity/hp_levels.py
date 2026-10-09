"""Catalog body HP at every playable level for named records (cards / evolutions / hero_forms) and units.
Usage: python hp_levels.py Balloon_hero DarkPrince_hero ...   [unit:<name>@<record>] scales a units entry by a record's
levels."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '../../../..')))
from pipeline import body_identity as BI

cat, _ = BI._catalog()
REC = {r['name']: r for f in ('cards', 'evolutions', 'hero_forms') for r in cat[f]}


def hps(name, rec, scale_rec):
    return {lv: sorted(h * m // 100 for h in BI._hitpoints(name, rec)) for lv, m in BI._levels(scale_rec)}


for a in sys.argv[1:]:
    if a.startswith('unit:'):
        u, r = a[5:].split('@')
        print(a, hps(u, cat['units'][u], REC[r]))
    else:
        print(a, hps(a, REC[a], REC[a]))
