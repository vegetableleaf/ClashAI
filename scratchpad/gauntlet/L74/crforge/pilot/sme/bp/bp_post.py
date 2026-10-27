"""Apply bp_rules flags that need only plays + frames to an existing inputs file (A2c-BP2, pod side; the extract hook does
the same on the laptop). Frames: the SME frames dir (live_frames rows, our elixir 'el').
    SME_BP_PRESS=1 python3 bp_post.py IN.jsonl FRAMES_DIR OUT.jsonl"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bp_rules
inp, fdir, outp = sys.argv[1:4]
n = 0
with open(outp, 'w') as w:
    for l in open(inp):
        r = json.loads(l)
        fp = os.path.join(fdir, r['match'] + '.jsonl')
        if bp_rules.PRESS and os.path.exists(fp):
            frames = {f['t']: f for f in map(json.loads, open(fp))}
            new = bp_rules.press_from_drop(r['plays'], frames, r['sides'])
            for a, b in zip(r['plays'], new):
                if a != b:
                    n += 1
                    print(r['match'], a['card'], a['tick'], a['run_ticks'], '->', b['tick'], b['run_ticks'])
            r['plays'] = new
        w.write(json.dumps(r) + '\n')
print('changed', n)
