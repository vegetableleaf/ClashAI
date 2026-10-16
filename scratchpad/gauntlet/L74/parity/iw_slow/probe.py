"""Ice Wizard slow probe: does an Ice Wizard (base or hero form) slow what it hits in a royalesim wheel?

Usage: python probe.py <unpacked royalesim wheel dir> [out.json]
Scenarios (blue princess towers down so no crown tower touches the scene; level 11; card table client160402017_20261006):
  move_*   : a red Giant walks from (9, 14) tiles to blue's king; a blue shooter stands off its path at (6.0, 7.5).
             Per-tick displacement of the Giant = its walk speed; slow window = ticks carrying a buff.
  attack_* : a red Knight is put next to blue's king tower; a blue shooter at (9, 9.2) hits it.
             The Knight's attack progress gain per tick (attack_ms) and its hit interval on the king (hp drops).
  shooters : none (control), IceWizard base (spawned), IceWizard hero form (played from hand at the same point,
             form 2), Musketeer (an unslowing ranged control).
  hero_press: the hero form, played next to a red Giant (deploy chill) and its button pressed: freeze + after-slow.
"""
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
import royalesim as sim  # noqa: E402

K = 18                      # subtiles per millitile (fixed.rs SUBTILE_PER_MILLITILE)
# IW_TABLE=default: the wheel's own default table (older runtimes, before the 160402017 table existed).
TABLE = None if os.environ.get('IW_TABLE') == 'default' else {'cards.CARD_TABLE': json.dumps('client160402017_20261006')}


def T(x_tiles, y_tiles):
    return int(x_tiles * 1000 * K), int(y_tiles * 1000 * K)


def new_battle():
    b = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides=TABLE)
    cat = [dict(zip(sim.CATALOGUE_FIELDS, r)) for r in json.loads(b.catalogue_json())]
    return b, {c['name']: i for i, c in enumerate(cat)}


def save(b):
    return json.loads(b.save())


def ent_rows(sv):
    E = sv['ents']
    n = len(E['alive'])
    # ents.buffs is FLAT: `slots` buff slots per entity (4 in 0.1.35), entity i owns buffs[i*slots:(i+1)*slots].
    # Reading buffs[i] (one per entity) shows entity i//slots's slot -- the source of the "buff id 0" misreading.
    slots = len(E['buffs']) // n
    return [{k: E[k][i] for k in ('alive', 'team', 'kind', 'card', 'pos', 'hp', 'speed', 'attack_phase', 'attack_ms',
                                    'stun_ms', 'target', 'deploy_ms')}
            | {'i': i, 'buffs': [s for s in E['buffs'][i * slots:(i + 1) * slots] if s['id']]} for i in range(n)]


def run(shooter, target, ticks=260, at_tiles=None, kill_at=None):
    b, ids = new_battle()
    deck_b = ['IceWizard', 'Knight', 'Giant', 'Musketeer', 'Tesla', 'Log', 'Tornado', 'Rocket']
    deck_r = ['Rocket', 'Knight', 'Giant', 'Musketeer', 'Tesla', 'Log', 'Tornado', 'IceWizard']   # Rocket in hand slot 0
    decks = [[ids[c] for c in deck_b], [ids[c] for c in deck_r]]
    forms = [[2 if shooter == 'hero' else 0] + [0] * 7, [0] * 8]
    # tower_hp in engine k order: [king, princess, princess]; blue princesses down.
    tower_hp = [[4824, 0, 0], [4824, 3052, 3052]]
    if target == 'giant':
        spawns = [(1, ids['Giant'], *T(9, 14), -1)]
        at = T(*(at_tiles or (6.0, 7.5)))
    else:
        spawns = [(1, ids['Knight'], *T(9, 5.0), -1)]
        at = T(9, 9.2)
    if shooter in ('base', 'musk'):
        spawns.append((0, ids['IceWizard' if shooter == 'base' else 'Musketeer'], *at, -1))
    b.reset(1, decks, 0, 200, [10000, 10000], tower_hp, spawns, forms=forms, levels=[[11] * 8, [11] * 8],
            tower_levels=[11, 11])
    cmds = [(0, 0, *at)] if shooter in ('hero', 'basecmd') else []   # played from hand: its deploy chill is cast
    out = []
    for t in range(ticks):
        if t == kill_at:
            cmds = cmds + [(1, 0, *at)]   # red Rockets the shooter: the last slow then runs out untouched
        res = b.step(cmds, 1)
        if cmds:
            out.append({'cmd': res})
            cmds = []
        rows = ent_rows(save(b))
        out.append({'tick': t, 'rows': [r for r in rows if r['alive'] and r['kind'] not in ('PrincessTower',)]})
    return out


