"""W10 (owner 10-20): Rocket decisions IN CONTEXT (situation clusters), one scorer for live logs, pro re-drives and SIM eval rows.

    icebow/.venv/Scripts/python.exe -B -X utf8 rocket_slices.py --live [--pro] [--sim NAME=DIR ...] [--out FILE]

Sources -> one match record (``M``), then every slice is computed by the same code:
  live  invlib.live_matches(index=rocket/index_clx.json): CLX at our tower 4858 (build_live_clx.py). Real reader frames.
  pro   invlib.pro_matches(): icebow8 Path of Legend sides. Decisions + results real; X-Bow lock = native re-drive.
  sim   gap.py D3 rows (any dir holding */D3/matches.jsonl or D3/*/matches.jsonl) that carry --record-plays (own_plays),
        --habit-log (xbow_y), --crown-log (Rocket aims, exact princess falls) and the o3 telemetry patch (o3_plays: the
        opponent's plays). Rows without them are refused by name, never guessed.
Definitions (reused, not re-derived):
  matchup / answer context: investment/analyze.py (archetype by revealed cards; K from counters_raw.json; ready / short /
    cycled / unrevealed from the opponent's revealed cycle and the OppElixirCounter estimate, hablib.counter_fn).
  Rocket aim: hablib.rocket_uses (tower = blast centre <= 3 tiles of an enemy princess / king slot; defence = y >= 15).
  heavy push: doctrine/measure.defence_episodes (opponent troop plays, gaps <= 5 s, >= 10 elixir; our answer = defensive
    plays from 2 s before to 8 s after).
  chip Rocket = a tower Rocket NOT followed by an enemy princess fall within FINISH_TICKS (a finisher is not cycling).
  Rocket opportunity = Rocket in our hand and own elixir >= 6 (sampled every 20 ticks), the denominator of the rates.
  SIM own hand = the icebow 8 minus the last 4 accepted plays (exact after the 4th play; earlier samples are dropped in every
    source so the denominators match); SIM own elixir = the logged elixir at the last play's decision - its cost + the
    engine regen schedule (opp_elixir_count.regen_between), capped at 10.
CIs: match-cluster bootstrap (hablib.boot_ci, 95%). Association only wherever a slice is set against results.
"""
from __future__ import annotations

import argparse
import bisect
import glob
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parent
REPO = L74.parents[2]
sys.path[:0] = [str(L74 / 'habits'), str(L74 / 'investment'), str(REPO)]
import hablib as H  # noqa: E402
import invlib as I  # noqa: E402
from pipeline.opp_elixir_count import regen_between  # noqa: E402

I8 = sorted(I.I8)
FINISH_TICKS = 80          # a tower Rocket followed by an enemy princess fall within 4 s = a finisher, not a chip
COMBO = (-24, 40)          # Rocket landing - Tornado landing, ticks (rocket-tornado-combo-plan: hits run -24..+12; setup <= 40)
AFTER_FAIL = 600           # 30 s after a failed bridge X-Bow's end (investment/analyze.py section 4)
STEP = 20
TANKS = {'golem', 'giant', 'electro_giant', 'goblin_giant', 'lava_hound', 'elixir_golem', 'royal_giant', 'pekka',
         'mega_knight', 'goblinstein', 'giant_skeleton', 'boss_bandit'}
ARCHS = ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER')
HOSTILE = {('EQ', 'ready'), ('EQ', 'short'), ('HOG', 'ready'), ('HOG', 'short'), ('BEATDOWN', 'ready'), ('BEATDOWN', 'short')}
_raw = json.load(open(L74 / 'investment/counters_raw.json'))
K = sorted(c for c, v in _raw.items() if 'live' in v and 'pro' in v and all(
    v[s]['n_eng'] >= 20 and v[s]['lock_eng'] <= v[s]['base_lock'] - 0.10 for s in ('live', 'pro')))


def archetype(rev):
    rev = set(rev)
    return ('EQ' if 'earthquake' in rev else 'SIEGE' if rev & {'x_bow', 'mortar'} else 'HOG' if 'hog_rider' in rev
            else 'BEATDOWN' if rev & TANKS else 'OTHER')


def answer_ctx(cyc, est):
    seen = [c for c in K if c in cyc]
    if not seen:
        return 'unrevealed'
    inhand = [c for c in seen if cyc[c] >= 4]
    if not inhand:
        return 'cycled'
    return 'ready' if any(est >= H.cost(c) for c in inhand) else 'short'


def rocket_aim(x, y):
    if any(math.hypot(x - tx, y - ty) <= 3.0 for tx, ty in I.TOWER_XY.values()):
        return 'tower'
    return 'defence' if y >= 15.0 else 'enemy_half'


