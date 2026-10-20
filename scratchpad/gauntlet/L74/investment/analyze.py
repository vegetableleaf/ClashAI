"""W5 PART 1: X-Bow / Rocket decisions IN CONTEXT, pros vs our live Marks, same code for both (rows.pkl from extract_all.py).

Clusters
  matchup  = the opponent archetype from the cards it revealed by the match end (first rule that fires):
             EQ (earthquake) > SIEGE (x_bow / mortar) > HOG (hog_rider) > BEATDOWN (a >= 6-elixir tank or goblinstein /
             royal_giant / electro_giant) > OTHER
  answer   = the decision context at the moment (revealed-so-far only, what the model can know): the opponent's revealed
             "X-Bow answer" cards K (derived in counters.py from what neutralised bridge X-Bows in BOTH sources):
             ready   = a K card is in their hand (>= 4 plays since its last play) and their counted elixir >= its cost
             short   = in hand but not affordable;  cycled = every revealed K card is in the queue;  unrevealed = none seen
Propensity = placements per OPPORTUNITY-minute (seconds with the X-Bow in hand and own elixir >= 6, in that context).
Outcome per bridge X-Bow: lock (enemy tower in reach lost >= 5% of a princess while it lived), reach damage (princess
units), next-20-s net = enemy tower HP lost - own tower HP lost in the 20 s after the placement, answer elixir - 6.
CAVEAT (printed in the tables): pro OUTCOMES come from the native level-11 open-loop re-drive (invlib docstring); pro
DECISIONS and results are real. Compare outcomes WITHIN a source across clusters; compare DECISIONS across sources.
    python analyze.py  -> analyze.out"""
from __future__ import annotations

import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'habits'))
import hablib as H  # noqa: E402

R = pickle.load(open(HERE / 'rows.pkl', 'rb'))
GROUPS = ('pro', 'CXXXVIII', 'CLIII', 'CLIX', 'CLX')
OURS = ('CXXXVIII', 'CLIII', 'CLIX', 'CLX')
TANKS = {'golem', 'giant', 'electro_giant', 'goblin_giant', 'lava_hound', 'elixir_golem', 'royal_giant', 'pekka',
         'mega_knight', 'goblinstein', 'giant_skeleton', 'boss_bandit'}
OUT = []


def say(*a):
    OUT.append(' '.join(str(x) for x in a))


# -------------------------------------------------------------------------------------------- the answer list K (data)
raw = json.load(open(HERE / 'counters_raw.json'))
K = sorted(c for c, v in raw.items() if 'live' in v and 'pro' in v and all(
    v[s]['n_eng'] >= 20 and v[s]['lock_eng'] <= v[s]['base_lock'] - 0.10 for s in ('live', 'pro')))
COST = {c: H.cost(c) for c in K}


def archetype(rev):
    rev = set(rev)
    if 'earthquake' in rev:
        return 'EQ'
    if rev & {'x_bow', 'mortar'}:
        return 'SIEGE'
    if 'hog_rider' in rev:
        return 'HOG'
    if rev & TANKS:
        return 'BEATDOWN'
    return 'OTHER'


def answer_ctx(r):
    cyc, est = r['cycle'], r['opp_est']
    seen = [c for c in K if c in cyc]
    if not seen:
        return 'unrevealed'
    inhand = [c for c in seen if cyc[c] >= 4]
    if not inhand:
        return 'cycled'
    return 'ready' if any(est >= COST[c] for c in inhand) else 'short'


def el_band(r):
    if r.get('own_el') is None:
        return None
    d = r['own_el'] - r['opp_est']
    return 'behind' if d < -1 else 'ahead' if d > 1 else 'even'


ARCH = {m['key']: archetype(m['revealed']) for m in R['match']}
MATCH = {m['key']: m for m in R['match']}
for r in R['xbow'] + R['rocket'] + R['opp_samples']:
    r['arch'] = ARCH[r['key']]
    r['ans'] = answer_ctx(r)
    r['elb'] = el_band(r)
for m in R['match']:
    m['arch'] = ARCH[m['key']]


