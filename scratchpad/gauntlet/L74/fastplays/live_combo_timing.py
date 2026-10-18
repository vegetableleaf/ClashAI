"""Live Rocket / Tornado timing from logged frames: for each Rocket play (and the nearest Tornado play within WIN ticks),
the tap tick, the first frame the Rocket projectile (proj, target = the aim) / Tornado effect (fx) appears, the Rocket's last
frame (impact ~ next), the Tornado's life, and enemy bodies within 2.5 / 5.5 tiles of the aim at the Tornado start and at impact.
    python live_combo_timing.py LOGDIR GLOB SHA8 [WIN]"""
import glob, json, math, os, sys

d, pat, sha8 = sys.argv[1:4]
win = int(sys.argv[4]) if len(sys.argv) > 4 else 120


def first(frames, t0, pred):
    return next((f for f in frames if f['tick'] >= t0 and pred(f)), None)


for p in sorted(glob.glob(os.path.join(d, pat))):
    start, plays, frames = None, [], []
    with open(p, encoding='utf-8') as fh:
        for s in fh:
            e = json.loads(s)
            ev = e.get('event')
            if ev == 'start':
                start = e
                if not str(e.get('ckpt_sha256', '')).startswith(sha8):
                    break
            elif ev == 'play':
                plays.append(e)
            elif ev == 'frame':
                frames.append(e)
    if not start or not str(start.get('ckpt_sha256', '')).startswith(sha8) or not frames:
        continue
    me = frames[0]['my_side']
    for a in plays:
        if a['name'] != 'Rocket':
            continue
        tor = [b for b in plays if b['name'] == 'Tornado' and 0 <= b['tick'] - a['tick'] <= win]
        if not tor:
            continue
        b = tor[0]
        fr = first(frames, a['tick'], lambda f: any(x[0] == me and x[3] == 28000003 for x in f['proj']))
        if fr is None:
            continue
        rk = next(x for x in fr['proj'] if x[0] == me and x[3] == 28000003)
        aim = (rk[4], rk[5])
        last = fr
        for f in frames:
            if f['tick'] > fr['tick'] and any(x[0] == me and x[3] == 28000003 and (x[4], x[5]) == aim for x in f['proj']):
                last = f
        ft = first(frames, b['tick'], lambda f: any(x[0] == me and x[3] == 28000012 for x in f['fx']))
        tl = None
        if ft:
            ends = [f['tick'] for f in frames if f['tick'] >= ft['tick'] and any(x[0] == me and x[3] == 28000012 for x in f['fx'])]
            tl = (ft['tick'], max(ends))

        def near(f, r):
            return sum(1 for x in f['ents'] if x[0] != me and x[6] not in (12, 13) and math.hypot(x[1] - aim[0], x[2] - aim[1]) <= r * 1000)
        imp = first(frames, last['tick'] + 1, lambda f: True)
        print(os.path.basename(p)[10:25], f"R tap {a['tick']} launch {fr['tick']} (+{fr['tick'] - a['tick']}) last {last['tick']}"
              f" flight {last['tick'] + 1 - fr['tick']} aim ({aim[0] / 1000:.1f},{aim[1] / 1000:.1f})",
              f"| T tap {b['tick']} (+{b['tick'] - a['tick']}{' FU' if b.get('follow_up') else ''})",
              f"fx {tl} (tap->fx +{tl[0] - b['tick']})" if tl else 'fx none',
              f"| impact - T start {last['tick'] + 1 - tl[0]}" if tl else '',
              f"| enemies <=2.5t of aim at T start {near(ft, 2.5) if ft else '-'} / <=5.5t {near(ft, 5.5) if ft else '-'};"
              f" at impact-1 <=2.5t {near(last, 2.5)}")
