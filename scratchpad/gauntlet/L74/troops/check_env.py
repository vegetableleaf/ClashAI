"""Pod checks for the tower-troop option (ROYALE_RUNTIME=fork36-linux; run from the checkout with PYTHONPATH=.):

    python scratchpad/gauntlet/L74/troops/check_env.py OUT_TABLE.json

1. tower table: princess-slot max_hp per tower level for the Princess and each troop (the fork's own numbers, as
   parity fights.py troop_level), written to OUT_TABLE.json for live_rates.py report.
2. RoyaleSelfPlayEnv.reset(tower_troops=...): the opponent's princess slots carry the troop's max_hp, a later reset
   without it is back to the Princess, no unknown-named body appears, 600 ticks step without error.
3. draw_tower_troop: frequencies over 200,000 keys match the rates; the same key always draws the same troop.
Exit 1 on any failure."""
import json
import sys
from collections import Counter

from pipeline.royale_runtime import activate

activate()
import royalesim as sim  # noqa: E402
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from pipeline.rl_royale import TOWER_TROOPS, draw_tower_troop  # noqa: E402
from pipeline import royale_heroiw as heroiw  # noqa: E402

ok = True


def check(cond, msg):
    global ok
    print(('PASS ' if cond else 'FAIL ') + msg)
    ok &= bool(cond)


# 1. table
b = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides={'cards.CARD_TABLE': json.dumps(heroiw.CARD_TABLE)})
tab = {}
for lv in range(1, 17):
    row = {}
    for name in (None,) + TOWER_TROOPS:
        b.set_tower_troops(name, None)
        try:
            b.reset(1, [[0], [0]], 0, 200, None, None, [], tower_levels=[lv, lv])
        except ValueError:
            continue
        k, p = json.loads(b.state_json())['players'][0]['tower_max_hp'][:2]
        row[name or 'PrincessTower'] = p
        row['king'] = k
    if row:
        tab[lv] = row
b.set_tower_troops(None, None)
for lv, r in tab.items():
    print(lv, r)
json.dump(tab, open(sys.argv[1], 'w'), indent=1)
check(tab[15]['PrincessTower'] == 4424 and tab[16]['PrincessTower'] == 4858, 'princess L15 4424 / L16 4858 (live)')
check(tab[15].get('Cannoneer') == 3792 and tab[16].get('ChefTower') == 4302 and tab[16].get('DaggerDuchess') == 4406,
      'troop hp = the three live-confirmed matches (Cannoneer L15 3792, Chef L16 4302, Duchess L16 4406)')

# 2. env
from pipeline import e1_eval as E  # noqa: E402
from pipeline.rl_royale import REPO, league_decks  # noqa: E402
ICE = list(E.ICEBOW_ENGINE_DECK)
OPP = league_decks(REPO / 'icebow/data/rltest/decks_rl.json')[0]['engine']
print('decks', ICE, OPP)
env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode='deck', hero_abilities=True, ability_policy='v2')


def princess(raw):
    return {s: sorted(t['max_hp'] for t in raw['episode']['crown_towers'] if t['side'] == s and t['type'] == 'princess')
            for s in (0, 1)}


base = princess(env.reset(ICE, OPP, 5))
print('princess slots, no troops:', base)
for name in TOWER_TROOPS:
    raw = env.reset(ICE, OPP, 5, tower_troops=[None, name])
    pr = princess(raw)
    print(name, 'on side 1:', pr, 'entities:', sorted({e['name'] for e in raw['entities']}))
    check(pr[0] == base[0] and pr[1] != base[1] and len(set(pr[1])) == 1, f'{name}: only side 1 princess slots changed')
    check(all(not str(e['name']).isdigit() for e in raw['entities']), f'{name}: no unknown-named body')
    env.advance_to(env.tick + 600)
    check(env.tick > 600, f'{name}: stepped to tick {env.tick} without error')
raw = env.reset(ICE, OPP, 5, tower_troops=[name, None])
check(princess(raw)[0] != base[0] and princess(raw)[1] == base[1], 'troop on side 0 when asked')
check(princess(env.reset(ICE, OPP, 5)) == base, 'a later reset without tower_troops is back to the Princess')

# 3. draws
rates = {'DaggerDuchess': 0.03, 'Cannoneer': 0.03, 'ChefTower': 0.015}
c = Counter(draw_tower_troop(rates, f'{i}:k') for i in range(200000))
print('draws', dict(c))
check(all(abs(c[k] / 200000 - v) < 0.002 for k, v in rates.items()), 'draw frequencies within 0.2 pp of the rates')
check(len({draw_tower_troop(rates, '17:x') for _ in range(50)}) == 1, 'same key, same draw')
sys.exit(0 if ok else 1)
