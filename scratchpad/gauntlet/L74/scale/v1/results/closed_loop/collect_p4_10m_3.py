"""Collect the specified P4-10M_3 results and append wall-time evidence."""
from pathlib import Path
import re
import subprocess
import statistics

ROOT = Path(__file__).resolve().parent
SSH = ['ssh', '-o', 'BatchMode=yes', '-i', str(Path.home() / '.ssh/runpod_clashbot'),
       '-p', '33308', 'root@157.157.221.29']

def remote(command):
    return subprocess.run(SSH + [command], check=True, stdout=subprocess.PIPE).stdout

for side, tag in [('base_ice', 'p4base_cf_e4'), ('clxiii', 'clxiii_cf_e4')]:
    dest = ROOT / side
    dest.mkdir(parents=True, exist_ok=True)
    source = f'/workspace/d2/ev/{tag}/{tag}_741200'
    for name, relative in [('matches.jsonl', 'D3/matches.jsonl'), ('SUMMARY.txt', 'SUMMARY.txt')]:
        data = remote(f'cat {source}/{relative}')
        if name == 'matches.jsonl' and len(data) > 8 * 1024 * 1024:
            raise RuntimeError('matches exceeds 8 MB; gzip handling required')
        (dest / name).write_bytes(data)
        print(f'{side}/{name}: {len(data)} bytes')
    (dest / 'wall_lines.txt').write_bytes(remote(f"grep -h ' wall ' {source}/D3/*.log"))

score = ROOT / 'score.txt'
score.write_text('Label mapping: crforge = candidate (base_ice); fin16 = CLXIII baseline.\n'
                 'Paired delta = candidate (base_ice) minus CLXIII baseline.\n\n', encoding='utf-8')
with score.open('a', encoding='utf-8') as out:
    result = subprocess.run(['python', 'scratchpad/gauntlet/L74/plan1026/d2g/score.py',
                             str(ROOT / 'base_ice/matches.jsonl'),
                             str(ROOT / 'clxiii/matches.jsonl'), '741200'],
                            stdout=out, stderr=subprocess.STDOUT)
if result.returncode:
    raise SystemExit(f'score.py failed with exit {result.returncode}; see {score}')
with score.open('a', encoding='utf-8') as out:
    for side in ['base_ice', 'clxiii']:
        lines = (ROOT / side / 'wall_lines.txt').read_text().splitlines()
        values = [float(m.group(1)) for line in lines
                  if (m := re.search(r'\[s0\].*?\bwall\s+(\d+(?:\.\d+)?)s', line))]
        if not values:
            raise RuntimeError(f'No [s0] wall values for {side}')
        out.write(f'\n{side}: mean wall seconds per match = {statistics.mean(values):.6f} '
                  f'(n={len(values)})\n')
        out.write(f'{side} SUMMARY.txt:\n')
        out.write((ROOT / side / 'SUMMARY.txt').read_text().rstrip() + '\n')
print(score.read_text())
