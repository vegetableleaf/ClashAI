import ctypes
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)

import collections
import datetime
import json
from pathlib import Path
import re
import time

# Gates: every line exactly once; PRE/GAP excluded; all requested tables; <300 s.
START = time.monotonic()
BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / 'results/transitions.md'
FIELDS = ['unknown', 'tap_through input', 'loading', 'nograb', 'total lines']

def table(headers, rows):
    def cell(x):
        return str(x).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows])

def main():
    path = BASE / 'L70/live/overnight.out'
    # Freeze the byte extent of the appended file; replacement decoding is explicit.
    with path.open('rb') as f:
        size = f.seek(0, 2)
        f.seek(0)
        lines = f.read(size).decode('utf-8', errors='replace').splitlines()
    segments = []
    current = None
    seen = False
    malformed = 0
    for num, line in enumerate(lines, 1):
        if time.monotonic() - START >= 295:
            raise TimeoutError('Stopped before five-minute limit')
        start = line.startswith('[ladder] launch screen:')
        if line.startswith('{"played":'):
            try:
                r = json.loads(line)
                start = isinstance(r, dict) and 'played' in r
            except ValueError:
                malformed += 1
        if start:
            if current:
                segments.append(current)
            current = dict(start=num, end=num, kind='TRANSITION', counts=[0]*5, stops=[], handoff=False)
            seen = True
        elif current is None:
            current = dict(start=num, end=num, kind='GAP' if seen else 'PRE', counts=[0]*5, stops=[], handoff=False)
        current['end'] = num
        c = current['counts']
        c[0] += line.startswith('[ladder] unknown:')
        c[1] += line.startswith('[ladder] tap_through: input ')
        c[2] += line.startswith('[ladder] loading:')
        c[3] += line.startswith('[ladder] nograb:')
        c[4] += 1
        if line.startswith('[ladder] HANDOFF:'):
            current['handoff'] = True
        if line.startswith('[ladder] STOP:'):
            current['stops'].append(line[len('[ladder] STOP:'):].strip())
        if line.startswith('[nav] run stopped') and current['kind'] == 'TRANSITION':
            segments.append(current)
            current = None
    if current:
        segments.append(current)
    for s in segments:
        s['class'] = 'STOP' if s['stops'] else ('HANDOFF' if s['handoff'] else 'OTHER')
    trans = [s for s in segments if s['kind'] == 'TRANSITION']
    hands = [s for s in trans if s['class'] == 'HANDOFF']
    stops = [s for s in trans if s['class'] == 'STOP']
    mixed = sum(bool(s['stops']) and s['handoff'] for s in trans)
    coverage = sum(s['counts'][4] for s in segments)
    contiguous = all(s['start'] == (segments[i-1]['end']+1 if i else 1) for i,s in enumerate(segments)) and (not segments or segments[-1]['end'] == len(lines))
    def quantile(values, q):
        if not values:
            return 'N/A'
        a = sorted(values)
        x = (len(a)-1)*q
        lo = int(x)
        return f'{a[lo] + (a[min(lo+1,len(a)-1)]-a[lo])*(x-lo):.2f}'
    stats = []
    for i,name in enumerate(FIELDS):
        a = [s['counts'][i] for s in hands]
        stats.append((name, min(a) if a else 'N/A', quantile(a,.5), quantile(a,.9), quantile(a,.99), max(a) if a else 'N/A'))
    # Prefix counts give exact grep line counts and STOP overlap in constant time/window.
    flags = [0]*(len(lines)+1)
    hp = [0]*(len(lines)+1)
    sp = [0]*(len(lines)+1)
    for ident,s in enumerate(segments,1):
        for n in range(s['start'],s['end']+1):
            if s['kind'] == 'TRANSITION' and s['class'] == 'HANDOFF':
                hp[n] = ident
            if s['kind'] == 'TRANSITION' and s['class'] == 'STOP':
                sp[n] = 1
    for n,line in enumerate(lines,1):
        flags[n] = flags[n-1] + bool(re.search(r'\] unknown:|tap_through:', line))
        sp[n] += sp[n-1]
    benign = overlap = other = fired = 0
    for end in range(12,len(lines)+1):
        first = end-11
        if flags[end]-flags[first-1] >= 6:
            fired += 1
            b = hp[first] != 0 and hp[first] == hp[end]
            s = sp[end]-sp[first-1] > 0
            benign += b
            overlap += s
            other += not b and not s
    elapsed = time.monotonic()-START
    summary = f'Coverage: sum of lines over all segments = {coverage} == total lines = {len(lines)}: {coverage == len(lines)}; contiguous/nonoverlapping: {contiguous}. Transitions={len(trans)}; HANDOFF={len(hands)}; STOP={len(stops)}; OTHER={len(trans)-len(hands)-len(stops)}; elapsed={elapsed:.3f}s.'
    text = ['# Overnight transition counts', f'Snapshot UTC: {datetime.datetime.now(datetime.timezone.utc).isoformat()}; input bytes: {size}.',
            'Line numbers are 1-based and inclusive. Start lines belong to the new transition; run-stopped lines belong to the ending transition. EOF closes the final segment. Percentiles use linear interpolation at (n-1)*p. STOP takes precedence if both STOP and HANDOFF occur.',
            summary, f'Transitions containing both HANDOFF and STOP: {mixed}. Malformed played JSON lines (retained as ordinary lines): {malformed}.',
            '## PRE and GAP segments', table(['Kind','First line','Last line','Lines'], [(s['kind'],s['start'],s['end'],s['counts'][4]) for s in segments if s['kind'] != 'TRANSITION']),
            '## HANDOFF distributions', table(['Count','Min','Median','p90','p99','Max'],stats),
            '## Every STOP transition', table(['First line','Last line']+FIELDS+['STOP why'], [(s['start'],s['end'],*s['counts'],'; '.join(s['stops'])) for s in stops]),
            '## Top 25 HANDOFF transitions by tap_through input count', 'Ties ordered by first line.', table(['First line','Last line']+FIELDS, [(s['start'],s['end'],*s['counts']) for s in sorted(hands,key=lambda s:(-s['counts'][1],s['start']))[:25]]),
            '## Old watcher: overlapping windows of 12 consecutive lines',
            table(['Window category','Rule-firing windows'], [('Entirely inside one HANDOFF transition (benign)',benign),('Overlap any STOP transition',overlap),('Other (including boundary/PRE/GAP windows)',other),('All firing windows',fired),('All candidate windows',max(0,len(lines)-11))]),
            '## Stricter transition rules', table(['Tap_through input threshold','HANDOFF transitions','STOP transitions'], [(v,sum(s['counts'][1]>=v for s in hands),sum(s['counts'][1]>=v for s in stops)) for v in [3,5,8]])]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text('\n\n'.join(text)+'\n',encoding='utf-8')
    print(summary)
    print(f'Old watcher: benign={benign}; STOP-overlap={overlap}; other={other}; total={fired}')
    assert coverage == len(lines) and contiguous and elapsed < 300

if __name__ == '__main__':
    main()
