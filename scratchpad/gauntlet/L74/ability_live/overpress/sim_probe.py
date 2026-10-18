"""Q2 / Q5 SIM probe (fork36): controlled Hero IW presses vs one enemy push, every tick logged.
Per trial: side 1 drops a push in the left lane, side 0 drops the Hero IW in front of its left princess; side 0 presses
at the first tick the button passes every readiness check (royale_env._scan) + DELAY ticks. Logged:
  cost       elixir debited on the press tick (engine elixir_milli before / after, same tick)
  repress    accepted presses when re-pressing every tick after the first (charges / cooldown)
  cube       IceWizardHero_IceCube life (ticks), hp trajectory
  freeze     per enemy body: ticks with stun_ticks > 0 or a Freeze buff, distance to the cube at first freeze, hp lost
  no_target  IW dropped far back: a press at the first ready tick (no enemy marked yet)
  dead_iw    check_deploy of the button after the IW died
Output: sim_probe.json + summary.   --dump: one trial, raw buff rows."""
import json
import statistics as st
import sys
from pathlib import Path

from pipeline.royale_runtime import activate
activate()
from pipeline.royale_env import RoyaleSelfPlayEnv, HAND_SIZE  # noqa: E402
from royalegym.rust_engine import DeployCommand, DeployStatus  # noqa: E402

ICE = ['Knight@evolution', 'Tesla@evolution', 'IceWizard@hero', 'Xbow', 'Rocket', 'Log', 'Tornado', 'Skeletons']
PUSHES = {'MegaKnight': [], 'Knight': [], 'Golem': [], 'HogRider': [], 'Valkyrie': [], 'Musketeer': [],
          'Knight+Musketeer': ['Musketeer'], 'Giant+Musketeer': ['Musketeer'], 'GoblinGang': [], 'Pekka': []}
OPP_FILL = ['Zap', 'Fireball', 'Arrows', 'Cannon', 'Bats', 'Minions', 'Barbarians', 'Wizard', 'BabyDragon']
env = RoyaleSelfPlayEnv(forms_mode='deck', hero_abilities=True, ability_policy='v2', feature_version=4, warmup_ticks=200)
UT = env.core.unit_types()
CUBE = UT.index('IceWizardHero_IceCube')
IWH = UT.index('IceWizardHero')
dump = '--dump' in sys.argv


def is_frozen(e_stun, e_buffs):
    return e_stun > 0 or any('Freeze' in b for b in e_buffs)


def trial(push, delay, seed, mode):
    main = push.split('+')[0]
    opp = ([main] + PUSHES[push] + [c for c in OPP_FILL if c not in PUSHES[push] and c != main])[:8]
    for s in range(seed, seed + 400):          # a deal with the IW in side 0's hand and the push in side 1's
        env.reset(ICE, opp, seed=s)
        p = env.core.state().players
        hand0 = [env.names[c] for c in p[0].hand]
        hand1 = [env.names[c] for c in p[1].hand]
        if 'IceWizard' in hand0 and all(c in hand1 for c in [main] + PUSHES[push]):
            break
    else:
        return None
    env.advance_to(env.tick + 120)             # elixir up
    for i, c in enumerate([main] + PUSHES[push]):
        r = env.act(1, env.decks[1].index(c), 3500, 20000 + 1500 * i)
        if not r['accepted']:
            return dict(push=push, error=f'opp {c} refused {r}')
    r = env.act(0, env.decks[0].index('IceWizard'), 3500, 9500 if mode != 'no_target' else 3000)
    if not r['accepted']:
        return dict(push=push, error=f'iw refused {r}')
    t_iw = env.tick
    out = dict(push=push, delay=delay, seed=s, mode=mode, presses=[], repress_accepted=0, repress_tried=0)
    first = pressed_at = None
    hist = []
    while env.tick < t_iw + 600 and not env.done:
        stt = env.core.state()
        ready = env._scan(0, lambda *a: True)
        if ready and pressed_at is None:
            first = env.tick if first is None else first
            if mode == 'no_target' or env.tick >= first + delay:
                el0 = stt.players[0].elixir_milli
                (rr,) = env.core.step([DeployCommand(0, HAND_SIZE + ready[0][0], 0, 0)], 0)
                el1 = env.core.state().players[0].elixir_milli
                marked = [e.uid for e in stt.entities if e.team == 1 and e.hp > 0 and e.buffs]
                out['presses'].append(dict(tick=env.tick, ok=rr.status == DeployStatus.OK, status=int(rr.status),
                                           cost=(el0 - el1) / 1000, marked_enemies=len(marked), since_iw=env.tick - t_iw))
                if rr.status == DeployStatus.OK:
                    pressed_at = env.tick
        elif pressed_at is not None:               # re-press every tick (raw engine command, no readiness gate)
            out['repress_tried'] += 1
            el0 = stt.players[0].elixir_milli
            (rr,) = env.core.step([DeployCommand(0, HAND_SIZE + 0, 0, 0)], 0)
            if rr.status == DeployStatus.OK:
                out['repress_accepted'] += 1
                out.setdefault('repress_costs', []).append((el0 - env.core.state().players[0].elixir_milli) / 1000)
        stt = env.core.state()
        hist.append((env.tick, [(e.uid, e.team, e.unit_type, e.hp, e.max_hp, e.x, e.y, e.stun_ticks,
                                 [str(b) for b in (e.buffs or [])]) for e in stt.entities]))
        if dump and pressed_at is not None and env.tick - pressed_at < 12:
            for e in stt.entities:
                if e.unit_type == CUBE or (e.team == 1 and e.buffs):
                    print(env.tick, UT[e.unit_type], e.hp, e.max_hp, e.x, e.y, e.stun_ticks, e.buffs)
        env.advance_to(env.tick + 1)
        if pressed_at is not None and env.tick > pressed_at + 200:
            break
    iw_alive = any(e.unit_type == IWH and e.hp > 0 for e in env.core.state().entities)
    out['dead_iw_check'] = None if iw_alive else int(env.core.check_deploy(DeployCommand(0, HAND_SIZE, 0, 0)))
    cubes, fz = {}, {}
    for t, ents in hist:
        cs = [e for e in ents if e[2] == CUBE]
        for e in cs:
            c = cubes.setdefault(e[0], dict(first=t, hp=[]))
            c['last'] = t
            c['hp'].append(e[3])
        for e in ents:
            if e[1] == 1 and e[2] != CUBE and is_frozen(e[7], e[8]):
                z = fz.setdefault(e[0], dict(first=t, name=UT[e[2]] if 0 <= e[2] < len(UT) else e[2], hp0=e[3],
                                             d0=min((((c[5] - e[5]) ** 2 + (c[6] - e[6]) ** 2) ** .5 / 1000 for c in cs),
                                                    default=None)))
                z['last'] = t
                z['hp1'] = e[3]
    out['cubes'] = [dict(life=c['last'] - c['first'], hp0=c['hp'][0], hp_last=c['hp'][-1], hp_min=min(c['hp'])) for c in cubes.values()]
    out['frozen'] = [dict(name=z['name'], ticks=z['last'] - z['first'], d0=z['d0'], dmg=z['hp0'] - z['hp1']) for z in fz.values()]
    if dump:
        print('buff samples', sorted({b for t, ents in hist for e in ents for b in e[8]})[:20])
    return out


