"""SME-FRESH: regen_inputs.one (unedited extract.py) with extract.TABLES swapped (as crforge/fork/r6465/ext635.py does) at
module level, so spawned workers swap too. LIST = a FRESH*.tsv (first column) or an inputs .jsonl ('match').
    icebow/.venv/Scripts/python.exe -I regen_fresh.py TABLES_DIR LIST OUT.jsonl [workers]
Writes every extracted record to OUT; SKIP lines name the rest."""
import json, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import regen_inputs  # noqa: E402
regen_inputs.extract.TABLES = Path(sys.argv[1])


def names(path):
    if path.endswith('.jsonl'):
        return [json.loads(l)['match'] for l in open(path)]
    return [l.split('\t')[0] for l in open(path) if l.strip() and not l.startswith('#')]


if __name__ == '__main__':
    todo = names(sys.argv[2])
    with ProcessPoolExecutor(int(sys.argv[4]) if len(sys.argv) > 4 else 4) as ex, open(sys.argv[3], 'w') as w:
        for name, r, why in ex.map(regen_inputs.one, todo):
            if r is None:
                print('SKIP', name, why); continue
            w.write(json.dumps(r) + '\n')
    print('done', len(todo), 'tables', regen_inputs.extract.TABLES)
