"""L74 identity extension (body_identity.extension, live --identity-ext on): new card ids and ability / evo spawn
bodies reach the model as learned classes; off (the default) leaves every identity as before."""
import argparse
import copy
from collections import deque
from pathlib import Path

import pytest
import torch

from pipeline import body_identity as BI, vocab
from pipeline.live_mem import deck_of, to_observe
from pipeline.obs_contract import from_engine
from pipeline.tests.test_live_mem import FRAME

L15 = 1.4535      # tower factor of a level-15 side (body_identity.level_of_factor -> 15)
U = vocab.UNIT_VOCAB

# (name as the live adapter gives it, max_hp, reader form) -> (class today, class with the extension, form with it)
CASES = [
    (('DarkPrince', 1971, 2), ('dark_prince', 'ram_rider', 0)),        # Hero Dark Prince's Rhino, L15
    (('DarkPrince', 1744, 2), ('dark_prince', 'dark_prince', 2)),      # the Hero Dark Prince himself, L15
    (('Musketeer', 2232, 2), ('musketeer', 'tesla', 0)),              # Trusty Turret, L15
    (('Musketeer', 1049, 2), ('musketeer', 'musketeer', 2)),          # Hero Musketeer, L15
    (('LittlePrince', 2325, 0), ('little_prince', 'knight', 0)),      # Guardienne, L15
    (('LittlePrince', 1015, 0), ('little_prince', 'little_prince', 0)),
    (('Mortar', 293, 1), ('mortar', 'goblins', 0)),                   # Evo Mortar goblin, L15
    (('Mortar', 1990, 1), ('mortar', 'mortar', 1)),
    (('Ghost', 119, 1), ('royal_ghost', 'skeletons', 0)),             # Evo Royal Ghost Souldier, L15
    (('13000043', 1949, 0), (None, 'elite_barbarians', 0)),           # Evo Elite Barbarians (not in the catalog)
    (('203000042', 945, 0), (None, 'electro_wizard', 0)),             # Hero Electro Wizard
    (('13000075', 6314, 0), (None, 'electro_giant', 0)),              # Evo Electro Giant
    (('26000107', 1817, 0), (None, 'balloon', 0)),                    # Minion Giant -> closest learned class
    (('Balloon', 688, 2), ('balloon', 'bandit', 0)),                  # Hero Balloon Skeletrooper, L15
    (('Balloon', 2436, 2), ('balloon', 'balloon', 2)),                # the Hero Balloon itself, L15
    (('Goblins', 3720, 2), ('goblins', None, 0)),                     # Hero Goblins banner, L15: dropped
    (('Goblins', 293, 2), ('goblins', 'goblins', 2)),                 # a Hero Goblin, L15
    (('Tombstone', 4224, 2), ('tombstone', 'giant', 0)),              # Hero Tombstone monster (L11 HP in a L15 board)
    (('Tombstone', 770, 2), ('tombstone', 'tombstone', 2)),           # the Hero Tombstone, L15
    (('EliteArcher', 394, 2), ('magic_archer', None, 0)),             # Hero Magic Archer decoy, L15: dropped
    (('EliteArcher', 770, 2), ('magic_archer', 'magic_archer', 2)),   # the Hero Magic Archer, L15
    (('Witch', 130, 0), ('skeletons', 'skeletons', 0)),               # fv5 family child: untouched
    (('Knight', 2539, 0), ('knight', 'knight', 0)),
]


def _board():
    return [(1, n, float(h), f, False) for (n, h, f), _ in CASES] + [(1, '-1', 915.0, 0, True), (1, 'Witch', -1.0, 1, False)]


def _cls(i):
    return None if i.cls is None else U[i.cls]


def test_off_is_today_and_on_maps_each_rule():
    off = BI.resolve_board(_board(), {0: L15, 1: L15})
    with BI.extension():
        on = BI.resolve_board(_board(), {0: L15, 1: L15})
    assert BI.EXTENSION is False
    for ((name, hp, form), (today, ext, ext_form)), a, e in zip(CASES, off, on):
        assert _cls(a) == today, (name, hp, a)
        assert (_cls(e), e.form) == ((ext, ext_form) if ext != today else (today, a.form)), (name, hp, e)
    assert off[-2:] == on[-2:]          # card_id -1 hog / unreadable Evo Witch untouched


