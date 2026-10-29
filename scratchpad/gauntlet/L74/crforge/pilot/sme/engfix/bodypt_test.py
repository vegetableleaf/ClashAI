"""ENG-FIX planted checks for parity/fights.py SME_OWN_BODYPT on the real log live_play_20261028_220244 (our evo Knight
tapped at (3500, 13500), the game's body at (2499, 13500); the bot's confirmation saw no body).
    icebow/.venv python -I bodypt_test.py LIVE_DIR -> 'ok N'"""
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
    rec, why = extract.match(os.path.join(sys.argv[1], 'live_play_20261028_220244.jsonl'), api=False)
    return {(p['side'], p['card'], p['tick'], p.get('x'), p.get('y')) for p in rec['plays'] if p['kind'] == 'play'}


fights.OWN_BODYPT = False
off = plays()
fights.OWN_BODYPT = True
on = plays()
check((0, 'Knight', 3373, 3500, 13500) in off and (0, 'Knight', 3373, 2499, 13500) in on, 'flag on: the body point')
check(off - on == {(0, 'Knight', 3373, 3500, 13500)} and on - off == {(0, 'Knight', 3373, 2499, 13500)}, 'only that play moves')
fights.OWN_BODYPT_D = 1500
check(plays() == off, 'a 1,001-unit offset under the threshold: kept at the tap')
fights.OWN_BODYPT_D, fights.OWN_SPAWN_CARDS = 750, {'Xbow', 'Tesla', 'IceWizard'}
check(plays() == off, 'a card outside OWN_SPAWN_CARDS: kept')
print('ok', n)
