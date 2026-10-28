"""LIVEOPS_1: bounded, single-process, read-only live-log snapshot."""
import ctypes
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
import collections
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import statistics
import time

BEGAN = time.monotonic()
BASE = Path(__file__).resolve().parents[2]
LIVE = BASE / 'L68/live_reader'
SUP = BASE / 'L70/live/supervisor.log'
OUT = Path(__file__).resolve().parent / 'results'
EDT = dt.timezone(dt.timedelta(hours=-4), 'EDT')
SCAN = dt.datetime.now(EDT)
RECORD_SKIPS = collections.Counter()

def record(line):
    try:
        value = json.loads(line)
    except (ValueError, UnicodeError):
        RECORD_SKIPS['invalid JSON'] += 1
        return None
    if not isinstance(value, dict) or not isinstance(value.get('event'), str):
        RECORD_SKIPS['not an event object'] += 1
        return None
    return value

def valid_metrics(event):
    if event['event'] == 'end':
        for key in ('played', 'confirmed', 'fails', 'seconds'):
            v = event.get(key)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
                return False
        towers = event.get('towers')
        if towers is not None and not isinstance(towers, dict):
            return False
        if towers:
            if towers.get('won') is not None and type(towers['won']) is not bool:
                return False
            for key in ('crowns_me', 'crowns_opp', 'tick'):
                v = towers.get(key)
                if v is not None and (type(v) not in (int, float) or not math.isfinite(v)):
                    return False
    if event['event'] == 'p3_capture' and type(event.get('ok')) is not bool:
        return False
    if event['event'] == 'stop' and event.get('why') is not None and not isinstance(event['why'], str):
        return False
    return True
CUTOFF = dt.datetime(2026, 10, 26, 14, 14)
SUP_CUTOFF = dt.datetime(2026, 10, 26, 14)

def deadline():
    if time.monotonic() - BEGAN >= 295:
        raise TimeoutError('Scan stopped at 295 seconds; scope was not widened')

def basename(value):
    return re.split(r'[/\\]', value)[-1]

def table(headers, data):
    def cell(x):
        return str(x if x is not None else '-').replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in data])

