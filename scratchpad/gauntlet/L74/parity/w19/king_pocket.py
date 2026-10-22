"""W18 lead (1): is the SIM's OWN KING damage after our princess falls a fight-parity error? From J1 fight outputs (each fight
restarts from the live board, so this isolates the engine from opponent placement): every fight that starts after one of OUR
princess towers is down (fall tick read off the live frames) -> our king's damage in the window, live vs SIM (sim[0]).
  python king_pocket.py LIVE_DIR RUN_DIR [RUN_DIR ...]
Reports all fights and the J1 strict-clean ones: sum SIM / sum live [match-bootstrap CI], fights with king damage live only /
SIM only, per-fight agreement within max(100, 10%), by opponent anchor card; the same for the standing princess."""
import glob
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402


def falls(path, side):
    """{'L': tick, 'R': tick} our princess fall ticks: the first frame at hp <= 0 on that slot, or the first frame after its
    row was last seen (a destroyed tower's row leaves the frames) when that is > 40 ticks before the last frame."""
    out, last, ticks = {}, {}, []
    with open(path, 'rb') as f:
        for raw in f:
            if b'"frame"' not in raw[:40]:
                continue
            j = json.loads(raw)
            ticks.append(j['tick'])
            for s_, x, y, cid, hp, mx, kind, addr in j['ents']:
                if cid != -1 or s_ != side or abs(x - 9000) < 1000:
                    continue
                if any(abs(x - tx) < 600 and abs(y - ty) < 600 for tx, ty in F.TOWER_SLOTS):
                    k = 'L' if x < 9000 else 'R'
                    if hp <= 0:
                        out.setdefault(k, j['tick'])
                    else:
                        last[k] = j['tick']
    for k, t in last.items():
        nxt = [u for u in ticks if u > t]
        if k not in out and nxt and ticks[-1] - t > 40:
            out[k] = nxt[0]
    return out


def boot(rows, B=2000):
    by = defaultdict(list)
    for r in rows:
        by[r[0]].append(r)
    ms, rng, v = sorted(by), random.Random(0), []
    for _ in range(B):
        xs = [r for m in rng.choices(ms, k=len(ms)) for r in by[m]]
        sl = sum(r[1] for r in xs)
        v.append(sum(r[2] for r in xs) / sl if sl else float('nan'))
    v.sort()
    return v[int(.025 * B)], v[int(.975 * B) - 1]


live_dir = Path(sys.argv[1])
rows = {'all': [], 'strict': []}
prow = {'all': [], 'strict': []}
by_card = defaultdict(lambda: [0, 0, 0])
n_m = 0
for run in sys.argv[2:]:
    for p in sorted(glob.glob(run + '/matches/*.json')):
        d = json.load(open(p, encoding='utf-8'))
        s = d['summary']
        if s.get('skipped'):
            continue
        side = s['side']
        fl = falls(live_dir / (s['match'] + '.jsonl'), side)
        if not fl:
            continue
        n_m += 1
        t_fall = min(fl.values())
        standing = {'L', 'R'} - set(fl)
        for r in d['fights']:
            if 'error' in r or r['t0'] < t_fall or 'towers' not in r:
                continue
            k = r['towers'].get(f'T{side}K')
            if k is None:
                continue
            row = (s['match'], k['live'], k['sim'], r['anchor']['name'], r['own'])
            modes = ['all'] + (['strict'] if F.is_clean(r, 'strict') else [])
            for mo in modes:
                rows[mo].append(row)
                for sl in standing:
                    pt = r['towers'].get(f'T{side}{sl}')
                    if pt and r['t0'] < fl.get(sl, 10 ** 9):
                        prow[mo].append((s['match'], pt['live'], pt['sim']))
            if not r['own'] and (k['live'] or k['sim']):
                c = by_card[r['anchor']['name']]
                c[0] += 1; c[1] += k['live']; c[2] += k['sim']
print(f'matches with our princess down: {n_m}')
for mo in ('all', 'strict'):
    rs = rows[mo]
    hit = [r for r in rs if r[1] or r[2]]
    agree = sum(abs(r[1] - r[2]) <= max(100, .1 * max(r[1], r[2])) for r in hit)
    sl, ss = sum(r[1] for r in rs), sum(r[2] for r in rs)
    lo, hi = boot(hit) if hit else (float('nan'), float('nan'))
    print(f'[{mo}] fights after our princess fell: {len(rs)}; with own-king damage live or SIM: {len(hit)} '
          f'(live only {sum(r[1] > 0 and r[2] == 0 for r in hit)}, SIM only {sum(r[2] > 0 and r[1] == 0 for r in hit)}); '
          f'king hp lost live {sl} SIM {ss} -> SIM/live {ss / sl if sl else float("nan"):.3f} [{lo:.3f}, {hi:.3f}]; '
          f'per-fight within max(100,10%): {agree}/{len(hit)}')
    ph = [r for r in prow[mo] if r[1] or r[2]]
    if ph:
        plo, phi = boot(ph)
        print(f'   standing princess in the same fights: SIM/live {sum(r[2] for r in ph) / max(1, sum(r[1] for r in ph)):.3f} '
              f'[{plo:.3f}, {phi:.3f}] over {len(ph)} fights')
print('opp anchor | fights with king damage | live hp | SIM hp | SIM/live')
for c, (n, l, s_) in sorted(by_card.items(), key=lambda kv: -kv[1][1] - kv[1][2])[:20]:
    print(f'{c} | {n} | {l} | {s_} | {s_ / l if l else float("nan"):.2f}')
