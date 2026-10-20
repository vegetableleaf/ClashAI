"""Dump the device spell tables as (global id, name, key columns) rows -- exploration helper for W9.

  python dump_tables.py TABLES_DIR > out.txt
Global id = class prefix x 1e6 + row index over NAMED rows (a row with an empty Name continues the previous entry).
"""
import csv
import sys
from pathlib import Path

PREFIX = {'spells_characters': 26, 'spells_buildings': 27, 'spells_other': 28, 'spells_evolved': 13,
          'spells_hero_form': 203}
COLS = ('Rarity', 'ManaCost', 'NotInUse', 'NotVisible', 'SummonCharacter', 'EvolvedSpells', 'HeroAbility', 'TID')


def rows(path):
    r = list(csv.reader(path.open(encoding='utf-8')))
    head = r[0]
    out = []
    for row in r[2:]:
        d = dict(zip(head, row))
        if d.get('Name'):
            out.append(d)
        elif out:
            for k, v in d.items():
                if v:
                    out[-1].setdefault('_cont_' + k, []).append(v)
    return out


if __name__ == '__main__':
    root = Path(sys.argv[1])
    for t, p in PREFIX.items():
        for i, d in enumerate(rows(root / f'{t}.csv')):
            print(p * 1000000 + i, t, d['Name'], *(f'{c}={d.get(c, "")}' for c in COLS),
                  'cont=' + ','.join(f'{k[6:]}:{"|".join(v)}' for k, v in d.items() if k.startswith('_cont_') and k[6:] in COLS))
