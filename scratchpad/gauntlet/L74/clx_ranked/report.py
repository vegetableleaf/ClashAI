"""W13 tables: CLX's live record, crown paths vs the SIM, overtime, opponent decks, loss clusters, CPU starvation.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/clx_ranked/report.py > scratchpad/gauntlet/L74/clx_ranked/report.out
Reads rows.json (anatomy.py) and sim_rows.json (sim.py).  Labels: every number here is MEASURED on these rows; CIs are Wilson
95% (rates) and Newcombe 95% (differences); the chip attribution is a proxy (anatomy.chip_sources)."""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import anatomy as AN  # noqa: E402

rows = json.load(open(HERE / 'rows.json'))
sim = json.load(open(HERE / 'sim_rows.json'))
S = {'ranked': [r for r in rows if r['sample'] == 'ranked'], 'ladder': [r for r in rows if r['sample'] == 'ladder'],
     'sim_w12': [r for r in sim if r['set'] == 'w12'], 'sim_e4': [r for r in sim if r['set'] == 'e4']}
fmt = AN.fmt
OFFZ = ('xbow_bridge', 'xbow_pocket', 'rocket_tower', 'offence')


def newcombe(k1, n1, k2, n2):
    p1, l1, u1 = AN.wilson(k1, n1)
    p2, l2, u2 = AN.wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def pp(t):
    d, lo, hi = t
    return f'{100 * d:+5.1f} [{100 * lo:+5.1f}, {100 * hi:+5.1f}]'


def wins(x):
    return sum(r['win'] == 1 for r in x)


def h(title):
    print('\n## ' + title)


# ------------------------------------------------------------------------------------------------------------------ record
h('T1 record')
for k, x in S.items():
    print(f'{k:8s} {wins(x):4d} W / {sum(r["win"] == 0 for r in x):4d} L / {sum(r["win"] == .5 for r in x)} D   win {fmt(wins(x), len(x))}')
rk = S['ranked']
print('ranked span', min(r['ts'] for r in rk), '..', max(r['ts'] for r in rk))
for lab, f in (('ranked 10-20 13:28-17:59', lambda r: r['ts'] < '20261020_180000'),
               ('ranked 10-20 18:00-21:59', lambda r: '20261020_180000' <= r['ts'] < '20261020_220000'),
               ('ranked 10-20 22:00-10-21 07:10', lambda r: r['ts'] >= '20261020_220000')):
    y = [r for r in rk if f(r)]
    print(f'  {lab:32s} {fmt(wins(y), len(y))}')

# ------------------------------------------------------------------------------------------------------------- crown path
h('T2 crown path (exclusive; share of ALL matches) -- live vs SIM')
PATHS = ['win_clean', 'win_comeback', 'L_gave_back', 'L_never_led_1x', 'L_never_led_2x', 'L_never_led_OT2x',
         'L_never_led_OT3x', 'L_tiebreak_drain']
print(f'{"path":20s}' + ''.join(f'{k:>24s}' for k in S) + '   ranked - sim_w12 (pp)')
for p in PATHS:
    c = {k: sum(r['path'] == p for r in x) for k, x in S.items()}
    print(f'{p:20s}' + ''.join(f'{c[k]:5d} {100 * c[k] / len(S[k]):5.1f}%{"":12s}' for k in S)
          + '   ' + pp(newcombe(c['ranked'], len(rk), c['sim_w12'], len(S['sim_w12']))))
for k, x in S.items():
    o = Counter(r['path'] for r in x if r['path'] not in PATHS)
    if o:
        print('  other paths', k, dict(o))

