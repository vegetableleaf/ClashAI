"""SIM side of the live phase-3 freeze reading: a red Knight hitting blue's king, the hero form shooting it, its button
pressed. Per tick: the Knight's buffs, stun_ms, attack progress (attack_ms) and load timer (attack_load_ms).

Usage: python freeze_sim.py <unpacked royalesim wheel dir>
Live (p3_20261016T134735): during IceWizardHero_FreezeBuff the attack progress AND the load timer are held (E-Wiz hero
load 800 before and after ~100 frozen ticks; Pekka 250/250); the SIM's status doc says the load keeps counting.
"""
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe  # noqa: E402

T = probe.T
b, ids = probe.new_battle()
deck = [ids[c] for c in ['IceWizard', 'Knight', 'Giant', 'Musketeer', 'Tesla', 'Log', 'Tornado', 'Rocket']]
b.reset(1, [deck, deck], 0, 200, [10000, 10000], [[4824, 0, 0], [4824, 3052, 3052]],
        [(1, ids['Knight'], *T(9, 5.0), -1)], forms=[[2] + [0] * 7, [0] * 8], levels=[[11] * 8, [11] * 8],
        tower_levels=[11, 11])
rows = []
for t in range(260):
    cmds = [(0, 0, *T(9, 9.2))] if t == 0 else ([(0, 4, 0, 0)] if t >= 70 else [])
    res = b.step(cmds, 1)
    if any(r[1] == 0 and cmds and cmds[0][1] == 4 for r in res):
        rows.append(('PRESS accepted', t))
    sv = json.loads(b.save())
    E = sv['ents']
    n = len(E['alive'])
    slots = len(E['buffs']) // n
    kn = next((i for i in range(n) if E['alive'][i] and E['team'][i] == 'Red' and E['kind'][i] == 'Troop'), None)
    if kn is None:
        rows.append(('knight gone', t))
        break
    bs = [(s['id'], s['ms']) for s in E['buffs'][kn * slots:(kn + 1) * slots] if s['id']]
    rows.append((t, bs, E['stun_ms'][kn], E['attack_phase'][kn], E['attack_ms'][kn], E['attack_load_ms'][kn]))
prev = None
for r in rows:   # print only state changes in buff set, plus every 5th tick
    key = r[1] if isinstance(r[0], int) else None
    if not isinstance(r[0], int) or key != prev or r[0] % 5 == 0:
        print(r)
    prev = key
