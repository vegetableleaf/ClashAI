"""L74 combo (10-17): the combo-rule evaluation.
    python analyze_combo.py eval DIR [ARMS...]     DIR/<arm>_{741200,742000}/D3/matches.jsonl (combo_queue.sh; default arms cur new newh)
    python analyze_combo.py scen DIR [ARMS...]     DIR/scen_<arm>/matches.jsonl (scen_combo.sh; default arms cur new)
eval: wins / 960 and the paired win difference vs 'cur' (heroiw/validate.paired_drift: 10,000 bootstrap draws within census x side, 95 %
CI); per match: rule combos (the rocket_tornado play accepted) by order and board region, follow-ups fired / cancelled, lone-rule
Rockets, every Rocket / Tornado; per combo: the elixir value its Rocket took (spell_value tracker: killed + damaged share of each body's
value) and enemy tower damage, MISS = it took < 50 % of the value the rule expected the pull to gather (measure_shim's combo_rule value).
Region of the combo centre (board tiles, me at the bottom): enemy half y < 15 | bridge / river 15 <= y < 20 | my king y >= 20, 6 <= x <= 12
| my princess y >= 20 elsewhere. scen: per designed scenario, whether the rule fired, its order and gap, the Rocket's group damage."""
import collections
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'heroiw'))
GX, GY = 36, 64                                   # lattice (model_v3 GRID_X / GRID_Y)
SEEDS = (741200, 742000)
MATCH_TICKS = 40                                  # spell_value.PLAY_MATCH_TICKS: a Rocket seen this long after its play's landing


def load(p):
    p = Path(p)
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()] if p.is_file() else []


def slug(c):
    return ''.join(ch for ch in str(c).split('@')[0].lower() if ch.isalpha())


def xy(cell):
    return (cell % GX) * 18.0 / GX, (cell // GX) * 32.0 / GY


def region(cell):
    x, y = xy(cell)
    return 'enemy_half' if y < 15 else 'bridge' if y < 20 else 'my_king' if 6 <= x <= 12 else 'my_princess'


def combos(r):
    """-> [dict(order, region, cell, value_expected, hit, tower_dmg, princess, fired)] of one match row."""
    plays = sorted(r.get('own_plays_x') or [], key=lambda q: q[1])
    rule = {c['tick']: c for c in r.get('combo_rule') or []}
    events = (r.get('spell') or {}).get('events') or []
    out = []
    for i, q in enumerate(plays):
        if q[6] != 'rocket_tornado' or not q[3]:
            continue
        order = 'rocket' if slug(q[2]) == 'rocket' else 'tornado'
        rk = q if order == 'rocket' else next((p for p in plays[i + 1:] if slug(p[2]) == 'rocket' and p[6] == 'follow_up' and p[3]), None)
        ev = None if rk is None else next((e for e in events if rk[1] <= e['seen'] <= rk[1] + MATCH_TICKS), None)
        exp = min(rule.items(), key=lambda kv: abs(kv[0] - q[0]))[1].get('value') if rule else None
        hit = None if ev is None else float(ev['kill']) + float(ev['dmg'])
        out.append(dict(order=order, region=region(q[5]), cell=q[5], expected=exp, hit=hit, rocket=rk is not None,
                        tower_dmg=0 if ev is None else ev.get('tower_dmg', 0), princess=bool(ev and ev.get('princess')),
                        miss=hit is not None and exp is not None and hit < 0.5 * exp))
    return out


def per_match(rs):
    n = len(rs)
    c = [x for r in rs for x in combos(r)]
    cnt = collections.Counter()
    for r in rs:
        for q in r.get('own_plays_x') or []:
            if q[3]:
                cnt[slug(q[2])] += 1
                cnt['lone_rule'] += q[6] == 'rocket_value'
        for k, v in (r.get('follow_ups') or {}).items():
            cnt['fu_' + k] += v
    ev = [e for r in rs for e in (r.get('spell') or {}).get('events') or []]
    hits = [x['hit'] for x in c if x['hit'] is not None]
    return dict(n=n, combos=len(c), combos_pm=len(c) / n, by_order=dict(collections.Counter(x['order'] for x in c)),
                by_region=dict(collections.Counter(x['region'] for x in c)), with_rocket=sum(x['rocket'] for x in c),
                rocket_found=len(hits), hit_mean=statistics.mean(hits) if hits else None,
                expected_mean=statistics.mean([x['expected'] for x in c if x['expected'] is not None] or [float('nan')]),
                misses=sum(x['miss'] for x in c), tower_dmg_mean=statistics.mean([x['tower_dmg'] for x in c] or [float('nan')]),
                princess=sum(x['princess'] for x in c),
                rocket_pm=cnt['rocket'] / n, tornado_pm=cnt['tornado'] / n, lone_pm=cnt['lone_rule'] / n,
                fu={k[3:]: v for k, v in cnt.items() if k.startswith('fu_')},
                rocket_events=len(ev), rocket_value_mean=statistics.mean(float(e['kill']) + float(e['dmg']) for e in ev) if ev else None,
                region_hit={g: statistics.mean([x['hit'] for x in c if x['region'] == g and x['hit'] is not None] or [float('nan')])
                            for g in sorted({x['region'] for x in c})})


def evaluate(d, arms):
    from validate import paired_drift
    data = {a: [r for s in SEEDS for r in load(Path(d) / f'{a}_{s}' / 'D3' / 'matches.jsonl')] for a in arms}
    for a, rs in data.items():
        if not rs:
            continue
        w = sum(r['outcome'] == 'win' for r in rs)
        print(f'{a:5s} wins {w}/{len(rs)} ({100 * w / len(rs):.1f}%)')
    for a in arms[1:]:
        if len(data[a]) == 960 and len(data[arms[0]]) == 960:
            p = paired_drift(data[arms[0]], data[a], expected=960)
            print(f'  {a} - {arms[0]}: {p["delta_pp"]:+.2f} pp [{p["ci95_pp"][0]:+.2f}, {p["ci95_pp"][1]:+.2f}] '
                  f'({100 * p["old_win_rate"]:.1f} -> {100 * p["new_win_rate"]:.1f})')
    for a, rs in data.items():
        if rs:
            m = per_match(rs)
            print(f'\n{a}: ' + json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()}))
    for a in arms[1:]:                                       # where the arms played differently: matches whose rows differ
        old = {(r['census'], r['seed']): r for r in data[arms[0]]}
        diff = [r for r in data[a] if old.get((r['census'], r['seed']), {}).get('end_tick') != r.get('end_tick')]
        flips = collections.Counter((old[(r['census'], r['seed'])]['outcome'], r['outcome']) for r in diff if (r['census'], r['seed']) in old)
        print(f'\n{a} vs {arms[0]}: {len(diff)} matches played out differently; outcome changes {dict(flips)}')


