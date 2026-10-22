"""W18 DIAG_12 8.12: is the SIM's 'depth does not pay' confounded by WHAT the SIM places deep? Window blockers (<= 3.5 s) by
class x depth (distance from our X-Bow) and by the blocker's y (tower-front = y <= 11, our frame), live vs SIM-pos.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/diag12/xbow_depth_confound.py"""
import sys
sys.path[:0]=['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/diag12']
import xbow_window_inside as WI
H = WI.H
def cls(k):
    k = H.norm(k)
    return 'building' if H.kind(k) == 'building' else 'tank' if WI.tank(k) else 'troop'
for nm, R in (('Ranked', WI.L), ('SIM', WI.S)):
    print(nm)
    for c in ('troop', 'tank', 'building'):
        row = []
        for lab, f in (('4-8', lambda b: b[2] <= 8), ('8-11.5', lambda b: b[2] > 8)):
            z = [l for b, l, _ in R if cls(b[1]) == c and f(b)]
            row.append(f'{lab}: n {len(z):3d} lock {100*sum(z)/max(1,len(z)):5.1f}')
        print(f'   {c:8s} ' + ' | '.join(row))
    for lab, f in (('tower-front y<=11', lambda b: b[3] <= 11), ('y>11', lambda b: b[3] > 11)):
        z = [l for b, l, _ in R if f(b)]
        print(f'   {lab:18s} n {len(z):3d} share {100*len(z)/len(R):4.1f}% lock {100*sum(z)/max(1,len(z)):5.1f}')
