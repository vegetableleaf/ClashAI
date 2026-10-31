"""RECON-7 pace probe driver (pod, in /workspace/opp/cb): D3 (CLXIII live stack vs ftR u80), N chunks, refusal reasons per match.
  python rr_probe.py OUTDIR NCHUNKS [extra worker flags...]"""
import json, os, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
CB = '/workspace/opp/cb'
sys.path[:0] = [CB, CB + '/scratchpad/gauntlet/L74/gap', CB + '/scratchpad/gauntlet/L74/livecal', CB + '/scratchpad/gauntlet/L74/heroiw']
import gap  # noqa: E402
out, nch = Path(sys.argv[1]), int(sys.argv[2]); extra = sys.argv[3:]
G = 'icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt'
OPP = os.environ.get('OPP_CKPT', '/workspace/oplm/d3/ck/oplc_ftR_l0003_live_s1f_u0080.pt')
CENSUS = CB + '/scratchpad/gauntlet/L74/mix/decks_live_eval.json'
plan = gap.prepare(out / 'inputs', G, 741200, OPP, 1.0, CENSUS)
EX = '--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log --record-board --tap-loss 1x:0.0180,2x:0.0363,ot2x:0.0388,ot3x:0.0890 --tap-slow 0.151:17'.split()
env = dict(os.environ, ROYALE_HEROIW_FORM='hero', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
PY = '/workspace/venvf16/bin/python'
jobs = plan['jobs'][:nch]
print('chunks in plan', len(plan['jobs']), 'seeds per chunk', len(jobs[0]['seeds']), flush=True)
def one(it):
    i, job = it
    dest = out / 'D3' / ('%05d' % i)
    cmd = gap.command('D3', job, out / 'inputs' / plan['censuses'][job['census']]['path'], dest, PY, EX + extra, (), (), 'all16')
    cmd[1] = '/workspace/smeR6/rr_wrap.py'
    (out / 'D3').mkdir(exist_ok=True)
    with dest.with_suffix('.log').open('w') as log:
        subprocess.run(cmd, cwd=CB, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    return [json.loads(s) for s in (dest / 'matches.jsonl').read_text().splitlines() if s.strip()]
with ThreadPoolExecutor(max_workers=int(os.environ.get('W', '4'))) as ex, (out / 'rows.jsonl').open('w') as f:
    for rows in ex.map(one, enumerate(jobs)):
        for r in rows:
            f.write(json.dumps(r) + '\n'); f.flush()
print('done', flush=True)
