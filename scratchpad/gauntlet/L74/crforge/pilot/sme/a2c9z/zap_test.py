"""A2c-9Z planted checks for mech_rules.zap_is_cast / zap_point (synthetic groups; no log needed).
python -I zap_test.py  -> prints 'ok N' or fails an assert."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import mech_rules as M  # noqa: E402

R = {'Xbow': 600, 'Tesla': 500, 'Skeleton': 500, 'PrincessTower': 1000}
stats = lambda n: {'collision_radius_milli': R.get(n, 500)}  # noqa: E731


def body(name, x, y, hp, side=0, drop=None, buffs=()):
    return dict(side=side, name=name, x=x, y=y, hp=hp, drop=drop, buffs=list(buffs))


def group(hits, pre=None, post=None, electro=()):
    hits = {f'h{i}': h for i, h in enumerate(hits)}
    return dict(c=723, s=1, hits=hits, pre=pre or dict(hits), post=post or dict(hits), electro=list(electro))


n = 0
xb = body('Xbow', 2500, 12500, 1373, drop=314)
assert M.zap_is_cast(group([xb]), 16); n += 1                                          # 204518@722 shape
assert not M.zap_is_cast(group([xb], electro=[(9000, 15000)]), 16); n += 1             # Electro body 7 tiles away
assert M.zap_is_cast(group([xb], electro=[(16404, 22612)]), 16); n += 1                # 204518's Electro Dragon, 17 tiles
assert not M.zap_is_cast(group([body('Xbow', 2500, 12500, 1, drop=1697)]), 16); n += 1  # Lightning-sized
assert not M.zap_is_cast(group([body('PrincessTower', 14500, 6500, 4000, drop=306)]), 16); n += 1   # 306 on a tower
assert M.zap_is_cast(group([body('PrincessTower', 14500, 6500, 4781, drop=77)]), 16); n += 1        # 010245@572 shape
assert not M.zap_is_cast(group([body('Knight', 0, 0, 500, drop=159)]), 16); n += 1      # Electro Spirit-sized
assert not M.zap_is_cast(group([xb]), 15); n += 1                                        # wrong level
assert not M.zap_is_cast(group([body('Knight_EV1', 0, 0, 900, drop=48, buffs=['Knight_Fortify_EV1'])]), 16); n += 1  # no usable hit
assert M.zap_is_cast(group([xb, body('Knight_EV1', 0, 0, 900, drop=48, buffs=['Knight_Fortify_EV1'])]), 16); n += 1   # fortify skipped

# point: kept when consistent, re-solved to cover a dead skeleton otherwise (001702@2492 shape)
hits = [body('Xbow', 2500, 19500, 1556, drop=315), body('Knight_EV1', 4211, 15397, 1754, drop=48)]
sk = {'d0': body('Skeleton', 3085, 14254, 130), 'd1': body('Skeleton', 2803, 16238, 130)}
g = group(hits)
g['pre'] = dict(g['hits'], **sk)
x, y = M.zap_point(g, 16, stats, (2300, 17836))
assert (x, y) != (2300, 17836) and all(((b['x'] - x) ** 2 + (b['y'] - y) ** 2) ** .5 <= 2500 + 500 for b in sk.values()); n += 1
assert M.zap_point(g, 16, stats, (x, y)) == (x, y); n += 1
# a point covering an unbuffed body of the victim side is re-solved away from it
g2 = group([xb])
g2['post'] = dict(g2['hits'], t=body('Tesla', 5000, 14000, 1000))
x2, y2 = M.zap_point(g2, 16, stats, (3500, 13000))
assert ((5000 - x2) ** 2 + (14000 - y2) ** 2) ** .5 > 3000 and ((2500 - x2) ** 2 + (12500 - y2) ** 2) ** .5 <= 3100; n += 1
print('ok', n)
