"""Numbers for the report from press_rows.json + button_rows.json + inventory.json. Prints; also writes summary.json."""
import json, statistics as stx
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / 'press_rows.json').read_text())
B = json.loads((HERE / 'button_rows.json').read_text())
INV = {m['log']: m for m in json.loads((HERE / 'inventory.json').read_text())}
OUT = {}


def q(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = lambda p: xs[min(len(xs) - 1, int(p * (len(xs) - 1) + .5))]  # noqa: E731
    return {'n': len(xs), 'p25': k(.25), 'med': k(.5), 'p75': k(.75), 'mean': round(sum(xs) / len(xs), 3)}


def pct(a, b):
    return f'{a}/{b} = {100 * a / b:.1f}%' if b else f'{a}/0'


def vbin(r):
    if r['kind'] != 'iw_clump':
        return 'wincon'
    v = r.get('rule_value') or 0
    return 'clump v4-5' if v < 5 else 'clump v5-7' if v < 7 else 'clump v7+'


for mark in ('CXXXVIII', 'CXXIV'):
    rows = [r for r in R if r['mark'] == mark]
    logs = [l for l, m in INV.items() if m.get('mark') == mark and m['frames'] >= 500]
    deploys = sum(1 for l in logs for e in INV[l]['events'] if e['event'] == 'confirmed')
    S = OUT[mark] = {}
    print(f'\n===== Mark {mark}: {len(logs)} matches, {deploys} IW deploys, {len(rows)} presses '
          f'({len(rows) / len(logs):.2f}/match, {100 * len(rows) / deploys:.1f}% of deploys)')
    S['matches'], S['deploys'], S['presses'] = len(logs), deploys, len(rows)
    print('why:', Counter(r['kind'] for r in rows))
    print('truth at the press frame:', Counter(r.get('truth') for r in rows))
    print('rule hero body:', Counter(r.get('rule_hero_name') for r in rows))
    print('n own IW bodies:', Counter(r.get('n_own_iw') for r in rows))
    ok = [r for r in rows if r.get('truth') == 'ready' and 'iw_pos' in r]
    print('rule target is a building:', pct(sum(r['rule_target_is_building'] for r in ok), len(ok)))
    print('no IW-marked enemy at the press (game has no target yet -> Pending):', pct(sum(r['n_marked'] == 0 for r in ok), len(ok)))
    print('rule target == game target (closest IW-marked enemy):', pct(sum(r['rule_target_eq_game'] for r in ok), len(ok)))
    print('effect state after the press:', Counter(r.get('effect_state') for r in ok))
    lat = [(r['effect_tick'] - r['tick']) / 20 for r in ok if r.get('effect_tick')]
    print('press -> state change (s):', q(lat))
    cube = [r for r in ok if r.get('cube_tick')]
    print('IceCube appeared in window:', pct(len(cube), len(ok)),
          '| no cube & window truncated by match end:', sum(1 for r in ok if not r.get('cube_tick') and r['truncated']))
    print('press -> cube (s):', q([(r['cube_tick'] - r['tick']) / 20 for r in cube]))
    pend = [r for r in ok if r.get('effect_state') == 7]
    print('pending presses: press -> cube (s):', q([(r['cube_tick'] - r['tick']) / 20 for r in pend if r.get('cube_tick')]),
          'never fired in window:', sum(1 for r in pend if not r.get('cube_tick')))
    print('cube distance to IW at press (t):', q([r['cube_dist_iw'] for r in cube]))
    print('cube distance to rule target at press (t):', q([r['cube_dist_rule_target'] for r in cube if r.get('cube_dist_rule_target') is not None]))
    print('rule target distance to IW (t):', q([r['rule_target_dist_iw'] for r in ok if r.get('rule_target_dist_iw') is not None]))
    print('age at press (logged, s):', q([r['age_logged'] for r in rows]))
    gens = Counter((r['log'], r.get('iw_gen')) for r in rows if r.get('iw_gen'))
    print('IW bodies pressed more than once:', sum(1 for v in gens.values() if v > 1))
    # ---- outcomes
    print('--- outcomes (presses whose IW was really ready; window', 'to +16 s)')
    groups = defaultdict(list)
    for r in ok:
        groups[vbin(r)].append(r)
        groups['ALL'].append(r)
    S['outcome'] = {}
    for g in ('ALL', 'wincon', 'clump v4-5', 'clump v5-7', 'clump v7+'):
        rs = groups.get(g, [])
        if not rs:
            continue
        nf = [r['n_frozen'] for r in rs]
        zero = sum(1 for r in rs if r['n_frozen'] == 0 and not r['truncated'])
        fz = [f for r in rs for f in r['frozen'].values()]
        d = {'presses': len(rs), 'zero_frozen(not truncated)': zero,
             'bodies_frozen': q(nf), 'value_frozen': q([r['frozen_value'] for r in rs]),
             'rule_value': q([r.get('rule_value') for r in rs]),
             'rule_bodies': sum(r['n_rule_frozen'] for r in rs),
             'rule_bodies_frozen': sum(r['rule_bodies_actually_frozen'] for r in rs),
             'frozen_bodies': len(fz), 'frozen_died': sum(f['died'] for f in fz),
             'frozen_died_during_freeze_or_2s': sum(1 for f in fz if f['died'] and f['died_by'] <= 2),
             'frozen_value': round(sum(f['value'] for f in fz), 1),
             'frozen_value_died': round(sum(f['value'] for f in fz if f['died']), 1),
             'frozen_hit_tower_after': sum(f['hit_tower_after'] for f in fz),
             'freeze_s': q([f['freeze_s'] for f in fz]),
             'frozen_on_my_half': sum(f['on_my_half'] for f in fz),
             'own_tower_loss_16s': q([r['own_tower_loss'] for r in rs]),
             'elixir_at': q([r['elixir_at'] for r in rs]),
             'elixir_min_6s': q([r['elixir_min_6s'] for r in rs]),
             'noaff_any_6s': sum(1 for r in rs if r['noaff_6s'] > 0),
             'noaff_with_threat_6s': sum(1 for r in rs if r['noaff_threat_6s'] > 0),
             'head_n_near_iw(2.5t)': q([r['head_n_near_iw'] for r in rs]),
             'head_val_near_iw': q([r['head_val_near_iw'] for r in rs])}
        S['outcome'][g] = d
        print(f'  [{g}]', json.dumps(d))
    tops = Counter(f['name'] for r in ok for f in r['frozen'].values())
    print('  most-frozen units:', tops.most_common(12))
    tg = Counter(r.get('rule_target') for r in ok)
    print('  rule targets:', tg.most_common(12))
    # ---- button vs truth (ticks)
    tk = Counter()
    reads = Counter()
    blue = defaultdict(list)
    for l, b in B.items():
        if b['mark'] != mark:
            continue
        for k, v in b['ticks'].items():
            tk[k] += v
        for t, truth, bl, gr in b['ready_reads']:
            reads[truth] += 1
            blue[truth].append(bl)
    tot_ready = sum(v for k, v in tk.items() if k.startswith('ready|'))
    print('--- button: seconds by (reading|truth):', {k: round(v / 20) for k, v in sorted(tk.items())})
    print('  "ready" readings by truth:', dict(reads), '| blue by truth:', {k: q(v) for k, v in blue.items()})
    print('  share of "ready" time with NO own IW on board:', pct(tk['ready|no_iw'], tot_ready))
    print('  truth-ready time read as ready / stale / grey / absent:',
          {s: round(tk[f'{s}|ready'] / 20) for s in ('ready', 'stale', 'grey', 'absent')})
    # ---- no_affordable baseline: 6 s windows from IW-ready ticks with no press in [-2 s, +10 s]
    base_n = base_aff = 0
    for l, b in B.items():
        if b['mark'] != mark:
            continue
        pt = sorted(r['tick'] for r in rows if r['log'] == l)
        na = sorted((t, a) for t, a in b['noaff'])
        nt = [t for t, _ in na]
        for t in b['iw_ready_ticks'][::5]:
            if any(-40 <= t - p <= 200 for p in pt):
                continue
            seg = na[bisect_right(nt, t):bisect_right(nt, t + 120)]
            base_n += 1
            base_aff += any(a for _, a in seg)
    print(f'  baseline (IW ready, no press): 6 s windows with a no_affordable decision: {pct(base_aff, base_n)}')
    S['baseline_noaff'] = [base_aff, base_n]
(HERE / 'summary.json').write_text(json.dumps(OUT, indent=1, default=str))