def ci(rows, f):
    lo, hi = H.boot_ci(rows, f, B=400)
    return f'[{lo:.2f}, {hi:.2f}]'


def rate(n_rows, s_rows):
    """placements per opportunity-minute; match bootstrap over the union of keys."""
    tot_s = len(s_rows)
    v = 60.0 * len(n_rows) / tot_s / 1.0 if tot_s else float('nan')
    rows = [dict(key=r['key'], p=1, s=0) for r in n_rows] + [dict(key=r['key'], p=0, s=1) for r in s_rows]
    lo, hi = H.boot_ci(rows, lambda xs: 60.0 * sum(x['p'] for x in xs) / max(1, sum(x['s'] for x in xs)), B=300)
    return v, lo, hi


say('# W5 analyze.out  (rows.pkl:', {k: len(v) for k, v in R.items()}, ')')
say('X-Bow answer list K (lock when engaged <= source base - 0.10 in BOTH sources, n_eng >= 20 each):', K)
say('NOTE pro outcomes = native level-11 open-loop re-drive (counterfactual); pro decisions + match results are real.')
say('Base bridge lock: live', round(H.mean([r['lock'] for r in R['xbow'] if r['src'] == 'live' and r['type'] == 'bridge' and 'lock' in r]), 3),
    'pro', round(H.mean([r['lock'] for r in R['xbow'] if r['src'] == 'pro' and r['type'] == 'bridge' and 'lock' in r]), 3))

# ------------------------------------------------------------------------------------------------------ 1. matchups
say('\n## 1. Matchup archetypes (revealed by the match end): per match')
say('arch | group | n | win | bridge X/match | def X/match | tower Rockets/match | lock/bridge X | reach dmg/bridge X | '
    'next20 net/bridge X')
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER'):
    for g in GROUPS + ('ours',):
        gs = OURS if g == 'ours' else (g,)
        ms = [m for m in R['match'] if m['arch'] == a and m['group'] in gs]
        if not ms:
            continue
        keys = {m['key'] for m in ms}
        bx = [r for r in R['xbow'] if r['key'] in keys and r['type'] == 'bridge']
        bl = [r for r in bx if 'lock' in r]
        tr = [r for r in R['rocket'] if r['key'] in keys and r['aim'] == 'tower']
        say(f"{a:8s} | {g:8s} | {len(ms):4d} | {H.wr(ms):.3f} {ci(ms, H.wr)} | {len(bx) / len(ms):.2f} | "
            f"{sum(m['n_def'] for m in ms) / len(ms):.2f} | {len(tr) / len(ms):.2f} | "
            f"{H.mean([r['lock'] for r in bl]):.3f} | {H.mean([r['dmg_reach'] for r in bl]):.3f} | "
            f"{H.mean([r['next_opp20'] - r['next_own20'] for r in bx]):+.3f}")

# ------------------------------------------------------------------------- 2. decision clusters: propensity + outcome
say('\n## 2. Decision clusters (matchup x answer context at the moment): propensity per opportunity-minute and outcome')
say('cluster | group | opp-min | bridge X / opp-min [CI] | def X / opp-min | bridge n | lock | reach dmg | next20 net | '
    'answer el - 6 | win (bridge X placed)')
