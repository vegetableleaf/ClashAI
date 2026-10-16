"""Gates for pipeline/sim_unit_state.py on small SIM scenarios (slowed Knight, frozen/stunned unit, hidden vs up Tesla,
X-Bow cycle, a shot in flight, river jump, charge, deploy).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_sim_unit_state.py

Runtime: PARITY_SIM_PATH=<unpacked royalesim 0.1.35 wheel dir> if set, else pipeline.royale_runtime.activate()
(honours ROYALE_RUNTIME). Skipped when the engine lacks the 160402017 card table or the save fields used here.
"""
import json
import os
import sys

import pytest

if os.environ.get('PARITY_SIM_PATH'):
    sys.path.insert(0, os.environ['PARITY_SIM_PATH'])
else:
    from pipeline.royale_runtime import activate
    activate()
sim = pytest.importorskip('royalesim')
if not hasattr(sim, 'EMBEDDED_CARDS_160402017_JSON') or not hasattr(sim.Battle, 'unit_types_digest'):
    pytest.skip('needs royalesim >= 0.1.35 (160402017 card table)', allow_module_level=True)

from pipeline.sim_unit_state import extract  # noqa: E402

K = 18000


def battle(spawns, deck=('Knight',), tower_hp=((4824, 0, 0), (4824, 3052, 3052))):
    """Blue = team 0 (princess towers down so only the scene fights), Red = team 1. spawns: (team, card, x_tiles, y_tiles). Deck = hand (<= 4 cards)."""
    b = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides={'cards.CARD_TABLE': json.dumps('client160402017_20261006')})
    ids = {dict(zip(sim.CATALOGUE_FIELDS, r))['name']: i for i, r in enumerate(json.loads(b.catalogue_json()))}
    d = [ids[n] for n in deck]
    sp = [(t, ids[n], int(x * K), int(y * K), -1) for t, n, x, y in spawns]
    b.reset(1, [d, d], 0, 200, [10000, 10000], [list(t) for t in tower_hp], sp,
            levels=[[11] * len(d)] * 2, tower_levels=[11, 11])
    return b


def unit(c, name, team):
    return next(u for u in c['units'] if u['name'] == name and u['team'] == team)


def test_slowed_knight_and_control():
    # Blue Ice Wizard shoots a red Knight that hits Blue's king: slowed, 35 progress per tick instead of 50.
    memo = {}
    slow = battle([(1, 'Knight', 9, 5), (0, 'IceWizard', 9, 9.2)], ('IceWizard',))
    ctrl = battle([(1, 'Knight', 9, 5), (0, 'Musketeer', 9, 9.2)], ('Musketeer',))
    for b in (slow, ctrl):
        b.step([], 45)
    k, kc = unit(extract(slow, memo), 'Knight', 1), unit(extract(ctrl), 'Knight', 1)
    assert k['status']['slowed'] and not kc['status']['slowed']
    assert 0 < k['status']['slow_frac'] <= 1 and kc['status']['slow_frac'] is None
    assert k['attack']['target'] is not None and k['attack']['hit_speed_ms'] == 1200 and k['state'] == 'engaged'
    steps = []
    for b in (slow, ctrl):
        p0 = unit(extract(b), 'Knight', 1)['attack']['progress_ms']
        b.step([], 1)
        steps.append(unit(extract(b), 'Knight', 1)['attack']['progress_ms'] - p0)
    assert steps == [35, 50]
    s = unit(extract(slow, memo), 'Knight', 1)['status']
    assert s['slowed'] and 0 < s['slow_frac'] <= 1
    json.dumps(extract(slow, memo))                       # plain data
    assert extract(slow) == extract(slow)                 # deterministic


def test_frozen_and_stunned():
    b = battle([(1, 'Knight', 9, 12), (1, 'Giant', 9, 13.5)], ('Freeze', 'Zap'))
    assert not unit(extract(b), 'Knight', 1)['status']['frozen']
    b.step([(0, 0, int(9 * K), int(12 * K))], 8)          # Freeze on the Knight
    c = extract(b)
    assert unit(c, 'Knight', 1)['status']['frozen'] and unit(c, 'Knight', 1)['buffs']
    z = battle([(1, 'Knight', 9, 12)], ('Zap',))
    z.step([(0, 0, int(9 * K), int(12 * K))], 6)
    zs = unit(extract(z), 'Knight', 1)['status']
    assert zs['frozen'] and not zs['stunned']              # the engine's stun = frozen (live: ZapFreeze); 'stunned' is name-only


