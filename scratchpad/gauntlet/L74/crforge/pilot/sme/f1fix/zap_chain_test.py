"""ENG-SME planted checks for SME_ZAP_CHAIN1 (fights.unseen_zaps): FRESH2 130148@3404 shape -- our princess tower takes 77
every 4-6 ticks from a periodic attacker and a 15-hp body of ours dies in the same gap. With the flag the periodic tower
drop is no Zap evidence (no Zap); a true Zap (two bodies take the drop once) is still found with the flag; without the
flag the old behaviour (false Zap) is kept.   python -I zap_chain_test.py"""
import importlib, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), *(['..'] * 7)))
CAT = {26000000: dict(display_name='Knight', type='troop'), 26000001: dict(display_name='Archers', type='troop')}
stats = lambda name: {'collision_radius_milli': 500}  # noqa: E731


def tower(hp):
    return dict(id='T', side=0, card_id=-1, x=3500, y=6500, hp=hp, tower=True)


def body(i, hp, x=4000, y=8000, cid=26000000):
    return dict(id=i, side=0, card_id=cid, x=x, y=y, hp=hp, tower=False)


def zaps(frames, chain):
    os.environ['SME_ZAP_CHAIN1'] = '1' if chain else '0'
    from scratchpad.gauntlet.L74.parity import fights
    importlib.reload(fights)
    return fights.unseen_zaps(dict(frames=frames), CAT, [], stats)


# periodic tower drops of 77 (3384, 3388, 3394, 3398, 3404) + a 15-hp body gone at 3404
hp, fr = 948, []
for t in range(3382, 3412, 2):
    if t in (3384, 3388, 3394, 3398, 3404, 3408):
        hp -= 77
    fr.append((t, [tower(hp)] + ([body('iw', 15)] if t < 3404 else [])))
assert len(zaps(fr, False)) >= 1, 'old rule: the false Zap is made'
assert zaps(fr, True) == [], zaps(fr, True)
# a true Zap: two bodies take 306 once, no repeat
fr2 = [(t, [tower(4858), body('k', 1000 if t < 2004 else 694), body('a', 500 if t < 2004 else 194, 4500, 8500, 26000001)])
       for t in range(1990, 2020, 2)]
z = zaps(fr2, True)
assert len(z) == 1 and z[0]['name'] == 'Zap' and z[0]['side'] == 1, z
print('zap_chain_test ok 3')
