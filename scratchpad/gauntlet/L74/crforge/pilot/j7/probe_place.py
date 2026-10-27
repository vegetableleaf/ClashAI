"""A2b-2b probe: do the fin wheels refuse, on an empty board at tick 400, the points fin refused in J7?
    PYTHONPATH=<tree> python probe_place.py     (engine as fin_run.py: PARITY_SIM_PATH / ROYALE_RUNTIME, PARITY_TABLE_1019)
Each case: (card, side, x, y) in game units; issued through fin_run's play() path (hand slot 0, mana full)."""
from scratchpad.gauntlet.L74.crforge.pilot.j7 import fin_run as R

CASES = [('Fireball', 0, 5500, 23500), ('Fireball', 0, 5500, 13500), ('Zap', 0, 10400, 22300), ('Heal', 0, 8804, 21939),
         ('Earthquake', 0, 5500, 21500), ('Log', 1, 9500, 30500), ('Log', 1, 9500, 27500), ('Log', 0, 8500, 1500),
         ('Log', 0, 9500, 4500), ('Knight', 0, 9500, 17500), ('Knight', 0, 9500, 14500), ('SuspiciousBush', 0, 14660, 22449),
         ('Valkyrie', 1, 8499, 11499), ('Xbow', 1, 14500, 12500), ('BarbLog', 1, 10500, 30500)]
FILL = ['Knight', 'Skeletons', 'IceSpirit', 'Cannon', 'Musketeer', 'Valkyrie', 'Tesla', 'Log']


def main():
    out = []
    for card, side, x, y in CASES:
        deck = [card] + [c for c in FILL if c != card][:7]
        plan = dict(match='live_play_20261026_120000', display=[deck, deck], slots=[[0] * 8, [0] * 8], levels=[[16] * 8, [16] * 8],
                    towers=[['King_PrincessTowers', 16, 16]] * 2,
                    cmds=[dict(kind='play', side=side, display=card, form=0, x=x, y=y, lo=400, hi=400)])
        r = R.run(plan, 'lo')
        out.append((card, side, x, y, r.get('crash') or r['refused_cmds'][0][2] if r.get('refused_cmds') else 'OK'))
    for o in out:
        print(*o)


if __name__ == '__main__':
    main()
