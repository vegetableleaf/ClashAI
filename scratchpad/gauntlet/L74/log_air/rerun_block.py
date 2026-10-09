"""Re-run `block` (Skeleton Barrel exempt) on the same candidate games as the first block run (a superset of the games the
exemption can still touch: it only removes touches).  Old block results are moved to old_block/ first.
python rerun_block.py   (laptop: local_run.ps1, 4 worker processes at a time)"""
import glob, json, os, shutil, subprocess
O = r'C:\Users\benpe\AppData\Local\Temp\logair_local'
RUN = r'C:\Users\benpe\ClashBot\.claude\worktrees\agent-a93fc9a12f7a33091\scratchpad\gauntlet\L74\log_air\local_run.ps1'
os.makedirs(f'{O}/old_block', exist_ok=True)
jobs = []
for d in sorted(glob.glob(f'{O}/block_*_b*')):
    name = os.path.basename(d)
    if os.path.isdir(d) and not name.startswith('fires_') and name.count('_') == 2:
        seeds = [json.loads(l)['tag'].split(':')[-1] for l in open(f'{d}/matches.jsonl')]
        jobs.append((name, name.split('_')[1], ','.join(sorted(seeds, key=int))))
for name, census, seeds in jobs:
    for p in (name, f'fires_{name}', f'{name}.log'):
        if os.path.exists(f'{O}/{p}'):
            shutil.move(f'{O}/{p}', f'{O}/old_block/{p}')
for name, census, seeds in jobs:
    if census == 'lad':
        continue
    print(name, seeds, flush=True)
    subprocess.run(['powershell', '-NoProfile', '-File', RUN, '-Name', name, '-Census', census, '-Seeds', seeds,
                    '-LogAir', 'block', '-Workers', str(min(4, seeds.count(',') + 1))])
print('rerun done', flush=True)
