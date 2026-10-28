"""Print the gate's D3 worker command (gap.command, all16) for one plan job with only its first N seeds, so it can run under
cProfile:  python prof_cmd.py INPUTS_DIR OUT_DIR N "<extra flags>"  (INPUTS_DIR = a gap.py run's inputs/ with plan.json)."""
import json
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path[:0] = [str(HERE.parents[2] / 'gap')]
import gap  # noqa: E402

inputs, out, n, extra = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4].split()
plan = json.loads((inputs / 'plan.json').read_text())
job = dict(plan['jobs'][0], seeds=plan['jobs'][0]['seeds'][:n])
cmd = gap.command('D3', job, inputs / plan['censuses'][job['census']]['path'], Path(out), sys.executable, extra,
                  levels='all16')
print(shlex.join(cmd[1:]))