h('T2b crown-path conditionals')
for k, x in S.items():
    lostf = [r for r in x if r['first'] == 'own']
    tookf = [r for r in x if r['first'] == 'opp']
    r11 = [r for r in x if r['reached_11']]
    ot = [r for r in x if r['ot']]
    print(f'{k:8s} lost first princess {fmt(len(lostf), len(x))} -> win {fmt(wins(lostf), len(lostf))} | took first '
          f'{fmt(len(tookf), len(x))} -> win {fmt(wins(tookf), len(tookf))}')
    print(f'{"":8s} reached 1-1 {fmt(len(r11), len(x))} -> win {fmt(wins(r11), len(r11))} | OT {fmt(len(ot), len(x))} '
          f'-> win {fmt(wins(ot), len(ot))} | king lost {sum(r["king_lost"] for r in x)}')
    led = [r for r in x if r['led']]
    print(f'{"":8s} led at some point {fmt(len(led), len(x))} -> gave it back and lost {fmt(sum(r["win"] == 0 for r in led), len(led))}')

# ---------------------------------------------------------------------------------------------------------------- overtime
h('T3 overtime: where the OT match was decided (share of OT matches, CLX win %)')


def ot_bucket(r):
    s = r['end_s']
    return 'OT 2x minute (180-240 s)' if s < 240 else 'OT 3x minute (240-299 s)' if s < 299.25 else 'tiebreak drain (>= 299 s)'


for k, x in S.items():
    ot = [r for r in x if r['ot']]
    for b in ('OT 2x minute (180-240 s)', 'OT 3x minute (240-299 s)', 'tiebreak drain (>= 299 s)'):
        y = [r for r in ot if ot_bucket(r) == b]
        print(f'  {k:8s} {b:28s} {len(y):4d} of {len(ot):4d} OT   CLX win {fmt(wins(y), len(y))}')
print('  ranked - sim_w12, CLX win in OT decided before the drain:',
      pp(newcombe(*(lambda a, b: (wins(a), len(a), wins(b), len(b)))(
          [r for r in rk if r['ot'] and r['end_s'] < 299.25], [r for r in S['sim_w12'] if r['ot'] and r['end_s'] < 299.25]))))

h('T3b live: lowest standing princess HP at 180 s decides the 0-0 overtime (live only; SIM rows have no 180 s HP)')
for k in ('ranked', 'ladder'):
    o00 = [r for r in S[k] if r['ot'] and tuple(r['reg_cr']) == (0, 0)]
    print(f'  {k}: 0-0 at 180 s = {len(o00)}; mean lowest own {sum(r["reg_own_min"] for r in o00) / len(o00):.3f} vs opp '
          f'{sum(r["reg_opp_min"] for r in o00) / len(o00):.3f}')
    for lab, f in (('behind  (own < opp - 0.10)', lambda r: r['reg_own_min'] < r['reg_opp_min'] - .1),
                   ('level   (within 0.10)', lambda r: abs(r['reg_own_min'] - r['reg_opp_min']) <= .1),
                   ('ahead   (own > opp + 0.10)', lambda r: r['reg_own_min'] > r['reg_opp_min'] + .1)):
        y = [r for r in o00 if f(r)]
        print(f'     {lab:28s} {fmt(len(y), len(o00))} of 0-0 OT matches; CLX win {fmt(wins(y), len(y))}')


def agg(x, key, top=10):
    c = Counter()
    for r in x:
        for kk, v in (r.get(key) or {}).items():
            c[kk] += v
    return round(sum(c.values()) / max(1, len(x)), 3), {kk: round(v / max(1, len(x)), 3) for kk, v in c.most_common(top)}


h('T3c princess HP (in princess units per match) taken / dealt in regulation, 0-0 OT matches, by result (chip proxy)')
for k in ('ranked', 'ladder'):
    o00 = [r for r in S[k] if r['ot'] and tuple(r['reg_cr']) == (0, 0)]
    for res, y in (('WIN', [r for r in o00 if r['win'] == 1]), ('LOSS', [r for r in o00 if r['win'] == 0])):
        print(f'  {k} {res} n={len(y)}  taken {agg(y, "taken_reg")}')
        print(f'  {"":{len(k)}s} {"":{len(res)}s} {"":{len(str(len(y))) + 2}s}  dealt {agg(y, "dealt_reg")}')
for k in ('ranked', 'ladder'):
    print(f'  ALL {k}: taken_reg {agg(S[k], "taken_reg")[0]}  dealt_reg {agg(S[k], "dealt_reg")}')

