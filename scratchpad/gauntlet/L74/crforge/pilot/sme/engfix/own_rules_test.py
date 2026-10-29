"""ENG-FIX4 planted checks for SME_OWN_PENDCAST (sme_live.own_pend_cast, FRESH4 001856@3157) and SME_RASCAL_EDGE2
(sme_live.rascals_back, FRESH4 201103@1605) on the real records (laptop, no SIM):   python -I own_rules_test.py -> 'ok N'"""
import copy, json, os, sys
for k in ('SME_OWN_PENDCAST', 'SME_RASCAL7', 'SME_RASCAL_EDGE2'):
    os.environ[k] = '1'
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(H))
import live_frames, sme_live  # noqa: E402
L = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/live_play_2026%s.jsonl'
rec = lambda m: next(json.loads(s) for s in open(H + '/r7/fresh4_off.jsonl') if m in s)   # noqa: E731
n = 0


def check(name, ok):
    global n
    assert ok, name
    n += 1


# --- SME_OWN_PENDCAST on 001856 (my side 0): press 2916 (own_press), play 3145, cast_seen 3157, no elixir drop
x, F = rec('001856'), {f['t']: f for f in live_frames.convert(L % '1029_001856')}
P = x['plays']
cast = next(p for p in P if p['kind'] == 'ability' and p['tick'] == 3157)
check('real cast dropped', sme_live.own_pend_cast(cast, P, 0, F))
check('the later own press kept', not sme_live.own_pend_cast(next(p for p in P if p['kind'] == 'ability' and p['tick'] == 3217), P, 0, F))
check('opponent side never', not sme_live.own_pend_cast(cast, P, 1, F))
# MUST NOT FIRE: a 2-elixir drop on a frame pair of the window (a paid press missing from the tap log)
F2 = copy.deepcopy(F)
for t in sorted(F2):
    if t >= 3159:
        F2[t]['el'] -= 20000
check('paid drop keeps the cast', not sme_live.own_pend_cast(cast, P, 0, F2))
# MUST NOT FIRE: no play of the card between the press and the cast
check('no newer hero keeps the cast', not sme_live.own_pend_cast(cast, [p for p in P if not (p['kind'] == 'play' and p['tick'] == 3145)], 0, F))
# MUST NOT FIRE: the earlier press already resolved (its cast seen before)
P3 = P + [dict(cast, tick=2920, run_ticks=[2920, 2920])]
check('resolved press keeps the cast', not sme_live.own_pend_cast(cast, P3, 0, F))
# MUST NOT FIRE (v2, r8 finding): dev 182050@3463, a cast own_press_elixir dated by a ~1.93 drop ('own_elixir'), after an
# unresolved press (2932) and a play of the card (3213)
y = next(json.loads(s) for s in open(H + '/r7/dev_off.jsonl') if '182050' in s)
c2 = next(p for p in y['plays'] if p['kind'] == 'ability' and p['tick'] == 3463)
check('drop-dated cast kept (182050)', c2.get('dated') == 'own_elixir' and not sme_live.own_pend_cast(
    c2, y['plays'], y['my_side'], {f['t']: f for f in live_frames.convert(L % '1026_182050')}))
# flag off: never
sme_live.OWN_PENDCAST = 0
check('flag off', not sme_live.own_pend_cast(cast, P, 0, F))
sme_live.OWN_PENDCAST = 1

# --- SME_RASCAL_EDGE2 on 201103 (opponent side 1): girls at (8277 / 10723, 31750), the boy's point (9581, 29893)
x, F = rec('201103'), {f['t']: f for f in live_frames.convert(L % '1028_201103')}
p = next(p for p in x['plays'] if p['card'] == 'Rascals' and p['tick'] == 1605)
check('clamp girls -> back edge', sme_live.rascals_back(p, F)['y'] == 31000 and sme_live.rascals_back(p, F)['x'] == 9581)
sme_live.RASCAL_EDGE2 = 0
check('flag off: point unchanged', sme_live.rascals_back(p, F) == p)
sme_live.RASCAL_EDGE2 = 1


def girls(f, dy=0, dx=0):
    F2 = copy.deepcopy(F)
    for t in F2:
        if 1605 < t <= 1613:
            for e in F2[t]['E']:
                if e[0] == 1 and e[3] == sme_live.RASCALS_CARD and e[2] == 31750:
                    e[2] += dy
                    e[1] += dx if e[1] > 9500 else 0
    return F2


# MUST NOT FIRE: girls 10 units inside the clamp, or the pair spacing broken by 20 units
check('girls off the clamp: unchanged', sme_live.rascals_back(p, girls(F, dy=-10)) == p)
check('girl spacing broken: unchanged', sme_live.rascals_back(p, girls(F, dx=20)) == p)
print('ok', n)