def test_spawn_hp_tables_reproduce_the_live_values_and_spare_the_parent():
    t = BI.ext_tables()
    measured = {('dark_prince', 2): ('ram_rider', {1796, 1971}), ('musketeer', 2): ('tesla', {1536, 1854, 2034, 2232, 2454}),
                ('little_prince', 0): ('knight', {1600, 1931, 2118, 2325, 2556}), ('mortar', 1): ('goblins', {267, 293, 323}),
                ('royal_ghost', 1): ('skeletons', {81, 108, 119, 130}), ('balloon', 2): ('bandit', {627, 688, 756, 832}),
                ('tombstone', 2): ('giant', {4224, 5593}), ('goblins', 2): (None, {3390, 3720, 4090}),
                ('magic_archer', 2): (None, {271, 394, 433})}
    for key, (cls, hps) in measured.items():
        for hp in hps:                                   # every live census value is an exact table entry
            assert {c[0] and U[c[0]] for c in t[key][hp] if c[2] == 'ext_child'} == {cls}, (key, hp)
        # the parent's own HP never resolves to the spawn class at the parent's own level
        own = [(hp, c[3]) for hp, cs in t[key].items() for c in cs if c[2] == 'parent']
        for hp, level in own:
            got = BI._pick(t[key][hp], None, level)
            assert got is None or got.reason == 'parent', (key, hp, level)


def test_extension_restores_the_flag_on_error():
    with pytest.raises(RuntimeError):
        with BI.extension():
            assert BI.EXTENSION is True
            raise RuntimeError
    assert BI.EXTENSION is False


def _frame_with(*bodies):
    f = copy.deepcopy(FRAME)                              # observer side 1; enemy = side 0
    for i, (cid, hp) in enumerate(bodies):
        f['entities'].append(dict(side=0, x=9000, y=14000 + 500 * i, card_id=cid, hp=hp, max_hp=hp, kind=15,
                                  address='0xe%d' % i, category=5000100 + i))
    return f


def _units(frame, ext):
    deck, names = deck_of(frame, 1)
    if ext:
        with BI.extension():
            bs = from_engine(to_observe(frame, 1, names), 1, deck, unmapped=set(), feature_version=5)
    else:
        bs = from_engine(to_observe(frame, 1, names), 1, deck, unmapped=set(), feature_version=5)
    return [(U[u.cls], u.side, round(u.x, 6), round(u.y, 6), u.hp_frac, u.form) for u in bs.units]


def test_from_engine_changes_only_the_targeted_bodies():
    # Rhino, Evo E-Barbs, a base Musketeer, a Hero Goblins banner
    f = _frame_with((203000027, 1971), (13000043, 1949), (26000014, 2232), (203000002, 3720))
    off, on = _units(f, False), _units(f, True)
    assert [u[0] for u in off] == ['knight', 'dark_prince', 'musketeer', 'goblins']   # the evo id is dropped today
    assert [u[0] for u in on] == ['knight', 'ram_rider', 'elite_barbarians', 'musketeer']   # the banner is dropped
    assert off[1][1:-1] == on[1][1:-1] and on[1][-1] == 0 and off[1][-1] == 2   # same position / hp, form 0
    assert off[0] == on[0] and off[2] == on[3]


def test_live_pilot_scopes_the_extension_to_its_board(monkeypatch):
    from pipeline import obs_contract
    from pipeline.dataset_gen import card_key
    from pipeline.live_gen import GenPilot
    seen = []

    class Stop(Exception):
        pass

    def spy(*a, **k):
        seen.append(BI.EXTENSION)
        raise Stop

    monkeypatch.setattr(obs_contract, 'from_engine', spy)
    for flag in (None, True):
        p = object.__new__(GenPilot)
        _, names = deck_of(FRAME, 1)
        p.gid = {card_key(n): i + 1 for i, n in enumerate(names)}
        p.feature_version, p.ext_h, p.frames, p.history, p.opp_est, p.use_counter = 3, 0, deque(maxlen=30), {}, None, True
        if flag is not None:
            p.identity_ext = flag
        with pytest.raises(Stop):
            p.row(copy.deepcopy(FRAME))
    assert seen == [False, True] and BI.EXTENSION is False


def test_flag_is_deployable_from_live_options(tmp_path):
    from pipeline.live_options import EXTRA_LIVE_FLAGS, add_live_options_arguments, parse_with_live_options
    from pipeline.decision_options import add_arguments
    assert dict(EXTRA_LIVE_FLAGS)['--identity-ext'] == dict(choices=('off', 'on'), default='off')
    src = (Path(__file__).resolve().parents[2] / 'scratchpad/gauntlet/L68/live_reader/live_play.py').read_text(encoding='utf-8')
    assert '"--identity-ext", choices=("off", "on"), default="off"' in src
    f = tmp_path / 'LIVE_OPTIONS'
    f.write_text('--identity-ext on\n')
    for argv, want in (([], 'on'), (['--identity-ext', 'off'], 'off'), (['--no-live-options'], 'off')):
        ap = argparse.ArgumentParser()
        add_arguments(ap)
        ap.add_argument('--identity-ext', choices=('off', 'on'), default='off')
        add_live_options_arguments(ap, f)
        a, _ = parse_with_live_options(ap, argv)
        assert a.identity_ext == want, argv