h('T3d play intensity per minute (own plays; opponent TROOP plays and troop elixir) -- live vs SIM w12')
for k in ('ranked', 'ladder', 'sim_w12'):
    for w in AN.INT_WIN:
        y = [r['intensity'][w] for r in S[k] if r.get('intensity') and w in r['intensity'] and r['intensity'][w]['min'] > 0.05]
        mins = sum(v['min'] for v in y)
        print(f'  {k:8s} {w:12s} matches {len(y):4d}  own {sum(v["own"] for v in y) / mins:5.2f}/min  opp troops '
              f'{sum(v["opp_troops"] for v in y) / mins:5.2f}/min  opp troop elixir {sum(v["opp_troop_el"] for v in y) / mins:5.2f}/min')

# ------------------------------------------------------------------------------------------------------------------ decks
h('T4 opponent win condition (first of anatomy.WINCON in the seen deck): n, CLX win, losses; SIM w12 by the same key')
sw = defaultdict(list)
for r in S['sim_w12']:
    sw[r['wincon']].append(r)
lad = defaultdict(list)
for r in S['ladder']:
    lad[r['wincon']].append(r)
byw = defaultdict(list)
for r in rk:
    byw[r['wincon']].append(r)
for w, y in sorted(byw.items(), key=lambda kv: -sum(r['win'] == 0 for r in kv[1])):
    print(f'  {w:16s} ranked {fmt(wins(y), len(y)):30s} losses {sum(r["win"] == 0 for r in y):3d} | ladder '
          f'{fmt(wins(lad[w]), len(lad[w])):30s} | sim_w12 {fmt(wins(sw[w]), len(sw[w]))}')
print('  owner archetypes (weekend/archetypes.classify):')
for k in ('ranked', 'ladder', 'sim_w12'):
    c = defaultdict(list)
    for r in S[k]:
        c[r['arch']].append(r)
    print('   ', k, {a: fmt(wins(y), len(y)) for a, y in sorted(c.items(), key=lambda kv: -len(kv[1]))})


# ---------------------------------------------------------------------------------------------------------- loss clusters
def cluster(r):
    """One situation cluster per loss, from the decisive fall (first rule that matches)."""
    d = r.get('decisive')
    if r['path'] == 'L_tiebreak_drain':
        return 'K_tiebreak_drain'
    if d is None:
        return 'Z_no_decisive'
    ph = d['phase']
    when = 'reg' if ph in ('1x', '2x') else 'ot'
    if d['hp20'] is not None and d['hp20'] < 0.30:
        return f'{when}_A_finish_weak_tower'         # the tower was already < 30% 20 s before: a chip deficit got finished
    if d['own_off_w'] + d['own_off_pre'] >= 6 and (d['el20'] or 0) < 5:
        return f'{when}_B_punished_commit'           # X-Bow at bridge / Rocket at tower in the 40 s before, low elixir at -20 s
    if d['opp_lane_el'] >= 9:
        return f'{when}_C_big_push'                  # >= 9 elixir of opponent cards in that lane in the 20 s window
    return f'{when}_D_small_push'


h('T5 loss clusters (decisive fall; ranked, then ladder) -- n, share of losses, window features, examples')
for k in ('ranked', 'ladder'):
    L = [r for r in S[k] if r['win'] == 0]
    cl = defaultdict(list)
    for r in L:
        cl[cluster(r)].append(r)
    print(f'  {k}: {len(L)} losses')
    for c, y in sorted(cl.items(), key=lambda kv: -len(kv[1])):
        ds = [r['decisive'] for r in y if r.get('decisive')]
        mean = lambda f: round(sum(f(d) for d in ds) / len(ds), 2) if ds else None  # noqa: E731
        att = Counter()
        for d in ds:
            for a, v in d['attackers'].items():
                att[a] += v
        wc = Counter(r['wincon'] for r in y)
        print(f'   {c:28s} {len(y):3d} ({100 * len(y) / len(L):4.1f}% of losses)  hp20 {mean(lambda d: d["hp20"] or 0)}  '
              f'el20 {mean(lambda d: d["el20"] or 0)}  elmin {mean(lambda d: d["el_min"] or 0)}  own_off(40s) '
              f'{mean(lambda d: d["own_off_w"] + d["own_off_pre"])}  opp_lane_el {mean(lambda d: d["opp_lane_el"])}  '
              f'gave_back {sum(r["path"] == "L_gave_back" for r in y)}')
        print(f'   {"":28s} attackers {dict(att.most_common(6))}  wincons {dict(wc.most_common(5))}')
        for r in y[:3]:
            d = r.get('decisive')
            print(f'   {"":28s} e.g. {r["key"]} fall {d and d["clock_s"]} s ({d and d["slot"]}), seq {r["seq"]}')

