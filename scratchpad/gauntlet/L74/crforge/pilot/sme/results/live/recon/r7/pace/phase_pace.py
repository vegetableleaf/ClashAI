"""RECON-7: CLXIII pace by elixir phase, live (confirmed plays, 856 calibration matches) vs SIM (accepted plays of a D3 rows file): plays / min, elixir spent / min,
mean cost, time share per phase. Laptop, icebow venv."""
import json, sys, statistics as st, collections
from pathlib import Path
H = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/humanlike')
sys.path[:0] = [str(H), str(H.parent), 'C:/Users/benpe/ClashBot']
import card
import live_table as LT
from pipeline.opp_elixir_count import card_cost
from pipeline import vocab
PH = [(0, 2400, '1x'), (2400, 3600, '2x'), (3600, 4800, 'ot2x'), (4800, 99999, 'ot3x')]
def cost(n):
    k = vocab.engine_key(str(n).split('@')[0]) or str(n)
    c = card_cost(k)
    return c if c else None
def phase_stats(matches):
    """matches: [(t0, end, [(tick, name)])] -> per phase dict"""
    out = {p[2]: dict(mins=0.0, n=0, el=0.0, nc=0) for p in PH}
    for t0, end, plays in matches:
        for a, b, nm in PH:
            lo, hi = t0 + a, min(end, t0 + b)
            if hi <= lo: continue
            out[nm]['mins'] += (hi - lo) / 1200.0
            for t, name in plays:
                if lo <= t < hi:
                    out[nm]['n'] += 1
                    c = cost(name)
                    if c is not None: out[nm]['el'] += c; out[nm]['nc'] += 1
    return out
def show(label, ps):
    tot = sum(v['mins'] for v in ps.values())
    print(label)
    for nm, v in ps.items():
        if v['mins']:
            print('  %-5s time share %.2f  plays/min %.2f  elixir spent/min %.2f  mean cost %.2f' % (nm, v['mins'] / tot, v['n'] / v['mins'], v['el'] / v['mins'], v['el'] / max(v['nc'], 1)))
live = []
for r in card.live_records('calibration'):
    d = LT.cached(card.LOGS / r['id'])
    if d: live.append((d['t0'], d['end'], [(t, n) for t, n in d['own_conf'] if t]))
show('LIVE CLXIII confirmed (n %d)' % len(live), phase_stats(live))
for f in sys.argv[1:]:
    sim = []
    for l in open(f):
        r = json.loads(l)
        sim.append((90, r['end_tick'], [(q[1], q[2]) for q in r['hab']['own'] if q[3]]))
    show('SIM %s accepted (n %d)' % (Path(f).parent.parent.parent.name, len(sim)), phase_stats(sim))

# ---- composition: SIM per-phase rates reweighted to live's time shares (pooled)
def pooled(ps):
    tot = sum(v['mins'] for v in ps.values())
    return sum(v['n'] for v in ps.values()) / tot, {k: v['mins'] / tot for k, v in ps.items()}, {k: v['n'] / v['mins'] for k, v in ps.items() if v['mins']}
lr, lsh, lph = pooled(phase_stats(live))
print('pooled LIVE confirmed plays/min %.2f' % lr)
for f in sys.argv[1:]:
    sim = []
    for l in open(f):
        r = json.loads(l)
        sim.append((90, r['end_tick'], [(q[1], q[2]) for q in r['hab']['own'] if q[3]]))
    sr, ssh, sph = pooled(phase_stats(sim))
    rew = sum(lsh[k] * sph[k] for k in lsh if k in sph)
    print('pooled SIM accepted plays/min %.2f; with LIVE time shares %.2f (composition explains %.2f of the %.2f gap; the per-phase rates the rest %.2f)' % (sr, rew, rew - sr, lr - sr, lr - rew))
    print('  time share live', {k: round(v, 2) for k, v in lsh.items()}, 'sim', {k: round(v, 2) for k, v in ssh.items()})
