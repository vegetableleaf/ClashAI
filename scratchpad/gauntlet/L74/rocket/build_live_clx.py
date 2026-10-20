"""W10: index + cache every graded live CLX match at our tower 4858 (since 10-19 14:02), then invlib.extract them.
Same index format / cache as investment/build_live.py (already-built pickles are reused); W5's index.json and rows.pkl are
NOT touched.  -> rocket/index_clx.json (the scorer re-loads the matches through invlib.live_matches(index=...))
    python -B build_live_clx.py         (single process; laptop-safe)"""
import json
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parent
sys.path[:0] = [str(L74 / 'habits'), str(L74 / 'monitor'), str(L74 / 'investment')]
import build_cache as B  # noqa: E402
import card_use  # noqa: E402
import invlib as I  # noqa: E402

MARK = 'ICEBOW Mark CLX: PARITY'
SINCE = 'live_play_20261019_140200'          # OPP_MODEL.md 0.1: own tower 4424 -> 4858 at 10-19 14:02
BADDELTA = 100                               # OPP_MODEL.md 8.1: |trophy change| > 100 = a fallback across an account switch


def main():
    reg = json.load(open(L74 / 'models/registry.json'))
    sha2mark = {f['sha256']: m['name'] for m in reg['marks'] for f in m.get('files', []) if f.get('sha256')}
    res = card_use.results()
    idx, skipped = {}, {'baddelta': 0}
    for p in sorted((B.LOGS).glob('live_play_2026*.jsonl')):
        if p.name < SINCE + '.jsonl' or p.name not in res:
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
    json.dump(idx, open(HERE / 'index_clx.json', 'w'), indent=0)
    C = L74 / 'habits/cache'
    todo = [n for n in sorted(idx) if not (C / (Path(n).stem + '.pkl')).exists()]
    print(len(idx), 'CLX logs since', SINCE, skipped, '|', len(todo), 'to cache', flush=True)
    for n in todo:
        try:
            m = B.livelog.read(B.LOGS / n)
        except Exception as e:  # noqa: BLE001 -- a broken log is skipped and named
            print('FAIL', n, repr(e)[:200], flush=True)
            continue
        if m is None:
            print('NOFRAMES', n, flush=True)
            continue
        tmp = C / (Path(n).stem + '.tmp')
        pickle.dump(B.compact(m, dict(idx[n], log=n)), open(tmp, 'wb'))
        tmp.replace(tmp.with_suffix('.pkl'))
    tow = {}
    for m in I.live_matches({'CLX'}, index=HERE / 'index_clx.json'):
        t = m['tmax'].get(('own', 'L'))
        tow[t] = tow.get(t, 0) + 1
    print('own princess max hp per loaded match:', tow, flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
