"""ENG-FIX5 planted checks for SME_GK_WALK (bp_rules.gk_walk / gk_from_buff). python -I gkwalk_test.py [LIVE_DIR]
Synthetic frames: a raged walk (77 / 39 a tick) is dropped, a dash (107 then 125) kept, 100 exactly dropped and 101 kept,
a buff-dated slow cast kept, a cast without frames kept, flag off keeps everything. With LIVE_DIR: FRESH4 230352@912
dropped, dev 030315@2863 (a buff-less dash) kept."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bp_rules  # noqa: E402

n = 0


def ok(c, msg):
    global n
    assert c, msg
    n += 1


def frames(steps, t0=100):
    """Knight path: frames t0, t0+2, ... with displacements (dx, dy) per 2-tick frame."""
    fr, x, y = {}, 9000, 15000
    for k, (dx, dy) in enumerate([(0, 0)] + steps):
        x, y = x + dx, y + dy
        fr[t0 + 2 * k] = {'t': t0 + 2 * k, 'E': [[0, x, y, 26000074, 1000, 15]], 'P': []}
    return fr


cast = {'side': 0, 'kind': 'ability', 'card': 'GoldenKnight', 'tick': 100, 'run_ticks': [99, 100], 'source': 'gk_dash'}
walk = frames([(-100, 118), (-50, 59)])            # 77 / tick, then 39
dash = frames([(-120, 180), (-150, 200)])          # 108, then 125
edge = frames([(120, 160), (120, 160)])            # exactly 100 / tick both pairs
over = frames([(120, 162), (120, 160)])            # 100.8 on the burst pair
ok(bp_rules.gk_walk(cast, walk), 'raged walk dropped')
ok(not bp_rules.gk_walk(cast, dash), 'dash kept')
ok(bp_rules.gk_walk(cast, edge), '100 a tick is a walk')
ok(not bp_rules.gk_walk(cast, over), 'over 100 is a dash')
ok(not bp_rules.gk_walk(cast, {}), 'no frames: kept')
sides = {'0': {'deck': ['Knight', 'GoldenKnight']}}
bp_rules.GK_WALK_ON = 0
ok(len(bp_rules.gk_from_buff([cast], [], walk, sides)) == 1, 'flag off keeps the cast')
bp_rules.GK_WALK_ON = 1
ok(bp_rules.gk_from_buff([cast], [], walk, sides) == [], 'flag on drops the walk')
ok(len(bp_rules.gk_from_buff([cast], [], dash, sides)) == 1, 'flag on keeps the dash')
dated = bp_rules.gk_from_buff([cast], [(0, 102)], walk, sides)  # a GoldenKnightCharge start at 102 re-dates it -> kept
ok(len(dated) == 1 and dated[0].get('dated') == 'gk_buff', 'buff-dated cast kept')

if len(sys.argv) > 1:
    import live_frames  # noqa: E402
    E = Path(__file__).resolve().parent
    for m, setf, tick, want in [('live_play_20261028_230352', 'r9/fresh4_off_all.jsonl', 912, True),
                                ('live_play_20261027_030315', 'r9/dev_off_all.jsonl', 2863, False)]:
        rec = next(json.loads(l) for l in open(E / setf) if m in l)
        p = next(p for p in rec['plays'] if p['kind'] == 'ability' and p.get('card') == 'GoldenKnight' and p['tick'] == tick)
        fr = {x['t']: x for x in live_frames.convert(os.path.join(sys.argv[1], m + '.jsonl'))}
        ok(bp_rules.gk_walk(p, fr) == want, '%s@%d gk_walk %s' % (m, tick, want))
print('ok', n)
