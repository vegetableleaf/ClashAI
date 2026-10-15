import json, sys, os
sys.path.insert(0, 'scratchpad/gauntlet/L74/heroiw')
from validate import paired_drift
load = lambda p: [json.loads(l) for l in open(p) if l.strip()]
R = 'C:/Users/benpe/pod_backup_weekend/pods1013/rltest/'; A = 'C:/Users/benpe/pod_backup_weekend/pod1014b_arms/'; T = 'C:/Users/benpe/pod_backup_weekend/pod1014b_twin/'
w = lambda rs: '%d/%d (%.2f%%)' % (sum(r['outcome'] == 'win' for r in rs), len(rs), 100 * sum(r['outcome'] == 'win' for r in rs) / len(rs))
def arm(a, k):
    base = A + f'{a}/{k}_'
    if not os.path.exists(base + '741200'):
        return None
    return load(base + f'741200/{k}/matches.jsonl') + load(base + f'742000/{k}/matches.jsonl')
REF = {'r1 deployed D3': load(T + 'TWIN_live_741200/D3/matches.jsonl') + load(T + 'TWIN_live_742000/D3/matches.jsonl'),
       'r1 plain D1': load(R + 'trajd1/u060_741200.jsonl') + load(R + 'trajd1/u060_742000.jsonl'),
       'ctrl D3': load(R + 'ctrl60g_D3.jsonl') + load(R + 's2_ctrl60g_D3.jsonl')}
F1 = {'D1': arm('rlarm_gae', 'D1'), 'D3': arm('rlarm_gae', 'D3')}
for a in sys.argv[1:]:
    d1, d3 = arm(a, 'D1'), arm(a, 'D3')
    if d1 is None:
        print(a, 'missing'); continue
    print(f'== {a}: D1 {w(d1)}  D3 {w(d3)}')
    for name, base, x in (('D3 vs r1 deployed', REF['r1 deployed D3'], d3), ('D1 vs r1 plain', REF['r1 plain D1'], d1),
                          ('D3 vs F1 (gae)', F1['D3'], d3), ('D1 vs F1 (gae)', F1['D1'], d1)):
        if a != 'rlarm_gae' or 'F1' not in name:
            d = paired_drift(base, x, expected=960); print('   %-18s %+.2f pp [%+.2f, %+.2f]' % (name, d['delta_pp'], *d['ci95_pp']))
