"""RECON-7 (pod): trace ONE unit's REC and SIM trajectories around the first divergence (position-only class).
  python3 recon/r7_trace.py PLAN.json FRAMES/MATCH.jsonl SIDE SX SY SHP RX RY RHP FIRST_DIV [--pre 40] [--post 8]
SIM unit = the C row of side SIDE at (SX, SY, SHP) at tick FIRST_DIV (the first-diff U_sim_only row); REC unit = the REC row (RX, RY, RHP) at FIRST_DIV.
Both are followed backward and forward by id (SIM) / nearest same-side row (REC, <= 250 units per frame). Prints the unit's SIM spawn tick + the plan
command that made it (run tick, kind, card) and the REC first listing tick, then per frame tick: SIM x y hp, REC x y hp, delta.  Env: envR.sh."""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import recon, sme_live  # noqa: E402
from sme import run_batch  # noqa: E402


def main():
    a = sys.argv[1:]
    plan = json.load(open(a[0])); frames = sme_live.load_frames(a[1])
    side, SX, SY, SHP, RX, RY, RHP, d = [int(v) for v in a[2:10]]
    pre = int(a[a.index('--pre') + 1]) if '--pre' in a else 40
    post = int(a[a.index('--post') + 1]) if '--post' in a else 8
    work = os.environ.get('R7_WORK', '/tmp/r7work_%d' % os.getpid())
    end = min(max(frames), d + post + 4)
    o = run_batch([(recon.runnable(plan), end + 3, 0)], work)[0]
    by = {x['t']: x for x in o}
    sid = name = None
    for e in by[d]['E']:
        if e[1] == 'C' and e[3] == side and abs(e[4] - SX) <= 1 and abs(e[5] - SY) <= 1 and e[6] == SHP:
            sid, name = e[0], e[2]
    if sid is None:
        print('no SIM unit at the first-diff point')
        return
    sim = {}
    for t in sorted(by):
        for e in by[t]['E']:
            if e[0] == sid:
                sim[t] = (e[4], e[5], e[6], e[8])
    def rows(t):
        return [(r[1], r[2], r[4]) for r in frames[t]['E'] if r[0] == side and r[3] != -1]
    rec = {d: (RX, RY, RHP)}
    for sgn in (-1, 1):
        cur = (RX, RY)
        ts = sorted((t for t in frames if (t < d if sgn < 0 else d < t <= d + post)), reverse=(sgn < 0))
        for t in ts:
            cand = [(math.hypot(x - cur[0], y - cur[1]), x, y, hp) for x, y, hp in rows(t)]
            if not cand or min(cand)[0] > 250:
                break
            c = min(cand); rec[t] = (c[1], c[2], c[3]); cur = (c[1], c[2])
    t0s = min(sim)
    src = sim[t0s][3]
    cm = plan['cmds'][int(src[3:].split('_')[0])] if src.startswith('cmd') and src[3:].split('_')[0].isdigit() else None
    print('unit', name, 'side', side, 'SIM spawn row tick', t0s, 'src', src, 'cmd', cm and {k: cm.get(k) for k in ('kind', 'card', 'run', 'given', 'x', 'y')},
          '| REC first listing (traced)', min(rec), 'first SIM row hp', sim[t0s][2])
    for t in sorted(set(sim) | set(rec)):
        if t < d - pre or t > d + post or t not in frames:
            continue
        s, r = sim.get(t), rec.get(t)
        dl = (r[0] - s[0], r[1] - s[1], r[2] - s[2]) if s and r else None
        print(t, 'SIM', s[:3] if s else None, 'REC', r, 'd', dl)


if __name__ == '__main__':
    main()
