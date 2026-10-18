"""Where does the freeze land, and which press-time board feature predicts what it freezes?

For every truth-ready press (press_rows.json): the game's real target (the enemy whose x equals the IceCube's x at the
moment the cube spawned), the cube's offset from it, and four press-time 'value inside 2.5 tiles' features:
  head  = around the Ice Wizard (the B6 head's radius feature, _ability_head_features),
  rule  = around the rule's target (nearest enemy to the IW, hero_button),
  cube0 = around the predicted cube point: closest IW-marked enemy (IceWizardHeroCold/Slow) shifted 1.5 t toward
          the enemy side (tables: PosY + (radius + 1000) * team_y_direction),
  cube1 = the same, with every enemy moved along its last-0.5 s velocity for the 1.4 s press->cube latency.
Spearman rank correlation of each with the value actually frozen. Out: features_rows.json + printout."""
import json, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit                                                             # noqa: E402

R = [r for r in json.loads((HERE / 'press_rows.json').read_text()) if r.get('truth') == 'ready' and r.get('iw_pos')]
INV = {m['log']: m for m in json.loads((HERE / 'inventory.json').read_text())}
LAT = 28                                                                 # ticks: press -> cube median (1.4 s)


def rank(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** .5
    vb = sum((y - mb) ** 2 for y in rb) ** .5
    return round(cov / (va * vb), 3) if va and vb else None


def troops(fr, side):
    return [e for e in fr['ents'] if e['side'] != side and e['kind'] not in (12, 13) and int(e['card_id']) >= 0
            and audit.NAMES.get(int(e['card_id']), '') not in audit.BUILDINGS]


def value_in(es, c, r=2.5):
    return sum(audit.VAL.get(audit.NAMES.get(int(e['card_id']), ''), audit.UNKNOWN) for e in es
               if audit.tiles((e['x'], e['y']), c) <= r)


out = []
by_log = {}
for r in R:
    by_log.setdefault(r['log'], []).append(r)
for li, (log, rs) in enumerate(by_log.items()):
    m = INV[log]
    side = m['side']
    toward_enemy = -1 if side == 1 else 1                               # my half y > 16000 iff side 1
    _, frames, _, _ = audit.scan(m)
    ticks = sorted(frames)
    for r in rs:
        P = r['tick']
        f0 = frames[max(t for t in ticks if t <= P)]
        fp = frames.get(max((t for t in ticks if t <= P - 10), default=ticks[0]))
        iw = tuple(r['iw_pos'])
        foes = troops(f0, side)
        prev = {e['category']: e for e in troops(fp, side)} if fp else {}
        dt = max(1, f0['tick'] - fp['tick']) if fp else 1
        moved = []
        for e in foes:
            p = prev.get(e['category'])
            vx, vy = ((e['x'] - p['x']) / dt, (e['y'] - p['y']) / dt) if p else (0, 0)
            moved.append(dict(e, x=e['x'] + vx * LAT, y=e['y'] + vy * LAT))
        U = f0['units']
        marked = [e for e in foes if any(b in ('IceWizardHeroCold', 'IceWizardHeroSlow') for b in U.get(e['category'], ('', 0, []))[2])]
        tgt = min(marked, key=lambda e: audit.tiles((e['x'], e['y']), iw)) if marked else None
        rt = next((e for e in f0['ents'] if e['category'] == r.get('rule_target_gen')), None)
        row = {'mark': r['mark'], 'log': log, 'tick': P, 'kind': r['kind'], 'rule_value': r.get('rule_value'),
               'frozen_value': r['frozen_value'], 'n_frozen': r['n_frozen'], 'truncated': r['truncated'],
               'head': value_in(foes, iw), 'rule': value_in(foes, (rt['x'], rt['y'])) if rt else 0.0,
               'marked_at_press': len(marked)}
        if tgt:
            c0 = (tgt['x'], tgt['y'] + toward_enemy * 1500)
            row['cube0'] = value_in(foes, c0)
            mt = next(e for e in moved if e['category'] == tgt['category'])
            c1 = (mt['x'], mt['y'] + toward_enemy * 1500)
            row['cube1'] = value_in(moved, c1)
        else:
            row['cube0'] = row['cube1'] = 0.0
        # the real target: the enemy sharing the cube's x at the cube tick (the table copies PosX exactly)
        if r.get('cube_tick'):
            cx, cy = r['cube_pos']
            reg = [t for t in ticks if r['tick'] < t <= r['cube_tick']]
            best = None
            for t in reversed(reg):
                for e in troops(frames[t], side):
                    if abs(e['x'] - cx) <= 60:
                        dy = (cy - e['y']) * toward_enemy / 1000       # + = cube placed toward the ENEMY side of it
                        if 0 <= dy <= 3.5 and (best is None or abs(dy - 1.5) < abs(best[1] - 1.5)):
                            best = (e['category'], dy, t)
                if best:
                    break
            if best:
                row['real_target_gen'], row['cube_offset_t'] = best[0], round(best[1], 2)
                row['real_eq_rule'] = best[0] == r.get('rule_target_gen')
                row['real_eq_marked_closest'] = bool(tgt and best[0] == tgt['category'])
            row['cube_y_from_my_tower_t'] = round(abs(cy - (25500 if side == 1 else 6500)) / 1000, 2)
            row['cube_on_my_half'] = (cy > 16000) == (side == 1)
        out.append(row)
    print(li, len(by_log), file=sys.stderr, flush=True) if li % 40 == 0 else None
(HERE / 'features_rows.json').write_text(json.dumps(out))

full = [x for x in out if not x['truncated']]
for mark in ('CXXXVIII', 'CXXIV', None):
    xs = [x for x in full if mark is None or x['mark'] == mark]
    fv = [x['frozen_value'] for x in xs]
    print(f'\n== {mark or "both"}: {len(xs)} presses (not truncated)')
    for k in ('head', 'rule', 'cube0', 'cube1'):
        v = [x[k] for x in xs]
        print(f'  {k:5s} press-time value in 2.5 t: median {sorted(v)[len(v) // 2]:.1f}  zero in {sum(a == 0 for a in v)}'
              f'  Spearman vs frozen value {spearman(v, fv)}  vs bodies frozen {spearman(v, [x["n_frozen"] for x in xs])}')
    tg = [x for x in xs if 'real_target_gen' in x]
    print('  real target identified:', len(tg), '| == rule target:', sum(x['real_eq_rule'] for x in tg),
          '| == closest IW-marked enemy at press:', sum(x['real_eq_marked_closest'] for x in tg))
    off = sorted(x['cube_offset_t'] for x in tg)
    print('  cube offset from its target toward the enemy side (t): p25/med/p75',
          off[len(off) // 4], off[len(off) // 2], off[3 * len(off) // 4])
    cy = sorted(x['cube_y_from_my_tower_t'] for x in xs if 'cube_y_from_my_tower_t' in x)
    print('  cube y-distance from my princess-tower line (t): p25/med/p75', cy[len(cy) // 4], cy[len(cy) // 2],
          cy[3 * len(cy) // 4], '| cube on my half:', sum(x.get('cube_on_my_half', False) for x in xs), '/', len(cy))
    print('  no IW-marked enemy at press:', sum(x['marked_at_press'] == 0 for x in xs))
