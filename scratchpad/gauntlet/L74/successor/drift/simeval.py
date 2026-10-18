"""SIM (promotion eval: fork36 + troops at live rates + live levels, D3, 960 paired) win rate by opponent group for the two
factorial reference models, next to the live win rate in the same groups (drift.json).  -> simeval.txt"""
import collections
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import drift as D                                                          # noqa: E402

A, bs = D.A, D.base_set
REF = 'C:/Users/benpe/pod_backup_weekend/pod1017_factorial/{0}/eval/{0}_*/D3/*/matches.jsonl'
CORE = {'megaknight', 'witch', 'firecracker', 'hogrider', 'electrogiant', 'elixirgolem', 'goldenknight'}
UNF = [a for a in A.ORDER if A.unfavorable(a)]
live = json.loads((HERE / 'drift.json').read_text())['live']
LIVE = {'CXXIV': [r for r in live if r['mark'] == 'CXXIV'], 'CXXXVIII': [r for r in live if r['mark'] == 'CXXXVIII']}
groups = {'ALL': lambda s: True, 'any 13k-core card': lambda s: bool(s & CORE), 'no core card': lambda s: not s & CORE,
          'megaknight': lambda s: 'megaknight' in s, 'witch': lambda s: 'witch' in s, 'firecracker': lambda s: 'firecracker' in s,
          'hogrider': lambda s: 'hogrider' in s, 'electrogiant': lambda s: 'electrogiant' in s,
          'unfavourable six': lambda s: A.classify(s) in UNF}
groups.update({f'arch {a}': (lambda a: lambda s: A.classify(s) == a)(a) for a in ('golem', 'hyperbait', 'weak_other', 'other')})
T = []
w = T.append
for ref, mark in (('ref_u250', 'CXXIV'), ('ref_cxxxviii', 'CXXXVIII')):
    rows = []
    for f in sorted(glob.glob(REF.format(ref))):
        for line in open(f, encoding='utf-8'):
            j = json.loads(line)
            rows.append(({A.canon(n.split('@')[0]) for n in j['opp_deck']}, int(j['outcome'] == 'win'), j.get('opp_tower'),
                         j['levels']['opp']['tower'] if j.get('levels') else None))
    w(f"== {ref} ({mark}): {len(rows)} SIM games; live rows {len(LIVE[mark])}")
    w(f"{'group':22s} {'SIM n':>6s} {'SIM win':>7s} {'95% CI':>13s} | {'live n':>6s} {'live win':>8s} {'95% CI':>13s} | SIM-live")
    for g, t in groups.items():
        s = [x[1] for x in rows if t(x[0])]
        l = [r['win'] for r in LIVE[mark] if t(bs(r))]
        if not s:
            continue
        cs, cl = D.wilson(sum(s), len(s)), D.wilson(sum(l), len(l))
        ps, pl = 100 * sum(s) / len(s), (100 * sum(l) / len(l) if l else float('nan'))
        w(f"{g:22s} {len(s):6d} {ps:7.1f} [{cs[0]:5.1f},{cs[1]:5.1f}] | {len(l):6d} {pl:8.1f} [{cl[0]:5.1f},{cl[1]:5.1f}] | {ps-pl:+6.1f}")
    tt = collections.defaultdict(list)
    for x in rows:
        tt['troop' if x[2] else 'princess'].append(x[1]); tt[f'opp tower L{x[3]}'].append(x[1])
    w('   SIM by opp tower: ' + '; '.join(f"{k} n {len(v)} win {100*sum(v)/len(v):.1f}%" for k, v in sorted(tt.items())))
(HERE / 'simeval.txt').write_text('\n'.join(T) + '\n', encoding='utf-8')
print('\n'.join(T))
