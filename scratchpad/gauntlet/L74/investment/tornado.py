"""W5 PART 2 (live + pros, same code): Tornado decisions in context. rows.pkl from extract_all.py.
(a) an opponent troop dropped at the bridge in a lane, BOTH own princesses up, our Tornado in hand and >= 3 elixir:
    what we played first (5 s), Tornado share, own princess HP lost + king hit in the next 15 s, by attacker.
(b) our Tornado casts that pull enemies TOWARD our king (toward_king > 1 tile) after >= 1 own princess fell: how often,
    per Mark, and what followed (king HP lost in 10 s, own tower HP lost in 20 s, result) vs other casts.
Pro outcomes = native level-11 re-drive (counterfactual); pro decisions are real.      python tornado.py -> tornado.out"""
import pickle
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'habits'))
import hablib as H  # noqa: E402

R = pickle.load(open(HERE / 'rows.pkl', 'rb'))
OURS = ('CXXXVIII', 'CLIII', 'CLIX', 'CLX')
BUILDING = {'hog_rider', 'ram_rider', 'battle_ram', 'royal_hogs', 'giant', 'royal_giant', 'goblin_giant', 'electro_giant',
            'golem', 'elixir_golem', 'balloon', 'wall_breakers', 'goblinstein', 'suspicious_bush', 'rune_giant'}
OUT = []


def say(*a):
    OUT.append(' '.join(str(x) for x in a))


def gsel(g):
    return OURS if g == 'ours' else (g,)


B = [r for r in R['bridge'] if r['hand'] and 'tornado' in r['hand'] and (r['own_el'] or 0) >= 3]
say('# W5 tornado.out')
say('## (a) bridge attacker, both princesses up, Tornado in hand, own elixir >= 3  (first response within 5 s)')
for att in ('hog_rider', 'BUILDING other', 'troop-targeting'):
    for g in ('pro', 'ours') + OURS:
        rs = [r for r in B if r['group'] in gsel(g) and (
            r['card'] == 'hog_rider' if att == 'hog_rider' else
            (r['card'] in BUILDING and r['card'] != 'hog_rider') if att == 'BUILDING other' else r['card'] not in BUILDING)]
        if len(rs) < 8:
            continue
        tn = [r for r in rs if r['tornado']]
        first = Counter(r['first'] for r in rs)
        say(f"{att:15s} | {g:8s} | n {len(rs):4d} | Tornado within 5 s {len(tn) / len(rs):.3f} | first: " +
            ', '.join(f'{k} {v / len(rs):.2f}' for k, v in first.most_common(5)) +
            f" | princess lost 15 s {H.mean([r['princess_lost'] for r in rs]):.3f} | king hit {H.mean([r['king_hit'] for r in rs]):.3f}")
say('\n(a2) the owner case: bridge HOG, both princesses up, Tornado in hand, own elixir in [3, 4) (exactly enough for one '
    '3-cost card)')
for g in ('pro', 'ours') + OURS:
    rs = [r for r in B if r['group'] in gsel(g) and r['card'] == 'hog_rider' and r['own_el'] < 4]
    if not rs:
        continue
    first = Counter(r['first'] for r in rs)
    say(f"{g:8s} n {len(rs):3d} | first: " + ', '.join(f'{k} {v / len(rs):.2f}' for k, v in first.most_common(6)))
say('\n(a3) outcome by first response to a bridge HOG (Tornado in hand, >= 3 elixir, both princesses up): own princess HP '
    'lost in 15 s, king hit (= king activated), n')
for g in ('pro', 'ours'):
    rs = [r for r in B if r['group'] in gsel(g) and r['card'] == 'hog_rider']
    for k, _ in Counter(r['first'] for r in rs).most_common(7):
        s = [r for r in rs if r['first'] == k]
        say(f"{g:5s} first={str(k):12s} n {len(s):4d} | princess lost {H.mean([r['princess_lost'] for r in s]):.3f} | "
            f"king hit {H.mean([r['king_hit'] for r in s]):.3f} | king lost {H.mean([r['king_lost'] for r in s]):.3f}")
