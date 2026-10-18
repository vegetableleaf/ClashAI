"""L74 combo eval arms (10-17): Mark CXXXVIII on the factorial / fast-plays eval (fork36, Hero IW + live press, D3 = the live rule
stack, seeds 741200 + 742000 = 960 paired, live levels + card levels + habit log + tower troops at live rates), fast plays OFF (= live).
  cur   the deployed live combo options (LIVE_OPTIONS 10-17)            = the fast-plays 'offc' arm row for row (+ measurement keys)
  new   + every 10-17 rule change: measured window, Tornado first, lone vs combo, enemy half (min y 0) + princess value, river full
  newh  new on MY half only (min y 16): the enemy-half change isolated
  newc  newh with rocket_tornado_lone combo (the combo where the pull adds value, never the lone Rocket)
  newd  new + rocket_tornado_lead drift (the enemy-half iteration: the push keeps walking for the ~50-80 ticks to the Tornado)"""
CK = 'icebow/data/bench/rl_royale/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt'
BASE = ('--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 '
        '--record-plays --spell-log')
CUR = '--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river on'
NEWH = ('--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river full '
        '--rocket-tornado-window measured --rocket-tornado-order either --rocket-tornado-lone best')
NEW = NEWH + ' --rocket-value-min-y 0 --rocket-value-towers on'
NEWD = NEW + ' --rocket-tornado-lead drift'
NEWC = NEWH.replace('--rocket-tornado-lone best', '--rocket-tornado-lone combo')
ARMS = {'cur': f'{BASE} {CUR}', 'new': f'{BASE} {NEW}', 'newh': f'{BASE} {NEWH}', 'newd': f'{BASE} {NEWD}', 'newc': f'{BASE} {NEWC}'}
MEASURE_KEYS = ('own_plays', 'own_plays_x', 'own_presses', 'spell', 'combo_rule', 'wall_s')

if __name__ == '__main__':          # combo_arms.py NAME -> the flag string (ARMS key, or CUR / NEW / NEWH): shell scripts read it
    import sys
    print(ARMS.get(sys.argv[1]) or globals()[sys.argv[1]])