def main():
    rows = []
    for push in PUSHES:
        for delay in (0, 10, 30):
            for k in range(3):
                r = trial(push, delay, 1000 * k + 17 * delay + 1, 'normal')
                if r:
                    rows.append(r)
                if dump:
                    print(json.dumps(r)[:2500])
                    return
        r = trial(push, 0, 5, 'no_target')
        if r:
            rows.append(r)
    Path(__file__).with_name('sim_probe.json').write_text(json.dumps(rows, indent=0))
    ok = [r for r in rows if 'error' not in r and r['mode'] == 'normal']
    P = [p for r in ok for p in r['presses'] if p['ok']]
    print('trials', len(rows), 'errors', [r['error'] for r in rows if 'error' in r][:5])
    print('press cost (elixir debited): values', sorted({round(p['cost'], 3) for p in P}), 'n', len(P))
    print('refused first presses', [(p['status'], p['marked_enemies']) for r in ok for p in r['presses'] if not p['ok']][:10])
    print('re-press: tried', sum(r['repress_tried'] for r in ok), 'accepted', sum(r['repress_accepted'] for r in ok))
    L = [c['life'] for r in ok for c in r['cubes']]
    print('cubes per accepted press', round(len(L) / max(1, len(P)), 3), 'cube life ticks median', st.median(L) if L else None,
          'deciles', [round(x) for x in st.quantiles(L, n=10)] if len(L) > 2 else L)
    print('cube hp0/hp_min/hp_last', sorted({(c['hp0'], c['hp_min'], c['hp_last']) for r in ok for c in r['cubes']})[:12])
    F = [z['ticks'] for r in ok for z in r['frozen']]
    D = [z['d0'] for r in ok for z in r['frozen'] if z['d0'] is not None]
    print('frozen per press', round(len(F) / max(1, len(P)), 2), 'freeze ticks median', st.median(F) if F else None,
          'deciles', [round(x) for x in st.quantiles(F, n=10)] if len(F) > 2 else F)
    print('frozen distance to cube median', round(st.median(D), 2) if D else None, 'max', round(max(D), 2) if D else None)
    for push in PUSHES:
        rr = [r for r in ok if r['push'] == push]
        print(f"  {push:18s} cube life {[c['life'] for r in rr for c in r['cubes']]} "
              f"frozen {[(z['name'], z['ticks'], z['dmg']) for r in rr for z in r['frozen']][:6]}")
    nt = [r for r in rows if r.get('mode') == 'no_target' and 'error' not in r]
    print('no_target presses (ok, status, cost, marked, since_iw)',
          [(p['ok'], p['status'], p['cost'], p['marked_enemies'], p['since_iw']) for r in nt for p in r['presses']][:10],
          'cubes', [len(r['cubes']) for r in nt])
    print('dead IW button check_deploy', [r['dead_iw_check'] for r in ok if r['dead_iw_check'] is not None][:10])


if __name__ == '__main__':
    main()