# ------------------------------------------------------------------------------------------------------------- adapters
def from_invlib(m, failed=True):
    """invlib live / pro match -> M. ``failed``: failed bridge X-Bow end ticks via invlib.xbow_rows (frames needed)."""
    own = []
    for q in sorted(m['own'], key=lambda q: q['tick']):
        r = dict(tick=q['tick'], card=q['card'], why=q.get('why'))
        if q['card'] == 'x_bow':
            r['xt'] = I.xtype(q['y'])
        elif q['card'] == 'rocket' and q['y'] is not None:
            r['aim'] = rocket_aim(q['x'], q['y'])
        elif q['card'] == 'tornado' and q['y'] is not None:
            r['xy'] = (q['x'], q['y'])
        if q['card'] == 'rocket' and q['y'] is not None:
            r['xy'] = (q['x'], q['y'])
        own.append(r)
    falls, fr = [], m['frames']                       # a princess that is down (<= 0 or absent) in the LAST frame fell at the
    for w in ('own', 'opp'):                          # first frame after its last alive one (reader blips are ignored)
        for s in 'LR':
            if fr[-1][1].get((w, s), 0) > 0:
                continue
            alive = [i for i, f in enumerate(fr) if f[1].get((w, s), 0) > 0]
            if alive and alive[-1] + 1 < len(fr):
                falls.append((fr[alive[-1] + 1][0], 'foe' if w == 'opp' else 'own'))
    falls.sort()
    fails = None
    if failed:
        fails = [r['end_tick'] for r in I.xbow_rows(m) if r['type'] == 'bridge' and 'lock' in r and not r['lock']
                 and not r['censored']]
    return dict(src=m['src'], key=m['key'], win=m['win'], end=m['end'], own=own,
                opp=[dict(tick=p['tick'], card=p['card']) for p in m['opp']], falls=falls, hand=m['hand'], fails=fails)


def sim_rows(root):
    files = sorted(glob.glob(str(Path(root) / '*/D3/matches.jsonl')))
    if not files:
        files = sorted(glob.glob(str(Path(root) / 'D3/*/matches.jsonl')))
    seen = set()
    for f in files:
        for line in open(f, encoding='utf-8'):
            if line.strip():
                r = json.loads(line)
                k = (r.get('census'), r.get('tag'), r.get('seed'), r.get('learner_side'))
                if k in seen:
                    raise ValueError(f'duplicate SIM row {k} in {f}')
                seen.add(k)
                yield r


def from_sim(r):
    """gap.py D3 row -> M, or (None, why)."""
    if r.get('wall_truncated') or r.get('outcome') not in ('win', 'loss', 'draw'):
        return None, 'truncated / no outcome'
    plays, hab, crown, o3 = r.get('own_plays'), r.get('habits') or {}, r.get('crown'), r.get('o3_plays')
    if plays is None or crown is None or o3 is None or 'xbow_y' not in hab:
        return None, 'missing own_plays / crown / o3_plays / habits.xbow_y'
    acc = [q for q in plays if q[3]]
    ys, rk = list(hab['xbow_y']), list(crown['rockets'])
    xb = [q for q in acc if H.norm(q[2]) == 'x_bow']
    rr = [q for q in acc if H.norm(q[2]) == 'rocket']
    if len(xb) != len(ys) or len(rr) != len(rk):
        return None, 'X-Bow / Rocket count differs between own_plays and habits / crown'
    own, xi, ri = [], iter(ys), iter(rk)
    for dec, land, card, _, el in acc:
        c = H.norm(card)
        q = dict(tick=land, dec=dec, card=c, el=el, why=None)
        if c == 'x_bow':
            q['xt'] = I.xtype(next(xi) * 32.0)
        elif c == 'rocket':
            a = next(ri)
            q['aim'] = rocket_aim(*a['aim'])
            q['xy'] = tuple(a['aim'])
        own.append(q)
    falls = [(f['tick'], f['who']) for f in crown['falls']]
    decs = [q['dec'] for q in own]

    def hand(t, own=own, decs=decs):
        i = bisect.bisect_right(decs, t)
        if i < 4:
            return None
        last4 = {q['card'] for q in own[i - 4:i]}
        q = own[i - 1]
        e = min(10.0, max(0.0, q['el'] - H.cost(q['card'])) + regen_between(q['dec'], t))
        return set(I8) - last4, e
    win = {'win': 1.0, 'loss': 0.0, 'draw': 0.5}[r['outcome']]
    return dict(src='sim', key=f"{r.get('census')}|{r.get('tag')}|{r.get('learner_side')}", win=win, end=r['end_tick'],
                own=own, opp=[dict(tick=t, card=H.norm(c)) for t, c in o3['opp']], falls=falls, hand=hand, fails=None,
                tiebreak=any(f['tick'] >= 5990 for f in crown['falls'])), None


