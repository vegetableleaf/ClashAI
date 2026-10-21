"""W13 check: live elixir regeneration rate by game phase (own elixir from the frame events, clock = tick - 78), to test
whether overtime runs at 2x or 3x and whether the SIM's OT law could differ.  Rate = rise of own elixir between consecutive
frames that are both below 9.5 and with no own elixir drop in between, per second of game clock.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/clx_ranked/elixir_rate.py [N logs]"""
import ctypes, json, re, sys
from collections import defaultdict
from pathlib import Path
try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception:
    pass
HERE = Path(__file__).resolve().parent
LOGS = HERE.parents[1] / 'L68/live_reader'
idx = json.load(open(HERE / 'index.json'))
ot = [n for n, v in sorted(idx.items()) if v['own_pmax'] == 4858 and (v['end_seconds'] or 0) > 200 and v['tro_na']]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 25
acc = defaultdict(lambda: [0.0, 0.0])
for n in ot[-N:]:
    prev = None
    for raw in open(LOGS / n, 'rb'):
        if not raw.startswith(b'{"event": "frame"'):
            continue
        m = re.search(rb'"tick": (\d+), "my_side": \d, "elixir": ([\d.]+)', raw[:200])
        if not m:
            continue
        t, e = int(m[1]) - 78, float(m[2])
        if prev and 0 < t - prev[0] <= 10 and e >= prev[1] and e < 9.5 and prev[1] < 9.5:
            b = 'reg_0-60' if t < 1200 else 'reg_60-120' if t < 2400 else 'reg_120-180' if t < 3600 else \
                'ot_0-60' if t < 4800 else 'ot_60-120'
            acc[b][0] += e - prev[1]
            acc[b][1] += (t - prev[0]) / 20
        prev = (t, e)
print(len(ot[-N:]), 'OT-length Ranked logs')
for b in ('reg_0-60', 'reg_60-120', 'reg_120-180', 'ot_0-60', 'ot_60-120'):
    d, s = acc[b]
    print(f'{b:12s} {d / s if s else float("nan"):.3f} elixir/s over {s:.0f} s  (= 1 per {s / d if d else float("nan"):.2f} s)')
