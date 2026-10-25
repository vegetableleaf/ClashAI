"""Crowns taken but no tower_fall in the SIM memory: when did the match end relative to the last memory sample, and what
HP did the memory last read for the towers? Usage: falls_check.py DUMP_DIR [...]"""
import pickle
import sys
from collections import Counter
from pathlib import Path

out = Counter()
for d in sys.argv[1:]:
    for f in sorted(Path(d).glob('*.pkl')):
        r = pickle.load(open(f, 'rb'))
        row, tf = r['row'], [e for e in r['tower_ev'] if e['type'] == 'tower_fall']
        for who, crowns, mine in (('for', row['crowns_for'], False), ('against', row['crowns_against'], True)):
            falls = sum(e['mine'] == mine for e in tf)
            if crowns > falls:
                last = r['t'][-1]
                idx = (0, 1, 2) if mine else (3, 4, 5)
                hp = [round(r['hp'][-1][i], 3) for i in idx]
                gap = row['end_tick'] - last
                out[(who, 'end - last sample <= 40' if gap <= 40 else 'gap > 40')] += 1
                if gap > 40 and out[('shown', who)] < 4:
                    out[('shown', who)] += 1
                    print(f.name, who, 'crowns', crowns, 'falls', falls, 'end', row['end_tick'], 'last sample', last, 'hp', hp)
print(dict(out))
