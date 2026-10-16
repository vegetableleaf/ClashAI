"""Target semantics: is the live target 'acquired' only inside the sight range? python explore2.py FILES..."""

import json
import sys
from pathlib import Path

from explore import load, conf

ROOT = Path(__file__).resolve().parents[5]
d = json.loads((ROOT / 'research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json').read_text())
SIGHT = {c['name']: c.get('sight_range_milli') for c in d['cards'] + d['towers'] + d['evolutions'] + d['hero_forms']}
SIGHT |= {c['summon_character']: c.get('sight_range_milli') for c in d['cards'] + d['evolutions'] + d['hero_forms'] if c.get('summon_character')}
RNG = {c['name']: c.get('range_milli') for c in d['cards'] + d['towers'] + d['evolutions'] + d['hero_forms']}

rows = load(sys.argv[1:])
b = [r for r in rows if r['k'] == 'b' and r['dist'] <= 250 and r['lv']['cue']]
sel = [r for r in b if r['lv']['tg'] is not None]


def ratio(r):
    s = SIGHT.get(r['name'])
    return None if not s or r['lv']['td'] is None else r['lv']['td'] / s


def bucket(x):
    return 'na' if x is None else '<=0.5' if x <= .5 else '<=1' if x <= 1 else '<=1.25' if x <= 1.25 else '>1.25'


conf('live target set: (sight bucket, sim target set)', [(bucket(ratio(r)), r['sm']['tg'] is not None) for r in sel], 12)
conf('live target set, tower rows: (sight bucket, sim set)', [(bucket(ratio(r)), r['sm']['tg'] is not None) for r in sel if r['tw']], 12)
conf('live target set, troop rows: (sight bucket, sim set, phase)', [(bucket(ratio(r)), r['sm']['tg'] is not None, r['lv']['ph']) for r in sel if not r['tw']], 14)
# sim set with live unset / differing
sel2 = [r for r in b if r['sm']['tg'] is not None]
conf('sim target set: live set?', [(r['lv']['tg'] is not None, r['lv']['tg'] == r['sm']['tg']) for r in sel2], 6)
