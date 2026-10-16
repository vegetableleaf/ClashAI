"""S6 analysis of the collector output: python analyze.py out/*.jsonl.gz > analysis.txt

Buckets: A = first second after the fight start (dt <= 20 ticks) and the body was on the board at t0 (setup), so the SIM
state at that moment is the live state seeded by fights.py -> measures encoding (definitional) disagreement plus the
first 20 ticks of dynamics. B = later frames of every paired body = encoding + simulation divergence (parity).
Only frames with the two bodies within 0.25 tile ("aligned") are scored; the all-pairs numbers are given once.
"""
import collections
import gzip
import json
import statistics
import sys

from pathlib import Path
_d = json.loads((Path(__file__).resolve().parents[5] / 'research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json').read_text())
SIGHT = {c['name']: c.get('sight_range_milli') for c in _d['cards'] + _d['towers'] + _d['evolutions'] + _d['hero_forms']}
SIGHT |= {c['summon_character']: c.get('sight_range_milli') for c in _d['cards'] + _d['evolutions'] + _d['hero_forms'] if c.get('summon_character')}
RANGE = {c['name']: c.get('range_milli') for c in _d['cards'] + _d['towers'] + _d['evolutions'] + _d['hero_forms']}
RANGE |= {c['summon_character']: c.get('range_milli') for c in _d['cards'] + _d['evolutions'] + _d['hero_forms'] if c.get('summon_character')}
SIGHT_SLACK = 1500        # mt added to the sight range: target acquired while centre distance <= sight + 1500 (explore3 sweep)


CHARGERS = {c['name'] for c in _d['cards'] + _d['evolutions'] + _d['hero_forms'] if c.get('charge')} |     {c['summon_character'] for c in _d['cards'] + _d['evolutions'] + _d['hero_forms'] if c.get('charge') and c.get('summon_character')}


sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from pipeline.sim_unit_state import _all_buffs   # noqa: E402
_ROWS, _TOT = _all_buffs(_d)
SLOWNAMES = {n for n, b in _ROWS.items() if -100 < (b.get('speed_multiplier_raw') or 0) < 0 or -100 < (b.get('hit_speed_multiplier_raw') or 0) < 0}


def rule_sf(r):
    """Live slow_frac under the proposed live mapping: remaining_ms / the card table's full duration of the buff (the live
    reader's own duration field accumulates while an area keeps refreshing a buff, so rem/dur is not comparable there)."""
    best = None
    for n, rem, fr in r['lv']['bf']:
        if n in SLOWNAMES and rem < 900000:
            tot = _TOT.get(n) or (rem / fr if fr else None)
            if tot:
                best = max(best or 0, round(min(1.0, rem / tot), 3))
    return best


def rule_tg(r):
    """Live target after the proposed live mapping: a target farther than sight + slack is a default/path target, not acquired."""
    tg = r['lv']['tg']
    s = max(SIGHT.get(r['name']) or 0, RANGE.get(r['name']) or 0)      # acquisition reaches the sight range or, for a building, its range
    if tg is not None and s and r['lv'].get('td') is not None and r['lv']['td'] > s + SIGHT_SLACK:
        return None
    return tg


ORDER = ('stunned', 'frozen', 'slowed', 'raged', 'taunted', 'invisible', 'shielded')
ALIGN = 250


def load(paths):
    rows = []
    for p in paths:
        for l in gzip.open(p, 'rt'):
            r = json.loads(l)
            r['log'] = p.split('/')[-1][10:-9]
            rows.append(r)
    return rows


def pct(a, n):
    return f'{a / n:6.3f}' if n else '   n/a'


def rate(rows, f):
    n = a = 0
    for r in rows:
        v = f(r)
        if v is None:
            continue
        n += 1
        a += bool(v)
    return a, n


def line(name, A, B, f, extra=''):
    a1, n1 = rate(A, f)
    a2, n2 = rate(B, f)
    print(f'{name:44s} A {pct(a1, n1)} ({a1}/{n1})   B {pct(a2, n2)} ({a2}/{n2}) {extra}')


def conf(title, pairs, top=12):
    c = collections.Counter(pairs)
    n = sum(c.values())
    print(f'-- {title} (n={n})')
    for k, v in c.most_common(top):
        print(f'     {v:7d} {v / n:6.3f}  {k}')


