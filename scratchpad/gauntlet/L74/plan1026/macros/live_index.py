"""P6-MACRO: index + cache the graded live CLXIII matches (rocket/build_live_clx.py's rules, CLXIII instead of CLX), EXCLUDING the
sealed opponent block of plan1026/opp/live_split.json (logs at or after its `sealed_from` are never read).
Pickles already in L74/habits/cache are reused read-only; missing ones are written to macros/live_cache/ (gitignored size).
    python -B live_index.py          (single process, laptop-safe)  -> macros/index_clxiii.json"""
import json
import pickle
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[1]
sys.path[:0] = [str(L74 / 'habits'), str(L74 / 'monitor')]
import build_cache as B  # noqa: E402
import card_use  # noqa: E402

MARK = 'ICEBOW Mark CLXIII: NOLEAK'
SPLIT = json.load(open(HERE.parent / 'opp/live_split.json'))
SEALED = 'live_play_' + SPLIT['sealed_from']          # never read a log at / after this stem
BADDELTA = 100
CACHES = (L74 / 'habits/cache', HERE / 'live_cache')


def results():
    """card_use.results() pairing (a summary JSON line names its log; the next '[ladder] result:' line is its outcome) without
    its trophy-digit requirement: on Ranked every result line says 'trophies n/a', so card_use.results() returns none of them.
    tro = None here (the BADDELTA account-switch filter cannot apply on Ranked)."""
    out, last = {}, None
    for line in card_use.OUT.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('{') and '"log"' in line:
            try:
                last = Path(json.loads(line)['log']).name
            except (ValueError, KeyError):
                pass
        elif line.startswith('[ladder] result:') and last:
            m = re.match(r'\[ladder\] result: (\w+)', line)
            if m:
                out[last] = (m[1], None)
            last = None
    return out


def cached(stem):
    return next((c / (stem + '.pkl') for c in CACHES if (c / (stem + '.pkl')).exists()), None)


def main():
    reg = json.load(open(L74 / 'models/registry.json'))
    sha2mark = {f['sha256']: m['name'] for m in reg['marks'] for f in m.get('files', []) if f.get('sha256')}
    res = results()
    idx, skipped = {}, {'baddelta': 0, 'sealed': 0}
    for p in sorted(B.LOGS.glob('live_play_2026*.jsonl')):
        if p.stem >= SEALED:
            skipped['sealed'] += 1
            continue
        if p.name not in res:
            continue
        with open(p, 'rb') as f:
            try:
                j = json.loads(f.readline())
            except ValueError:
                continue
        if j.get('event') != 'start' or j.get('dry_run') or sha2mark.get(j.get('ckpt_sha256')) != MARK:
            continue
        if res[p.name][1] is not None and abs(res[p.name][1]) > BADDELTA:
            skipped['baddelta'] += 1
            continue
        idx[p.name] = dict(mark=MARK, result=res[p.name][0], tro=res[p.name][1])
    (HERE / 'live_cache').mkdir(exist_ok=True)
    todo = [n for n in sorted(idx) if cached(Path(n).stem) is None]
    print(len(idx), 'CLXIII logs before', SEALED, skipped, '|', len(todo), 'to cache', flush=True)
    for n in todo:
        try:
            m = B.livelog.read(B.LOGS / n)
        except Exception as e:  # noqa: BLE001 -- a broken log is skipped and named
            print('FAIL', n, repr(e)[:200], flush=True)
            continue
        if m is None:
            print('NOFRAMES', n, flush=True)
            continue
        tmp = HERE / 'live_cache' / (Path(n).stem + '.tmp')
        pickle.dump(B.compact(m, dict(idx[n], log=n)), open(tmp, 'wb'))
        tmp.replace(tmp.with_suffix('.pkl'))
    json.dump(idx, open(HERE / 'index_clxiii.json', 'w'), indent=0)
    print('done', flush=True)


if __name__ == '__main__':
    main()
