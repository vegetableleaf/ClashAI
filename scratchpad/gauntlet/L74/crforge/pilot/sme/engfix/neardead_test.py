"""ENG-FIX planted checks for parity/fights.py SME_OWN_NEARDEAD (deployments' H-NEARPARENT, own side).
    icebow/.venv python -I neardead_test.py LIVE_DIR -> 'ok N'. Real log live_play_20261028_142334: our hero Ice Wizard
    tapped at 1669 (confirmed 1693), born 1693, 2,954 units from our earlier hero Ice Wizard that died at 1692."""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract  # noqa: E402
extract.TABLES = Path(r'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3')
fights = extract.fights
SRC = os.path.join(sys.argv[1], 'live_play_20261028_142334.jsonl')
n = 0


def check(c, what):
    global n
    assert c, what
    n += 1


def plays(path):
    rec, why = extract.match(path, api=False)
    assert rec is not None, why
    return [(p['side'], p['card'], p['tick'], p.get('source')) for p in rec['plays']]


def planted(edit):
    f = tempfile.NamedTemporaryFile('wb', suffix='.jsonl', delete=False, prefix='live_play_20261028_142334_')
    for line in open(SRC, 'rb'):
        if line.startswith(b'{"event": "play", "tick": 1669,') or line.startswith(b'{"event": "confirmed", "tick": 1693,'):
            d = json.loads(line); edit(d); line = (json.dumps(d) + '\n').encode()
        f.write(line)
    f.close()
    return f.name


iw = lambda ps: [p for p in ps if p[0] == 1 and p[1] == 'IceWizard' and 1680 <= p[2] <= 1700]  # noqa: E731
fights.OWN_NEARDEAD = False
off = plays(SRC)
check(iw(off) == [], 'flag off: the play is dropped (the near-parent rule)')
fights.OWN_NEARDEAD = True
on = plays(SRC)
check(iw(on) == [(1, 'IceWizard', 1691, 'own_tap')], 'flag on: the tap is the play')
check(sorted(set(on) - set(off)) == iw(on) and set(off) <= set(on), 'flag on changes only that play')
# without a confirmed tap of the card (the tap planted as another card: no confirmed IceWizard play), no play
p = planted(lambda d: d.update(name='Knight'))
check(iw(plays(p)) == [], 'no confirmed tap of the card: no play')
os.unlink(p)
print('ok', n)