def main(paths):
    rows = load(paths)
    b = [r for r in rows if r['k'] == 'b']
    print('logs', sorted({r['log'] for r in b}), 'fights', len({(r['log'], r['f']) for r in b}),
          'body-frames', len(b), 'aligned', sum(r['dist'] <= ALIGN for r in b))
    al = [r for r in b if r['dist'] <= ALIGN]
    A = [r for r in al if r['dt'] <= 20 and r['setup']]
    B = [r for r in al if not (r['dt'] <= 20 and r['setup'])]
    C = [r for r in al if r['lv']['cue']]
    As, Bs = [r for r in A if r['lv']['cue']], [r for r in B if r['lv']['cue']]          # buff cues known
    Ac, Bc = [r for r in As if r['lv'].get('at', True)], [r for r in Bs if r['lv'].get('at', True)]            # attack cues known (phase 3)
    nt = lambda rs: [r for r in rs if not r['tw']]
    tw = lambda rs: [r for r in rs if r['tw']]
    print(f'A rows {len(A)} (cue {len(Ac)}), B rows {len(B)} (cue {len(Bc)}); cue coverage {len(C)}/{len(al)}')

    print('\n== state ==')
    for nm, f in (('troops', nt), ('towers', tw)):
        line('state exact ' + nm, f(A), f(B), lambda r: r['lv']['st'] == r['sm']['st'])
    conf('state live->sim, troops, A', [(r['lv']['st'], r['sm']['st']) for r in nt(A)], 16)
    conf('state live->sim, troops, B', [(r['lv']['st'], r['sm']['st']) for r in nt(B)], 20)
    conf('state live->sim, towers, all', [(r['lv']['st'], r['sm']['st']) for r in tw(al)])
    sp = [r for r in al if r['lv']['raw'] in (3, 5, 6, 10) or r['sm']['st'] in ('jumping', 'tunnelling', 'casting')]
    conf('special states: (raw live state, live class, sim class, name)', [(r['lv']['raw'], r['lv']['st'], r['sm']['st'], r['name']) for r in sp], 20)
    conf('raw live state values (troops)', [r['lv']['raw'] for r in nt(al)], 15)

    print('\n== charging (live derived from 2-frame speed; compared where derivable) ==')
    chg = lambda rs: [r for r in rs if r['lv']['ch'] is not None and r['name'] in CHARGERS]
    line('charging bool, charger cards (live speed rule)', chg(A), chg(B), lambda r: r['lv']['ch'] == r['sm']['ch'])
    allm = lambda rs: [r for r in rs if r['lv']['ch'] is not None]
    line('charging bool, ALL moving troops (rule not restricted)', allm(A), allm(B), lambda r: r['lv']['ch'] == r['sm']['ch'])
    for nm in sorted({r['name'] for r in chg(al)}):
        conf('charging (live,sim) ' + nm, [(r['lv']['ch'], r['sm']['ch']) for r in chg(al) if r['name'] == nm], 4)
    conf('non-charger live-rule True by name', [r['name'] for r in allm(al) if r['lv']['ch'] and r['name'] not in CHARGERS], 6)
    sc = [r for r in nt(al) if r['name'] in CHARGERS and r['sm']['chf'] > 0]
    print(f'   SIM charge_frac > 0 on charger rows: {len(sc)}; SIM charging True {sum(r["sm"]["ch"] for r in sc)}')

    print('\n== Tesla hide ==')
    hd = lambda rs: [r for r in rs if r['lv']['hide'] is not None or r['sm']['hide'] is not None]
    conf('hide live->sim, A', [(r['lv']['hide'], r['sm']['hide']) for r in hd(A)])
    conf('hide live->sim, B', [(r['lv']['hide'], r['sm']['hide']) for r in hd(B)])

    print('\n== attack ==')
    line('hit_speed equal (cue rows)', Ac, Bc, lambda r: (r['lv']['hs'], r['sm']['hs']) and (r['lv']['hs'] == r['sm']['hs'] if r['lv']['hs'] and r['sm']['hs'] else None))
    conf('hit_speed live vs sim differing', [(r['name'], r['lv']['hs'], r['sm']['hs']) for r in Bc if r['lv']['hs'] and r['sm']['hs'] and r['lv']['hs'] != r['sm']['hs']], 8)
    line('target identical, all', Ac, Bc, lambda r: r['lv']['tg'] == r['sm']['tg'])
    busy = lambda rs: [r for r in rs if r['lv']['ph'] in ('windup', 'hit') or r['sm']['ph'] in ('windup', 'hit')]
    line('target identical, either side attacking', busy(Ac), busy(Bc), lambda r: r['lv']['tg'] == r['sm']['tg'])
    both = lambda rs: [r for r in rs if r['lv']['ph'] != 'idle' and r['sm']['ph'] != 'idle']
    line('target identical, both attacking', both(Ac), both(Bc), lambda r: r['lv']['tg'] == r['sm']['tg'])
    line('target identical, troops', nt(Ac), nt(Bc), lambda r: r['lv']['tg'] == r['sm']['tg'])
    line('target identical, towers', tw(Ac), tw(Bc), lambda r: r['lv']['tg'] == r['sm']['tg'])
    line('RULE target identical, all', Ac, Bc, lambda r: rule_tg(r) == r['sm']['tg'])
    line('RULE target identical, troops', nt(Ac), nt(Bc), lambda r: rule_tg(r) == r['sm']['tg'])
    line('RULE target identical, towers', tw(Ac), tw(Bc), lambda r: rule_tg(r) == r['sm']['tg'])
    line('RULE target identical, either attacking', busy(Ac), busy(Bc), lambda r: rule_tg(r) == r['sm']['tg'])
    line('RULE target identical, troops, live phase idle', [r for r in nt(Ac) if r['lv']['ph'] == 'idle'], [r for r in nt(Bc) if r['lv']['ph'] == 'idle'], lambda r: rule_tg(r) == r['sm']['tg'])
    line('phase bucket exact', Ac, Bc, lambda r: r['lv']['ph'] == r['sm']['ph'])
    line('phase exact, either attacking', busy(Ac), busy(Bc), lambda r: r['lv']['ph'] == r['sm']['ph'])
    line('idle-vs-active (hit|windup) agree', Ac, Bc, lambda r: (r['lv']['ph'] == 'idle') == (r['sm']['ph'] == 'idle'))
    line('progress_ms exact', Ac, Bc, lambda r: r['lv']['pg'] == r['sm']['pg'])
    line('progress_ms within 100', Ac, Bc, lambda r: abs(r['lv']['pg'] - r['sm']['pg']) <= 100)
    line('load_ms within 50', Ac, Bc, lambda r: abs(r['lv']['ld'] - r['sm']['ld']) <= 50)
    fr = lambda rs: [r for r in rs if r['lv']['fr'] is not None and r['sm']['fr'] is not None]
    wrap = lambda r: min(abs(r['lv']['fr'] - r['sm']['fr']), 1 - abs(r['lv']['fr'] - r['sm']['fr']))
    line('frac within 0.10 (both defined)', fr(Ac), fr(Bc), lambda r: wrap(r) <= .10)
    for nm, rs in (('A', fr(Ac)), ('B', fr(Bc))):
        d = [wrap(r) for r in rs]
        print(f'   frac |diff| median {statistics.median(d) if d else None}  p90 {sorted(d)[int(.9 * len(d))] if d else None}  n={len(d)}')
    conf('phase live->sim A', [(r['lv']['ph'], r['sm']['ph']) for r in Ac])
    conf('phase live->sim B', [(r['lv']['ph'], r['sm']['ph']) for r in Bc])
    conf('target presence (live set, sim set, live phase) A troops', [(r['lv']['tg'] is not None, r['sm']['tg'] is not None, r['lv']['ph']) for r in nt(Ac)], 10)
    conf('target presence (live set, sim set, live phase) A towers', [(r['lv']['tg'] is not None, r['sm']['tg'] is not None, r['lv']['ph']) for r in tw(Ac)], 10)

    print('\n== attack by attacker (rows where either side is attacking; A = first second, B = later) ==')
    names = collections.Counter(r['name'] for r in Bc if r['lv']['ph'] != 'idle' or r['sm']['ph'] != 'idle')
    for nm, n in names.most_common(14):
        ra = [r for r in Ac if r['name'] == nm and (r['lv']['ph'] != 'idle' or r['sm']['ph'] != 'idle')]
        rb = [r for r in Bc if r['name'] == nm and (r['lv']['ph'] != 'idle' or r['sm']['ph'] != 'idle')]
        f = lambda rs, g: pct(*rate(rs, g))
        fr_ = lambda rs: [r for r in rs if r['lv']['fr'] is not None and r['sm']['fr'] is not None]
        print(f'   {nm:26s} n_A {len(ra):4d} n_B {len(rb):5d} | phase A {f(ra, lambda r: r["lv"]["ph"] == r["sm"]["ph"])} B {f(rb, lambda r: r["lv"]["ph"] == r["sm"]["ph"])}'
              f' | progress==  A {f(ra, lambda r: r["lv"]["pg"] == r["sm"]["pg"])} B {f(rb, lambda r: r["lv"]["pg"] == r["sm"]["pg"])}'
              f' | frac<=.1 A {f(fr_(ra), lambda r: wrap(r) <= .1)} B {f(fr_(rb), lambda r: wrap(r) <= .1)}')

    print('\n== status ==')
    for i, k in enumerate(ORDER):
        line(f'status.{k}', As, Bs, lambda r: r['lv']['S'][i] == r['sm']['S'][i])
        tp = sum(1 for r in Bs if r['lv']['S'][i] and r['sm']['S'][i])
        fn = [r for r in Bs if r['lv']['S'][i] and not r['sm']['S'][i]]
        fp = [r for r in Bs if r['sm']['S'][i] and not r['lv']['S'][i]]
        print(f'     B live-true {tp + len(fn)}: both {tp}, live-only {len(fn)}, sim-only {len(fp)}')
        if fn:
            print('       live-only live buffs:', collections.Counter(tuple(sorted(x[0] for x in r['lv']['bf'])) for r in fn).most_common(4))
        if fp:
            print('       sim-only sim buffs:', collections.Counter(tuple(sorted(x[0] for x in r['sm']['bf'])) + (('stunned',) if k == 'stunned' else ()) for r in fp).most_common(4))
    sf = lambda rs: [r for r in rs if r['lv']['sf'] is not None and r['sm']['sf'] is not None]
    line('slow_frac within 0.15 (both defined)', sf(As), sf(Bs), lambda r: abs(r['lv']['sf'] - r['sm']['sf']) <= .15)
    d = [abs(r['lv']['sf'] - r['sm']['sf']) for r in sf(Bs)]
    print(f'   slow_frac |diff| median {statistics.median(d) if d else None} n={len(d)}')
    sr = lambda rs: [r for r in rs if rule_sf(r) is not None and r['sm']['sf'] is not None]
    line('RULE slow_frac (rem/table total) within 0.15', sr(As), sr(Bs), lambda r: abs(rule_sf(r) - r['sm']['sf']) <= .15)
    d = [abs(rule_sf(r) - r['sm']['sf']) for r in sr(Bs)]
    print(f'   RULE slow_frac |diff| median {statistics.median(d) if d else None} n={len(d)}')
    line('slow_frac presence (live set == sim set)', As, Bs, lambda r: (r['lv']['sf'] is None) == (r['sm']['sf'] is None))
    conf('live buff names (all cue rows)', [x[0] for r in C for x in r['lv']['bf']], 20)
    conf('sim buff names (all cue rows)', [x[0] for r in C for x in r['sm']['bf']], 20)

    print('\n== projectiles (live ids; weapon shots = live projectiles whose card is not a spell; frames >= 40 ticks after the fight start) ==')
    P = [r for r in rows if r['k'] == 'p' and r['dt'] >= 40]
    wl = lambda r: [p for p in r['live'] if p.get('ct') != 'spell']
    for nm, key in (('(src,tgt)', lambda p: (p['src'], p['tgt'])), ('src only', lambda p: p['src'])):
        nl = ns = nm_ = fe = 0
        for r in P:
            lk = collections.Counter(key(p) for p in wl(r))
            sk = collections.Counter(key(p) for p in r['sim'])
            nl += sum(lk.values()); ns += sum(sk.values()); nm_ += sum((lk & sk).values())
            fe += lk == sk
        print(f'   weapon shots {nm}: frames {len(P)}, live {nl}, sim {ns}, matched {nm_}, precision {pct(nm_, ns)}, '
              f'recall {pct(nm_, nl)}, frames with identical multiset {pct(fe, len(P))}')
    # +-1 frame (2 ticks) tolerance on presence: a shot of the same (source, target) in the other side's neighbouring frame
    byf = collections.defaultdict(dict)
    for r in P:
        byf[(r['log'], r['f'])][r['dt']] = r
    hit_l = tot_l = hit_s = tot_s = 0
    for fr_ in byf.values():
        for dt, r in fr_.items():
            near = [fr_.get(dt + k) for k in (-2, 0, 2)]
            sk = {(p['src'], p['tgt']) for q in near if q for p in q['sim']}
            lk = {(p['src'], p['tgt']) for q in near if q for p in wl(q)}
            for p in wl(r):
                tot_l += 1; hit_l += (p['src'], p['tgt']) in sk
            for p in r['sim']:
                tot_s += 1; hit_s += (p['src'], p['tgt']) in lk
    print(f'   weapon shots (src,tgt) with +-1 frame tolerance: live shot found in SIM {pct(hit_l, tot_l)} ({hit_l}/{tot_l}); SIM shot found in live {pct(hit_s, tot_s)} ({hit_s}/{tot_s})')
    kind = lambda s: 'none' if s is None else ('tower' if str(s).startswith('T') else 'troop')
    for k in ('tower', 'troop', 'none'):
        nl = sum(1 for r in P for p in wl(r) if kind(p['src']) == k)
        ns = sum(1 for r in P for p in r['sim'] if kind(p['src']) == k)
        print(f'   {k} sources: live shots {nl}, sim shots {ns}')
    d = []
    for r in P:
        S = collections.defaultdict(list)
        for p in r['sim']:
            S[(p['src'], p['tgt'])].append(p)
        for p in wl(r):
            q = S.get((p['src'], p['tgt']))
            if q:
                d.append(min(((p['x'] - z['x']) ** 2 + (p['y'] - z['y']) ** 2) ** .5 for z in q))
    if d:
        d.sort()
        print(f'   matched-pair position error (mt): median {d[len(d) // 2]:.0f}, p90 {d[int(.9 * len(d))]:.0f}, n={len(d)}')
    conf('live weapon shot target is None', [p['tgt'] is None for r in P for p in wl(r)], 3)
    conf('sim shot target is None', [p['tgt'] is None for r in P for p in r['sim']], 3)
    conf('sim projectile types', [p['type'] for r in P for p in r['sim']], 12)
    conf('live spell projectiles (name, src kind)', [(p.get('cn'), kind(p['src'])) for r in P for p in r['live'] if p.get('ct') == 'spell'], 12)
    conf('live weapon shots by shooter card', [p.get('cn') for r in P for p in wl(r)], 12)
    conf('sim shots by projectile type', [p['type'] for r in P for p in r['sim']], 12)
    PA = [r for r in rows if r['k'] == 'p' and r['dt'] <= 20]
    print(f'   A (dt<=20; the SIM starts with no shot in flight): live weapon shots {sum(len(wl(r)) for r in PA)}, sim shots {sum(len(r["sim"]) for r in PA)}')

    print('\n== areas (live fx rows vs SIM Pulsing areas) and spells in the air (live spell projectiles vs SIM non-Pulsing areas) ==')
    PR = {(r['log'], r['f'], r['dt']): r for r in rows if r['k'] == 'p'}
    for nm, sel in (('A', lambda r: r['dt'] <= 20), ('B', lambda r: r['dt'] > 20)):
        P = [r for r in rows if r['k'] == 'a' and sel(r)]
        eqs = eqf = 0
        rem = []
        for r in P:
            eqs += sorted(a['name'] for a in r['live']) == sorted(a['name'] for a in r['sim'] if a['motion'] == 'Pulsing')
            pr = PR.get((r['log'], r['f'], r['dt']))
            eqf += sorted(p['cn'] or '' for p in pr['live'] if p.get('ct') == 'spell') == sorted(a['name'] for a in r['sim'] if a['motion'] != 'Pulsing')
            for a in r['live']:
                c = [z for z in r['sim'] if z['name'] == a['name'] and z['motion'] == 'Pulsing' and z['rem'] is not None]
                if c and a['rem'] is not None and a['rem'] < 900000:
                    z = min(c, key=lambda z: (z['x'] - a['x']) ** 2 + (z['y'] - a['y']) ** 2)
                    if ((z['x'] - a['x']) ** 2 + (z['y'] - a['y']) ** 2) ** .5 < 1500:
                        rem.append(abs(z['rem'] - a['rem']))
        rem.sort()
        print(f'   {nm}: frames {len(P)}, static-area name multiset equal {pct(eqs, len(P))}, in-air spell multiset equal {pct(eqf, len(P))}, '
              f'remaining_ms |diff| median {rem[len(rem) // 2] if rem else None} p90 {rem[int(.9 * len(rem))] if rem else None} n={len(rem)}')
    conf('live fx names', [a['name'] for r in rows if r['k'] == 'a' for a in r['live']], 12)
    conf('sim Pulsing area names', [a['name'] for r in rows if r['k'] == 'a' for a in r['sim'] if a['motion'] == 'Pulsing'], 12)
    conf('sim in-air area (name, motion)', [(a['name'], a['motion']) for r in rows if r['k'] == 'a' for a in r['sim'] if a['motion'] != 'Pulsing'], 8)
    conf('live in-air spell projectiles', [p.get('cn') for r in rows if r['k'] == 'p' for p in r['live'] if p.get('ct') == 'spell'], 8)


if __name__ == '__main__':
    main(sys.argv[1:])
