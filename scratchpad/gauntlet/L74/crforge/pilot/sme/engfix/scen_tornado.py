"""ENG-FIX2 scripted check (P4_AUDIT 3.F / lead queue): an opponent Hog Rider at the bridge, our Tornado pulling it toward
our king, both princesses up, on the SME lib (crforge 5e8089a4 tickprobe). Does the Hog retarget to the king, does our
princess lose less HP? Variants: no Tornado; Tornado on the Hog (no net pull); Tornado centre D units from the Hog toward
our king (9000, 3000). Uses 150053's plan as a template (decks / levels / towers), its commands replaced.
    (diag.sh env) python3 scen_tornado.py TEMPLATE_PLAN OUT.txt"""
import json, math, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', '/workspace/pilot/f1fix/sme11f'))
import sme_live  # noqa: E402
from sme import run_batch  # noqa: E402
tpl = json.load(open(sys.argv[1]))
END = 900
KING, PL = (9000, 3000), (3500, 6500)
base = dict(tpl, deals=[[6, 0, 1, 2, 3, 4, 5, 7], [5, 0, 1, 2, 3, 4, 6, 7]], cmds=[])
hog = dict(kind='play', given=180, run=200, side=1, card='HogRider', level=16, x=3500, y=18500)


def plan(tornado=None):
    p = json.loads(json.dumps(base))
    p['cmds'] = [dict(hog)] + ([dict(kind='play', given=tornado[0] - 20, run=tornado[0], side=0, card='Tornado', level=16,
                                    x=tornado[1], y=tornado[2])] if tornado else [])
    return sme_live.runnable(p)


def rows(o, kind=None, name=None):
    return [e for e in o['E'] if (kind is None or e[1] == kind) and (name is None or name in e[2])]


def summary(obs, label, out):
    by = {o['t']: o for o in obs}
    hp0 = {(e[3], e[4], e[5]): e[6] for e in rows(by[min(by)], 'T')}
    last = by[max(by)]
    hpN = {(e[3], e[4], e[5]): e[6] for e in rows(last, 'T')}
    king_shots = sorted({o['t'] for o in obs for e in rows(o, 'P', 'King')})
    out.write('projectile names: %s\n' % sorted({e[2] for o in obs for e in rows(o, 'P')}))
    out.write('shooters (projectile src point) at 300..480: %s\n' % sorted({(e[2], e[4] // 500 * 500, e[5] // 500 * 500)
                                                                          for o in obs if 300 <= o['t'] <= 480 for e in rows(o, 'P')})[:12])
    traj = [(t, [(e[4], e[5], e[6], e[9], e[10]) for e in rows(by[t], 'C', 'Hog')]) for t in sorted(by) if t % 20 == 0 and 200 <= t <= 700]
    out.write('== %s\n' % label)
    out.write('own towers hp lost: %s\n' % {k: hp0[k] - hpN.get(k, 0) for k in hp0 if k[0] == 0})
    out.write('king-tower projectiles first/last tick: %s / %s (n ticks %d)\n' % (king_shots[:1], king_shots[-1:], len(king_shots)))
    for t, h in traj:
        out.write('  %d hog %s\n' % (t, h))
    return traj


with open(sys.argv[2], 'w') as out:
    a = run_batch([(plan(), END, 0)], '/tmp/scen_%d' % os.getpid())[0]
    traj = summary(a, 'A: no Tornado', out)
    # cast when the Hog is ~6 tiles from our left princess (y about 12500), as a player would at the bridge
    t0, pos = next((t, h[0][:2]) for t, h in traj if h and h[0][1] <= 12500)
    ux, uy = KING[0] - pos[0], KING[1] - pos[1]
    L = math.hypot(ux, uy)
    for label, D in (('B: Tornado on the Hog (no net pull)', 0), ('C: centre 2000 toward our king', 2000),
                     ('D: centre 3500 toward our king', 3500), ('E: centre 5000 toward our king', 5000)):
        x, y = round(pos[0] + ux / L * D), round(pos[1] + uy / L * D)
        o = run_batch([(plan((t0, x, y)), END, 0)], '/tmp/scen_%d' % os.getpid())[0]
        out.write('Tornado run %d at (%d, %d); Hog at %s\n' % (t0, x, y, pos))
        summary(o, label, out)
print(open(sys.argv[2]).read())
