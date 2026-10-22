import sys, math
from collections import Counter
sys.path[:0]=['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/diag12']
import diag12 as D
import invlib as I
H = D.H
STUN = {'zap', 'electro_spirit', 'electro_wizard', 'lightning', 'electro_dragon', 'freeze', 'electro_giant', 'ice_spirit', 'giant_snowball', 'barbarian_barrel', 'the_log', 'fireball', 'rocket', 'earthquake', 'poison', 'arrows', 'tornado'}
VIS_STUN = {'electro_spirit', 'electro_wizard', 'electro_dragon', 'electro_giant'}       # troops: seen by the live detector
def cls(ans):
    ks = {H.norm(k) for k in ans}
    if ks & VIS_STUN: return 'visible stun troop'
    if ks & {'zap', 'lightning', 'freeze'}: return 'stun spell'
    if ks & {'fireball', 'rocket', 'earthquake', 'poison', 'arrows', 'giant_snowball', 'the_log', 'barbarian_barrel', 'tornado'}: return 'damage spell'
    return 'other'
for nm, xs in (('Ranked', D.live_xbows()), ('SIM', [x for j in D.sim_raw(D.POS_ROOT) for x in D.sim_xbows(j)])):
    y = [x for x in xs if x['type'] == 'bridge' and x['state'] == '0-0']
    c, l = Counter(), Counter()
    for x in y:
        k = cls(x['ans']); c[k] += 1; l[k] += x['lock_reach']
    print(nm, len(y), ' | '.join(f'{k} {100*v/len(y):.1f}% (lock {100*l[k]/v:.0f}%)' for k, v in c.most_common()))
