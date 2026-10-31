"""pod: SEL.jsonl (rows with match, path) -> LIST.jsonl (match, plan_path, frames_path, me)."""
import glob, json, os, sys
frames = {}
for pat in ('/workspace/smeR*/data/*/frames/live_play_*.jsonl', '/workspace/smeR*/data/allframes/live_play_*.jsonl',
            '/workspace/smeR*/data/pa_frames/live_play_*.jsonl', '/workspace/smeR*/data/f*/frames/live_play_*.jsonl'):
    for p in glob.glob(pat):
        frames.setdefault(os.path.basename(p)[:-6], p)
n = miss = 0
with open(sys.argv[2], 'w') as w:
    for l in open(sys.argv[1]):
        r = json.loads(l)
        d = r['path']
        pp = os.path.join(d, 'recon_plan.json')
        if not os.path.exists(pp):
            pp = os.path.join(d, 'plan.json')
        plan = json.load(open(pp))
        own = {c['side'] for c in plan['cmds'] if (c.get('_src') or {}).get('own')}
        me = own.pop() if len(own) == 1 else None
        fp = frames.get(r['match'])
        if fp is None or me is None:
            miss += 1
            print('MISS', r['match'], fp, me, file=sys.stderr)
            continue
        w.write(json.dumps({'match': r['match'], 'plan_path': pp, 'frames_path': fp, 'me': me, 'run': r.get('run')}) + '\n')
        n += 1
print('list', n, 'miss', miss)
