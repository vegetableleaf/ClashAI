"""ENG-FIX planted checks for parity/fights.py SME_OWN_SPAWN (read_match's confirmed-play point).
    python -I spawn_test.py LIVE_DIR -> 'ok N'. Plants edited copies of the real log live_play_20261028_142926 (Knight tapped
    at 211, unconfirmed, re-tapped at 248; confirmation at 254 with err_tiles 7.61 and the body at the first tap)."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'parity'))
import fights  # noqa: E402
live = sys.argv[1]
SRC = os.path.join(live, 'live_play_20261028_142926.jsonl')
TAP, BODY = [2500, 17500], [5499, 24499]   # side 1: raw_xy of the second tap's intended point / of the confirmation's spawn
n = 0


def check(c, what):
    global n
    assert c, what
    n += 1


def knight(path):
    m, why = fights.read_match(path)
    assert m is not None, why
    k = [p for p in m['plays'] if p['name'] == 'Knight' and p['tick'] == 248]
    assert len(k) == 1
    return [k[0]['x'], k[0]['y']], k[0].get('spawn_moved')


def planted(edit):
    """copy of SRC with the 254 Knight confirmation edited by edit(dict) -> path"""
    f = tempfile.NamedTemporaryFile('wb', suffix='.jsonl', delete=False, prefix='live_play_20261028_142926_')
    for line in open(SRC, 'rb'):
        if line.startswith(b'{"event": "confirmed", "tick": 254,'):
            d = json.loads(line); edit(d); line = (json.dumps(d) + '\n').encode()
        f.write(line)
    f.close()
    return f.name


fights.OWN_SPAWN = False
check(knight(SRC) == (TAP, None), 'flag off: the tap point')
fights.OWN_SPAWN = True
check(knight(SRC) == (BODY, 7.61), 'flag on: the body point')
cases = [(lambda d: d.update(err_tiles=0.5), TAP, 'err 0.5 (the back-row clamp): kept'),
         (lambda d: d.update(err_tiles=0.75), BODY, 'err 0.75: moved'),
         (lambda d: d.update(err_tiles=None), TAP, 'no err_tiles: kept'),
         (lambda d: d.update(spawn=None), TAP, 'no spawn: kept'),
         (lambda d: d.update(spawn=d['spawn'] * 2), TAP, 'two spawn points: kept')]
for edit, want, what in cases:
    p = planted(edit)
    check(knight(p)[0] == want, what)
    os.unlink(p)
fights.OWN_SPAWN_CARDS = {'Xbow', 'Tesla', 'IceWizard'}
check(knight(SRC)[0] == TAP, 'a card outside OWN_SPAWN_CARDS: kept')
print('ok', n)
