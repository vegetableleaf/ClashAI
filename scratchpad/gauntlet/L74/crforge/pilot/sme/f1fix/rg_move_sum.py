"""SME-F1FIX: rg_move.py's output summarised: launches whose Rune Giant was walking just before (step from L-2 to L > 0)
and whether it kept stepping on every frame of (L, L + 12] (giantbuffer_no_move_on_buff lasts 600 ms = 12 ticks).
python -I rg_move_sum.py RG_MOVE.txt"""
import sys
walk = on = 0
stops = []
for line in open(sys.argv[1]):
    name, L, *st = line.split()
    s = {int(a): int(b) for a, b in (x.split(':') for x in st)}
    before = [v for k, v in s.items() if k <= 0]
    after = [v for k, v in s.items() if 0 < k <= 12]
    if not before or before[-1] == 0 or not after:
        continue
    walk += 1
    if min(after) > 0:
        on += 1
    else:
        stops.append((name, L))
print('launches with the Rune Giant walking just before:', walk, '| kept stepping through (L, L+12]:', on, '| stopped:', stops)
