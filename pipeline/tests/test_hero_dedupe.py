"""Lead 2026-10-06: reader v2's Hero Ice Wizard + FloatingCube pair (same id 203000023) must reach the model as ONE hero."""
from pipeline.reader_identity_aliases import dedupe_hero_bodies, HERO_ICE_WIZARD_ID as H


def e(side, x, y, cid=H, hp=1000):
    return {'side': side, 'x': x, 'y': y, 'card_id': cid, 'hp': hp, 'max_hp': 1000, 'kind': 15}


def test_pair_becomes_one_and_first_is_kept():
    f = {'entities': [e(1, 2656, 19548, hp=804), e(1, 2656, 19548), e(0, 9000, 3000, cid=26000000)]}
    out = dedupe_hero_bodies(f)
    heroes = [x for x in out['entities'] if x['card_id'] == H]
    assert len(heroes) == 1 and heroes[0]['hp'] == 804 and len(out['entities']) == 2
    assert len(f['entities']) == 3                       # input untouched


def test_no_duplicate_returns_same_object():
    f = {'entities': [e(1, 2656, 19548), e(0, 2656, 19548), e(1, 9000, 9000, cid=26000000)]}
    assert dedupe_hero_bodies(f) is f                    # one per side, far apart or other ids -> unchanged


def test_far_apart_same_side_kept():
    f = {'entities': [e(1, 2000, 19000), e(1, 9000, 9000)]}
    assert dedupe_hero_bodies(f) is f