h('T5b SIM w12 losses: the same window features (cards / elixir only; no positions)')
L = [r for r in S['sim_w12'] if r['win'] == 0 and r.get('decisive')]
for ph in ('1x', '2x', 'OT2x', 'OT3x', 'drain'):
    y = [r['decisive'] for r in L if r['decisive']['phase'] == ph]
    if y:
        print(f'  {ph:6s} n={len(y):4d} own_off(40s) {sum(d["own_off_w"] + d["own_off_pre"] for d in y) / len(y):.2f}  '
              f'opp troop elixir in window {sum(d["opp_troop_el"] or 0 for d in y) / len(y):.2f}')
for k in ('ranked', 'ladder'):
    for ph in ('1x', '2x', 'OT2x', 'OT3x', 'drain'):
        y = [r['decisive'] for r in S[k] if r['win'] == 0 and r.get('decisive') and r['decisive']['phase'] == ph]
        if y:
            print(f'  {k:6s} {ph:6s} n={len(y):3d} own_off(40s) {sum(d["own_off_w"] + d["own_off_pre"] for d in y) / len(y):.2f}  '
                  f'opp lane elixir in window {sum(d["opp_lane_el"] for d in y) / len(y):.2f}')

# --------------------------------------------------------------------------------------------------------- CPU starvation
h('T6 CPU starvation vs result (per match: median decision ms, cpu_starved events)')
for k in ('ranked', 'ladder'):
    x = [r for r in S[k] if r.get('dec_ms_median') is not None]
    for lab, f in (('median < 60 ms', lambda r: r['dec_ms_median'] < 60), ('60-80 ms', lambda r: 60 <= r['dec_ms_median'] < 80),
                   ('80-100 ms', lambda r: 80 <= r['dec_ms_median'] < 100), ('>= 100 ms', lambda r: r['dec_ms_median'] >= 100)):
        y = [r for r in x if f(r)]
        print(f'  {k:7s} {lab:15s} {fmt(wins(y), len(y))}')
    a = [r for r in x if r['n_cpu_starved'] > 0]
    b = [r for r in x if r['n_cpu_starved'] == 0]
    print(f'  {k:7s} any CPU-STARVED event {fmt(wins(a), len(a))} vs none {fmt(wins(b), len(b))}  diff '
          + pp(newcombe(wins(a), len(a), wins(b), len(b))))
