"""Compact per-match cache of the live logs for L74/habits (laptop, run at idle priority: nice -n 19).
  python build_cache.py [--marks CXXIV,CXXXVIII,CLIII]   -> cache/<log stem>.pkl (skips ones already built)
Each pickle: meta, own plays (+ decision why), opponent public plays (+ the counter right before), decisions (hand, elixir,
the model's opponent-elixir input), frames every >= 6 ticks (towers, enemy bodies with stable ids, own X-Bows / Teslas),
counter self-check (rebuilt vs logged), rebases."""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import livelog  # noqa: E402

LOGS = livelog.REPO / 'scratchpad/gauntlet/L68/live_reader'
GAP_SPLIT = 60
STEP = 6


def compact(m, meta):
    seen, ids, frames = {}, {}, []
    last_kept = -10 ** 9
    for tick, ents, towers in m['frames']:
        cur_en, cur_own = [], []
        for addr, who, X, Y, key, form, hp, mx in ents:
            k = (who, addr)
            last = seen.get(k)
            if last is None or tick - last[1] > GAP_SPLIT or last[2] != key:
                ids[k] = ids.get(k, 0) + 1
                bid = f'{"M" if who == "own" else "E"}{len(seen)}_{ids[k]}' if last is None else f'{last[0].split("_")[0]}_{ids[k]}'
                last = (bid, tick, key)
            seen[k] = (last[0], tick, key)
            if who == 'opp':
                cur_en.append((last[0], key, form, hp, mx, round(X, 2), round(Y, 2)))
            elif key in ('x_bow', 'tesla'):
                cur_own.append((last[0], key, hp, round(X, 2), round(Y, 2)))
        if tick - last_kept >= STEP:
            frames.append((tick, dict(towers), cur_en, cur_own))
            last_kept = tick
    # own plays + the decision that produced them (latest play decision of that card <= 80 ticks before the confirmation)
    dec = m['dec']
    own = []
    for q in m['own']:
        d = next((d for d in reversed(dec) if d['play'] and d['name'] == q['name'] and 0 <= q['tick'] - d['tick'] <= 80), None)
        own.append(dict(tick=q['tick'], name=q['name'], x=q['x'], y=q['y'], why=(d or {}).get('why'),
                        dec_tick=(d or {}).get('tick'), opp_est_model=(d or {}).get('opp_est')))
    ests = m['ests']
    diff = [abs(a - b) for _, a, b in ests if b is not None]
    c = m['counter']
    return dict(meta=dict(meta, side=m['side'], flip=m['flip'], end=m['end'], ckpt_sha=(m['start'] or {}).get('ckpt_sha256'),
                          decision_options=(m['start'] or {}).get('decision_options')),
                own=own, opp=m['opp'],
                dec=[(d['tick'], d['hand'], d['own_el'], d['opp_est'], d['play'], d['name'], d['why']) for d in dec],
                frames=frames, est=[(t, round(a, 3)) for t, a, _ in ests[::3]],
                check=dict(n=len(diff), exact=sum(x < 1e-6 for x in diff), max=max(diff) if diff else None,
                           rebases=c.rebases if c else None, rebase_total=round(c.rebase_total, 3) if c else None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--marks', default='CXXIV,CXXXVIII,CLIII')
    a = ap.parse_args()
    want = {f'ICEBOW Mark {r}' for r in a.marks.split(',')}
    idx = json.load(open(HERE / 'index.json'))
    out = HERE / 'cache'
    out.mkdir(exist_ok=True)
    todo = [(n, v) for n, v in sorted(idx.items()) if any(v['mark'].startswith(w + ':') for w in want)
            and not (out / (Path(n).stem + '.pkl')).exists()]
    print(len(todo), 'to build', flush=True)
    t0 = time.time()
    for i, (n, v) in enumerate(todo):
        try:
            m = livelog.read(LOGS / n)
        except Exception as e:                      # noqa: BLE001 -- a broken log is skipped and named
            print('FAIL', n, repr(e)[:200], flush=True)
            continue
        if m is None:
            print('NOFRAMES', n, flush=True)
            continue
        tmp = out / (Path(n).stem + '.tmp')
        pickle.dump(compact(m, dict(v, log=n)), open(tmp, 'wb'))
        tmp.replace(out / (Path(n).stem + '.pkl'))
        if i % 20 == 0:
            print(i, n, round(time.time() - t0), 's', flush=True)
    print('done', round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
