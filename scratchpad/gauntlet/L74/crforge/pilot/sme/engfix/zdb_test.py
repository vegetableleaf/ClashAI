"""ENG-FIX4 planted checks for SME_ZD_BLDG (mech_rules.zap_dead's enemy_body_near, ZD_HARMLESS) on FRESH4 155749@4266
(laptop, no SIM):   python -I zdb_test.py -> 'ok N'   (MECH_DIR=dir: mech_rules from there)"""
import json, os, sys
os.environ['SME_ZAP_DEAD'] = '1'
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get('MECH_DIR') or os.path.dirname(H))
import mech_rules as M  # noqa: E402
L = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/live_play_20261028_155749.jsonl'
T = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
x = next(json.loads(s) for s in open(H + '/r7/fresh4_off.jsonl') if '155749' in s)
SIDES = {int(k): v for k, v in x['sides'].items()}
FR = M.zd_frames(L)
n = 0


def check(name, ok):
    global n
    assert ok, name
    n += 1


def run(flag, rename=None):
    M.ZD_BLDG = flag
    fr = FR
    if rename:   # every Hog Rider of the frames renamed (a body of another row in the same place)
        fr = [(t, {a: dict(b, name=rename) if b['name'] == 'HogRider' else b for a, b in B.items()}, P, F) for t, B, P, F in FR]
    _, f, b = M.zap_dead(fr, x['plays'], SIDES, T, x.get('reader_hidden') or ())
    return [e for e in f if e['t'] == 4266], [e['why'] for e in b if e['t'] == 4266]


f, b = run(0)
check('flag off: blocked by the Hog Rider', not f and b == ['enemy_body_near'])
f, b = run(1)
check('flag on: fires R 4265, 3 Skeletons', len(f) == 1 and f[0]['R'] == 4265 and len(f[0]['victims']) == 3)
# MUST NOT FIRE: the same body as a row that can hurt troops
for row in ('BattleRam_EV1', 'GiantHero', 'Balloon', 'Knight'):
    f, b = run(1, rename=row)
    check('%s near blocks' % row, not f and b)
check('harmless: HogRider / Giant', M.ZD_HARMLESS(M.zd_cols(T, 'HogRider')) and M.ZD_HARMLESS(M.zd_cols(T, 'Giant')))
check('not harmless: BattleRam / Balloon / GiantHero / RamRider', not any(M.ZD_HARMLESS(M.zd_cols(T, r)) for r in
                                                                        ('BattleRam', 'Balloon', 'GiantHero', 'RamRider')))
M.ZD_BLDG = 0
print('ok', n)
