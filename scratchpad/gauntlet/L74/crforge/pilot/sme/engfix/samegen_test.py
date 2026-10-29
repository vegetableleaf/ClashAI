"""ENG-FIX5 planted checks for SME_SAMETICK_GEN (bp9/order_inputs.reorder gens=). python -I samegen_test.py [LIVE_DIR]
Synthetic frames: rows say A first, generations say B first; spurious / missing generations fall back to the rows; no gens =
the old rule. With LIVE_DIR: the real FRESH6 031310@3931 pair (MK, Knight_EV1) and FRESH4 235316@5451 (Xbow, Tornado)."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bp9'))
_argv, sys.argv = sys.argv, [sys.argv[0], '', '']  # order_inputs reads src, dst from argv at import
import order_inputs as oi  # noqa: E402
sys.argv = _argv

n = 0


def ok(c, msg):
    global n
    assert c, msg
    n += 1


def play(side, card, x, y, t=100):
    return dict(side=side, kind='play', card=card, x=x, y=y, tick=t, source='s')


T = {'t': 0, 'E': [[0, 9000, 3000, -1, 7728, 12], [1, 9000, 29000, -1, 7728, 12]]}
F = {'t': 102, 'E': T['E'] + [[0, 2500, 14500, 26000055, 6380, 14], [1, 9000, 22000, 13000102, 600, 13],
                              [1, 2500, 17500, 13000000, 2822, 14]]}
fr = [(0, T), (102, F)]
rec = dict(match='x', plays=[play(0, 'MegaKnight', 2500, 14500), play(1, 'Knight', 2500, 17500)])
order = lambda r: [p['card'] for p in r['plays']]
ok(order(oi.reorder(rec, [], fr=fr)) == ['MegaKnight', 'Knight'], 'rows: MK first (old rule)')
G = {0: [5000000, 5000003], 102: [5000000, 5000003, 5000173, 5000156, 5000172]}
ok(order(oi.reorder(rec, [], fr=fr, gens=G)) == ['Knight', 'MegaKnight'], 'gens: Knight first')
ok(order(oi.reorder(rec, [], fr=fr, gens=None)) == ['MegaKnight', 'Knight'], 'gens None = old rule')
G2 = {0: [5000000, 5000174], 102: G[102]}  # a body of the frame before is newer than the reading: not new -> rows
ok(order(oi.reorder(rec, [], fr=fr, gens=G2)) == ['MegaKnight', 'Knight'], 'spurious generation falls back to rows')
G3 = {0: G[0], 102: [5000000, 5000003, 5000173, 5000156, None]}  # a missing generation -> rows
ok(order(oi.reorder(rec, [], fr=fr, gens=G3)) == ['MegaKnight', 'Knight'], 'missing generation falls back to rows')
G4 = {0: G[0]}  # no generations in the reading frame -> rows
ok(order(oi.reorder(rec, [], fr=fr, gens=G4)) == ['MegaKnight', 'Knight'], 'no reading-frame generations -> rows')
G5 = {0: G[0], 102: [5000000, 5000003, 5000172, 5000156, 5000173]}  # gens agree with rows -> unchanged
ok(order(oi.reorder(rec, [], fr=fr, gens=G5)) == ['MegaKnight', 'Knight'], 'agreeing generations keep the order')
rec3 = dict(match='x', plays=[play(0, 'MegaKnight', 2500, 14500), play(1, 'Log', 9000, 9000), play(1, 'Knight', 2500, 17500)])
ok(order(oi.reorder(rec3, [], fr=fr, gens=G)) == ['Knight', 'Log', 'MegaKnight'], 'a play with no reading keeps its slot')
rec4 = dict(match='x', plays=[play(0, 'MegaKnight', 2500, 14500), play(1, 'Knight', 2500, 17500, t=101)])
ok(order(oi.reorder(rec4, [], fr=fr, gens=G)) == ['MegaKnight', 'Knight'], 'different ticks are never reordered')

if len(sys.argv) > 1:
    LD = sys.argv[1]
    for m, tick, want_gen, want_row in [('live_play_20261029_031310', 3931, ['Knight', 'MegaKnight'], ['MegaKnight', 'Knight']),
                                        ('live_play_20261028_235316', 5451, None, None)]:
        path = os.path.join(LD, m + '.jsonl')
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import live_frames  # noqa: E402
        fr = [(f['t'], f) for f in live_frames.convert(path)]
        gens = oi.gen_frames(path)
        if m.endswith('031310'):
            rec = dict(match=m, plays=[play(0, 'MegaKnight', 2499, 14500, tick), play(1, 'Knight', 2500, 17500, tick)])
            ok(order(oi.reorder(rec, [], fr=fr)) == want_row, '031310 rows: MK first')
            ok(order(oi.reorder(rec, [], fr=fr, gens=gens)) == want_gen, '031310 gens: Knight first')
        else:
            r8 = [json.loads(l) for l in open(Path(__file__).resolve().parent / 'r8' / 'fresh4_on.jsonl')]
            rec = [r for r in r8 if r['match'] == m][0]
            ok(oi.reorder(rec, [], fr=fr, gens=gens)['plays'] == oi.reorder(rec, [], fr=fr)['plays'], '235316 Tornado: unchanged')
print('ok', n)
