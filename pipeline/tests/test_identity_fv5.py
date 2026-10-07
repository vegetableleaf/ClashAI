"""Feature-version-5 spawner identity: every family's children are their own class (form 0), parents stay parents,
level-scaled HP resolves by the tower level, unreadable parents stay on the board with an unknown hp, card_id -1
troops map by catalog HP. fv4 is untouched. HP values: catalog base x level multiplier (level 11 = 256%, 15 = 372%,
16 = 409%), each also measured natively (L73 identity_fix/native_census.out) or live (spawners/map_live.json)."""
import pytest

from pipeline import obs_contract as O, vocab
from pipeline.body_identity import level_of_factor, resolve

DECK = O.load_deck('icebow')
L11_TOWERS = (3052, 4824)
L15_TOWERS = (4424, 7032)        # MEASURED live (live_play_20261004_002238)


def frame(bodies, towers=L11_TOWERS, card_ids=None):
    """Raw observe() dict; side 1 = enemy bodies (name, max_hp[, hp][, form via status_flags])."""
    princess, king = towers
    crown = [dict(side=s, type=t, x=x, y=y, hp=h, max_hp=h)
             for s in (0, 1) for t, x, y, h in (('king', 9000, 3000 if s == 0 else 29000, king),
                                                ('princess', 3500, 6500 if s == 0 else 25500, princess),
                                                ('princess', 14500, 6500 if s == 0 else 25500, princess))]
    ents = []
    for i, b in enumerate(bodies):
        name, mhp = b[0], b[1]
        hp = b[2] if len(b) > 2 else mhp
        e = dict(side=1, x=2000 + 300 * i, y=24000, name=name, hp=hp, max_hp=mhp, kind=15,
                 card_id=(card_ids or {}).get(i, 1 if name != '-1' else -1), entity_id=100 + i)
        if len(b) > 3:
            e['status_flags'] = b[3]
        ents.append(e)
    return dict(tick=200, players=[], entities=ents, episode=dict(crown_towers=crown))


def classes(obs, fv=5):
    bs = O.from_engine(obs, 0, DECK, unmapped=set(), feature_version=fv)
    return [(vocab.UNIT_VOCAB[u.cls], u.form, u.hp_frac) for u in bs.units]


# (engine name, level-11 child HP, child class, level-11 parent HP) -- native census values
FAMILIES = [('Witch', 81, 'skeletons', 839, 'witch'), ('DarkWitch', 81, 'bats', 906, 'night_witch'),
            ('FirespiritHut', 217, 'fire_spirit', 727, 'furnace'), ('Tombstone', 81, 'skeletons', 529, 'tombstone'),
            ('GoblinHut', 133, 'spear_goblins', 1180, 'goblin_hut'),
            ('BarbarianHut', 716, 'barbarians', 1164, 'barbarian_hut'), ('Graveyard', 81, 'skeletons', None, None),
            ('GoblinDrill', 202, 'goblins', 1313, 'goblin_drill'),
            ('SkeletonBalloon', 81, 'skeletons', 532, 'skeleton_barrel'),
            ('GoblinGiant', 133, 'spear_goblins', 3110, 'goblin_giant'),
            ('SkeletonKing', 1, 'skeletons', 2298, 'skeleton_king'),
            ('WitchMother', 629, 'mother_witch_hog', 529, 'mother_witch')]


@pytest.mark.parametrize('name,child_hp,child,parent_hp,parent', FAMILIES)
def test_level11_child_and_parent(name, child_hp, child, parent_hp, parent):
    bodies = [(name, child_hp, child_hp, 0)] + ([(name, parent_hp, parent_hp, 0)] if parent_hp else [])
    got = classes(frame(bodies))
    assert got[0][:2] == (child, 0)
    if parent_hp:
        assert got[1][:2] == (parent, 0)
    # fv4 is the legacy parent label for every child (unchanged contract)
    assert classes(frame(bodies), fv=4)[0][0] == vocab.UNIT_VOCAB[vocab.engine_unit_id(name, float(child_hp))]


@pytest.mark.parametrize('name,flags,child_hp,child', [
    ('Witch', 8, 81, 'skeletons'), ('FirespiritHut', 8, 217, 'fire_spirit'), ('Tombstone', 16, 81, 'skeletons'),
    ('GoblinDrill', 8, 202, 'goblins'), ('SkeletonBalloon', 8, 81, 'skeletons'), ('GoblinGiant', 8, 202, 'goblins')])
def test_evolved_parent_children_form0(name, flags, child_hp, child):
    # native/live: the child carries the evo/hero id (form 1/2) -> still form 0; SIM: status 0 -> same class
    for child_flags in (flags, 0):
        got = classes(frame([(name, child_hp, child_hp, child_flags)]))
        assert got[0][:2] == (child, 0), (child_flags, got)


