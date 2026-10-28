"""frames rows: python -I frrows.py MATCH T0 T1 CARD [side]  (card id or -0 for none); prints el + rows of that card"""
import sys
sys.path.insert(0, r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\crforge\pilot\sme')
import live_frames
m, t0, t1, card = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
for f in live_frames.convert(r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\%s.jsonl' % m):
    if t0 <= f['t'] <= t1:
        print(f['t'], f['el'], f['hand'], [e for e in f['E'] if e[3] == card], [p for p in f['P'] if p[3] == card])