def rate(w, l, interval=True):
    n = w + l
    if not n:
        return 'n/a (0 decided)'
    p, z = w / n, 1.959963984540054
    den = 1 + z*z/n
    mid = (p + z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return f'{100*p:.2f}%' + (f' [{100*(mid-half):.2f}, {100*(mid+half):.2f}]' if interval else '')

def counts(rows):
    c = collections.Counter(r['result'] for r in rows)
    assert c['W'] + c['L'] + c['?'] == len(rows)
    return c['W'], c['L'], c['?']

def main():
    names = {'live_play': [], 'ladder_nav': []}
    pat = re.compile(r'^(live_play|ladder_nav)_(\d{8}_\d{6})\.jsonl$')
    # Exactly one directory enumeration; no stat of non-matching entries.
    with os.scandir(LIVE) as entries:
        for entry in entries:
            deadline()
            m = pat.fullmatch(entry.name)
            if m and m[2] >= ('20261026_141400' if m[1] == 'live_play' else '20261026_140000'):
                names[m[1]].append(entry.name)
    for group in names.values():
        group.sort()
    outcomes = {}
    outcome_events = []
    unmappable = 0
    for name in names['ladder_nav']:
        deadline()
        try:
            with (LIVE / name).open(encoding='utf-8', errors='replace') as f:
                for line in f:
                    deadline()
                    event = record(line)
                    if event is None or event['event'] != 'outcome':
                        continue
                    log = event.get('log')
                    if not isinstance(log, str) or not log:
                        unmappable += 1
                        continue
                    key = basename(log)
                    outcome_events.append(key)
                    if event.get('won') is not None and type(event['won']) is not bool:
                        RECORD_SKIPS['invalid outcome won'] += 1
                        continue
                    value = (event.get('won'), event.get('src'))
                    if key in outcomes and outcomes[key] != value:
                        RECORD_SKIPS['conflicting outcome (kept first)'] += 1
                        continue
                    outcomes[key] = value
        except OSError:
            RECORD_SKIPS['unreadable ladder_nav file'] += 1
    skipped = collections.Counter()
    rows, outcome_sources = [], collections.Counter()
    newest = names['live_play'][-1] if names['live_play'] else None
    for name in names['live_play']:
        deadline()
        try:
            with (LIVE / name).open('rb') as f:
                # Unbuffered size snapshot; never scan the middle of a live log.
                size = os.fstat(f.fileno()).st_size
                first = f.readline()
                try:
                    start = json.loads(first)
                except (ValueError, UnicodeError):
                    skipped['invalid first-line JSON'] += 1
                    continue
                if not isinstance(start, dict) or not isinstance(start.get('ckpt'), str) or not start['ckpt']:
                    skipped['missing ckpt'] += 1
                    continue
                if start.get('event') != 'start':
                    skipped['first event is not start'] += 1
                    continue
                if start.get('barrel_decoy') is not None and type(start['barrel_decoy']) is not bool:
                    RECORD_SKIPS['invalid barrel_decoy (field skipped)'] += 1
                    start['barrel_decoy'] = None
                if 'CLXIII_NOLEAK' not in basename(start['ckpt']):
                    skipped['non CLXIII_NOLEAK checkpoint'] += 1
                    continue
                offset = max(0, size - 65536)
                f.seek(offset)
                tail = f.read(min(size, 65536))
        except OSError as exc:
            skipped[f'unreadable: {type(exc).__name__}'] += 1
            continue
        lines = tail.splitlines()
        if offset:
            lines = lines[1:]
        end = p3 = stop = None
        for line in lines:
            event = record(line)
            if event is None:
                continue
            if not valid_metrics(event):
                RECORD_SKIPS['invalid ' + event['event'] + ' record shape'] += 1
                continue
            if event.get('event') == 'end':
                end = event
            elif event.get('event') == 'p3_capture':
                p3 = event
            elif event.get('event') == 'stop':
                stop = event
        towers = (end or {}).get('towers') or {}
        original_src = None
        if end is None and name == newest:
            won, src, why = None, 'none', 'in_progress'
        else:
            why = (stop or {}).get('why')
            if name in outcomes:
                won, original_src = outcomes[name]
                src = 'outcome'
                outcome_sources[str(original_src)] += 1
            elif towers.get('won') is not None:
                won, src = towers['won'], 'end'
            else:
                won, src = None, 'none'
        stamp = dt.datetime.strptime(name[10:25], '%Y%m%d_%H%M%S')
        r = dict(stem=name[:-6], day=stamp.strftime('%Y-%m-%d'), start_hhmm=stamp.strftime('%H:%M'),
                 barrel_decoy=start.get('barrel_decoy'), result='W' if won is True else 'L' if won is False else '?',
                 result_src=src, outcome_src=original_src, crowns_me=towers.get('crowns_me'), crowns_opp=towers.get('crowns_opp'),
                 tick=towers.get('tick'))
        for key in ('played', 'confirmed', 'fails', 'seconds'):
            r[key] = (end or {}).get(key)
        r['unconfirmed'] = r['played'] - r['confirmed'] if end is not None else None
        r['p3_ok'] = (p3 or {}).get('ok')
        r['stop_why'] = why
        rows.append(r)
    matched = {r['stem'] + '.jsonl' for r in rows}
    unmappable += sum(key not in matched for key in outcome_events)
    assert len(rows) == len(matched)
    assert len(rows) + sum(skipped.values()) == len(names['live_play'])
    groups = [ ('2026-10-26 from 14:14', [r for r in rows if r['day'] == '2026-10-26']),
               ('2026-10-27', [r for r in rows if r['day'] == '2026-10-27']),
               ('2026-10-28 before 11:45', [r for r in rows if r['day'] == '2026-10-28' and r['start_hhmm'] < '11:45']),
               ('2026-10-28 from 11:45', [r for r in rows if r['day'] == '2026-10-28' and r['start_hhmm'] >= '11:45'])]
    covered = {'2026-10-26', '2026-10-27', '2026-10-28'}
    for day in sorted({r['day'] for r in rows} - covered):
        groups.append((day, [r for r in rows if r['day'] == day]))
    daily = []
    for label, group in groups:
        w, l, unknown = counts(group)
        sums = [sum(r[k] or 0 for r in group) for k in ('played', 'confirmed', 'unconfirmed', 'fails')]
        seconds = [r['seconds'] for r in group if r['seconds'] is not None]
        daily.append([label, len(group), w, l, unknown, rate(w,l), f'{statistics.mean(seconds):.2f}' if seconds else '-',
                      *sums, f'{100*sums[2]/sums[0]:.2f}' if sums[0] else '-',
                      sum(r['p3_ok'] is False for r in group), sum(r['barrel_decoy'] is True for r in group)])
    blocks = []
    for hour in (0,6,12,18):
        group = [r for r in rows if hour <= int(r['start_hhmm'][:2]) < hour+6]
        w,l,u = counts(group)
        blocks.append([f'{hour:02d}-{hour+6:02d}', len(group), w,l,u,rate(w,l,False)])
    restarts, reasons = [], collections.Counter()
    pending = None
    datepat = r'\w{3} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} EDT \d{4}'
    active = False
    with SUP.open(encoding='utf-8', errors='replace') as f:
        for raw in f:
            deadline()
            raw = raw.rstrip('\r\n')
            d = re.search(datepat, raw)
            try:
                when = dt.datetime.strptime(d[0], '%a %b %d %H:%M:%S EDT %Y') if d else None
            except ValueError:
                RECORD_SKIPS['invalid supervisor date (raw retained)'] += 1
                when = None
            if when is not None:
                active = when >= SUP_CUTOFF
            if not active:
                continue
            start = re.fullmatch(r'\[sup\] start \(restarts used \d+/10\) deck=icebow ('+datepat+r')', raw)
            end = re.fullmatch(r'\[sup\] exit (-?\d+) ('+datepat+r'): (.*)', raw)
            if start:
                if pending is not None:
                    restarts.append([pending, None, None, 'No paired exit'])
                pending = when.isoformat(' ')
            elif end:
                reason = end[3]
                restarts.append([pending, when.isoformat(' '), int(end[1]), reason[:140]])
                pending = None
                nav = re.search(r'\[nav\] run stopped[^:]*:\s*(.*)', reason)
                cls = 'stop-file' if re.search(r'stop[- ]file', reason, re.I) else ('[nav] run stopped: '+nav[1] if nav else 'other')
                reasons[cls] += 1
            else:
                # Preserve all unparsed lines, including done/adopting and ancillary text.
                restarts.append([None, when.isoformat(' ') if when else None, None, raw])
    if pending is not None:
        restarts.append([pending, None, None, 'No paired exit at scan time'])
    hourly_counts = collections.Counter((r['day'], int(r['start_hhmm'][:2])) for r in rows)
    hourly = []
    stop_hour = SCAN.replace(tzinfo=None, minute=0, second=0, microsecond=0)
    for hour in range(24):
        eligible = []
        day = CUTOFF.date()
        while day <= stop_hour.date():
            slot = dt.datetime.combine(day, dt.time(hour))
            if slot + dt.timedelta(hours=1) > CUTOFF and slot <= stop_hour:
                eligible.append(hourly_counts[(day.isoformat(), hour)])
            day += dt.timedelta(days=1)
        hourly.append([f'{hour:02d}', len(eligible), min(eligible) if eligible else '-', statistics.median(eligible) if eligible else '-', max(eligible) if eligible else '-'])
    w,l,u = counts(rows)
    assert [sum(d[i] for d in daily) for i in (1,2,3,4)] == [len(rows),w,l,u]
    text = '\n'.join([f'Inputs: {LIVE} / live_play_*.jsonl (>=20261026_141400, CLXIII_NOLEAK).',
                       f'Inputs: {LIVE} / ladder_nav_*.jsonl (>=20261026_140000); {SUP}.',
                       f'Scan time: {SCAN.isoformat()} (EDT; snapshot; missing end metrics are null; means exclude null; hourly zero bins included, boundary hours partial).']) + '\n\n'
    text += '\n\n'.join([
        table(['Day / deployment window','Matches','W','L','?','Win rate [Wilson 95%]','Mean seconds','Played','Confirmed','Unconfirmed','Fails','Unconfirmed / 100 plays','p3 failures','barrel_decoy true'], daily),
        table(['6-hour block (EDT, all days)','Matches','W','L','?','Win rate'],blocks),
        table(['Supervisor start (EDT)','Exit / event time (EDT)','rc','Reason (paired exits: first 140 chars) / unparsed raw line'],restarts),
        table(['Paired exit reason class','Count'],sorted(reasons.items())),
        table(['Hour (EDT)','Observed day-hours','Min matches/day-hour','Median matches/day-hour','Max matches/day-hour'],hourly),
        table(['Outcome event src (used results)','Count'],sorted(outcome_sources.items())),
        table(['Total / audit','Value'],[['Total matches',len(rows)],['Total W / L / ?',f'{w} / {l} / {u}'],['Overall win rate [Wilson 95%]',rate(w,l)],['Distinct candidate log files',len(names['live_play'])],['Logs skipped',sum(skipped.values())],['outcomes without a mappable log: ' + str(unmappable), ''],['skipped records: ' + str(sum(RECORD_SKIPS.values())) + ' (reasons: ' + ('; '.join(f'{k}: {v}' for k,v in sorted(RECORD_SKIPS.items())) or 'none') + ')', ''],*[[f'Skipped: {k}',v] for k,v in sorted(skipped.items())],['Skip reasons','none' if not skipped else '; '.join(f'{k}: {v}' for k,v in sorted(skipped.items()))],['Daily totals equal row totals','PASS'],['Scan elapsed seconds',f'{time.monotonic()-BEGAN:.3f}']])]) + '\n'
    deadline()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'health_rows.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    (OUT / 'health_table.md').write_text(text, encoding='utf-8')
    print(json.dumps(dict(rows=len(rows), W=w,L=l,unknown=u, skipped=dict(skipped), candidates=len(names['live_play']), unmappable_outcomes=unmappable, skipped_records=dict(RECORD_SKIPS), seconds=round(time.monotonic()-BEGAN,3),daily=daily)))

if __name__ == '__main__':
    main()
