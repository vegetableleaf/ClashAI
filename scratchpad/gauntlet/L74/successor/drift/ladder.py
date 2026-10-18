"""Ladder results in order from overnight.out, each with trophies before / after (back-filled from the nearest
'[ladder] trophies: N total' anchor read on the home screen AFTER that match). Ranked matches ('trophies n/a') carry no delta.

    python ladder.py OUT.json
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
OUT = REPO / 'scratchpad/gauntlet/L70/live/overnight.out'


def ladder():
    ms, last, segs, cur = [], None, [], []
    for line in OUT.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('{') and '"log"' in line:
            try:
                last = Path(json.loads(line)['log']).name
            except (ValueError, KeyError):
                last = None
        elif line.startswith('[ladder] result:'):
            m = re.match(r'\[ladder\] result: (\w+).*?trophies ([+-]?\d+|n/a)', line)
            if m:
                cur.append(dict(log=last, result=m[1], delta=None if m[2] == 'n/a' else int(m[2])))
            last = None
        elif line.startswith('[ladder] trophies:'):
            m = re.match(r'\[ladder\] trophies: (\d+) total', line)
            if m:
                segs.append((cur, int(m[1]))); cur = []
    # back-fill each segment from its closing anchor; check it against the previous anchor
    bad, prev = 0, None
    for seg, anchor in segs:
        t = anchor
        for x in reversed(seg):
            x['after'] = t
            t = t - (x['delta'] or 0)
            x['before'] = t
        if prev is not None and seg and abs(seg[0]['before'] - prev) > 2:
            bad += 1
            for x in seg:
                x['anchor_gap'] = seg[0]['before'] - prev
        prev = anchor
        ms += seg
    t = prev
    for x in cur:                       # after the last anchor: forward
        x['before'] = t; t = t + (x['delta'] or 0); x['after'] = t
    ms += cur
    return ms, bad, len(segs)


if __name__ == '__main__':
    ms, bad, n = ladder()
    Path(sys.argv[1]).write_text(json.dumps(ms))
    print(len(ms), 'results;', n, 'anchors;', bad, 'anchor segments inconsistent with the previous anchor (>2 trophies)')
