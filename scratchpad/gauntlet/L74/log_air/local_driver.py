"""Laptop staged driver: for each (census, seeds, n) run base (name base_<census>_b<n>), then retarget and block on the candidate
games (base played an only_air Log), 4 worker processes at a time (local_run.ps1).
  python local_driver.py air:30:80:2 air:80:240:3 evo:100:220:4 lad:100:220:5     (an existing finished base is reused)"""
import glob, json, os, subprocess, sys

O = r'C:\Users\benpe\AppData\Local\Temp\logair_local'
RUN = r'C:\Users\benpe\ClashBot\.claude\worktrees\agent-a93fc9a12f7a33091\scratchpad\gauntlet\L74\log_air\local_run.ps1'


def run(name, census, seeds, arm='', workers=4):
    if os.path.exists(f'{O}/done.log') and f'{name} rc=0' in open(f'{O}/done.log').read():
        return
    cmd = ['powershell', '-NoProfile', '-File', RUN, '-Name', name, '-Census', census, '-Seeds', seeds, '-Workers', str(workers)]
    if arm:
        cmd += ['-LogAir', arm]
    subprocess.run(cmd, check=False)


def candidates(name):
    done, cand = set(), set()
    for l in open(f'{O}/{name}/matches.jsonl'):
        done.add(json.loads(l)['tag'])
    for f in glob.glob(f'{O}/fires_{name}/fires_*.jsonl'):
        for l in open(f):
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if x.get('play') and x.get('kind') == 'only_air' and x['tag'] in done:
                cand.add(int(x['tag'].split(':')[-1]))
    return sorted(cand)


for spec in sys.argv[1:]:
    census, a, b, n = spec.split(':')
    base = f'base_{census}_b{n}'
    run(base, census, f'{a}:{b}')
    c = candidates(base)
    print(base, 'candidates', c, flush=True)
    for arm in ('retarget', 'block'):
        if c:
            run(f'{arm}_{census}_b{n}', census, ','.join(map(str, c)), arm, min(4, len(c)))
print('driver done', flush=True)