CL = {}
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER'):
    for ctx in ('ready', 'short', 'cycled', 'unrevealed'):
        for g in ('pro', 'ours') + OURS:
            gs = OURS if g == 'ours' else (g,)
            S = [r for r in R['opp_samples'] if r['arch'] == a and r['ans'] == ctx and r['group'] in gs]
            X = [r for r in R['xbow'] if r['arch'] == a and r['ans'] == ctx and r['group'] in gs]
            bx = [r for r in X if r['type'] == 'bridge']
            dx = [r for r in X if r['type'] == 'defensive']
            if len(S) < 60 and len(bx) < 10:
                continue
            v, lo, hi = rate(bx, S)
            vd = 60.0 * len(dx) / len(S) if S else float('nan')
            bl = [r for r in bx if 'lock' in r]
            row = dict(opp_min=len(S) / 60, bridge_rate=v, ci=(lo, hi), def_rate=vd, n=len(bx),
                       lock=H.mean([r['lock'] for r in bl]), dmg=H.mean([r['dmg_reach'] for r in bl]),
                       net=H.mean([r['next_opp20'] - r['next_own20'] for r in bx]),
                       trade=H.mean([r['answer_el'] - 6 for r in bl]), win=H.wr(bx))
            CL[(a, ctx, g)] = row
            if g in OURS:
                continue        # per-Mark rows go to section 2b
            say(f"{a}/{ctx:10s} | {g:5s} | {row['opp_min']:6.1f} | {v:.2f} [{lo:.2f}, {hi:.2f}] | {vd:.2f} | {len(bx):4d} | "
                f"{row['lock']:.3f} | {row['dmg']:.3f} | {row['net']:+.3f} | {row['trade']:+.2f} | {row['win']:.3f}")
say('\n## 2b. Same clusters per Mark (bridge X / opp-min, lock, n)')
for (a, ctx, g), row in sorted(CL.items()):
    if g in OURS:
        say(f"{a}/{ctx:10s} | {g:8s} | opp-min {row['opp_min']:5.1f} | bridge/opp-min {row['bridge_rate']:.2f} "
            f"[{row['ci'][0]:.2f}, {row['ci'][1]:.2f}] | n {row['n']:3d} | lock {row['lock']:.3f} | net {row['net']:+.3f}")

# ---------------------------------------------------------------------- 3. the ratio ours / pros of bridge propensity
say('\n## 3. Bridge-X-Bow propensity ratio ours / pro per cluster (> 1 = we force more bridge X-Bows than pros there)')
for (a, ctx, g), row in sorted(CL.items()):
    if g != 'ours' or (a, ctx, 'pro') not in CL:
        continue
    p = CL[(a, ctx, 'pro')]
    say(f"{a}/{ctx:10s} ours {row['bridge_rate']:.2f} vs pro {p['bridge_rate']:.2f} -> x{row['bridge_rate'] / p['bridge_rate']:.2f} | "
        f"def ours {row['def_rate']:.2f} vs pro {p['def_rate']:.2f} | our lock {row['lock']:.2f} (pro re-drive {p['lock']:.2f}) | "
        f"our net {row['net']:+.3f} | our opp-min {row['opp_min']:.0f}")

# ------------------------------------------------------------------------------------------- 4. sunk-cost sequences
say('\n## 4. Sunk cost: the X-Bow AFTER a failed bridge X-Bow (no lock, not censored) in the same match')
say('arch | group | failed bridge X | next X-Bow: bridge share | its lock | defensive share | no further X-Bow | '
    'tower Rockets in the 30 s after the failure')
by = defaultdict(list)
for r in R['xbow']:
    by[r['key']].append(r)
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER', 'ALL'):
    for g in ('pro', 'ours'):
        gs = OURS if g == 'ours' else (g,)
        nxt, none, fails, rk = [], 0, 0, 0
        for k, xs in by.items():
            if (a != 'ALL' and ARCH[k] != a) or xs[0]['group'] not in gs:
                continue
            xs = sorted(xs, key=lambda r: r['tick'])
            for i, r in enumerate(xs):
                if r['type'] != 'bridge' or 'lock' not in r or r['lock'] or r['censored']:
                    continue
                fails += 1
                rk += sum(1 for q in R['rocket'] if q['key'] == k and q['aim'] == 'tower' and r['end_tick'] <= q['tick'] <= r['end_tick'] + 600)
                if i + 1 < len(xs):
                    nxt.append(xs[i + 1])
                else:
                    none += 1
        if not fails:
            continue
        nb = [r for r in nxt if r['type'] == 'bridge']
        say(f"{a:8s} | {g:4s} | {fails:4d} | {len(nb) / fails:.3f} | {H.mean([r.get('lock') for r in nb if 'lock' in r]):.3f} | "
            f"{sum(r['type'] == 'defensive' for r in nxt) / fails:.3f} | {none / fails:.3f} | {rk / fails:.3f}")

