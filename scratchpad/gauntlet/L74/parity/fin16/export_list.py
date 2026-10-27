"""export_list.py LIST OUT_ATTACKS OUT_BUFFS: phase-2 buffs + phase-3 attacks / births / shields (fights.py's own readers) for
exactly the logs named in LIST (one live_play_*.jsonl name per line). A1 (10-27) re-creates the c13 export this way: W19's
attacks13s / buffs13 files are gone from the laptop. Same readers and torn-line rule as w19 export22.py."""
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, 'C:/Users/benpe/ClashBot')
os.environ.pop('PARITY_ATTACKS', None); os.environ.pop('PARITY_BUFFS', None)
from scratchpad.gauntlet.L74.parity import fights as F

names = [Path(x.strip()).name for x in open(sys.argv[1]) if x.strip()]
out_a, out_b = Path(sys.argv[2]), Path(sys.argv[3])
runs = {}
for r in F.p3_runs():
    try:
        n = json.loads(r.read_text()).get('live_log')
    except ValueError:
        continue
    if n and n not in runs:
        runs[n] = r
missing = [n for n in names if n not in runs]
print('names', len(names), 'with a capture', len(names) - len(missing), 'missing', missing[:5], flush=True)
att, buf, births, shields = {}, {}, {}, {}
t = time.time()
for i, n in enumerate(names):
    if n not in runs:
        continue
    F.p3_runs = lambda n=n: [runs[n]]
    try:
        F.phase3_attacks(n)
    except ValueError:                         # a torn line: read a copy without it
        src = runs[n].parent; dst = out_a.parent / 'clean' / src.name; dst.mkdir(parents=True, exist_ok=True)
        (dst / 'run.json').write_bytes((src / 'run.json').read_bytes())
        bad = 0
        with open(src / 'frames.jsonl', 'rb') as fi, open(dst / 'frames.jsonl', 'wb') as fo:
            for raw in fi:
                try:
                    json.loads(raw); fo.write(raw)
                except ValueError:
                    bad += 1
        print('torn lines dropped', n, bad, flush=True)
        runs[n] = dst / 'run.json'
        F.p3_runs = lambda n=n: [runs[n]]
    att[n] = F.phase3_attacks(n)
    b = F.phase3_births(n)
    if b:
        births[n] = b
    s = F.phase3_shields(n)
    if s:
        shields[n] = s
    buf[n] = F.phase2_buffs(n)
    if i % 50 == 0:
        print(i, f'{time.time() - t:.0f}s', flush=True)
att['_births'] = births; att['_shields'] = shields
out_a.write_text(json.dumps(att, separators=(',', ':')))
out_b.write_text(json.dumps(buf))
print('EXPORT_DONE logs', len(att) - 2, 'births', len(births), 'shields', len(shields), f'{time.time() - t:.0f}s', flush=True)
