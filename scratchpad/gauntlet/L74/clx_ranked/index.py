import ctypes
import csv
import json
import pickle
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception:
    pass

HERE = Path(__file__).resolve().parent
L74 = HERE.parent
REPO = L74.parents[2]
sys.path[:0] = [str(L74 / 'habits'), str(L74 / 'monitor'), str(L74 / 'investment')]
import build_cache as B

MARK = 'ICEBOW Mark CLX: PARITY'
SINCE = 'live_play_20261019_140200.jsonl'
RESULT = re.compile(r'\[ladder\] result: (\w+)\s+\(session W(\d+) L(\d+) D(\d+)[^)]*\)\s+trophies (n/a|[+-]?\d+)\s+src=(\w+)')
DECIDE = re.compile(rb'"decide_ms": (\d+)')
FIELDS = 'log ts result session_w session_l tro tro_na src mark sha my_side own_pmax opp_pmax n_dec dec_ms_median dec_ms_p90 dec_ms_mean frac_dec_gt80 n_cpu_starved cpu_starved_first_tick tap_ms_median tap_end_ms_median confirm_latency_median n_play n_confirmed end_seconds end_crowns_me end_crowns_opp end_won'.split()


def median(values):
    return statistics.median(values) if values else None


def main():
    t0 = time.monotonic()
    with open(L74 / 'models/registry.json', encoding='utf-8') as f:
        reg = json.load(f)
    sha2mark = {f['sha256']: m['name'] for m in reg['marks'] for f in m.get('files', []) if f.get('sha256')}
    summaries = {}
    pending = None
    with open(REPO / 'scratchpad/gauntlet/L70/live/overnight.out', encoding='utf-8') as f:
        for line in f:
            if line.startswith('{') and '"log"' in line:
                summary = json.loads(line)
                name = Path(summary['log']).name
                pending = name if name >= SINCE else None
                if name >= SINCE and name not in summaries:
                    summaries[name] = None
            elif pending is not None and line.startswith('[ladder] result:'):
                match = RESULT.search(line)
                if match is None:
                    raise ValueError('Unrecognized result line for ' + pending)
                if pending in summaries and summaries[pending] is None:
                    summaries[pending] = match.groups()
                pending = None

    rows = {}
    skipped = dict(no_start=0, dry=0, other_mark=0)
    for name in sorted(summaries):
        p = B.LOGS / name
        if not p.exists():
            continue
        with open(p, 'rb') as f:
            first = f.readline()
            try:
                start = json.loads(first)
            except ValueError:
                skipped['no_start'] += 1
                continue
            if not first.startswith(b'{"event": "start"') or start.get('event') != 'start':
                skipped['no_start'] += 1
                continue
            if start.get('dry_run') is not False:
                skipped['dry'] += 1
                continue
            sha = start.get('ckpt_sha256')
            if sha2mark.get(sha) != MARK:
                skipped['other_mark'] += 1
                continue
            row = dict.fromkeys(FIELDS)
            row.update(log=name, ts=name[10:25], result='NONE', tro_na=False,
                       mark=MARK, sha=sha[:12], n_dec=0, n_cpu_starved=0,
                       n_play=0, n_confirmed=0)
            result = summaries[name]
            if result is not None:
                outcome, w, l, d, tro, src = result
                row.update(result=outcome, session_w=int(w), session_l=int(l),
                           tro=None if tro == 'n/a' else int(tro), tro_na=tro == 'n/a', src=src)
            decisions, taps, tap_ends, latencies = [], [], [], []
            got_frame = False
            for line in f:
                if line.startswith(b'{"event": "decision"'):
                    match = DECIDE.search(line[:300])
                    if match is None:
                        raise ValueError('Missing decide_ms in ' + name)
                    decisions.append(int(match[1]))
                elif not got_frame and line.startswith(b'{"event": "frame"'):
                    frame = json.loads(line)
                    got_frame = True
                    side = frame['my_side']
                    row['my_side'] = side
                    towers = [e for e in frame['ents'] if e[3] == -1 and abs(e[1] - 9000) > 2000]
                    row['own_pmax'] = max((e[5] for e in towers if e[0] == side), default=None)
                    row['opp_pmax'] = max((e[5] for e in towers if e[0] != side), default=None)
                elif line.startswith(b'{"event": "cpu_starved"'):
                    event = json.loads(line)
                    if row['n_cpu_starved'] == 0:
                        row['cpu_starved_first_tick'] = event['tick']
                    row['n_cpu_starved'] += 1
                elif line.startswith(b'{"event": "tap_timing"'):
                    event = json.loads(line)
                    if event.get('tap_ms') is not None:
                        taps.append(event['tap_ms'])
                    if event.get('tap_end_ms') is not None:
                        tap_ends.append(event['tap_end_ms'])
                elif line.startswith(b'{"event": "confirmed"'):
                    event = json.loads(line)
                    row['n_confirmed'] += 1
                    if event.get('latency_s') is not None:
                        latencies.append(event['latency_s'])
                elif line.startswith(b'{"event": "play"'):
                    row['n_play'] += 1
                elif line.startswith(b'{"event": "end"'):
                    event = json.loads(line)
                    towers = event.get('towers') or {}
                    row.update(end_seconds=event.get('seconds'), end_crowns_me=towers.get('crowns_me'),
                               end_crowns_opp=towers.get('crowns_opp'), end_won=towers.get('won'))
            decisions.sort()
            n = len(decisions)
            row.update(n_dec=n, dec_ms_median=median(decisions),
                       dec_ms_p90=decisions[int(0.9 * (n - 1))] if n else None,
                       dec_ms_mean=round(statistics.mean(decisions), 1) if n else None,
                       frac_dec_gt80=round(sum(v > 80 for v in decisions) / n, 3) if n else None,
                       tap_ms_median=median(taps), tap_end_ms_median=median(tap_ends),
                       confirm_latency_median=median(latencies))
            rows[name] = row
        if len(rows) % 25 == 0:
            print('INDEX', len(rows), name, round(time.monotonic() - t0, 1), 's', flush=True)

    with open(HERE / 'index.json', 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=0)
    with open(HERE / 'timing.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows.values())
    print('total rows:', len(rows), flush=True)
    print('skip counts:', skipped, flush=True)
    print('counts by result:', dict(sorted(Counter(r['result'] for r in rows.values()).items())), flush=True)
    print('hour tro_na own_pmax count', flush=True)
    counts = Counter((r['ts'][:11], r['tro_na'], r['own_pmax']) for r in rows.values())
    for key in sorted(counts, key=lambda k: (k[0], k[1], -1 if k[2] is None else k[2])):
        print(*key, counts[key], flush=True)
    check = rows['live_play_20261021_070110.jsonl']
    assert check['result'] == 'WIN'
    assert check['tro_na'] is True
    assert check['end_crowns_me'] == 1
    assert check['n_cpu_starved'] == 6
    assert all(r['ts'] >= '20261019_140200' for r in rows.values())
    print('self-check asserts: PASS', flush=True)

    idx = {n: {k: r[k] for k in ('mark', 'result', 'tro')} for n, r in rows.items()}
    C = L74 / 'habits/cache'
    todo = [n for n in sorted(idx) if not (C / (Path(n).stem + '.pkl')).exists()]
    built = failed = 0
    print('cache existing:', len(idx) - len(todo), 'to build:', len(todo), flush=True)
    for i, n in enumerate(todo, 1):
        try:
            try:
                m = B.livelog.read(B.LOGS / n)
            except Exception as e:
                print('FAIL', n, repr(e)[:200], flush=True)
                failed += 1
                continue
            if m is None:
                print('NOFRAMES', n, flush=True)
                failed += 1
                continue
            tmp = C / (Path(n).stem + '.tmp')
            pickle.dump(B.compact(m, dict(idx[n], log=n)), open(tmp, 'wb'))
            tmp.replace(tmp.with_suffix('.pkl'))
            built += 1
        finally:
            if i % 25 == 0:
                print('CACHE', i, n, round(time.monotonic() - t0, 1), 's', flush=True)
    missing = [n for n in rows if not (C / (Path(n).stem + '.pkl')).exists()]
    print('cache pickles built:', built, 'failed:', failed, 'missing:', len(missing), flush=True)
    print('total runtime:', round(time.monotonic() - t0, 1), 's', flush=True)


if __name__ == '__main__':
    main()
