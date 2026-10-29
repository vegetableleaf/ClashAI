"""ENG-FIX5 planted checks for SME_ZD_SINGLE (mech_rules.zd_single / zap_dead). python -I zds_test.py
zd_single on table rows; then the real candidates: FRESH8 080149@516 fires with the flag and is blocked without it,
FRESH5 022148@458 (exact without a Zap; a goblinstein_doctor with an Ability targets a victim) stays blocked."""
import json, os, sys
from pathlib import Path
os.environ['SME_ZAP_DEAD'] = '1'
os.environ['SME_ZD_BLDG'] = '1'
S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S))
import mech_rules as M  # noqa: E402
T = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
LIVE = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
n = 0


def ok(c, msg):
    global n
    assert c, msg
    n += 1


for name, want in [('HogRider', True), ('Knight', True), ('Musketeer', True), ('Hunter', False), ('Bomber', False),
                   ('ElectroWizard', False), ('goblinstein_doctor', False), ('NoSuchRow', False), (None, False)]:
    ok(M.zd_single(T, name) is want, 'zd_single %s %s' % (name, want))


def outcome(setf, m, t, flag):
    r = next(json.loads(l) for l in open(setf) if m in l)
    M.ZD_SINGLE = flag
    _, fi, bl = M.zap_dead(M.zd_frames(LIVE + r['match'] + '.jsonl'), r['plays'], {int(k): v for k, v in r['sides'].items()},
                           T, r.get('reader_hidden') or ())
    return ['FIRED' for e in fi if e['t'] == t] + [e['why'] for e in bl if e['t'] == t]


E = Path(__file__).resolve().parent
ok(outcome(E / 'fresh8/inputs_rngfree.jsonl', '080149', 516, 0) == ['enemy_targets_victim'], '080149 off: blocked')
ok(outcome(E / 'fresh8/inputs_rngfree.jsonl', '080149', 516, 1) == ['FIRED'], '080149 on: fired')
ok(outcome(E / 'r9/fresh5_on.jsonl', '022148', 458, 1) == ['enemy_targets_victim'], '022148 on: still blocked (Ability)')
print('ok', n)
