"""RECON-6: the position-only first-diff offsets (rec_only / sim_only twin, equal hp) of the failing records after RECON-5, in ticks of the unit's walk (offset / the unit's Speed row; laptop):
  python -I recon/r6_offticks.py -> results/live/recon/r6/position_offsets_in_ticks.txt"""
import json, sys, math, collections
sys.path.insert(0, 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/recon')
from r2_tally import klass, load
R5 = 'C:/Users/benpe/ClashBot/.foreman/scratch/recon5/'
T = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3/'
ch = json.load(open(T + 'characters.json'))['rows']
def speed(n):
    n = n.replace('C:', '')
    for k in (n, n.replace('Hero', ''), n.replace('_EV1', '')):
        if k in ch:
            return ch[k]['columns'].get('Speed')
    return None
sets = {'FRESH9': load(R5 + 'f9/f9_v3.jsonl'), 'FRESH10': load(R5 + 'f10_v3.jsonl'), 'dev49': load(R5 + 'd49_cyc2.jsonl')}
sets['FRESH9'].update(load(R5 + 'f9_cyc_aff.jsonl')); sets['FRESH10'].update(load(R5 + 'f10_cyc_aff.jsonl'))
rows = []
for name, V in sets.items():
    for m, r in V.items():
        if 'error' in r or klass(r) >= 1: continue
        fd = r.get('first_detail') or []
        if not fd or fd[0][0] != 'U_rec_only' or not fd[0][3]: continue
        near = fd[0][3]
        if len(near) > 2 and near[2]: continue
        sims = [x[2] for x in fd if x[0] == 'U_sim_only']
        if not sims: continue
        sp = speed(sims[0])
        d = math.hypot(near[0], near[1])
        rows.append((name, m[-13:], sims[0], round(d), sp, round(d / sp, 2) if sp else None))
for x in sorted(rows, key=lambda x: x[2]): print(x)