def test_hero_buff_rows_and_tesla_deploy():
    from pipeline import sim_unit_state as m
    buffs = m._tbl(sim)['buffs']
    assert buffs['IceWizardHeroSlow']['speed_multiplier_raw'] == -30       # nested row: only in the projectile / ability
    assert m._statuses('IceWizardHeroSlow', buffs) == {'slowed'}
    assert m._statuses('Freeze|ZapFreeze|GiantHero_Slap_Stun', buffs) == {'frozen'}   # merged id: no name-word tags
    b = battle([], ('Tesla',))
    b.step([(0, 0, int(9 * K), int(8 * K))], 2)            # played, still deploying
    t = unit(extract(b), 'Tesla', 0)
    assert t['state'] == 'deploying' and t['hide'] is None


def test_tesla_hidden_then_up():
    far = battle([(1, 'Tesla', 9, 12), (0, 'Knight', 9, 4)])   # 8 tiles: out of range
    near = battle([(1, 'Tesla', 9, 12), (0, 'Knight', 9, 8)])  # 4 tiles: in range
    for b in (far, near):
        b.step([], 60)
    h, u = unit(extract(far), 'Tesla', 1), unit(extract(near), 'Tesla', 1)
    assert (h['hide'], h['attack']['target']) == ('hidden', None) and h['attack']['phase'] == 'idle'
    assert u['hide'] == 'up' and u['attack']['target'] is not None and u['attack']['hit_speed_ms'] == 1100
    assert unit(extract(near), 'Knight', 0)['hide'] is None


def test_xbow_mid_cycle():
    b = battle([(1, 'Xbow', 9, 12), (0, 'Giant', 9, 5)])
    b.step([], 100)                                          # past deploy, locked on the Giant
    phases, fracs = [], []
    for _ in range(24):
        a = unit(extract(b), 'Xbow', 1)['attack']
        phases.append(a['phase']); fracs.append(a['frac'])
        b.step([], 1)
    assert a['hit_speed_ms'] == 400 and a['target'] is not None
    assert phases.count('hit') == 3 and phases.count('windup') == 21     # one hit every 8 ticks (400 ms / 50)
    assert all(0 <= f < 1 for f in fracs) and set(fracs) == {i / 8 for i in range(8)}


def test_projectile_in_flight_with_target_and_effect():
    b = battle([(1, 'Knight', 9, 5), (0, 'IceWizard', 9, 9.2)], ('IceWizard',))
    shot = None
    for _ in range(60):
        b.step([], 1)
        c = extract(b)
        shot = next((p for p in c['projectiles'] if p['type'] == 'ice_wizardProjectile'), None)
        if shot:
            break
    assert shot, 'no Ice Wizard shot seen'
    kn, iw = unit(c, 'Knight', 1), unit(c, 'IceWizard', 0)
    assert shot['source'] == iw['uid'] and shot['target'] == kn['uid'] and shot['team'] == 0
    assert shot['effect'] == {'buff': 'IceWizardSlowDown', 'ms': 2500}


def test_river_jump_and_charge_and_deploy():
    hogs = battle([(1, 'RoyalHogs', 9, 19)], ('RoyalHogs',))
    seen = set()
    for _ in range(40):
        hogs.step([], 1)
        seen |= {u['state'] for u in extract(hogs)['units'] if u['name'] == 'RoyalHog'}
    assert {'moving', 'jumping'} <= seen
    prince = battle([(1, 'Prince', 9, 14)], ('Prince',))
    prince.step([], 12)
    p = unit(extract(prince), 'Prince', 1)
    assert not p['charging'] and 0 < p['charge_frac'] < 1
    prince.step([], 36)
    assert unit(extract(prince), 'Prince', 1)['charging']
    play = battle([], ('Knight',))
    play.step([(0, 0, int(9 * K), int(8 * K))], 8)
    assert unit(extract(play), 'Knight', 0)['state'] == 'deploying'
    play.step([], 30)
    assert unit(extract(play), 'Knight', 0)['state'] in ('moving', 'engaged')


def test_area_spell_remaining_fraction():
    b = battle([(1, 'Knight', 9, 12)], ('Tornado',))
    b.step([(0, 0, int(9 * K), int(12 * K))], 4)
    a = extract(b)['areas']
    assert [x['name'] for x in a] == ['Tornado'] and a[0]['motion'] == 'Pulsing' and 0.5 < a[0]['frac'] < 1
    b.step([], 12)
    assert extract(b)['areas'][0]['frac'] < a[0]['frac']
