"""Re-extract the matches of an inputs file with the current extract.py (round 3.3): same matches, same battle-log entry.
    icebow/.venv/Scripts/python.exe -I regen_inputs.py OLD_INPUTS.jsonl OUT.jsonl [workers]"""
import json, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'extract'))
import extract  # noqa: E402

_CTX = None


def one(name):
    global _CTX
    if _CTX is None:
        names, (cat, by_name) = extract.id_names(extract.TABLES), extract.load_catalog()
        _CTX = dict(names=names, cat=cat, by_name=by_name, shims=extract.table_shims(extract.TABLES),
                    tt=extract.tower_table(), uhp=extract.unit_hp_table(), bl=extract.battles())
    p = extract.LIVE / (name + '.jsonl')
    _, b = extract.battle_for(p, _CTX['bl'])
    c = {k: v for k, v in _CTX.items() if k != 'bl'}
    r, why = extract.match(p, [b] if b else None, **c)
    return name, r, why


if __name__ == '__main__':
    old = [json.loads(l)['match'] for l in open(sys.argv[1])]
    with ProcessPoolExecutor(int(sys.argv[3]) if len(sys.argv) > 3 else 4) as ex, open(sys.argv[2], 'w') as w:
        for name, r, why in ex.map(one, old):
            if r is None:
                print('SKIP', name, why)
                continue
            w.write(json.dumps(r) + '\n')
    print('done', len(old))
