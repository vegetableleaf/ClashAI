"""Raw reader card-id census over the live logs (W9, 10-20): which card ids the LIVE game actually reported, how often.

Reads every scratchpad/gauntlet/L68/live_reader/live_play_*.jsonl (read only) with two byte regexes, no JSON parse:
  frame ents rows  [side, x, y, card_id, hp, max_hp, kind, "0xADDR"]   (logs with frame events, 10-16+)
  dict bodies      "card_id": N ... "address": "0x.."                    (decision.public.raw_bodies, 10-05+)
A body = distinct (log, address, card_id). Per card id: logs it appears in, bodies, max_hp values seen (frames only).
Single process, below-normal CPU priority (the laptop runs live play).

  python raw_id_census.py OUT.json [--since YYYYMMDD]
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL
except Exception:
    pass

LOGS = Path(__file__).resolve().parents[2] / 'L68/live_reader'
ROW = re.compile(rb'\[([01]), -?\d+, -?\d+, (-?\d+), -?\d+, (-?\d+), (\d+), "(0x[0-9a-f]+)"\]')
DICT = re.compile(rb'"card_id": (-?\d+), "hp": -?\d+, "max_hp": (-?\d+), "kind": (\d+), "address": "(0x[0-9a-f]+)"')


def scan(path):
    data = path.read_bytes()
    bodies, mhp = {}, defaultdict(set)
    for side, cid, mx, kind, addr in ROW.findall(data):
        bodies.setdefault((addr, int(cid)), int(kind))
        mhp[int(cid)].add(int(mx))
    for cid, mx, kind, addr in DICT.findall(data):
        bodies.setdefault((addr, int(cid)), int(kind))
        mhp[int(cid)].add(int(mx))
    return bodies, mhp


def main(argv):
    out = Path(argv[0])
    since = argv[argv.index('--since') + 1] if '--since' in argv else '0'
    files = sorted(p for p in LOGS.glob('live_play_*.jsonl') if p.stem[10:18] >= since)
    logs, bodies, first, last, kinds = Counter(), Counter(), {}, {}, defaultdict(Counter)
    mhp = defaultdict(set)
    for i, p in enumerate(files):
        b, m = scan(p)
        seen = set()
        for (addr, cid), kind in b.items():
            bodies[cid] += 1
            seen.add(cid)
            kinds[cid][kind] += 1
        for cid in seen:
            logs[cid] += 1
            first.setdefault(cid, p.stem)
            last[cid] = p.stem
        for cid, v in m.items():
            mhp[cid] |= v
        if i % 250 == 0:
            print(f'[{i}/{len(files)}] {p.name} ids {len(logs)}', flush=True)
    res = dict(files=len(files), since=since,
               ids={str(c): dict(logs=logs[c], bodies=bodies[c], first=first[c], last=last[c],
                                 kinds=dict(kinds[c]), max_hp=sorted(mhp[c])[:40]) for c in sorted(logs)})
    out.write_text(json.dumps(res, indent=1))
    print(f'{len(files)} logs, {len(logs)} distinct card ids -> {out}')


if __name__ == '__main__':
    main(sys.argv[1:])