def scen(d, arms):
    print('arm  scenario         n  combo%  order(R/T)  gap(T-R) median  lone%  R group dmg  group hp lost  enemy tower dmg')
    for a in arms:
        rs = [r for r in load(Path(d) / f'scen_{a}' / 'matches.jsonl') if r.get('skipped') == 'scenario']
        by = collections.defaultdict(list)
        for r in rs:
            by[r['scenario']].append(r)
        for name, xs in by.items():
            fired, order, gaps, lone, rdmg = 0, collections.Counter(), [], 0, []
            for r in xs:
                ps = [p for p in r['plays'] if p['acc']]
                first = next((p for p in ps if p['why'] == 'rocket_tornado'), None)
                lone += any(p['why'] == 'rocket_value' for p in ps)
                if first:
                    fired += 1
                    order[first['card'][0].upper()] += 1
                    R = next((p for p in ps if p['card'] == 'rocket' and p['land'] >= first['land']), None)
                    T = next((p for p in ps if p['card'] == 'tornado' and p['land'] >= first['land']), None)
                    if R and T:
                        gaps.append(T['land'] - R['land'])
                if r['rockets']:
                    rdmg.append(r['rockets'][0].get('group_hp_drop', 0))
            n = len(xs)
            g = sorted(gaps)
            print(f'{a:4s} {name:15s} {n:3d}  {100 * fired / n:5.0f}   {dict(order)!s:11s} {str(g[len(g) // 2]) if g else "-":>6s}'
                  f' ({min(g) if g else "-"}..{max(g) if g else "-"})  {100 * lone / n:4.0f}  '
                  f'{statistics.mean(rdmg) if rdmg else 0:8.0f} ({len(rdmg)})  '
                  f'{statistics.mean(r["group_hp0"] - r["group_hp_end"] for r in xs):8.0f}  '
                  f'{statistics.mean(r["etowers0"] - r["etowers_end"] for r in xs):8.0f}')


if __name__ == '__main__':
    mode, d = sys.argv[1], sys.argv[2]
    if mode == 'eval':
        evaluate(d, sys.argv[3:] or ['cur', 'new', 'newh'])
    else:
        scen(d, sys.argv[3:] or ['cur', 'new'])
