"""Apply mech_rules (SME_MECH_* flags) to an inputs jsonl, frames from the converted live frames, raw logs (for the
buff rules) from LOGDIR (A2c-M measurement only; extract.py merges the hook).
python3 mech_inputs.py IN.jsonl FRAMES_DIR|- OUT.jsonl [LOGDIR]"""
import json, os, sys
import mech_rules

src, fdir, dst = sys.argv[1:4]
logdir = sys.argv[4] if len(sys.argv) > 4 else None
log, n = [], 0
with open(dst, 'w') as w:
    for line in open(src):
        r = json.loads(line)
        fp = os.path.join(fdir, r['match'] + '.jsonl')
        frames = {f['t']: f for f in map(json.loads, open(fp))} if fdir != '-' and os.path.exists(fp) else {}
        path = os.path.join(logdir, r['match'] + '.jsonl') if logdir else None
        before = len(log)
        r['plays'] = mech_rules.apply(path if path and os.path.exists(path) else None, r['plays'], r['sides'], frames, log)
        for x in log[before:]:
            print(r['match'], *x)
        w.write(json.dumps(r) + '\n')
        n += 1
print('matches', n, 'changes', len(log), file=sys.stderr)
