"""our elixir + areas of a card id + own ents of a card: python -I elx.py MATCH T0 T1 AREA_CARD"""
import sys
sys.path.insert(0, r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\crforge\pilot\sme')
import live_frames
m, t0, t1, ac = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
p = None
for f in live_frames.convert(r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\%s.jsonl' % m):
    if t0 <= f['t'] <= t1:
        print(f['t'], f['el'], (f['el'] - p) if p else '', [a for a in f['A'] if a[3] == ac], f['hand'])
    p = f['el']
