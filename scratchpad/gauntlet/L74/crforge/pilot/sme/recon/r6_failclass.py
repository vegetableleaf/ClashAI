"""RECON-6: classify every failing record of FRESH9 / FRESH10 / dev49 (RECON-5 final rows) by the type of its first diff row (laptop):
  python -I recon/r6_failclass.py   -> the table of results/live/recon/r6/failclass_after_recon5.txt. near = the twin body (dx, dy, dhp) of a rec_only / sim_only row."""
import json, sys, collections
sys.path.insert(0, 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/recon')
from r2_tally import klass, load
R5 = 'C:/Users/benpe/ClashBot/.foreman/scratch/recon5/'
def final(v3, cyc):
    V = load(v3); V.update(load(cyc)); return V
sets = {'FRESH9': final(R5 + 'f9/f9_v3.jsonl', R5 + 'f9_cyc_aff.jsonl'), 'FRESH10': final(R5 + 'f10_v3.jsonl', R5 + 'f10_cyc_aff.jsonl'), 'dev49': load(R5 + 'd49_cyc2.jsonl')}
def cls_of(r):
    fd = r.get('first_detail') or []
    if not fd: return 'no detail'
    kinds = [x[0] for x in fd]
    k = fd[0][0]
    near = fd[0][3] if len(fd[0]) > 3 else None
    nm = str(fd[0][2])
    if k.startswith('S') and k.endswith('elixir'): return 'elixir only'
    if k[0] in 'AP': return 'area/projectile first'
    if k[0] == 'T': return 'tower row first'
    if near is None:
        return 'unit rec_only, no twin (unseen body)' if 'rec_only' in k else 'unit sim_only, no twin (extra / hidden body)'
    dx, dy = near[0], near[1]; dh = near[2] if len(near) > 2 else 0
    if dx == dy == 0 and dh: return 'unit hp-only difference (same point)'
    if (dx or dy) and not dh: return 'unit position-only offset'
    return 'unit position + hp'
tot = collections.Counter()
rows = collections.defaultdict(list)
for name, V in sets.items():
    for m, r in V.items():
        if 'error' in r or klass(r) >= 1: continue
        c = cls_of(r)
        tot[c] += 1
        rows[c].append((name, m[-13:], r.get('first_div')))
for c, n in tot.most_common():
    print(n, c, [x[1] for x in rows[c]][:12])
print(sum(tot.values()))
print('---- position-only offsets')
for name, V in sets.items():
    for m, r in V.items():
        if 'error' in r or klass(r) >= 1: continue
        if cls_of(r) != 'unit position-only offset': continue
        fd = r['first_detail']
        pairs = [(x[2], x[3]) for x in fd if x[0] == 'U_rec_only' and x[3]]
        print(name, m[-13:], 'first', r['first_div'], 'rec_only offsets', pairs[:3], 'n div', r['counts'].get('div'))
print('---- twin names (sim side) of position / hp rows')
c2 = collections.Counter()
for name, V in sets.items():
    for m, r in V.items():
        if 'error' in r or klass(r) >= 1: continue
        if cls_of(r) not in ('unit position-only offset', 'unit hp-only difference (same point)', 'unit position + hp'): continue
        fd = r['first_detail']
        sims = [x[2] for x in fd if x[0] == 'U_sim_only']
        c2[tuple(sorted(set(s.replace('C:', '') for s in sims)))[:3]] += 1
        print(name, m[-13:], cls_of(r)[5:20], sims[:3])
