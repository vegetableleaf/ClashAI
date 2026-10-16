"""Can a harness SET an Ice Wizard slow on a body at fight start? Save -> write the body's buff slot -> load -> step.

Usage: python inject.py <unpacked royalesim wheel dir>
A red Knight hitting blue's king alone (no Ice Wizard anywhere). Arm A: untouched. Arm B: IceWizardHeroSlow (id read
off a probe where the hero's shot put it on, not typed) written into the Knight's first buff slot with 2500 ms left.
Prints the Knight's attack-progress gain per tick and the king's hp-drop intervals for each arm.
"""
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe  # noqa: E402  (same scene helpers; probe reads sys.argv[1] for the wheel)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *['..'] * 5)))
from scratchpad.gauntlet.L74.parity.mechanics import load_edited  # noqa: E402  (the harness's rehash-on-edit helper)

sim = probe.sim
K = 18000


def hero_slow_id():
    """The interned id the hero's shot hangs (read from a live probe run, not typed)."""
    fr = probe.run('hero', 'knight', 80)
    for f in fr:
        for r in f.get('rows', []):
            if r['team'] == 'Red' and r['kind'] == 'Troop' and r['buffs']:
                return r['buffs'][0]['id']
    raise SystemExit('no hero slow seen')


def arm(slow_id):
    b, ids = probe.new_battle()
    deck = [ids[c] for c in ['Knight', 'Giant', 'Musketeer', 'Tesla', 'Log', 'Tornado', 'Rocket', 'IceWizard']]
    b.reset(1, [deck, deck], 0, 200, [10000, 10000], [[4824, 0, 0], [4824, 3052, 3052]],
            [(1, ids['Knight'], 9 * K, 5 * K, -1)], levels=[[11] * 8, [11] * 8], tower_levels=[11, 11])
    b.step([], 20)                                     # the Knight is deployed and swinging
    if slow_id:
        before = json.loads(b.save())
        sv = json.loads(json.dumps(before))
        E = sv['ents']
        n = len(E['alive'])
        slots = len(E['buffs']) // n
        kn = next(i for i in range(n) if E['alive'][i] and E['team'][i] == 'Red' and E['kind'][i] == 'Troop')
        E['buffs'][kn * slots] = dict(E['buffs'][kn * slots], id=slow_id, ms=2500)
        # a plain load refuses the edit (self-check hash, probed); load_edited takes the engine's rebuilt hash once
        load_edited(b, before, sv)
        E2 = json.loads(b.save())['ents']
        print('  slot after load:', E2['buffs'][kn * slots])
    prog, drops, hp, last = {}, [], None, None
    for t in range(120):
        b.step([], 1)
        E = json.loads(b.save())['ents']
        kn = next(i for i in range(len(E['alive'])) if E['alive'][i] and E['team'][i] == 'Red' and E['kind'][i] == 'Troop')
        king = next(i for i in range(len(E['alive'])) if E['team'][i] == 'Blue' and E['kind'][i] == 'KingTower')
        if last is not None and E['attack_ms'][kn] > last:
            g = E['attack_ms'][kn] - last
            prog[g] = prog.get(g, 0) + 1
        last = E['attack_ms'][kn]
        if hp is not None and E['hp'][king] < hp:
            drops.append(t)
        hp = E['hp'][king]
    return {'progress_gain_per_tick': prog, 'king_hit_ticks': drops, 'intervals': [b - a for a, b in zip(drops, drops[1:])]}


if __name__ == '__main__':
    sid = hero_slow_id()
    print('hero slow id', sid)
    print('A untouched :', arm(None))
    print('B injected  :', arm(sid))
