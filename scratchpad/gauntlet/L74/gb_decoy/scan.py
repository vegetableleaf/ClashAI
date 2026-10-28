"""Scan live logs for opponent Goblin Barrel casts (evo pairs and plain), their landings and our responses.
Reads only public frame data (proj / ents / phase2 unit names) and our own decision / play events.
Never reads the opponent elixir estimate or hand."""
import json, glob, os, sys, re
from multiprocessing import Pool
from lowprio import low

GB = 28000004
LIVE = r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader'
TICK = re.compile(rb'"tick": (\d+)')


def scan(path):
    try:
        lines = open(path, 'rb').readlines()
    except OSError:
        return None
    if not lines or b'28000004' not in b''.join(lines[:]):
        return None
    start = json.loads(lines[0]) if lines[0].startswith(b'{"event": "start"') else {}
    my_side, projs, ents, names, evs, end = None, {}, {}, {}, [], None
    for line in lines:
        head = line[:40]
        if b'"frame"' in head:
            if my_side is None or b'28000004' in line:
                d = json.loads(line)
                if d.get('my_side') is not None:
                    my_side = d['my_side']
                if b'28000004' not in line or my_side is None:
                    continue
                t = d['tick']
                for p in d.get('proj') or []:
                    if p[3] == GB and p[0] != my_side:
                        r = projs.setdefault(p[7], dict(gen=p[7], first=t, start=(p[1], p[2]), tgt=(p[4], p[5]), pts=[]))
                        r['last'] = t
                        r['pts'].append((t, p[1], p[2], p[4], p[5]))
                gob = {}
                for u in ((d.get('phase2') or {}).get('units') or []):
                    gob[u['address']] = u.get('name')
                for e in d.get('ents') or []:
                    if e[3] == GB and e[0] != my_side:
                        r = ents.setdefault(e[7], dict(addr=e[7], first=t, xy=(e[1], e[2]), hp=e[4], maxhp=e[5], kind=e[6]))
                        r['last'] = t
                        if gob.get(e[7]):
                            r['name'] = gob[e[7]]
        elif b'"decision"' in head or b'"play"' in head or b'"confirmed"' in head or b'"unconfirmed"' in head:
            m = TICK.search(line[:60])
            evs.append((int(m.group(1)) if m else -1, line))
        elif b'"end"' in head:
            end = json.loads(line)
    return dict(file=os.path.basename(path), ckpt=os.path.basename(start.get('ckpt', '')),
                opts={k: (start.get('decision_options') or {}).get(k) for k in ('log_aim', 'barrel_lane', 'log_air')},
                my_side=my_side, projs=list(projs.values()), ents=list(ents.values()), evs=evs, end=end)


def casts(m):
    """Group barrel projectiles whose first sighting is within 4 ticks -> one cast."""
    ps = sorted(m['projs'], key=lambda r: r['first'])
    out = []
    for p in ps:
        if out and p['first'] - out[-1][0]['first'] <= 4:
            out[-1].append(p)
        else:
            out.append([p])
    return out


def landing(p, ents, used):
    """The goblin-barrel ents first seen near p's target within [last - 2, last + 12]."""
    tx, ty = p['tgt']
    got = [e for e in ents if e['addr'] not in used and p['last'] - 2 <= e['first'] <= p['last'] + 12
           and abs(e['xy'][0] - tx) <= 2000 and abs(e['xy'][1] - ty) <= 2000]
    for e in got:
        used.add(e['addr'])
    return got


def to_my(x, y, side):
    x, y = x / 18000, y / 32000
    return (x, 1 - y) if side == 0 else (1 - x, y)


def summarize(m):
    rows = []
    used = set()
    decs = []
    for t, line in m['evs']:
        decs.append((t, line))
    for c in casts(m):
        t0 = c[0]['first']
        tl = max(p['last'] for p in c)
        lands = [landing(p, m['ents'], used) for p in c]
        resp = []
        for t, line in decs:
            if t0 - 2 <= t <= tl + 60:
                d = json.loads(line)
                ev = d['event']
                if ev == 'decision':
                    dd = d['decision']
                    if not dd.get('play'):
                        continue
                    mp = [r for r in (d.get('public') or {}).get('model_projectiles') or []]
                    resp.append(dict(ev='decision', tick=t, name=dd.get('name'), xy=dd.get('xy'), why=dd.get('why'),
                                     forced=d.get('forced'), mp=mp))
                elif ev == 'play':
                    resp.append(dict(ev='play', tick=t, name=d.get('name'), xy=d.get('xy'), forced=d.get('forced'),
                                     why=d.get('why')))
                elif ev == 'confirmed':
                    resp.append(dict(ev='confirmed', tick=t, name=d.get('name'), intended=d.get('intended')))
        rows.append(dict(file=m['file'], ckpt=m['ckpt'], opts=m['opts'], my_side=m['my_side'], t0=t0, t_land=tl,
                         projs=[dict(gen=p['gen'], first=p['first'], last=p['last'], start=p['start'], tgt=p['tgt'],
                                     tgt_my=to_my(*p['tgt'], m['my_side']), n=len(p['pts'])) for p in c],
                         lands=[[dict(name=e.get('name'), maxhp=e['maxhp'], kind=e['kind'], first=e['first'],
                                      xy_my=to_my(*e['xy'], m['my_side'])) for e in L] for L in lands],
                         resp=resp, won=(m['end'] or {}).get('towers', {}).get('won')))
    return rows


def work(path):
    m = scan(path)
    return summarize(m) if m else []


if __name__ == '__main__':
    pat = sys.argv[1]
    outp = sys.argv[2]
    files = sorted(glob.glob(os.path.join(LIVE, pat)))
    files = [f for f in files if os.path.getsize(f) > 0]
    print(len(files), 'files', flush=True)
    n = 0
    low()
    with Pool(3, initializer=low) as pool, open(outp, "w") as out:
        for rows in pool.imap(work, files, chunksize=4):
            for r in rows:
                out.write(json.dumps(r) + '\n'); n += 1
    print('casts', n)
