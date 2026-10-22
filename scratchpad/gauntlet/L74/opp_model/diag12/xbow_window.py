"""W18 DIAG_12 8.10 (OWNER HYPOTHESIS 10-22): humans thwart an X-Bow by placing a tank / blocker DURING its ~3.5 s deploy; if
nothing the X-Bow can target is placed in that window, it locks.  Bridge X-Bows at 0-0, live Ranked (233) vs SIM-pos (I u40,
block 741200).  Blocker = the opponent's first GROUND troop or building deployed within X-Bow range (11.5 tiles) of our X-Bow,
from 1 s before to 10 s after our X-Bow landed (live: X-Bow confirm tick, opponent first sighting; SIM: both landing ticks).
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/diag12/xbow_window.py"""
import sys, math, statistics as st
sys.path[:0]=['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/diag12']
import diag12 as D
import invlib as I
H, PK = D.H, D.PK
AIR = {'minions','minion_horde','bats','mega_minion','baby_dragon','inferno_dragon','balloon','lava_hound','skeleton_dragons',
       'electro_dragon','phoenix','flying_machine','skeleton_balloon'}
RANGE, WIN = 11.5, 3.5
def ground(k):
    k = H.norm(k)
    return H.kind(k) != 'spell' and k not in AIR and k not in PK.ANYWHERE
def rec(t_x, xy, opp, lock, dmg, beat):
    b = [(t - t_x) / 20 for t, k, x, y in opp if ground(k) and -20 <= t - t_x <= 200 and math.hypot(x - xy[0], y - xy[1]) <= RANGE]
    return dict(first=min(b) if b else None, lock=lock, dmg=dmg, beat=beat)
L = []
lb = D.LIVE_BEAT()
for key, m in D.live_matches().items():
    opp = [(p['tick'], p['card'], p['x'], p['y']) for p in m['opp'] if p['x'] is not None]
    for r in I.xbow_rows(m):
        if 'lock' not in r or r['type'] != 'bridge' or PK.state(r['our_cr'], r['their_cr']) != '0-0': continue
        L.append(rec(r['tick'], (r['x'], r['y']), opp, r['lock'], r['dmg_reach'], lb[key]))
S = []
for j in D.sim_raw(D.POS_ROOT):
    xs = D.sim_xbows(j)
    if not xs: continue
    me, tf = int(j['learner_side']), D._tf(j)
    opp = [(p[0], p[2], *tf(p[3], p[4])) for p in j['o3_pos'] if p[1] != me]
    deps = [(p[0], *tf(p[3], p[4])) for p in j['o3_pos'] if p[1] == me and p[2] == 'Xbow']
    for x in xs:
        if x['type'] != 'bridge' or x['state'] != '0-0': continue
        t = next((t for t, X, Y in deps if abs(X - x['x']) < 1e-6 and abs(Y - x['y']) < 1e-6), None)
        if t is not None:
            S.append(rec(t, (x['x'], x['y']), opp, x['lock_reach'], x['dmg_reach'], x['beat']))
def cls(r, w=WIN):
    return 'inside' if r['first'] is not None and r['first'] <= w else 'later' if r['first'] is not None else 'none'
def table(nm, R, w=WIN):
    n = len(R); out = {}
    for c in ('inside', 'later', 'none'):
        z = [r for r in R if cls(r, w) == c]
        out[c] = (len(z) / n, sum(r['lock'] for r in z) / max(1, len(z)), st.mean([r['dmg'] for r in z]) if z else 0.0, len(z))
    tot = (sum(r['lock'] for r in R) / n, st.mean(r['dmg'] for r in R))
    print(f'  {nm:6s} n {n:4d} lock {100*tot[0]:5.1f} dmg {tot[1]:.3f} | ' + ' | '.join(
        f'{c} {100*s:4.1f}% (lock {100*l:4.1f}, dmg {d:.3f}, n {k})' for c, (s, l, d, k) in out.items()))
    fi = [r['first'] for r in R if r['first'] is not None]
    print(f'         first blocker after our X-Bow: median {st.median(fi):+.1f} s, p25 {sorted(fi)[len(fi)//4]:+.1f}, p75 {sorted(fi)[3*len(fi)//4]:+.1f}')
    return out, tot
for lab, f in (('ALL decks', lambda r: True), ('BEAT decks', lambda r: r['beat']), ('rest', lambda r: not r['beat'])):
    print(f'\n{lab} (window {WIN} s, range {RANGE} tiles)')
    lo, lt = table('Ranked', [r for r in L if f(r)])
    so, stt = table('SIM', [r for r in S if f(r)])
    # decomposition of the SIM - live gap: (a) the SIM's share of inside / later / none at live conditional rates,
    # (b) live shares at SIM conditional rates
    for key, i, nm in ((1, 'lock'), (2, 'dmg')) if False else ((1, 1, 'lock'), (2, 2, 'dmg')):
        gap = (stt[0] if nm == 'lock' else stt[1]) - (lt[0] if nm == 'lock' else lt[1])
        mix = sum(so[c][0] * lo[c][i] for c in lo) - sum(lo[c][0] * lo[c][i] for c in lo)        # timing / shares only
        cond = sum(lo[c][0] * so[c][i] for c in lo) - sum(lo[c][0] * lo[c][i] for c in lo)       # conditional rates only
        k = 100 if nm == 'lock' else 1
        print(f'  {nm}: gap SIM - live {k*gap:+.3f}; from WHEN the blocker comes (SIM shares at live rates) {k*mix:+.3f}; '
              f'from what happens GIVEN the timing (live shares at SIM rates) {k*cond:+.3f}')
print('\nwindow sensitivity (ALL decks): inside share / lock inside / lock otherwise, live vs SIM')
for w in (2.5, 3.0, 3.5, 4.0, 5.0):
    def s(R):
        a = [r for r in R if cls(r, w) == 'inside']; b = [r for r in R if cls(r, w) != 'inside']
        return f'{100*len(a)/len(R):4.1f}% / {100*sum(r["lock"] for r in a)/max(1,len(a)):4.1f} / {100*sum(r["lock"] for r in b)/max(1,len(b)):4.1f}'
    print(f'  {w:.1f} s: Ranked {s(L)} | SIM {s(S)}')
