"""Live crown-tower-troop rates (ticket 10-17): which (tower, level) each side's princess slots are, per captured live match.

    python live_rates.py extract OUT.json                 (laptop: first frame of every p3_captures/*/run.json live log)
    python live_rates.py report  OUT.json TABLE.json      (TABLE = tower_table.py on the fork: {level: {name: max_hp}})

A princess-slot max_hp is matched EXACTLY (+-1, as diag_night/tesla/tower_hp.py) to one (tower, level) of the table;
no match -> 'unknown'. Ranked population = our princess slots 4424 (main account, fights.py OWN_PRINCESS_MAX)."""
import json, math, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAP, LOGS = ROOT/'icebow/data/p3_captures', ROOT/'scratchpad/gauntlet/L68/live_reader'
SLOTS = {(3500, 6500), (14500, 6500), (3500, 25500), (14500, 25500)}      # princess slots (fights.py TOWER_SLOTS)
OWN_MAIN = 4424


def first_frame(path):
    with open(path, 'rb') as f:
        for raw in f:
            if b'"frame"' in raw[:40]:
                return json.loads(raw)
    return None


def extract(out):
    rows = []
    for d in sorted(CAP.iterdir()):
        r = d/'run.json'
        if not r.is_file():
            rows.append(dict(capture=d.name, skipped='no run.json')); continue
        log = LOGS/json.loads(r.read_text())['live_log']
        j = first_frame(log) if log.is_file() else None
        if j is None:
            rows.append(dict(capture=d.name, skipped='no log' if not log.is_file() else 'no frame')); continue
        pr = {0: set(), 1: set()}
        for s, x, y, cid, hp, mx, kind, _ in j['ents']:
            if cid == -1 and any(abs(x-a) < 600 and abs(y-b) < 600 for a, b in SLOTS):
                pr[s].add(mx)
        rows.append(dict(capture=d.name, log=log.name, tick=j['tick'], my_side=j['my_side'],
                         own=sorted(pr[j['my_side']]), opp=sorted(pr[1-j['my_side']])))
    Path(out).write_text(json.dumps(rows, indent=0))
    print(len(rows), 'captures;', Counter(r.get('skipped', 'ok') for r in rows))


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'),)*2
    p = k/n; c = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/(1+z*z/n); m = (p + z*z/(2*n))/(1+z*z/n)
    return max(0.0, m-c), min(1.0, m+c)


def report(out, table):
    rows = [r for r in json.loads(Path(out).read_text()) if not r.get('skipped')]
    tab = json.loads(Path(table).read_text())

    def kind(hps):
        if len(hps) != 1:
            return 'unknown', None              # both slots must agree (one tower type per side)
        hits = [(n, int(lv)) for lv, r in tab.items() for n, v in r.items() if n != 'king' and abs(v - hps[0]) <= 1]
        return hits[0] if len(hits) == 1 else ('ambiguous' if hits else 'unknown', None)
    lines = []
    for label, sel in (('ALL captured', rows), ('RANKED main account (own princess 4424)', [r for r in rows if r['own'] == [OWN_MAIN]])):
        n = len(sel)
        opp, own = Counter(kind(r['opp'])[0] for r in sel), Counter(kind(r['own'])[0] for r in sel)
        lines.append(f'{label}: n = {n} matches')
        for side, c in (('OPPONENT', opp), ('OUR side', own)):
            for name in sorted(c, key=lambda k: -c[k]):
                lo, hi = wilson(c[name], n)
                lines.append(f'  {side:8s} {name:14s} {c[name]:4d}  {100*c[name]/n:5.1f}%  95% CI [{100*lo:.1f}, {100*hi:.1f}]')
            troops = sum(v for k, v in c.items() if k not in ('PrincessTower', 'unknown', 'ambiguous'))
            lo, hi = wilson(troops, n)
            lines.append(f'  {side:8s} any troop      {troops:4d}  {100*troops/n:5.1f}%  95% CI [{100*lo:.1f}, {100*hi:.1f}]')
    odd = [(r['capture'], r['own'], r['opp']) for r in rows if 'unknown' in (kind(r['own'])[0], kind(r['opp'])[0])
           or 'ambiguous' in (kind(r['own'])[0], kind(r['opp'])[0])]
    lines.append(f'unmatched / ambiguous princess-slot max_hp (capture, own, opp): {odd}')
    lines.append('own princess max_hp values: ' + str(Counter(tuple(r['own']) for r in rows).most_common()))
    print('\n'.join(lines))
    return lines


if __name__ == '__main__':
    {'extract': extract, 'report': report}[sys.argv[1]](*sys.argv[2:])
