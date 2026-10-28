"""Live matches started at/after a stamp: start-event flags (barrel_decoy, reader), event counts, errors, final towers.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/gb_decoy/newlogs.py 20261028_1144
(copy of .foreman/scratch/gb_decoy/newlogs.py, generalised to any day; reads whole logs: run it at below-normal priority)"""
import ctypes
import json
import os
import re
import sys

L = r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader'
after = sys.argv[1]                                    # e.g. 20261028_1144
try:
    k = ctypes.windll.kernel32
    k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
except Exception:                                      # noqa: BLE001
    pass
for name in sorted(e.name for e in os.scandir(L) if re.fullmatch(r'live_play_\d{8}_\d{6}\.jsonl', e.name)):
    if name[10:10 + len(after)] < after:
        continue
    lines = open(os.path.join(L, name), 'rb').readlines()
    st = json.loads(lines[0]) if lines else {}
    ev = {}
    for l in lines:
        e = l[:40].split(b'"event": "')[1].split(b'"')[0].decode() if b'"event": "' in l[:40] else '?'
        ev[e] = ev.get(e, 0) + 1
    end = [json.loads(l) for l in lines if l.startswith(b'{"event": "end"')]
    print(name, 'barrel_decoy', st.get('barrel_decoy'), 'from_file', (st.get('live_options') or {}).get('from_file', {}).get('barrel_decoy'),
          'reader', (st.get('cue_inputs') or {}).get('reader'), 'decisions', ev.get('decision'), 'plays', ev.get('play'),
          'errors', {k: v for k, v in ev.items() if 'err' in k or 'exc' in k or k == 'stop'}, 'end', end[0]['towers'] if end else None)
