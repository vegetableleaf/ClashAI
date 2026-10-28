"""GB-DECOY in the SIM (barrel_decoy_sim): on the same evolved Goblin Barrel situation (live 090643@4315: real left,
decoy mirrored right), the crforge SIM rows with the key on give the policy the projectile tokens live's --barrel-decoy
on gives it; key off = today's SIM (no barrel token in flight). CPU only; the crforge_core part needs the pod runtime."""
import os
from types import SimpleNamespace as NS

import pytest

from pipeline import barrel_decoy as B
from pipeline.projectile_motion import ProjectileMotion
from pipeline.projectile_observation import objects, sim_objects, tokens_from_objects

GB_SIM = 112                        # RoyaleSim catalogue id of GoblinBarrel (decoy_probe.out: spells card 112)
NAMES = {GB_SIM: 'GoblinBarrel'}
SCALE = 18                          # royale_env.SCALE
GID = {'goblin-barrel': 42}         # B0 / CLXIII vocab: no decoy key
ME, TICK = 0, 300


def reader():                       # what live's reader lists: both barrels under the Goblin Barrel card id
    real = dict(side=1, x=9000, y=28224, card_id=28000004, target_x=3499, target_y=6499, generation_key=4000357)
    return dict(projectiles=[real, dict(real, target_x=14501, generation_key=4000358)], effects=[])


def sim(flag_on):
    """crforge facade state() rows of the same flight: the real barrel (GoblinBarrelSpell_EV1) is a FLIGHT spell row only
    with the key on, else a crown-tower shot; the decoy (GoblinBarrelSpell_EV1_Decoy) is a crown-tower shot either way."""
    xy = dict(team=1, x=9000 * SCALE, y=28224 * SCALE, aim_y=6499 * SCALE)
    shot = lambda ax: NS(**xy, aim_x=ax, target_uid=-1, splash=0, firer_card_id=-1)   # noqa: E731
    real = NS(**xy, card_id=GB_SIM, motion=0, aim_x=3499 * SCALE, delay_ticks=0, travelled=0, length=0, hits=0)
    spells, shots = ([real], [shot(14501 * SCALE)]) if flag_on else ([], [shot(3499 * SCALE), shot(14501 * SCALE)])
    return NS(spells=spells, projectiles=shots)


def tokens(got, gid=GID):
    return tokens_from_objects(ProjectileMotion(catalog_fallback=True).update(got, TICK), ME, gid)['projectiles']


def live(gid=GID):
    return tokens(B.objects(reader(), source='reader'), gid)


def sim_tokens(flag_on, gid=GID):
    return tokens(objects(sim_objects(sim(flag_on), NAMES, SCALE), source='sim'), gid)


def test_key_off_is_todays_sim_no_barrel_token():
    assert not sim_tokens(False)[:, 0].any()


def test_key_on_matches_live_relabel_one_real_barrel_token():
    got, want = sim_tokens(True), live()
    assert (got == want).all()
    rows = got[got[:, 0] != 0]
    assert len(rows) == 1 and rows[0, 0] == 42
    assert abs(rows[0, 4] - 3499 / 18000) < 1e-6          # the token's landing x is the REAL (left) barrel's


def test_known_limit_a_vocab_with_the_decoy_key():
    # live shows a successor that adds DECOY_KEY a second token; the SIM (decoy left a tower shot) does not
    gid = dict(GID, **{B.DECOY_KEY: 43})
    assert (live(gid)[:, 0] != 0).sum() == 2 and (sim_tokens(True, gid)[:, 0] != 0).sum() == 1


def test_crforge_core_objects_by_env(monkeypatch):
    pytest.importorskip('royalegym')
    from pipeline import crforge_core as cc
    monkeypatch.delenv('CRFORGE_BARREL_DECOY_SIM', raising=False)
    assert cc.barrel_decoy_sim_objects() == {}
    monkeypatch.setenv('CRFORGE_BARREL_DECOY_SIM', '1')
    assert cc.barrel_decoy_sim_objects() == {'GoblinBarrelSpell_EV1': ('GoblinBarrel', 0), 'SnowballSpell_EV1': ('Snowball', 0)}
    monkeypatch.setenv('CRFORGE_BARREL_DECOY_SIM', 'yes')
    with pytest.raises(ValueError):
        cc.barrel_decoy_sim_objects()


def test_rl_royale_key(monkeypatch):
    from pipeline import rl_royale as R
    monkeypatch.delenv('CRFORGE_BARREL_DECOY_SIM', raising=False)
    for absent in ({}, {'barrel_decoy_sim': None}, {'barrel_decoy_sim': False}):
        assert R.barrel_decoy_sim_cfg(absent) is False and 'CRFORGE_BARREL_DECOY_SIM' not in os.environ
    assert R.barrel_decoy_sim_cfg({'barrel_decoy_sim': True}) is True
    assert os.environ['CRFORGE_BARREL_DECOY_SIM'] == '1'
    with pytest.raises(SystemExit):
        R.barrel_decoy_sim_cfg({'barrel_decoy_sim': 'on'})
    monkeypatch.setenv('CRFORGE_BARREL_DECOY_SIM', '0')
    with pytest.raises(SystemExit):
        R.barrel_decoy_sim_cfg({'barrel_decoy_sim': True})


def test_evolved_snowball_key_on_matches_live():
    # crforge: an evolved Snowball (SnowballSpell_EV1) is a crown-tower shot (no token) unless the key maps it to a Snowball
    # FLIGHT row; live lists it under the Snowball card (28000017, or the evo form 13000094: both decode to Snowball)
    xy = dict(team=1, x=9000 * SCALE, y=28224 * SCALE, aim_x=3500 * SCALE, aim_y=6500 * SCALE)
    off = NS(spells=[], projectiles=[NS(**xy, target_uid=-1, splash=0, firer_card_id=-1)])
    on = NS(spells=[NS(**xy, card_id=125, motion=0, delay_ticks=0, travelled=0, length=0, hits=0)], projectiles=[])
    gid, names = {'giant-snowball': 7}, {125: 'Snowball'}
    sim = lambda st: tokens(objects(sim_objects(st, names, SCALE), source='sim'), gid)   # noqa: E731
    assert not sim(off)[:, 0].any()
    for card in (28000017, 13000094):
        row = dict(side=1, x=9000, y=28224, card_id=card, target_x=3500, target_y=6500, generation_key=4000001)
        live_tok = tokens(B.objects(dict(projectiles=[row], effects=[]), source='reader'), gid)
        assert (sim(on) == live_tok).all() and (live_tok[:, 0] != 0).sum() == 1
