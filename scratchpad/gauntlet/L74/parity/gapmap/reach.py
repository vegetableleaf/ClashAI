"""Coverage ceiling at +d days: tier-B share on cards that cannot meet even with a perfect SIM (p_need(+d) above the card's
noise ceiling, or n < 30, or no strict fights at all), and the slack left for 0.90. usage: python reach.py trigger.json"""
import json, sys
from trigger import p_need, GOAL_CARD, GOAL_N
T = json.load(open(sys.argv[1]))
sB = T['tierB_share']
for d in (0, 1, 3, 7, 14):
    bad, names = 0., []
    for c in T['cards']:
        if 'n' not in c:
            bad += c['share']; names.append(c['card'] + ' (not in cohort)'); continue
        n2 = c['n'] + d*T['per_day']*c['rate']
        need = p_need(n2, c['f'], GOAL_CARD)
        ceil = c['ceil'] if c['ceil'] is not None else 1.
        if n2 < GOAL_N or need is None or need > ceil:
            if c['p'] >= 1 and n2 >= GOAL_N:
                continue                                     # perfect so far: the bootstrap gives [1, 1]
            bad += c['share']; names.append(c['card'])
    own_open = sum(c['share'] for c in T['cards'] if c['card'].startswith('own ') and not c['meets'])
    print(f"+{d} d: unreachable {bad:.4f} of plays = {bad/sB:.3f} of tier B -> max coverage {1-bad/sB:.3f}; slack for 0.90: "
          f"{(1-bad/sB-.9)*sB:.4f} of plays ({len(names)} cards: {', '.join(names)})")
print(f"own cards not meeting today: {own_open:.4f} of plays")
