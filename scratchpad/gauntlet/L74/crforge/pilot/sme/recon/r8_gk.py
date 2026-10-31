"""RECON-8 (pod): the Golden Knight's trajectory in the SIM (every tick, with buffs and targeting reference) next to the REC rows (frames), for a window.
  SME_TGT=1 bash recon/envR.sh python3 recon/r8_gk.py PLAN.json FRAMES.jsonl SIDE T0 T1 [--out DIR]
SIDE = the Golden Knight's side (the opponent's side in these records).  Env: envR.sh (SME_TGT=1 adds the targeting reference)."""
import json, math, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sme_live  # noqa: E402
from sme import run_batch  # noqa: E402
import recon  # noqa: E402
GK = 26000074


def main():
    a = sys.argv[1:]
    plan = json.load(open(a[0])); frames = sme_live.load_frames(a[1])
    side, t0, t1 = int(a[2]), int(a[3]), int(a[4])
    out = a[a.index('--out') + 1] if '--out' in a else '/dev/shm/r8_gk_%d' % os.getpid()
    o = run_batch([(recon.runnable(plan), min(max(frames), t1) + 3, 0)], out)[0]
    shutil.rmtree(out, ignore_errors=True)   # RAM-disk work dir (the pod disk is full)
    by = {x['t']: x for x in o}
    prev = {}
    for t in range(t0, t1 + 1):
        if t not in by:
            continue
        rows = by[t]['E']
        byid = {e[0]: e for e in rows}
        for e in rows:
            if e[1] == 'C' and e[2] == 'GoldenKnight' and e[3] == side:
                p = prev.get(e[0])
                sp = round(math.hypot(e[4] - p[4], e[5] - p[5])) if p else 0
                tg = e[12] if len(e) > 12 else None
                tgs = ''
                if tg is not None and tg in byid:
                    q = byid[tg]; tgs = '%s %s (%d,%d) hp %d d %d' % (q[1], q[2], q[4], q[5], q[6], math.hypot(q[4] - e[4], q[5] - e[5]))
                print('SIM t%d id%d (%d,%d) hp %d sp %d buffs [%s] tgt %s %s' % (t, e[0], e[4], e[5], e[6], sp, e[11], tg, tgs))
                prev[e[0]] = e
        if '--areas' in a:
            for e in rows:
                if e[1] == 'A':
                    print('   SIM-A t%d %s side %d (%d,%d) countdown %d' % (t, e[2], e[3], e[4], e[5], e[6]))
        if t in frames:
            for r in frames[t]['E']:
                if r[3] == GK:
                    print('   REC t%d side %d (%d,%d) hp %d' % (t, r[0], r[1], r[2], r[4]))
            if '--areas' in a:
                for r in frames[t]['A']:
                    print('   REC-A t%d side %d (%d,%d) id %d' % (t, r[0], r[1], r[2], r[3]))


if __name__ == '__main__':
    main()
