"""Apply bp_rules (../bp_rules.py) to an inputs file on the laptop (it reads the raw live logs). Equal to extract.match
calling bp_rules.apply(path, plays, sides, frames) right after crforge_casts, since nothing after that call reads ability
ticks or play points (checked: regen with the hook = this file's output, byte for byte).
    SME_BP_VALK=1 SME_BP_GK=1 SME_BP_GIANT=1 SME_BP_RASCALS=1 python -I bp_inputs.py IN.jsonl OUT.jsonl LIVE_DIR"""
import json, os, sys
SME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SME)
import bp_rules  # noqa: E402
import live_frames  # noqa: E402
n = 0
with open(sys.argv[2], 'w', newline='\n') as w:
    for l in open(sys.argv[1]):
        r = json.loads(l)
        path = os.path.join(sys.argv[3], r['match'] + '.jsonl')
        frames = {f['t']: f for f in live_frames.convert(path)} if (bp_rules.GK or bp_rules.RASCALS) else None
        new = bp_rules.apply(path, r['plays'], r['sides'], frames)
        old = [json.dumps(p, sort_keys=True) for p in r['plays']]
        n += sum(1 for p in new if json.dumps(p, sort_keys=True) not in old) + max(0, len(r['plays']) - len(new))
        r['plays'] = new
        w.write(json.dumps(r) + '\n')
print('changed / added / dropped plays', n)