def run_press(ticks=320):
    """Hero form played 2.6 tiles from a red Giant's path (deploy chill reaches it), button pressed every tick."""
    b, ids = new_battle()
    deck_b = ['IceWizard', 'Knight', 'Giant', 'Musketeer', 'Tesla', 'Log', 'Tornado', 'Rocket']
    deck_r = ['Knight', 'Giant', 'Musketeer', 'Tesla', 'Log', 'Tornado', 'Rocket', 'IceWizard']
    decks = [[ids[c] for c in deck_b], [ids[c] for c in deck_r]]
    b.reset(1, decks, 0, 200, [10000, 10000], [[4824, 0, 0], [4824, 3052, 3052]],
            [(1, ids['Giant'], *T(9, 14), -1)], forms=[[2] + [0] * 7, [0] * 8], levels=[[11] * 8, [11] * 8],
            tower_levels=[11, 11])
    out = []
    for t in range(ticks):
        cmds = [(0, 0, *T(6.0, 7.5))] if t == 0 else ([(0, 4, 0, 0)] if t >= 60 else [])
        res = b.step(cmds, 1)
        rows = ent_rows(save(b))
        out.append({'tick': t, 'cmd': [r for r in res if r[1] == 0],
                    'rows': [r for r in rows if r['alive'] and r['kind'] not in ('PrincessTower',)]})
    return out


def run_tower(shooter, ticks=320):
    b, ids = new_battle()
    deck = ['IceWizard', 'Knight', 'Giant', 'Musketeer', 'Tesla', 'Log', 'Tornado', 'Rocket']
    decks = [[ids[c] for c in deck], [ids[c] for c in deck]]
    at = T(3.5, 20.0)        # 5.5 tiles below red's left princess tower (3.5, 25.5): both shoot each other
    spawns = [] if shooter == 'hero' else [(0, ids['IceWizard' if shooter == 'base' else 'Musketeer'], *at, -1)]
    b.reset(1, decks, 0, 200, [10000, 10000], [[4824, 3052, 3052], [4824, 3052, 3052]], spawns,
            forms=[[2 if shooter == 'hero' else 0] + [0] * 7, [0] * 8], levels=[[11] * 8, [11] * 8], tower_levels=[11, 11])
    out = []
    for t in range(ticks):
        # the hero is played on blue's side at (3.5, 13) (no deploy on red's half) and walks into the tower's reach
        res = b.step([(0, 0, *T(3.5, 13.0))] if (t == 0 and shooter == 'hero') else [], 1)
        rows = ent_rows(save(b))
        out.append({'tick': t, 'cmd': [r for r in res],
                    'rows': [r for r in rows if r['alive'] and not (r['kind'] == 'PrincessTower' and r['team'] == 'Blue')]})
    return out


def main():
    res = {'version': getattr(sim, '__version__', None), 'provenance': list(sim.Battle.provenance()), 'runs': {}}
    jobs = [(f'{t}_{s}', run, (s, t)) for s in ('none', 'base', 'hero', 'musk') for t in ('giant', 'knight')]
    jobs.append(('giant_hero_press', run_press, ()))
    # a crown tower as the victim (live m2: IceWizardHeroSlow sat on a PrincessTower): the shooter stands in red's left
    # princess tower's reach; the tower's hit interval is read off the shooter's hp drops
    jobs += [(f'tower_{s}', run_tower, (s,)) for s in ('base', 'hero', 'musk')]
    # expiry: red Rockets the shooter at tick 60, so its last slow on the Giant runs out untouched
    jobs += [(f'giant_{s}_rocketed', run, (s, 'giant', 200, None, 60)) for s in ('none', 'base', 'hero')]
    # deploy chill: the card played from hand 2 tiles in front of the Giant (IceWizardCold / IceWizardColdHero reach it)
    jobs += [(f'giant_{s}_chill', run, (s, 'giant', 120, (9.0, 12.0))) for s in ('basecmd', 'hero')]
    for name, fn, args in jobs:
        try:
            res['runs'][name] = fn(*args)
        except Exception as e:   # an older wheel has no hero form: recorded, not fatal
            res.setdefault('errors', {})[name] = repr(e)[:300]
            print('ERROR', name, repr(e)[:200])
    path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), 'probe_out.json')
    with open(path, 'w') as f:
        json.dump(res, f)
    print('wrote', path, res['version'], res['provenance'])


if __name__ == '__main__':
    main()
