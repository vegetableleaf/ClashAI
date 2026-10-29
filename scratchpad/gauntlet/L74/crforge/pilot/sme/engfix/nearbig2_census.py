"""ENG-FIX2: plays that SME_NEAR_BIGGER (old) and SME_NEAR_BIGGER2 (narrow) add or remove vs both off, per log, under the
FRESH4 extractor flags. NEAR_BIGGER2 is the old rule plus a condition, so it can only fire where the old one does.
    icebow/.venv python -I nearbig2_census.py TABLES LIST... > OUT.txt"""
import os, sys
for k in ('SME_HIDDEN_GEN SME_TOWER_ZAP SME_ZAP_CHAIN1 SME_TOMB_HERO SME_BB_RISE SME_OWN_SPAWN SME_OWN_NEARDEAD SME_OWN_BODYPT '
          'SME_UNIT_HP SME_IW_DEPLOY SME_IW_AREA SME_HERO7 SME_OWNPLAY7 SME_RASCAL7 SME_GOLEM7 SME_OWN_CAST SME_BP_VALK SME_BP_GK '
          'SME_BP_GIANT SME_BP_RASCALS SME_BP_PRESS SME_MECH_GB SME_MECH_DRILL SME_MECH_HB SME_MECH_ZAP SME_HIDDEN SME_GK8 '
          'SME_CHARGE8 SME_ZAP_ADD SME_ZAP_POINT SME_LATE9 SME_MADE9 SME_SAMETICK_ORDER SME_IWPEND9 SME_IWGHOST10').split():
    os.environ[k] = '1'
import json  # noqa: E402
from pathlib import Path  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract  # noqa: E402
LIVE = Path(__file__).resolve().parents[7] / 'scratchpad/gauntlet/L68/live_reader'


def plays(m):
    rec, why = extract.match(str(LIVE / (m + '.jsonl')), api=False)
    return set() if rec is None else {(p['side'], p['card'], p['tick'], p.get('x'), p.get('y')) for p in rec['plays']}


def one(a):
    tables, m = a
    extract.TABLES = Path(tables)
    f = extract.fights
    f.NEAR_BIGGER = f.NEAR_BIGGER2 = False
    off = plays(m)
    f.NEAR_BIGGER = True
    old = plays(m)
    f.NEAR_BIGGER, f.NEAR_BIGGER2 = False, True
    new = plays(m)
    return m, sorted(old - off), sorted(off - old), sorted(new - off), sorted(off - new)


if __name__ == '__main__':
    jobs = []
    for f in sys.argv[2:]:
        ms = [json.loads(l)['match'] for l in open(f)] if f.endswith('.jsonl') else \
            [l.split('\t')[0] for l in open(f) if l.strip() and not l.startswith('#')]
        jobs += [(sys.argv[1], m) for m in ms]
    n_old = n_new = 0
    with ProcessPoolExecutor(4) as ex:
        for m, oa, orm, na, nrm in ex.map(one, jobs):
            if oa or orm or na or nrm:
                n_old += bool(oa or orm); n_new += bool(na or nrm)
                print(m, 'OLD +', oa, '-', orm, '| NEW +', na, '-', nrm, flush=True)
    print('logs', len(jobs), 'old changes', n_old, 'new changes', n_new)