# ----------------------------------------------------------------------------------- 5. Rocket cycling by cluster
say('\n## 5. Rocket use per matchup: tower Rockets per minute of match, share fired with NO X-Bow alive ("Rocket cycle"),'
    ' tower damage per tower Rocket')
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER'):
    for g in ('pro', 'ours'):
        gs = OURS if g == 'ours' else (g,)
        ms = [m for m in R['match'] if m['arch'] == a and m['group'] in gs]
        keys = {m['key'] for m in ms}
        tr = [r for r in R['rocket'] if r['key'] in keys and r['aim'] == 'tower']
        mins = sum(m['end'] for m in ms) * 0.05 / 60
        cyc = [r for r in tr if not r['xbow_alive']]
        say(f"{a:8s} | {g:4s} | matches {len(ms):4d} | tower Rockets/min {len(tr) / mins:.3f} | no-X-Bow share "
            f"{len(cyc) / max(1, len(tr)):.2f} | dmg/Rocket {H.mean([r.get('tower_dmg') for r in tr]):.3f} | "
            f"Rocket-cycle Rockets/min {len(cyc) / mins:.3f}")

# --------------------------------------------------- 6. what happens after we turtle (defensive X-Bow) in hostile ones
say('\n## 6. Defensive X-Bows: next-20-s net and own tower HP lost, by matchup (live real frames; pro re-drive)')
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER'):
    for g in ('pro', 'ours'):
        gs = OURS if g == 'ours' else (g,)
        dx = [r for r in R['xbow'] if r['arch'] == a and r['group'] in gs and r['type'] == 'defensive']
        bx = [r for r in R['xbow'] if r['arch'] == a and r['group'] in gs and r['type'] == 'bridge']
        if not dx:
            continue
        say(f"{a:8s} | {g:4s} | def n {len(dx):4d} net {H.mean([r['next_opp20'] - r['next_own20'] for r in dx]):+.3f} "
            f"own lost {H.mean([r['next_own20'] for r in dx]):.3f} | bridge n {len(bx):4d} net "
            f"{H.mean([r['next_opp20'] - r['next_own20'] for r in bx]):+.3f} own lost {H.mean([r['next_own20'] for r in bx]):.3f}")

# ------------------------------------------------------------------------------ 7. robustness: crowns-matching re-drives
say('\n## 7. Robustness: pro rows restricted to re-drives that reproduced the recorded crowns (crowns_match)')
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER'):
    bx = [r for r in R['xbow'] if r['src'] == 'pro' and r['arch'] == a and r['type'] == 'bridge' and 'lock' in r]
    bm = [r for r in bx if r['crowns_match']]
    say(f"{a:8s} pro bridge lock all {H.mean([r['lock'] for r in bx]):.3f} (n {len(bx)}) vs crowns_match "
        f"{H.mean([r['lock'] for r in bm]):.3f} (n {len(bm)})")

# ------------------------------------------------- 8. our bridge X-Bows by answer context: lock / longer horizon, CIs
say('\n## 8. OUR bridge X-Bows (live, real frames) by answer context within each matchup: lock [match-bootstrap CI], '
    'net over 40 s, P(an own princess falls within 40 s)')
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER', 'ALL'):
    for ctx in ('ready', 'short', 'cycled', 'unrevealed'):
        for g in ('ours', 'pro'):
            bx = [r for r in R['xbow'] if r['group'] in (OURS if g == 'ours' else ('pro',)) and r['type'] == 'bridge'
                  and r['ans'] == ctx and (a == 'ALL' or r['arch'] == a) and 'lock' in r]
            if len(bx) < 15:
                continue
            say(f"{a:8s} {ctx:10s} {g:4s} n {len(bx):4d} | lock {H.mean([r['lock'] for r in bx]):.3f} "
                f"{ci(bx, lambda xs: H.mean([r['lock'] for r in xs]))} | net40 "
                f"{H.mean([r['next_opp40'] - r['next_own40'] for r in bx]):+.3f} | own princess falls <= 40 s "
                f"{H.mean([r['princess_fell40'] for r in bx]):.3f}")