# ------------------------------------------------------------------------------------------------------- per-match pass
def crowns_at(M, t):
    return (sum(1 for ft, w in M['falls'] if ft <= t and w == 'foe' and ft < 5990),
            sum(1 for ft, w in M['falls'] if ft <= t and w == 'own' and ft < 5990))


def cyc_at(M, t):
    seq = [p['card'] for p in sorted(M['opp'], key=lambda p: p['tick']) if p['tick'] < t]
    return {c: len(seq) - 1 - i for i, c in enumerate(seq)}


def ctx(M, t, est):
    our, their = crowns_at(M, t)
    return dict(phase='1x' if t < 2400 else '2x' if t < 3600 else 'OT',
                state='ahead' if our > their else 'behind' if our < their else 'even',
                ans=answer_ctx(cyc_at(M, t), est(t)))


def scan(M, group):
    """One match -> (rockets, samples, pushes, fails, match row): plain dicts, every one tagged with key / group / arch."""
    M['arch'] = archetype({p['card'] for p in M['opp']})
    base = dict(key=M['key'], group=group, arch=M['arch'], win=M['win'])
    est = H.counter_fn(M['opp'])
    torn = [q['tick'] for q in M['own'] if q['card'] == 'tornado']
    rockets = []
    for q in M['own']:
        if q['card'] != 'rocket' or 'aim' not in q:
            continue
        t = q['tick']
        fin = q['aim'] == 'tower' and any(t <= ft <= t + FINISH_TICKS and w == 'foe' for ft, w in M['falls'])
        h = M['hand'](t - 1)
        rockets.append(dict(base, tick=t, aim=q['aim'], chip=q['aim'] == 'tower' and not fin, finish=fin, why=q.get('why'),
                            combo=any(COMBO[0] <= t - tt <= COMBO[1] for tt in torn), known=h is not None, **ctx(M, t, est)))
    samples = []
    for t in range(0, int(M['end']), STEP):
        h = M['hand'](t)
        if h is None or 'rocket' not in h[0] or (h[1] or 0) < 6:
            continue
        samples.append(dict(base, tick=t, **ctx(M, t, est)))
    pushes = []
    opp = sorted([p for p in M['opp'] if H.kind(p['card']) == 'troop'], key=lambda p: p['tick'])
    eps = []
    for p in opp:
        if eps and p['tick'] - eps[-1]['t1'] <= 100:
            eps[-1]['t1'] = p['tick']
            eps[-1]['v'] += H.cost(p['card'])
        else:
            eps.append(dict(t0=p['tick'], t1=p['tick'], v=H.cost(p['card'])))
    for e in eps:
        if e['v'] < 10:
            continue
        h = M['hand'](e['t0'])
        if h is None:
            continue
        rk = [r for r in rockets if e['t0'] - 40 <= r['tick'] <= e['t1'] + 160 and r['aim'] == 'defence']
        pushes.append(dict(base, tick=e['t0'], v=e['v'], rocket_in_hand='rocket' in h[0], el=h[1], rocket=bool(rk),
                           **ctx(M, e['t0'], est)))
    fails = None
    if M['fails'] is not None:
        fails = [dict(base, tick=t, rocket30=any(r['chip'] and t <= r['tick'] <= t + AFTER_FAIL for r in rockets),
                      tower30=any(r['aim'] == 'tower' and t <= r['tick'] <= t + AFTER_FAIL for r in rockets), **ctx(M, t, est))
                 for t in M['fails']]
    xb = [dict(base, tick=q['tick'], xt=q['xt'], **ctx(M, q['tick'], est)) for q in M['own'] if q['card'] == 'x_bow' and q.get('xt')]
    hostile_s = sum(1 for s in samples if (s['arch'], s['ans']) in HOSTILE)
    row = dict(base, end=M['end'], n_chip=sum(r['chip'] for r in rockets),
               n_chip_hostile=sum(r['chip'] and (r['arch'], r['ans']) in HOSTILE for r in rockets),
               hostile_min=hostile_s * STEP / 1200, opp_min=len(samples) * STEP / 1200, tiebreak=M.get('tiebreak'),
               ot=M['end'] >= 3600, n_bridge=sum(x['xt'] == 'bridge' for x in xb),
               n_bridge_hostile=sum(x['xt'] == 'bridge' and (x['arch'], x['ans']) in HOSTILE for x in xb))
    return rockets, samples, pushes, fails, xb, row


