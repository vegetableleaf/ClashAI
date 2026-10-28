import ctypes
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)

import time
START = time.monotonic()
import os
import re
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

ROOT = Path('C:/Users/benpe/ClashBot')
SOURCE = ROOT / 'scratchpad/gauntlet/L68/live_reader'
REPORT = ROOT / 'scratchpad/gauntlet/L74/liveops/short0_3/short_losses.md'
CUTOFF = '20261020_000000'
SPLIT = '20261026_141400'
counts = Counter()

def deadline():
    if time.monotonic() - START >= 240:
        raise TimeoutError('Scan exceeded 240 seconds; stopped.')

def table(headers, rows):
    def line(row):
        return '| ' + ' | '.join(str(v).replace('|', '\\|') for v in row) + ' |'
    return '\n'.join([line(headers), line(['---'] * len(headers))] + [line(r) for r in rows])

def quantile(values, p):
    if not values:
        return 'n/a'
    pos = (len(values) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    return f'{values[lo] + (values[hi] - values[lo]) * (pos - lo):.2f}'

def main():
    scan_time = datetime.now().isoformat(timespec='seconds')
    names = []
    with os.scandir(SOURCE) as entries:
        for entry in entries:
            deadline()
            match = re.fullmatch(r'ladder_nav_(\d{8}_\d{6})\.jsonl', entry.name)
            if match and match[1] >= CUTOFF:
                names.append(entry.name)
    outcomes = {}
    for name in sorted(names):
        deadline()
        with (SOURCE / name).open('r', encoding='utf-8') as stream:
            for number, line in enumerate(stream, 1):
                deadline()
                counts['lines'] += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    counts['bad_json'] += 1
                    continue
                if not isinstance(event, dict):
                    raise ValueError(f'Unexpected non-object JSON: {name}:{number}')
                if event.get('event') != 'outcome':
                    continue
                counts['outcome_events'] += 1
                null_log = event.get('log') is None
                null_towers = event.get('towers') is None
                counts['null_log'] += null_log
                counts['null_towers'] += null_towers
                if null_log or null_towers:
                    counts['excluded_null'] += 1
                    continue
                log = event['log']
                if not isinstance(log, str) or not re.fullmatch(r'live_play_\d{8}_\d{6}\.jsonl', log):
                    raise ValueError(f'Unexpected log format: {name}:{number}')
                counts['eligible_events'] += 1
                outcomes[log] = event
    records = []
    for log, event in sorted(outcomes.items()):
        deadline()
        stamp = log[len('live_play_'):-len('.jsonl')]
        if stamp < CUTOFF:
            counts['before_start'] += 1
            continue
        dt = datetime.strptime(stamp, '%Y%m%d_%H%M%S')
        towers = event['towers']
        if not isinstance(towers, dict):
            raise ValueError(f'Unexpected towers: {log}')
        for key in ('crowns_me', 'crowns_opp'):
            if type(towers.get(key)) is not int:
                raise ValueError(f'Missing/noninteger {key}: {log}')
        tick = towers.get('tick')
        if tick is not None and (type(tick) not in (int, float) or not math.isfinite(tick)):
            raise ValueError(f'Unexpected tick: {log}')
        records.append(dict(log=log, stamp=stamp, day=dt.date().isoformat(), start=dt.isoformat(sep=' '),
                            tick=tick, me=towers['crowns_me'], opp=towers['crowns_opp'], won=event['won']))
    flagged = [r for r in records if r['opp'] == 3 and r['tick'] is not None and r['tick'] < 2400]
    if len(flagged) > 60:
        raise ValueError(f'{len(flagged)} flagged logs exceeds the approximately 60-file allowance; stopped before live-log reads.')
    for r in flagged:
        deadline()
        try:
            with (SOURCE / r['log']).open('r', encoding='utf-8') as stream:
                first = stream.readline()
            counts['live_first_lines'] += 1
            start = json.loads(first)
        except (OSError, json.JSONDecodeError, UnicodeError):
            r['ckpt'] = 'unreadable'
            continue
        if not isinstance(start, dict) or start.get('event') != 'start' or not isinstance(start.get('ckpt'), str):
            raise ValueError(f'Unexpected first-line start/ckpt schema: {r["log"]}')
        r['ckpt'] = start['ckpt'].replace('\\', '/').rsplit('/', 1)[-1]
    first_day = datetime(2026, 10, 20).date()
    last_day = max([datetime.now().date()] + [datetime.strptime(r['day'], '%Y-%m-%d').date() for r in records])
    days = [(first_day + timedelta(days=i)).isoformat() for i in range((last_day - first_day).days + 1)]
    def stats(label, rr):
        opp = [r for r in rr if r['opp'] == 3]
        def below(seq, limit):
            return sum(r['tick'] is not None and r['tick'] < limit for r in seq)
        return [label, len(rr), sum(not r['won'] for r in rr), len(opp), below(opp,1800), below(opp,1500), below(opp,1350), below(rr,1800), below(rr,1500), sum(r['tick'] is None for r in rr)]
    headers = ['Day / period', 'Matches with towers', 'Losses', 'Opp 3', 'Opp 3 <1800', 'Opp 3 <1500', 'Opp 3 <1350', 'Any <1800', 'Any <1500', 'Missing tick']
    rows = [stats(day, [r for r in records if r['day'] == day]) for day in days]
    day_sum = sum(row[1] for row in rows)
    assert day_sum == len(records)
    text = ['# LIVEOPS_4: short opponent-three-crown outcomes', f'Scan started (local laptop time): {scan_time}.',
            '20 ticks = 1 second; 1800 = 90 s, 1500 = 75 s, 1350 = 67.5 s, 2400 = 120 s. Thresholds are strict.',
            'Days and split use match start timestamps from log stems, without timezone conversion. Losses use outcome `won == false`; opponent-three-crown counts use only `crowns_opp == 3`.',
            'Deduplication keeps the last eligible outcome in ascending navigator filename order and line order. Null-log/null-towers outcomes are excluded before deduplication. This is a one-pass live-file snapshot; later transitions are not included.',
            '## Table 1: daily counts', table(headers, rows + [stats('TOTAL', records)])]
    for label, predicate in [('Before 2026-10-26 14:14', lambda r: r['stamp'] < SPLIT), ('At/after 2026-10-26 14:14 (CLXIII back on)', lambda r: r['stamp'] >= SPLIT)]:
        subset = [r for r in records if predicate(r)]
        text += [f'### {label}', table(headers, [stats(day, [r for r in subset if r['day'] == day]) for day in days] + [stats('TOTAL', subset)])]
    text += ['## Table 2: every opponent-three-crown match with tick <2400', table(['Log stem','Start time','Tick','Crowns me','Checkpoint basename','won'], [[r['log'][:-6],r['start'],r['tick'],r['me'],r['ckpt'],str(r['won']).lower()] for r in flagged])]
    text += ['## Anchor presence']
    for stem, expected in [('live_play_20261028_154218',1328),('live_play_20261028_154335',1311)]:
        rr = next((r for r in records if r['log'] == stem + '.jsonl'), None)
        if rr is None:
            text += [f'- `{stem}`: absent from eligible deduplicated outcomes; expected tick {expected}; no eligible outcome observed yet.']
        else:
            text += [f'- `{stem}`: PRESENT; tick {rr["tick"]} (expected {expected}); crowns_opp={rr["opp"]}; table 2: {"yes" if rr in flagged else "no"}.']
    dist = []
    for label, subset in [('Opponent 3 crowns',[r for r in records if r['opp']==3]),('All matches',records)]:
        ticks = sorted(r['tick'] for r in subset if r['tick'] is not None)
        dist.append([label,len(ticks),len(subset)-len(ticks)] + [quantile(ticks,p) for p in [0,.05,.25,.5,.75,1]])
    text += ['## Table 3: tick distribution', 'Percentiles use linear interpolation at index (n-1)*p; missing ticks are excluded.', table(['Population','Known ticks','Missing ticks','Min','p5','p25','Median','p75','Max'],dist)]
    rates = []
    for day in days + ['TOTAL']:
        rr = records if day == 'TOTAL' else [r for r in records if r['day']==day]
        n = sum(r['opp']==3 for r in rr)
        rates.append([day,f'{n}/{len(rr)}',f'{100*n/len(rr):.2f}%' if rr else 'n/a'])
    text += ['## Table 4: opponent-three-crown rate',table(['Day','Opp 3 / matches with towers','Rate'],rates), '## Acceptance and scan footnotes',
             f'- Per-day match sum = {day_sum}; deduplicated outcome events used = {len(records)}; equality verified.',
             f'- Navigator files selected: {len(names)}; lines read: {counts["lines"]}; outcome events: {counts["outcome_events"]}; eligible events before deduplication: {counts["eligible_events"]}; duplicate eligible events removed: {counts["eligible_events"]-len(outcomes)}; deduplicated matches before start date excluded: {counts["before_start"]}.',
             f'- Bad JSON lines skipped: {counts["bad_json"]}; null-log outcomes: {counts["null_log"]}; null-towers outcomes: {counts["null_towers"]}; union excluded: {counts["excluded_null"]} (categories can overlap).',
             f'- Missing tick: {sum(r["tick"] is None for r in records)}; included in match/rate denominators, excluded from threshold counts and distributions.',
             f'- Flagged matches: {len(flagged)}; live-log first lines read: {counts["live_first_lines"]}; unreadable checkpoints: {sum(r["ckpt"]=="unreadable" for r in flagged)}.',
             f'- Opponent-three-crown outcomes with won=true: {sum(r["opp"]==3 and r["won"] for r in records)}.']
    deadline()
    elapsed = time.monotonic()-START
    text += [f'- Elapsed seconds: {elapsed:.3f}; under 240 seconds: yes.', '- STATUS: DONE']
    REPORT.write_text('\n\n'.join(text)+'\n',encoding='utf-8')
    print(json.dumps({'status':'DONE','elapsed_seconds':round(time.monotonic()-START,3),'matches':len(records),'flagged':len(flagged),'opp3':sum(r['opp']==3 for r in records),'report':str(REPORT)}))

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        elapsed = time.monotonic()-START
        REPORT.write_text(f'# LIVEOPS_4\n\nSTATUS: BLOCKED\n\n{type(exc).__name__}: {exc}\n\nElapsed seconds: {elapsed:.3f}\n',encoding='utf-8')
        print(f'STATUS: BLOCKED: {exc}; elapsed={elapsed:.3f}s')
        raise SystemExit(1)
