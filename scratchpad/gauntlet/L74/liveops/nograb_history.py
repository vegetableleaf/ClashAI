import ctypes
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)

import collections
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import time

START = time.monotonic()
BASE = Path(__file__).resolve().parents[2]
READER = BASE / 'L68/live_reader'
OUT = Path(__file__).parent / 'results/nograb_history.md'
HEALTH = OUT.parent / 'health_rows.jsonl'
EDT = dt.timezone(dt.timedelta(hours=-4), 'EDT')
bad = collections.Counter()


def deadline():
    if time.monotonic() - START >= 230:
        raise TimeoutError('Scan stopped at 230-second safety cutoff before the four-minute limit')


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows])


def record(line, kind):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        bad[kind] += 1
        return None
    if not isinstance(value, dict):
        bad[kind + ' values'] += 1
        return None
    return value


def supervisor_date(line):
    patterns = [
        (r'\b\w{3} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} EDT \d{4}', '%a %b %d %H:%M:%S EDT %Y'),
        (r'\b\w{3}, \w{3} \d{1,2}, \d{4}\s+\d{1,2}:\d{2}:\d{2} [AP]M', '%a, %b %d, %Y %I:%M:%S %p'),
        (r'\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}', '%Y-%m-%d %H:%M:%S'),
    ]
    for pattern, fmt in patterns:
        m = re.search(pattern, line)
        if m:
            try:
                value = ' '.join(m[0].split())
                if fmt.startswith('%Y'):
                    value = value.replace('T', ' ')
                return dt.datetime.strptime(value, fmt).replace(tzinfo=EDT)
            except ValueError:
                pass
    return None


