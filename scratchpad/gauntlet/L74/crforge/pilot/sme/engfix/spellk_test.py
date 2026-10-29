"""ENG-FIX2 planted checks for parity/fights.py SME_SPELL_KING: the real log live_play_20261028_151109 (an opponent
Snowball first seen at 925 one step from its king: run 924, the mid-gap default 923) + synthetic shots for each block.
    icebow/.venv python -I spellk_test.py LIVE_DIR -> 'ok N'"""
import os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract  # noqa: E402
extract.TABLES = Path(r'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3')
fights = extract.fights
n = 0


def check(c, what):
    global n
    assert c, what
    n += 1


def plays():
    rec, why = extract.match(os.path.join(sys.argv[1], 'live_play_20261028_151109.jsonl'), api=False)
    return {(p['side'], p['card'], p['tick'], tuple(p['run_ticks'])) for p in rec['plays'] if p['kind'] == 'play'}


fights.SPELL_KING = False
off = plays()
fights.SPELL_KING = True
on = plays()
# F4_fe's repair moved the 2860 and 3690 Snowballs to 2861 / 3691 by hand (rounds 1, 4); the 923 one it could not
check(off - on == {(0, 'Snowball', t, (t, t + 1)) for t in (923, 2860, 3690)}
      and on - off == {(0, 'Snowball', t + 1, (t, t + 1)) for t in (923, 2860, 3690)},
      'real log: only the three k = 1 Snowballs move one tick, window kept')
check((0, 'Snowball', 325, (325, 326)) in on, 'k = 2 at 327: the default 325 is the rule tick')

CAT = {1: {'type': 'spell', 'display_name': 'Fireball'}}
K = fights.TOWER_SLOTS[0]                       # (9000, 3000)


def cast(rows, ticks=(98, 100, 102, 104)):
    """rows: {tick: [(x, y, aim_x, aim_y, serial, src)]} -> the one seen cast's tick (and lo, hi)."""
    m = dict(frames=[(t, []) for t in ticks], fx={},
             proj={t: [(0, x, y, 1, ax, ay, s, src, None) for x, y, ax, ay, s, src in rs] for t, rs in rows.items()})
    c = [e for e in fights.seen_casts(m, CAT) if e['kind'] == 'play']
    assert len(c) == 1, c
    return c[0]['tick'], c[0]['lo'], c[0]['hi']


v = 600                                          # units per tick along +y from the king, aim (9000, 15000)
one = {100: [(9000, 3000 + v, 9000, 15000, 7, 'T0K')], 102: [(9000, 3000 + 3 * v, 9000, 15000, 7, 'T0K')]}
check(cast(one) == (99, 98, 99), 'k = 1 on frame 100 (prev 98): tick 99 (default 98)')
fights.SPELL_KING = False
check(cast(one) == (98, 98, 99), 'flag off: the mid-gap default')
fights.SPELL_KING = True
two = {100: [(9000, 3000 + 2 * v, 9000, 15000, 7, 'T0K')], 102: [(9000, 3000 + 4 * v, 9000, 15000, 7, 'T0K')]}
check(cast(two) == (98, 98, 99), 'k = 2: tick 98')
check(cast({100: [(9000 + 400, 3000 + v, 9000, 15000, 7, 'T0K')], 102: [(9400, 3000 + 3 * v, 9000, 15000, 7, 'T0K')]})
      == (98, 98, 99), 'first sighting 400 off the king -> aim line: default kept')
check(cast({100: [(9000, 3000 + 1.5 * v, 9000, 15000, 7, 'T0K')], 102: [(9000, 3000 + 3.5 * v, 9000, 15000, 7, 'T0K')]})
      == (98, 98, 99), 'k = 1.5 (not whole): default kept')
check(cast({100: [(9000, 3000 + v, 9000, 15000, 7, 'T0K')]}) == (98, 98, 99), 'no second sighting: default kept')
check(cast({100: [(9000, 3000 + v, 9000, 15000, 7, 'T0L')], 102: [(9000, 3000 + 3 * v, 9000, 15000, 7, 'T0L')]})
      == (98, 98, 99), 'source not a king (a princess): default kept')
check(cast({100: [(9000, 3000 + v, 9000, 15000, 7, None)], 102: [(9000, 3000 + 3 * v, 9000, 15000, 7, None)]})
      == (98, 98, 99), 'no source: default kept')
check(cast({100: [(9000, 3000 + 3 * v, 9000, 15000, 7, 'T0K')], 102: [(9000, 3000 + 5 * v, 9000, 15000, 7, 'T0K')]})
      == (98, 98, 99), 'k = 3 outside the window [98, 99]: default kept')
check(cast({100: [(9000, 3000 + v, 9000, 15000, 7, 'T0K'), (9100, 3000 + v, 9600, 15000, 8, 'T0K')],
            102: [(9000, 3000 + 3 * v, 9000, 15000, 7, 'T0K')]}) == (98, 98, 99), 'two shots on one frame (Arrows): default kept')
top = {100: [(9000, 29000 - v, 9000, 17000, 7, 'T1K')], 102: [(9000, 29000 - 3 * v, 9000, 17000, 7, 'T1K')]}
check(cast(top) == (99, 98, 99), 'the other king (9000, 29000): k = 1 -> 99')
print('ok', n)
