import sys
sys.path.insert(0, 'recon')
from r2_tally import klass, load
from r4_report import guard
D = 'results/live/recon/r7/f12/'
G, Ga = load(D + 'f12_gate_results.jsonl'), load(D + 'f12_gate_a0_results.jsonl')
V, Va = load(D + 'f12_v3_results.jsonl'), load(D + 'f12_v3_a0_results.jsonl')
for name, on, off in (('gate', G, Ga), ('v3', V, Va)):
    on1 = {m: on[m] for m in off}
    print(name, 'ASSIGN off vs on, reader-hidden records:', sorted(m[-13:] for m in off), 'problems:', guard(off, on1) or 'none', '| class on/off', [(klass(on[m]), klass(off[m])) for m in off])