blocks = (('10-20 13:28-21:59', lambda r: r['ts'] < '20261020_220000'), ('10-20 22:00-10-21 07:10', lambda r: r['ts'] >= '20261020_220000'))
for lab, f in blocks:
    y = [r for r in rk if f(r)]
    a = [r for r in y if r['n_cpu_starved'] > 0]
    b = [r for r in y if r['n_cpu_starved'] == 0]
    med = sorted(r['dec_ms_median'] for r in y)[len(y) // 2]
    print(f'  ranked {lab:24s} n={len(y)} median-of-medians {med} ms; starved {fmt(wins(a), len(a))} vs not {fmt(wins(b), len(b))}')
for k in ('ranked', 'ladder'):
    x = S[k]
    fails = lambda r: (r['n_play'] or 0) - (r['n_confirmed'] or 0)  # noqa: E731
    W = [r for r in x if r['win'] == 1]
    Lx = [r for r in x if r['win'] == 0]
    print(f'  {k:7s} unconfirmed plays / match: wins {sum(map(fails, W)) / len(W):.2f}, losses {sum(map(fails, Lx)) / len(Lx):.2f}; '
          f'confirm latency median wins {sorted(r["confirm_latency_median"] or 0 for r in W)[len(W) // 2]} s, '
          f'losses {sorted(r["confirm_latency_median"] or 0 for r in Lx)[len(Lx) // 2]} s')

# ------------------------------------------------------------------------------------------------------- extra tables
BEAT = {'giant', 'electro_giant', 'royal_hogs', 'battle_ram', 'pekka', 'golem', 'goblin_giant', 'lava_hound', 'royal_giant',
        'elixir_golem', 'rune_giant', 'giant_skeleton', 'three_musketeers', 'boss_bandit'}
h('T7 tank / bridge-spam win conditions (anatomy.wincon in BEAT) vs the rest')
for k in S:
    a = [r for r in S[k] if r['wincon'] in BEAT]
    b = [r for r in S[k] if r['wincon'] not in BEAT]
    print(f'  {k:8s} BEAT {fmt(wins(a), len(a)):30s} losses {sum(r["win"] == 0 for r in a):4d} | rest {fmt(wins(b), len(b)):30s} '
          f'losses {sum(r["win"] == 0 for r in b):4d}')
a, b = [r for r in rk if r['wincon'] in BEAT], [r for r in S['sim_w12'] if r['wincon'] in BEAT]
print('  ranked - sim_w12 on BEAT:', pp(newcombe(wins(a), len(a), wins(b), len(b))))
a, b = [r for r in rk if r['wincon'] not in BEAT], [r for r in S['sim_w12'] if r['wincon'] not in BEAT]
print('  ranked - sim_w12 on the rest:', pp(newcombe(wins(a), len(a), wins(b), len(b))))
for k in ('ranked', 'sim_w12'):
    x = [r for r in S[k] if r['wincon'] in BEAT]
    print(f'  {k} BEAT paths', dict(Counter(r['path'] for r in x).most_common()))

MECH = {'K_tiebreak_drain': '1 chip race lost, decided in OT', 'ot_A_finish_weak_tower': '1 chip race lost, decided in OT',
        'reg_A_finish_weak_tower': '3 chipped tower finished in regulation',
        'reg_B_punished_commit': '2 punished offensive commit', 'ot_B_punished_commit': '2 punished offensive commit',
        'reg_C_big_push': '4 push through a healthy tower', 'reg_D_small_push': '4 push through a healthy tower',
        'ot_C_big_push': '4 push through a healthy tower', 'ot_D_small_push': '4 push through a healthy tower'}
h('T8 loss mechanisms (ranked; T5 clusters grouped) x opponent group')
L = [r for r in rk if r['win'] == 0]
mc = Counter((MECH.get(cluster(r), cluster(r)), r['wincon'] in BEAT) for r in L)
for mname in sorted({k[0] for k in mc}):
    tot = mc[(mname, True)] + mc[(mname, False)]
    print(f'  {mname:40s} {tot:3d} ({100 * tot / len(L):4.1f}%)   BEAT {mc[(mname, True)]:3d}  rest {mc[(mname, False)]:3d}')

h('T9 OT targeting: in OT losses before the drain, did the fallen tower = CLX lowest princess at 180 s?')
for k in ('ranked', 'ladder'):
    y = [r for r in S[k] if r['win'] == 0 and r.get('decisive') and r['decisive']['phase'] in ('OT2x', 'OT3x')
         and r.get('reg_own_low')]
    print(f'  {k}: {sum(r["decisive"]["slot"] == r["reg_own_low"] for r in y)} / {len(y)} fell on the tower that was lowest at 180 s')
    y = [r for r in S[k] if r['win'] == 1 and r['ot'] and tuple(r['reg_cr']) == (0, 0) and r.get('reg_opp_low')]
    took = [r for r in y if any(s[0] >= 179.5 and s[1] == 'opp' for s in r['seq'])]
    print(f'  {k}: CLX OT takes on the opponent tower lowest at 180 s: '
          f'{sum(next(s[2] for s in r["seq"] if s[0] >= 179.5 and s[1] == "opp") == r["reg_opp_low"] for r in took)} / {len(took)}')

h('T10 bridge X-Bow efficiency, live (invlib.xbow_rows: lock = >= 5% of a princess while alive, dmg in princess units)')
for k in ('ranked', 'ladder'):
    x = S[k]
    n = sum(r['xbow']['bridge_tracked'] for r in x)
    print(f'  {k:7s} X-Bows/match {sum(r["xbow"]["n"] for r in x) / len(x):.2f}  bridge/match {sum(r["xbow"]["bridge"] for r in x) / len(x):.2f}'
          f'  lock {fmt(sum(r["xbow"]["bridge_lock"] for r in x), n)}  dmg/bridge X-Bow {sum(r["xbow"]["bridge_dmg"] for r in x) / n:.3f}'
          f'  answer elixir/bridge X-Bow {sum(r["xbow"]["bridge_answer_el"] for r in x) / n:.2f}  life {sum(r["xbow"]["bridge_life_s"] for r in x) / n:.1f} s')
    for res in (1.0, 0.0):
        y = [r for r in x if r['win'] == res]
        n2 = sum(r['xbow']['bridge_tracked'] for r in y)
        print(f'     {"wins" if res else "losses":6s} lock {fmt(sum(r["xbow"]["bridge_lock"] for r in y), n2)}  dmg/bridge '
              f'{sum(r["xbow"]["bridge_dmg"] for r in y) / n2:.3f}')

h('T11 is the SIM calibrated to the ladder or to Ranked?  (live - sim_w12, pp, Newcombe 95%)')
pre = lambda x: [r for r in x if r['ot'] and r['end_s'] < 299.25]  # noqa: E731
cells = (('overall win', lambda x: x, lambda r: r['win'] == 1), ('win vs BEAT', lambda x: [r for r in x if r['wincon'] in BEAT], lambda r: r['win'] == 1),
         ('win vs rest', lambda x: [r for r in x if r['wincon'] not in BEAT], lambda r: r['win'] == 1),
         ('win | OT', lambda x: [r for r in x if r['ot']], lambda r: r['win'] == 1),
         ('win | OT decided before drain', pre, lambda r: r['win'] == 1),
         ('lost first princess', lambda x: x, lambda r: r['first'] == 'own'),
         ('lost in regulation', lambda x: x, lambda r: r['win'] == 0 and not r['ot']))
for name, sel, f in cells:
    out = []
    for k in ('ladder', 'ranked'):
        a, b = sel(S[k]), sel(S['sim_w12'])
        out.append(f'{k} {100 * sum(map(f, a)) / len(a):5.1f} vs {100 * sum(map(f, b)) / len(b):5.1f}: '
                   + pp(newcombe(sum(map(f, a)), len(a), sum(map(f, b)), len(b))))
    print(f'  {name:30s} ' + '   |   '.join(out))

h('T12 examples per mechanism (ranked; log file, decisive fall clock s and GAME tick = clock tick + 78)')
for mname in sorted(set(MECH.values())):
    ex = [r for r in L if MECH.get(cluster(r)) == mname][:6]
    print(f'  {mname}:')
    for r in ex:
        d = r['decisive']
        own = ', '.join(f'{c}@{dt / 20:+.0f}s:{z}' for dt, c, z in d['own_cards'][-5:])
        opp = ', '.join(f'{c}@{dt / 20:+.0f}s' for dt, c in d['opp_cards'][-5:])
        print(f'    {r["key"]} fall {d["clock_s"]} s (game tick {d["t"] + 78}) {d["slot"]} tower hp20 {d["hp20"]} el20 {d["el20"]} '
              f'| {r["wincon"]} | attackers {list(d["attackers"])[:3]} | CLX: {own} | opp: {opp}')
