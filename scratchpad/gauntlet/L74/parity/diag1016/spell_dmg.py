"""Live own-spell damage: histogram of single-frame hp drops on enemy non-tower bodies (and towers) right after own
spell taps. No SIM. usage: spell_dmg.py SPELL [lo hi] (ticks after tap)"""
import sys, glob
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F
from scratchpad.gauntlet.L74.parity.core import load_catalog, ps
spell = sys.argv[1]; lo, hi = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (15, 80)
catalog, _ = load_catalog()
troop, tower, nm, named = Counter(), Counter(), 0, Counter()
for p in sorted(ps.LIVE.glob('live_play_2026101[5-9]_*.jsonl')):
    m, why = F.read_match(str(p))
    if not m: continue
    nm += 1
    fr = m['frames']
    for pl in m['plays']:
        if pl['name'] != spell: continue
        win = [(t, {b['id']: b for b in bs}) for t, bs in fr if pl['tick']+lo-5 <= t <= pl['tick']+hi]
        for (ta, A), (tb, B) in zip(win, win[1:]):
            for k, b in B.items():
                a = A.get(k)
                if a is None or b['side'] == m['side'] or b['hp'] >= a['hp']: continue
                (tower if b["tower"] else troop)[a["hp"]-b["hp"]] += 1
                if a["hp"]-b["hp"] in (390, 351, 323, 355, 429): named[a["hp"]-b["hp"], catalog.get(b["card_id"], {}).get("display_name"), tb-pl["tick"]>=0] += 1
print(nm, 'matches', spell, 'troop drops', troop.most_common(15))
print('tower drops', tower.most_common(10))
print(sorted(named.items(), key=lambda x:-x[1])[:30])