def main():
    # Exactly one directory enumeration; no DirEntry stat/is_file calls.
    names = []
    with os.scandir(READER) as entries:
        for entry in entries:
            deadline()
            if re.fullmatch(r'ladder_nav_\d{8}_\d{6}\.jsonl', entry.name):
                names.append(entry.name)
    navs = []
    links = collections.defaultdict(list)
    for name in sorted(names):
        deadline()
        nav = dict(name=name, stamp=name[11:-6], count=0, durations=[], end='no end event',
                   pending='unknown', last=None, grep=False, stop=None)
        active = None
        with (READER / name).open(encoding='utf-8', errors='replace') as source:
            for line in source:
                deadline()
                nav['grep'] |= 'screenshots failing' in line
                r = record(line, 'nav')
                if r is None:
                    continue
                t = r.get('t')
                if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
                    bad['nav timestamp values'] += 1
                    continue
                if nav['last'] is not None and t < nav['last']:
                    bad['nav backwards timestamp values'] += 1
                    continue
                nav['last'] = t
                event = r.get('event')
                if not isinstance(event, str):
                    bad['nav event values'] += 1
                    continue
                if event == 'nav_start':
                    try:
                        pending = r['state'].get('pending_match')
                        if pending is not None:
                            nav['pending'] = pending['log'].replace('\\', '/').rsplit('/', 1)[-1]
                    except (KeyError, TypeError, AttributeError):
                        bad['nav pending match values'] += 1
                if active is not None and (event == 'stop' or ('screen' in r and r['screen'] != 'nograb')):
                    nav['durations'].append(t - active)
                    active = None
                if event == 'screen' and r.get('screen') == 'nograb':
                    nav['count'] += 1
                    if active is None:
                        active = t
                if event == 'stop':
                    if isinstance(r.get('why'), str):
                        nav['stop'] = r['why']
                        nav['end'] = 'stop: ' + r['why']
                    else:
                        bad['nav stop reason values'] += 1
                        nav['end'] = 'stop: unknown'
                elif event == 'handoff':
                    nav['end'] = 'handoff'
        if active is not None:
            nav['durations'].append(nav['last'] - active)
        if any(d < 0 for d in nav['durations']):
            raise ValueError(f'Negative episode duration in {name}')
        navs.append(nav)
        if nav['pending'] != 'unknown':
            links[nav['pending']].append(nav)

    matches = []
    with HEALTH.open(encoding='utf-8') as source:
        for line in source:
            deadline()
            r = record(line, 'health_rows')
            if r is None:
                continue
            try:
                start = dt.datetime.strptime(r['day'] + ' ' + r['start_hhmm'], '%Y-%m-%d %H:%M')
                if not isinstance(r['stem'], str) or 'result' not in r or 'p3_ok' not in r:
                    raise ValueError('invalid health row')
            except (KeyError, TypeError, ValueError):
                bad['health row values'] += 1
                continue
            if start < dt.datetime(2026, 10, 26, 14, 14):
                bad['health rows before cutoff'] += 1
                continue
            linked = links.get(r['stem'] + '.jsonl', [])
            if len(linked) > 1:
                bad['ambiguous next nav mappings'] += 1
                linked = []
            if r['p3_ok'] is not None and type(r['p3_ok']) is not bool:
                bad['health p3_ok values'] += 1
                continue
            matches.append((r, linked[0] if linked else None))

    sup_lines, exits = [], []
    first_unparsed = None
    with (BASE / 'L70/live/supervisor.log').open(encoding='utf-8', errors='replace') as source:
        for number, line in enumerate(source, 1):
            deadline()
            line = line.rstrip('\r\n')
            if 'screenshots failing' in line:
                sup_lines.append((number, line))
            if '[sup] exit' in line:
                date = supervisor_date(line)
                if date is None:
                    bad['supervisor unparsed dates'] += 1
                    if first_unparsed is None:
                        first_unparsed = number
                    continue
                exits.append((date.timestamp(), number, date.isoformat(), line))
    exits.sort()
    selected = [n for n in navs if n['count']]
    durations = [d for n in selected for d in n['durations']]
    hist = [sum(d < 1 for d in durations), sum(1 <= d < 5 for d in durations),
            sum(5 <= d < 15 for d in durations), sum(15 <= d < 60 for d in durations), sum(d >= 60 for d in durations)]
    stopped = sum(n['stop'] == 'screenshots failing for 60 s' for n in navs)
    grep_count = sum(n['grep'] for n in navs)
    failed = [(r, n) for r, n in matches if r['p3_ok'] is False]
    counts = collections.Counter((r['p3_ok'], bool(n['count'])) for r, n in matches if n and r['p3_ok'] is not None)
    long_rows = []
    for n in selected:
        if max(n['durations']) < 10:
            continue
        following = next((e for e in exits if e[0] >= n['last']), None)
        long_rows.append((n['name'], f"{max(n['durations']):.1f}",
                          dt.datetime.fromtimestamp(n['last'], EDT).isoformat(),
                          following[2] if following else 'none recorded',
                          f"{following[0] - n['last']:.2f}" if following else 'N/A',
                          following[1] if following else 'N/A'))
    anchor = next(n for n in navs if n['name'] == 'ladder_nav_20261028_121413.jsonl')
    anchor_ok = (anchor['pending'] == 'live_play_20261028_120902.jsonl' and
                 len(anchor['durations']) == 1 and round(anchor['durations'][0], 1) == 60.3 and
                 any(r['stem'] == 'live_play_20261028_120902' and r['p3_ok'] is False for r, _ in matches))
    sup_anchor = '[sup] exit 1 Mon Oct 19 08:20:49 EDT 2026: [nav] run stopped before match 1: screenshots failing for 60 s'
    sup_ok = any(sup_anchor in line for _, line in sup_lines)
    text = ['# Navigator nograb history',
            f'Nav files: {len(navs)}; nograb files: {len(selected)}; episodes: {len(durations)}. Single-process, below-normal priority scan; no live_play files read.',
            '## 1. Every nav file with nograb',
            'Consecutive nograb screen events form one episode, ending at the next different screen, stop, or last event. Durations are seconds rounded to one decimal.',
            table(['Nav file (stamp)', 'Nograb events', 'Episode durations (s)', 'End', 'Pending match basename'],
                  [(n['name'], n['count'], ', '.join(f'{d:.1f}' for d in n['durations']), n['end'], n['pending']) for n in selected]),
            '## 2. Episode histogram and stop counts',
            'Histogram bins use unrounded durations; lower bounds are inclusive and upper bounds exclusive.',
            table(['Duration (s)', 'Episodes'], zip(['<1', '1-5', '5-15', '15-60', '>=60'], hist)),
            table(['Stop reason', 'Nav files with stop', 'Python substring file count'], [('screenshots failing for 60 s', stopped, grep_count)]),
            "Substring count is the Python equivalent of grep -l 'screenshots failing' ladder_nav_*.jsonl | wc -l, using the same files (including malformed lines).",
            '## 3. Supervisor screenshots-failing lines',
            table(['Line', 'Text (first 200 characters)'], [(num, line[:200]) for num, line in sup_lines]),
            '## 4. p3_capture join from health_rows.jsonl since 2026-10-26 14:14',
            'Next nav is mapped only by exact nav_start state.pending_match.log basename.',
            table(['Match stem', 'Start HH:MM', 'Result', 'Next nav', 'Had nograb', 'Longest episode (s)'],
                  [(r['stem'], r['start_hhmm'], r['result'], n['name'] if n else 'unmapped',
                    ('yes' if n['count'] else 'no') if n else 'N/A',
                    f"{max(n['durations'], default=0):.1f}" if n else 'N/A') for r, n in failed]),
            table(['p3_ok', 'Next nav nograb yes', 'Next nav nograb no'],
                  [(str(status).lower(), counts[status, True], counts[status, False]) for status in [True, False]]),
            f'Health rows: {len(matches)}; false: {len(failed)}; mapped with boolean p3_ok: {sum(counts.values())}; unmapped: {sum(n is None for _, n in matches)}; null p3_ok: {sum(r["p3_ok"] is None for r, _ in matches)} (excluded from the 2x2).',
            '## 5. Supervisor exit timing after episodes >=10 s',
            'Times use local EDT (UTC-04:00). Approximate matching: show the next recorded [sup] exit and its time minus the nav file last-event epoch. The requested window is 0 through 120 s; time differences are reported without judging restart causality.',
            table(['Nav file', 'Longest (s)', 'Last event EDT', 'Next supervisor exit EDT', 'Exit minus last event (s)', 'Supervisor line'], long_rows),
            '## Footnote: skipped bad JSON lines and unparsable values',
            table(['Input', 'Skipped lines / values'], [('nav bad JSON', bad['nav']), ('health_rows bad JSON', bad['health_rows'])] +
                  [(key, value) for key, value in sorted(bad.items()) if key not in ('nav', 'health_rows')]),
            f'supervisor lines with unparsed dates: {bad["supervisor unparsed dates"]}, first at line {first_unparsed if first_unparsed is not None else "N/A"}. Date parsing applies to [sup] exit lines used in table 5; table 3 preserves raw text.']
    deadline()
    elapsed = time.monotonic() - START
    summary = (f'Nav files={len(navs)}; nograb files={len(selected)}; episodes={len(durations)}; '
               f'stop count={stopped}; substring count={grep_count}; health rows={len(matches)}; '
               f'p3 false={len(failed)}; long-episode navs={len(long_rows)}; '
               f'nav anchor={anchor_ok}; supervisor anchor (2026-10-19 08:20:49)={sup_ok}; elapsed seconds={elapsed:.3f}')
    text += ['## Acceptance', summary]
    OUT.write_text('\n\n'.join(text) + '\n', encoding='utf-8')
    print(summary, flush=True)
    if not anchor_ok or not sup_ok:
        raise ValueError('Required anchor verification failed')
    deadline()
    print(f'Total elapsed including report write: {time.monotonic() - START:.3f}s', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        message = f'STATUS: BLOCKED\n\n{type(exc).__name__}: {exc}\n\nElapsed seconds: {time.monotonic() - START:.3f}\n'
        OUT.write_text('# Navigator nograb history\n\n' + message, encoding='utf-8')
        print(message, flush=True)
        raise SystemExit(1)