# ------------------------------------------------------- 9. what pros invest in instead: shares per decision context
say('\n## 9. Investment plays per context: shares of bridge X-Bow / defensive X-Bow / tower Rocket (all own X-Bows + tower '
    'Rockets placed in that context) and tower Rockets per opportunity-minute')
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER'):
    for ctx in ('ready', 'short', 'cycled', 'unrevealed'):
        for g in ('pro', 'ours'):
            gs = OURS if g == 'ours' else ('pro',)
            bx = sum(1 for r in R['xbow'] if r['group'] in gs and r['arch'] == a and r['ans'] == ctx and r['type'] == 'bridge')
            dx = sum(1 for r in R['xbow'] if r['group'] in gs and r['arch'] == a and r['ans'] == ctx and r['type'] == 'defensive')
            rk = sum(1 for r in R['rocket'] if r['group'] in gs and r['arch'] == a and r['ans'] == ctx and r['aim'] == 'tower')
            n = bx + dx + rk
            S = sum(1 for r in R['opp_samples'] if r['group'] in gs and r['arch'] == a and r['ans'] == ctx)
            if n < 15:
                continue
            say(f"{a}/{ctx:10s} {g:4s} n {n:4d} | bridge {bx / n:.2f} | defensive {dx / n:.2f} | tower Rocket {rk / n:.2f} | "
                f"tower Rockets / opp-min {60 * rk / max(1, S):.2f}")

# ------------------------------------------- 10. within OUR matches: failed bridge X-Bows / tower Rockets vs result
say('\n## 10. Within our live matches (association only; a losing match also produces failures): win rate by the number '
    'of FAILED bridge X-Bows and by tower Rockets, per matchup')
fails = defaultdict(int)
for r in R['xbow']:
    if r['type'] == 'bridge' and 'lock' in r and not r['lock'] and not r['censored']:
        fails[r['key']] += 1
rk_n = defaultdict(int)
for r in R['rocket']:
    if r['aim'] == 'tower':
        rk_n[r['key']] += 1
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER', 'ALL'):
    for g in ('ours', 'pro'):
        ms = [m for m in R['match'] if m['group'] in (OURS if g == 'ours' else ('pro',)) and (a == 'ALL' or m['arch'] == a)]
        if not ms:
            continue
        cells = []
        for lab, f in (('fails 0', lambda m: fails[m['key']] == 0), ('fails 1', lambda m: fails[m['key']] == 1),
                       ('fails 2+', lambda m: fails[m['key']] >= 2), ('rockets 0', lambda m: rk_n[m['key']] == 0),
                       ('rockets 1', lambda m: rk_n[m['key']] == 1), ('rockets 2+', lambda m: rk_n[m['key']] >= 2)):
            sub = [m for m in ms if f(m)]
            cells.append(f"{lab}: {H.wr(sub):.2f} (n {len(sub)})" if sub else f'{lab}: -')
        say(f"{a:8s} {g:4s} | " + ' | '.join(cells))

# -------------------------------------------------------------------------- 11. per-minute bridge X-Bow volume
say('\n## 11. Bridge X-Bows and tower Rockets per minute of match, per matchup (match length differs between groups)')
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER'):
    for g in ('pro', 'ours'):
        ms = [m for m in R['match'] if m['group'] in (OURS if g == 'ours' else ('pro',)) and m['arch'] == a]
        mins = sum(m['end'] for m in ms) * 0.05 / 60
        say(f"{a:8s} {g:4s} | minutes {mins:6.1f} | bridge X-Bows/min {sum(m['n_bridge'] for m in ms) / mins:.3f} | "
            f"defensive/min {sum(m['n_def'] for m in ms) / mins:.3f} | mean match length {mins * 60 / len(ms):.0f} s")

open(HERE / 'analyze.out', 'w').write('\n'.join(OUT) + '\n')
json.dump({'|'.join(k): v for k, v in CL.items()}, open(HERE / 'clusters.json', 'w'), indent=0, default=float)
print('\n'.join(OUT))