# ------------------------------------------------------------------------------------------------------------- reporting
def ci(rows, f, B=400):
    lo, hi = H.boot_ci(rows, f, B=B)
    return f'[{lo:.2f}, {hi:.2f}]'


def per_min(ev, smp):
    """events per opportunity-minute, match-bootstrap CI over the union of keys."""
    rows = [dict(key=r['key'], e=1, s=0) for r in ev] + [dict(key=r['key'], e=0, s=1) for r in smp]
    f = lambda xs: 60.0 * sum(x['e'] for x in xs) / max(1, sum(x['s'] for x in xs)) / (STEP * I.TICK_S)  # noqa: E731
    v = f(rows) if smp else float('nan')
    return f'{v:.3f} {ci(rows, f, B=300)}' if smp else 'n/a'


def share(rows, field):
    if not rows:
        return 'n/a (n 0)'
    f = lambda xs: sum(bool(x[field]) for x in xs) / max(1, len(xs))  # noqa: E731
    return f'{f(rows):.3f} {ci(rows, f)} (n {len(rows)})'


def report(D, say):
    say('## S1 Rocket in the answer to a HEAVY push (>= 10 elixir), only pushes where Rocket was in our hand')
    say('group | all heavy pushes w/ Rocket in hand: P(defensive Rocket in answer) | elixir >= 6 at push start | ... 14+ elixir pushes')
    for g, d in D.items():
        ps = [p for p in d['pushes'] if p['rocket_in_hand']]
        say(f"{g} | {share(ps, 'rocket')} | {share([p for p in ps if p['el'] >= 6], 'rocket')} | "
            f"{share([p for p in ps if p['el'] >= 6 and p['v'] >= 14], 'rocket')}")
    say('\n## S2 Chip tower Rockets (non-finishing) per Rocket-opportunity-minute, by matchup x answer context')
    for a in ARCHS:
        for c in ('ready', 'short', 'cycled', 'unrevealed'):
            cells = []
            for g, d in D.items():
                smp = [s for s in d['samples'] if s['arch'] == a and s['ans'] == c]
                ev = [r for r in d['rockets'] if r['chip'] and r['known'] and r['arch'] == a and r['ans'] == c]
                cells.append(f"{g}: {per_min(ev, smp)} (opp-min {len(smp) * STEP / 1200:.0f})" if len(smp) >= 30 else f'{g}: -')
            say(f'{a}/{c:10s} | ' + ' | '.join(cells))
    say('\n## S2b Investment shares in the hostile clusters (EQ / HOG / BEATDOWN x ready / short): bridge X / def X / chip Rocket')
    for g, d in D.items():
        bx = sum(x['xt'] == 'bridge' for x in d['xb'] if (x['arch'], x['ans']) in HOSTILE)
        dx = sum(x['xt'] == 'defensive' for x in d['xb'] if (x['arch'], x['ans']) in HOSTILE)
        rk = sum(r['chip'] for r in d['rockets'] if (r['arch'], r['ans']) in HOSTILE)
        n = bx + dx + rk
        say(f'{g} | n {n} | bridge {bx / max(1, n):.2f} | defensive {dx / max(1, n):.2f} | chip Rocket {rk / max(1, n):.2f}')
    say('\n## S3 After a FAILED bridge X-Bow (no lock, not censored): chip Rocket within 30 s (any tower Rocket in brackets)')
    for g, d in D.items():
        if d['fails'] is None:
            say(f'{g} | n/a (SIM rows carry no X-Bow life / tower HP series; see ROCKET.md "logging owed")')
            continue
        hf = [f for f in d['fails'] if f['arch'] in ('EQ', 'HOG', 'BEATDOWN')]
        say(f"{g} | all {share(d['fails'], 'rocket30')} [{share(d['fails'], 'tower30')}] | EQ/HOG/BEATDOWN {share(hf, 'rocket30')}")
    say('\n## S4 Late game: chip Rockets per Rocket-opportunity-minute by phase x crown state')
    for ph in ('1x', '2x', 'OT'):
        for st in ('ahead', 'even', 'behind'):
            cells = []
            for g, d in D.items():
                smp = [s for s in d['samples'] if s['phase'] == ph and s['state'] == st]
                ev = [r for r in d['rockets'] if r['chip'] and r['known'] and r['phase'] == ph and r['state'] == st]
                cells.append(f"{g}: {per_min(ev, smp)} (opp-min {len(smp) * STEP / 1200:.0f})" if len(smp) >= 30 else f'{g}: -')
            say(f'{ph}/{st:6s} | ' + ' | '.join(cells))
    say('\n## S5 Rocket + Tornado combos: share of our Rockets with our Tornado landing -24..+40 ticks around them; per match')
    for g, d in D.items():
        n = len(d['match'])
        say(f"{g} | combo share of Rockets {share(d['rockets'], 'combo')} | combos / match {sum(r['combo'] for r in d['rockets']) / max(1, n):.3f}"
            f" | Rockets / match {len(d['rockets']) / max(1, n):.2f} | chip / match {sum(r['chip'] for r in d['rockets']) / max(1, n):.2f}"
            f" | finishers / match {sum(r['finish'] for r in d['rockets']) / max(1, n):.2f}")
    say('\n## V Value (ASSOCIATION): win rate by chip Rockets per match, all / hostile-cluster chips; tiebreak matches')
    for g, d in D.items():
        ms = d['match']
        cells = []
        for lab, f in (('chip 0', lambda m: m['n_chip'] == 0), ('chip 1', lambda m: m['n_chip'] == 1),
                       ('chip 2+', lambda m: m['n_chip'] >= 2)):
            sub = [m for m in ms if f(m)]
            cells.append(f'{lab}: {H.wr(sub):.3f} {ci(sub, H.wr)} (n {len(sub)})' if sub else f'{lab}: -')
        say(f'{g} | ' + ' | '.join(cells))
        hs = [m for m in ms if m['hostile_min'] >= 0.5]
        for lab, f in (('hostile chip 0', lambda m: m['n_chip_hostile'] == 0), ('hostile chip 1+', lambda m: m['n_chip_hostile'] >= 1)):
            sub = [m for m in hs if f(m)]
            say(f'   {g} matches with >= 0.5 hostile opp-min: {lab}: {H.wr(sub):.3f} {ci(sub, H.wr)} (n {len(sub)})' if sub
                else f'   {g} {lab}: -')
        tb = [m for m in ms if m.get('tiebreak')]
        if tb:
            for lab, f in (('chip 0', lambda m: m['n_chip'] == 0), ('chip 1+', lambda m: m['n_chip'] >= 1)):
                sub = [m for m in tb if f(m)]
                say(f'   {g} TIEBREAK matches (n {len(tb)}): {lab}: {H.wr(sub):.3f} {ci(sub, H.wr)} (n {len(sub)})' if sub else '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live', action='store_true')
    ap.add_argument('--pro', type=int, default=0, help='pro matches to read (0 = none, -1 = all)')
    ap.add_argument('--sim', nargs='*', default=[], help='NAME=DIR of gap.py D3 rows')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    D = {}

    def add(g, M):
        d = D.setdefault(g, dict(rockets=[], samples=[], pushes=[], fails=[], xb=[], match=[], refused=defaultdict(int)))
        rk, sm, pu, fa, xb, row = scan(M, g)
        d['rockets'] += rk
        d['samples'] += sm
        d['pushes'] += pu
        d['xb'] += xb
        d['match'].append(row)
        if fa is None:
            d['fails'] = None
        elif d['fails'] is not None:
            d['fails'] += fa
    if a.live:
        for m in I.live_matches({'CLX'}, index=HERE / 'index_clx.json'):
            if m['tmax'].get(('own', 'L')) == 4858:
                add('live CLX@4858', from_invlib(m))
    if a.pro:
        for m in I.pro_matches(limit=None if a.pro < 0 else a.pro):
            add('pro', from_invlib(m))
    for spec in a.sim:
        name, root = spec.split('=', 1)
        for r in sim_rows(root):
            if r.get('learner_side') not in (0, 1):
                continue
            M, why = from_sim(r)
            if M is None:
                D.setdefault(name, dict(rockets=[], samples=[], pushes=[], fails=None, xb=[], match=[],
                                        refused=defaultdict(int)))['refused'][why] += 1
                continue
            add(name, M)
    out = []
    say = out.append
    say('# W10 rocket_slices  ' + ' '.join(sys.argv[1:]))
    say('K (X-Bow answers, investment/analyze.py rule): ' + ', '.join(K))
    for g, d in D.items():
        say(f"{g}: matches {len(d['match'])}, win {H.wr(d['match']):.3f}, Rockets {len(d['rockets'])}, "
            f"Rocket-opp-min {len(d['samples']) * STEP / 1200:.0f}, refused {dict(d['refused'])}")
    report(D, say)
    txt = '\n'.join(out) + '\n'
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(txt)
    print(txt)


if __name__ == '__main__':
    main()
