"""Minimal card set for 90% tier-B coverage at +d days: today's MEETS + data-limited cards (meet by +d at today's p) are free;
then the reachable (p_need(+d) <= ceiling) error-limited cards by live share, largest first. usage: python minset.py trigger.json D"""
import json, sys
from trigger import p_need, GOAL_CARD, GOAL_N, TIER_SHARE
T, d = json.load(open(sys.argv[1])), float(sys.argv[2])
sB = T['tierB_share']
free, err, out = [], [], []
for c in T['cards']:
    if 'n' not in c:
        out.append(c); continue
    n2 = c['n'] + d*T['per_day']*c['rate']
    need = p_need(n2, c['f'], GOAL_CARD)
    ceil = c['ceil'] if c['ceil'] is not None else 1.
    perfect = c['p'] >= 1 and n2 >= GOAL_N
    if c['meets'] or perfect or (need is not None and c['p'] >= need and n2 >= GOAL_N):
        free.append(c)
    elif n2 >= GOAL_N and need is not None and need <= ceil:
        err.append((c, need))
    else:
        out.append(c)
s_free = sum(c['share'] for c in free)
gap = TIER_SHARE*sB - s_free
print(f"+{d:g} d: free (MEETS today or data-limited) {s_free:.4f} of plays = {s_free/sB:.3f} of tier B; gap to 0.90: {gap:.4f} of plays")
acc, pick = 0., []
for c, need in sorted(err, key=lambda x: -x[0]['share']):
    if acc >= gap:
        break
    acc += c['share']; pick.append((c, need))
print(f"error-limited cards to FIX (largest share first): {len(pick)}, {acc:.4f} of plays")
for c, need in pick:
    print(f"  {c['card']} | share {c['share']:.4f} | n {c['n']} | p {c['p']:.3f} -> p_need {need:.3f} | deficit {max(0, (need-c['p'])*c['n']):.1f} fights")
rest = [c for c, _ in err if all(c is not q for q, _ in pick)]
print(f"reachable but not needed: {len(rest)} cards, {sum(c['share'] for c in rest):.4f} of plays (spare)")
print(f"unreachable: {len(out)} cards, {sum(c['share'] for c in out):.4f}: " + ', '.join(c['card'] for c in out))
print('free cards: ' + ', '.join(c['card'] for c in free if not c['meets']))
