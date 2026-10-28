"""ENG-SME planted checks for SME_TOWER_ZAP (mech_rules.tower_zaps) on synthetic frames shaped like FRESH1 000420@3519:
our right princess tower at 7 hp, last listed 3517, gone from 3519; the opponent's deck holds a level-16 Zap; our Knight
5.4 tiles away; the opponent's last play a far Fireball at 3336. The base case must fire once (R 3518, window
[3517, 3518], the tower's centre); every planted cause must block it with its reason.   python -I tower_zap_test.py"""
import copy, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import mech_rules as M  # noqa: E402

TOWERS = [[0, 9000, 3000, -1, 7728, 7728, 12, 'k0'], [0, 3500, 6500, -1, 1920, 4858, 13, 'p0a'],
          [0, 14500, 6500, -1, 4715, 4858, 13, 'p0b'], [1, 9000, 29000, -1, 7728, 7728, 12, 'k1'],
          [1, 3500, 25500, -1, 4605, 4858, 13, 'p1a'], [1, 14500, 25500, -1, 7, 4858, 13, 'p1b']]
KNIGHT = [1, 12654, 20389, 26000000, 2499, 2822, 15, 'kn']
OPP = ['Wizard', 'MiniPekka', 'Witch', 'Knight', 'ElixirGolem', 'SkeletonArmy', 'Zap', 'Fireball']
US = ['Knight', 'IceWizard', 'Tesla', 'Log', 'Xbow', 'Rocket', 'Tornado', 'Skeletons']


def scene(gone=3519, last=3600):
    fr = []
    for t in range(3401, last + 1, 2):
        ents = [list(e) for e in TOWERS if not (e[7] == 'p1b' and t >= gone)] + [list(KNIGHT)]
        fr.append((t, ents, [], []))
    return fr


def sides(opp=OPP, lv=16):
    return {0: dict(deck=list(opp), levels=[lv] * 8), 1: dict(deck=list(US), levels=[16] * 8)}


PLAYS = [dict(side=0, kind='play', card='Fireball', name='Fireball', tick=3336, x=3500, y=17500)]


def at(fr, t):
    return next(f for f in fr if f[0] == t)


def run(fr=None, sd=None, plays=None, hidden=()):
    return M.tower_zaps(fr or scene(), PLAYS if plays is None else plays, sd or sides(), hidden)


def blocked_as(why, **kw):
    out, fired, blocked = run(**kw)
    assert not fired and [b['why'] for b in blocked] == [why], (why, fired, blocked)
    return 1


ok = 0
# base: fires once at the tower's centre, R = t - 1, window [tp, t - 1]
out, fired, blocked = run()
z = [p for p in out if p.get('mech') == 'tower_zap']
assert len(fired) == 1 and not blocked and len(z) == 1, (fired, blocked)
assert (z[0]['side'], z[0]['card'], z[0]['tick'], z[0]['run_ticks'], z[0]['x'], z[0]['y'], z[0]['deck_index']) == \
    (0, 'Zap', 3518, [3517, 3518], 14500, 25500, 6), z[0]
assert fired[0]['tp'] == 3517 and fired[0]['t'] == 3519 and fired[0]['hp'] == 7
assert [p['tick'] for p in out] == sorted(p['tick'] for p in out) and len(out) == len(PLAYS) + 1
ok += 1
# no firing -> the very same plays object back (the extractor's record stays byte-identical)
fr = scene(); fr = [(t, [e for e in ents if e[7] != 'p1b'], p, a) for t, ents, p, a in fr]
assert run(fr=fr)[0] is PLAYS and not run(fr=fr)[1]
ok += 1
# planted causes
ok += blocked_as('no_zap_in_deck', sd=sides([c if c != 'Zap' else 'Arrows' for c in OPP]))
ok += blocked_as('opp_play', plays=PLAYS + [dict(side=0, kind='play', card='Zap', name='Zap', tick=3500, x=3500, y=17500)])
ok += blocked_as('opp_play', plays=PLAYS + [dict(side=0, kind='play', card='Lightning', name='Lightning', tick=3480,
                                                 x=14500, y=25500)])
