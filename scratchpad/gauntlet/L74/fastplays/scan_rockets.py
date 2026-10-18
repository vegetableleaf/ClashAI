"""Every Rocket of a checkpoint's live logs with the nearest Tornado (either order, within WIN ticks).
    python scan_rockets.py LOGDIR GLOB SHA8 [WIN]"""
import glob, json, os, sys

d, pat, sha8 = sys.argv[1:4]
win = int(sys.argv[4]) if len(sys.argv) > 4 else 250
for p in sorted(glob.glob(os.path.join(d, pat))):
    start, plays, end, sched = None, [], None, []
    with open(p, encoding='utf-8') as f:
        for s in f:
            if s.startswith('{"event": "frame"'):
                continue
            try:
                e = json.loads(s)
            except ValueError:
                continue
            ev = e.get('event')
            if ev == 'start':
                start = e
                if not str(e.get('ckpt_sha256', '')).startswith(sha8):
                    break
            elif ev == 'play':
                plays.append(e)
            elif ev == 'end':
                end = e
            elif ev and ev.startswith('follow_up'):
                sched.append(e)
    if not start or not str(start.get('ckpt_sha256', '')).startswith(sha8):
        continue
    out = (end or {}).get('outcome') or (end or {}).get('result') or '?'
    for a in plays:
        if a['name'] != 'Rocket':
            continue
        t = [b for b in plays if b['name'] == 'Tornado' and abs(b['tick'] - a['tick']) <= win]
        t.sort(key=lambda b: abs(b['tick'] - a['tick']))
        tor = t[0] if t else None
        print(os.path.basename(p)[10:25], f"R@{a['tick']} xy=({a['xy'][0]:.3f},{a['xy'][1]:.3f}) el={a.get('elixir', 0):.1f}",
              a.get('why', ''), (f"T@{tor['tick']} d={tor['tick'] - a['tick']:+d} xy=({tor['xy'][0]:.3f},{tor['xy'][1]:.3f})"
                                  f"{' FU' if tor.get('follow_up') else ''}") if tor else '-', out)
