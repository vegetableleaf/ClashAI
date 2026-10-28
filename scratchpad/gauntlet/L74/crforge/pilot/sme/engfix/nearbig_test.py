"""ENG-FIX planted checks for parity/fights.py SME_NEAR_BIGGER on the real log live_play_20261028_101018 (a second
Goblinstein at 5968 beside the first play's living doctor). icebow/.venv python -I nearbig_test.py LIVE_DIR -> 'ok N'."""
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
    rec, why = extract.match(os.path.join(sys.argv[1], 'live_play_20261028_101018.jsonl'), api=False)
    return {(p['side'], p['card'], p['tick'], p.get('x'), p.get('y')) for p in rec['plays'] if p['kind'] == 'play'}


fights.NEAR_BIGGER = False
off = plays()
fights.NEAR_BIGGER = True
on = plays()
check(on - off == {(0, 'Goblinstein', 5967, 3499, 14500)}, 'flag on adds the second Goblinstein at its monster point')
check(off <= on, 'flag on drops no play')
check(sum(1 for p in on if p[1] == 'Goblinstein') == sum(1 for p in off if p[1] == 'Goblinstein') + 1, 'one play added')
print('ok', n)