ok += blocked_as('opp_play', plays=PLAYS + [dict(side=0, kind='ability', card='MiniPekka', name='MiniPekka', tick=3490)])
fr = scene(); at(fr, 3517)[2].append([0, 9000, 20000, 28000003, 14500, 25500, 'pr', 1, 's', 't'])
ok += blocked_as('enemy_projectile', fr=fr)
fr = scene(); at(fr, 3517)[2].append([0, 14400, 24000, 27000008, 3500, 6500, 'pr', 1, 's', 't'])   # passing close by
ok += blocked_as('enemy_projectile', fr=fr)
fr = scene(); at(fr, 3515)[1].append([0, 14000, 18000, 26000000, 600, 2822, 15, 'ek'])         # 7,516 away
ok += blocked_as('enemy_body', fr=fr)
fr = scene(); at(fr, 3519)[3].append([0, 13000, 22000, 28000009, 400, 16, 'fx', 1])            # an area at t
ok += blocked_as('enemy_area', fr=fr)
fr = scene(); fr = [(t, [e for e in ents if not (e[7] == 'k1' and t >= 3519)], p, a) for t, ents, p, a in fr]
ok += blocked_as('cascade', fr=fr)
fr = scene(); fr = [(t, [e for e in ents if not (e[7] == 'p1a' and t >= 3519)], p, a) for t, ents, p, a in fr]
ok += blocked_as('cascade', fr=fr)
fr = scene(); at(fr, 3523)[1].append(list(TOWERS[5]))                                           # read again 2 frames on
_, fired, blocked = run(fr=fr)                         # 3519 relisted at 3523; its second removal (3525) is a flicker
assert not fired and [b['why'] for b in blocked] == ['relisted', 'flicker'], (fired, blocked)
ok += 1
ok += blocked_as('match_end', fr=scene(last=3519))
fr = [(t + 2700, e, p, a) for t, e, p, a in scene()]                         # the same shape at 6219: overtime tie-break
ok += blocked_as('tiebreak_window', fr=fr, plays=[])
ok += blocked_as('hidden_body', hidden=[dict(side=0, name='MiniPekkaHero', last=3450, end=3470, track={})])
fr = scene(); at(fr, 3517)[1].append([1, 14000, 23500, 26000001, 300, 300, 15, 'sk'])          # our body in Zap reach
ok += blocked_as('own_body_in_reach', fr=fr)
# hp: above the level's crown-tower damage -> not a candidate at all; at it -> fires
t5 = copy.deepcopy(TOWERS)
for hp, lv, n in ((78, 16, 0), (77, 16, 1), (71, 15, 0), (70, 15, 1)):
    fr = scene(); [e.__setitem__(4, hp) for f in fr for e in f[1] if e[7] == 'p1b']
    _, fired, blocked = run(fr=fr, sd=sides(lv=lv))
    assert len(fired) == n and not blocked, (hp, lv, fired, blocked)
    ok += 1
# not blocking: an opponent play far away, an old play near, a hidden window that ended long before, our own spell
ok += len(run(plays=PLAYS + [dict(side=0, kind='play', card='Knight', name='Knight', tick=3500, x=3000, y=12000)])[1]) == 1
ok += len(run(plays=PLAYS + [dict(side=0, kind='play', card='Lightning', name='Lightning', tick=3450, x=14500, y=25500)])[1]) == 1
ok += len(run(hidden=[dict(side=0, name='MiniPekkaHero', last=1093, end=1314, track={})])[1]) == 1
ok += len(run(plays=PLAYS + [dict(side=1, kind='play', card='Log', name='Log', tick=3510, x=14500, y=25500)])[1]) == 1
assert ok == 25, ok
print('tower_zap_test ok', ok)
