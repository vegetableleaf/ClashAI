"""ENG-FIX2 planted checks for extract.py SME_HIDDEN_CHILD on the real log live_play_20261028_210016 (a Golemite listed
under the Golem card id, hidden 2068-2154 while our tower's shot homes on it) + table cases.
    icebow/.venv python -I hchild_test.py LIVE_DIR -> 'ok N'"""
import os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract  # noqa: E402
extract.TABLES = Path(r'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3')
cat = extract.load_catalog()[0]
os.environ['SME_HIDDEN_GEN'] = '1'
n = 0


def check(c, what):
    global n
    assert c, what
    n += 1


log = os.path.join(sys.argv[1], 'live_play_20261028_210016.jsonl')
extract.HIDDEN_CHILD = False
off = extract.reader_hidden(log, cat)
extract.HIDDEN_CHILD = True
on = extract.reader_hidden(log, cat)
check([h['name'] for h in off] == ['Golem'] and [h['name'] for h in on] == ['Golemite'], 'real log: Golem -> Golemite')
check([dict(h, name=None) for h in off] == [dict(h, name=None) for h in on], 'only the name changes (window, track)')
check(on[0]['last'] == 2066 and on[0]['track']['2070'] == [5470, 8831], 'the window starts after 2066, track at 2070')
check(extract.hidden_child('Golem', 8180) == 'Golem', 'a level-16 Golem (own unit hp) keeps its name')
check(extract.hidden_child('Golem', 1827) == 'Golemite', 'a Golemite hp: the death spawn')
check(extract.hidden_child('Knight', 1234) == 'Knight', 'no death spawn: name kept')
check(extract.hidden_child('NoSuchRow', 5) == 'NoSuchRow', 'no unit row: name kept')
print('ok', n)