def test_no_class_children_keep_parent_class_form0():
    # Goblin Brawler (native 1080 / SIM 1121) and Phoenix egg (317): no vocab class -> parent class, form 0
    got = classes(frame([('GoblinCage', 1080, 1080, 8), ('GoblinCage', 1121, 1121, 0), ('Phoenix', 317, 317, 0),
                         ('GoblinCage', 780, 780, 8)]))
    assert got == [('goblin_cage', 0, 1.0), ('goblin_cage', 0, 1.0), ('phoenix', 0, 1.0), ('goblin_cage', 1, 1.0)]


def test_goblin_drill_dig_body_is_the_drill():
    assert classes(frame([('GoblinDrill', 2560, 2560, 9)]))[0][:2] == ('goblin_drill', 1)


def test_level_scaled_hp_live():
    # level 15 (tower factor 4424/3052): Witch 1220 + skeletons 119, Furnace 1056 + fire spirits 312 (MEASURED live)
    assert level_of_factor(4424 / 3052) == 15 and level_of_factor(1.0) == 11
    got = classes(frame([('Witch', 1220), ('Witch', 119), ('FirespiritHut', 1056), ('FirespiritHut', 312)], L15_TOWERS))
    assert [g[0] for g in got] == ['witch', 'skeletons', 'furnace', 'fire_spirit']


def test_level_tie_broken_by_tower_then_parent():
    # 343 = fire spirit at level 16 (calibrated 84 x 409%) = furnace at level 3 (284 x 121%)
    assert resolve('FirespiritHut', 343).reason == 'ambiguous_hp'
    assert classes(frame([('FirespiritHut', 343)], L15_TOWERS))[0][0] == 'fire_spirit'          # tower level 15
    # level-5 towers alone pick the level-3 furnace; a level-16 furnace on the same board overrides the tower level
    low = (1740, 2750)
    assert level_of_factor(1740 / 3052) == 5
    assert classes(frame([('FirespiritHut', 343)], low))[0][0] == 'furnace'
    got = classes(frame([('FirespiritHut', 1161), ('FirespiritHut', 343)], low))
    assert [g[0] for g in got] == ['furnace', 'fire_spirit']
    assert resolve('FirespiritHut', 343, parent_levels={16}, level=5).how == 'parent_level'


def test_mirror_level17_evo_witch():
    # MEASURED live_play_20261006_150923: 1476 = 328 x 4.50, 144 = 32 x 4.50
    parent, child = resolve('Witch', 1476, 1), resolve('Witch', 144, 1)
    assert (parent.cls, parent.form, child.cls, child.form) == (vocab.unit_id('witch'), 1, vocab.unit_id('skeletons'), 0)


def test_unreadable_evo_witch_kept_with_unknown_hp():
    obs = frame([('Witch', -1, -1, 8), ('Witch', 81, 81, 0)])
    assert classes(obs) == [('witch', 1, None), ('skeletons', 0, 1.0)]
    tok, mask, _ = O.to_tokens(O.from_engine(obs, 0, DECK, feature_version=5))
    row = tok[mask][[int(t[0]) for t in tok[mask]].index(vocab.unit_id('witch'))]
    assert row[7] == 0.0                                      # hp_known = 0: the token format's unknown-hp marker
    assert classes(obs, fv=4) == [('witch', 0, 1.0)]          # fv4 still drops her (and labels the skeleton witch)


def test_unnamed_troops_map_by_catalog_hp():
    # card_id -1: cursed hog 629 (L11) / 915 (L15 live), cursed goblin 202; towers and unknown HPs stay dropped
    got = classes(frame([('-1', 629), ('-1', 202), ('-1', 4444), ('-1', 0, 0)]))
    assert got == [('mother_witch_hog', 0, 1.0), ('goblins', 0, 1.0)]
    assert classes(frame([('-1', 915)], L15_TOWERS)) == [('mother_witch_hog', 0, 1.0)]
    assert classes(frame([('-1', 629)]), fv=4) == []


def test_native_list_frame_matches_raw():
    from pipeline.native_recording import tag_native_recording
    rows = [[1, 2000, 24000, 'Witch', 81, 81, 15, 13000007, 5000010], [1, 2300, 24000, 'Witch', -1, -1, 15, 13000007, 5000011],
            [1, 2600, 24000, '-1', 629, 629, 15, -1, 5000012], [1, 9000, 29000, '-1', 4824, 4824, 12, -1, 5000000]]
    rec = dict(record_native=True, frames=[dict(tick=100, elixir=[5, 5], towers=[], entities=rows)])
    compact = tag_native_recording(rec, {})['frames'][0]
    bs = O.from_engine(compact, 0, DECK, unmapped=set(), feature_version=5)
    assert [(vocab.UNIT_VOCAB[u.cls], u.form, u.hp_frac) for u in bs.units] == \
        [('skeletons', 0, 1.0), ('witch', 1, None), ('mother_witch_hog', 0, 1.0)]
    old = O.from_engine(compact, 0, DECK, unmapped=set(), feature_version=4)
    assert [(vocab.UNIT_VOCAB[u.cls], u.form) for u in old.units] == [('witch', 1)]


def test_dead_bodies_still_dropped():
    assert classes(frame([('Witch', 839, 0), ('Witch', 81, -5)])) == []
