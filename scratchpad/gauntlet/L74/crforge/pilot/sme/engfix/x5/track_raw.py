"""ENG-FIX5: live_frames.convert rows of one card id in [T0, T1] straight from a raw log. python track_raw.py LOG T0 T1 CARD"""
import sys
from pathlib import Path
sys.path.insert(0, 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme')
import live_frames  # noqa: E402
t0, t1, card = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
for f in live_frames.convert(sys.argv[1]):
    if t0 <= f['t'] <= t1:
        print(f['t'], [e for e in f['E'] if e[3] == card])