say('\n(a3b) bridge HOG: did the Hog itself come <= 3.5 tiles from our king centre in the next 15 s (redirected onto the king)?')
for g in ('pro', 'ours'):
    rs = [r for r in B if r['group'] in gsel(g) and r['card'] == 'hog_rider']
    tn = [r for r in rs if r['tornado']]
    nt = [r for r in rs if not r['tornado']]
    say(f"{g:5s} with a Tornado within 5 s: n {len(tn):3d} Hog at king {H.mean([(r['att_king_dist'] or 99) <= 3.5 for r in tn]):.3f} | "
        f"without: n {len(nt):3d} Hog at king {H.mean([(r['att_king_dist'] or 99) <= 3.5 for r in nt]):.3f}")
say('\n(a4) WHERE our Tornado went vs a bridge Hog (distance of the cast from our king centre), and king hit rate')
for g in ('pro', 'ours'):
    s = [r for r in B if r['group'] in gsel(g) and r['card'] == 'hog_rider' and r['tornado']]
    for lo, hi in ((0, 4), (4, 6), (6, 8), (8, 99)):
        ss = [r for r in s if lo <= r['tornado']['d_king'] < hi]
        if ss:
            say(f"{g:5s} cast {lo}-{hi} tiles from our king: n {len(ss):3d} king hit {H.mean([r['king_hit'] for r in ss]):.3f} "
                f"princess lost {H.mean([r['princess_lost'] for r in ss]):.3f}")

T = R['tornado']
say('\n## (b) our Tornado casts by own princesses standing and pull direction (toward_king > 1 tile = enemies pulled toward '
    'OUR king; needs >= 1 enemy body in the radius)')
for g in ('pro', 'ours') + OURS:
    rs = [r for r in T if r['group'] in gsel(g)]
    nm = len({r['key'] for r in R['match'] if r['group'] in gsel(g)})
    for up in (2, 1):
        s = [r for r in rs if r['princesses_up'] == up and r['n_in']]
        tk = [r for r in s if r['toward_king'] is not None and r['toward_king'] > 1]
        ot = [r for r in s if r not in tk]
        if not s:
            continue
        say(f"{g:8s} princesses up {up} | casts {len(s):4d} ({len(s) / nm:.2f}/match) | toward king {len(tk):4d} "
            f"({len(tk) / max(1, len(s)):.2f} of casts, {len(tk) / nm:.3f}/match) | king lost 10 s: toward "
            f"{H.mean([r['king_lost10'] for r in tk]):.3f} vs other {H.mean([r['king_lost10'] for r in ot]):.3f} | own lost 20 s: "
            f"toward {H.mean([r['own_lost20'] for r in tk]):.3f} vs other {H.mean([r['own_lost20'] for r in ot]):.3f} | win: "
            f"toward {H.wr(tk):.3f} vs other {H.wr(ot):.3f}")
say('\n(b2) post-princess-loss pulls toward our king: which units were pulled (ours, all Marks)')
s = [r for r in T if r['group'] in OURS and r['princesses_up'] == 1 and r['toward_king'] is not None and r['toward_king'] > 1]
say(Counter(u for r in s for u in r['units']).most_common(15))
say('(b3) same for pros')
s = [r for r in T if r['group'] == 'pro' and r['princesses_up'] == 1 and r['toward_king'] is not None and r['toward_king'] > 1]
say(Counter(u for r in s for u in r['units']).most_common(15))
say('\n(b4) both princesses up, Tornado pulling a building-targeter toward our king (the redirect trick): king hit within '
    '10 s (king HP down) by unit (ours / pros)')
for g in ('pro', 'ours'):
    s = [r for r in T if r['group'] in gsel(g) and r['princesses_up'] == 2 and r['king_full_before'] and r['toward_king'] is not None
         and r['toward_king'] > 1]
    for u in ('hog_rider', 'ram_rider', 'battle_ram', 'royal_hogs', 'giant', 'balloon', 'golem', 'goblinstein', 'knight',
              'mini_pekka', 'valkyrie', 'musketeer', 'wizard', 'mega_knight', 'pekka'):
        ss = [r for r in s if u in r['units']]
        if len(ss) >= 5:
            say(f"{g:5s} {u:12s} n {len(ss):4d} king hit (lost > 0) {H.mean([r['king_lost10'] > 0 for r in ss]):.3f} | that unit came "
                f"<= 3.5 tiles from our king centre {H.mean([r['reach_king'].get(u, 99) <= 3.5 for r in ss]):.3f}")
open(HERE / 'tornado.out', 'w').write('\n'.join(OUT) + '\n')
print('\n'.join(OUT))
