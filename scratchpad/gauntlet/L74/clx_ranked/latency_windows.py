"""W13 T6b: decision latency INSIDE the decisive 20 s, not just per match.  For each ranked loss with a decisive own fall:
median decide_ms of the decisions in [fall - 20 s, fall] vs the same match's median; for each ranked win the same around
CLX's first princess take (also a push window, so scene load is comparable).  -> latency_windows.json + prints
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/clx_ranked/latency_windows.py   (idle priority, raw logs, read-only)"""
import ctypes
import json
import re
import statistics as st
from pathlib import Path

try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception:
    pass
HERE = Path(__file__).resolve().parent
LOGS = HERE.parents[1] / 'L68/live_reader'
OFF, WIN = 78, 400
rows = [r for r in json.load(open(HERE / 'rows.json')) if r['sample'] == 'ranked']
out = []
for r in rows:
    if r['win'] == 0 and r.get('decisive'):
        t, kind = r['decisive']['t'], 'loss_decisive'
    elif r['win'] == 1 and r['first'] == 'opp':
        t, kind = int(round(r['seq'][0][0] / 0.05)), 'win_first_take'
    else:
        continue
    ms, win = [], []
    for raw in open(LOGS / r['key'], 'rb'):
        if raw.startswith(b'{"event": "decision"'):
            m = re.search(rb'"tick": (\d+).*?"decide_ms": (\d+)', raw[:300])
            if m:
                tick, d = int(m[1]) - OFF, int(m[2])
                ms.append(d)
                if t - WIN <= tick <= t:
                    win.append(d)
    if ms and win:
        out.append(dict(key=r['key'], kind=kind, match_med=st.median(ms), win_med=st.median(win),
                        win_gt80=round(sum(d > 80 for d in win) / len(win), 3), n_win=len(win)))
json.dump(out, open(HERE / 'latency_windows.json', 'w'), indent=0)
for kind in ('loss_decisive', 'win_first_take'):
    y = [o for o in out if o['kind'] == kind]
    print(f'{kind:15s} n={len(y):3d}  window median-of-medians {st.median(o["win_med"] for o in y)} ms vs match '
          f'{st.median(o["match_med"] for o in y)} ms; window share > 80 ms {st.mean(o["win_gt80"] for o in y):.3f}; '
          f'window slower than its match in {sum(o["win_med"] > o["match_med"] for o in y)} / {len(y)}')
