"""ENG-FIX2 planted checks for parity/fights.py SME_NEAR_BIGGER2 on real logs: FRESH2 101018 (a second Goblinstein whose
monster has the max hp of the first play's monster -> a play) and dev 154839 (hero Musketeer 2454-hp bodies beside an
earlier 1153-hp hero Musketeer -> no play); control: the old NEAR_BIGGER adds them.
    icebow/.venv python -I nearbig2_test.py LIVE_DIR -> 'ok N'"""
import os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract  # noqa: E402
fights = extract.fights
n = 0


def check(c, what):
    global n
    assert c, what
    n += 1


def plays(m, tables):
    extract.TABLES = Path(tables)
    rec, why = extract.match(os.path.join(sys.argv[1], m + '.jsonl'), api=False)
    return {(p['side'], p['card'], p['tick'], p.get('x'), p.get('y')) for p in rec['plays']}


T635 = r'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
T402 = r'C:/Users/benpe/crforge_eval/cache/tables/16.402.22'
fights.NEAR_BIGGER2 = False
a0, b0 = plays('live_play_20261028_101018', T635), plays('live_play_20261026_154839', T402)
fights.NEAR_BIGGER2 = True
a1, b1 = plays('live_play_20261028_101018', T635), plays('live_play_20261026_154839', T402)
check(a1 - a0 == {(0, 'Goblinstein', 5967, 3499, 14500)} and not a0 - a1, '101018: the second Goblinstein becomes a play')
check(b1 == b0, '154839: no hero Musketeer play added (2454 hp is no earlier play body of the card)')
fights.NEAR_BIGGER = True
check(plays('live_play_20261026_154839', T402) - b0, 'control: the old NEAR_BIGGER does add the false Musketeer plays')
print('ok', n)
