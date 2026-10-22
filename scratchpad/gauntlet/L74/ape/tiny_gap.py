"""A tiny gap.py D3 run (first plan job, first N seeds, 1 worker) to check an eval flag end to end.

  python tiny_gap.py OUT CKPT N "EXTRA FLAGS" [RUNTIME [IW_FORM]]
  laptop (no Hero IW runtime here): tiny_gap.py OUT icebow/.../x.pt 2 "--record-plays --habit-log --record-board" "" normal
  pods: RUNTIME 20261012-linux (gap.py's default) and IW_FORM hero
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gap'))
import gap  # noqa: E402

out, ckpt, n, extra = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4].split()
runtime = sys.argv[5] if len(sys.argv) > 5 else '20261012-linux'
iw_form = sys.argv[6] if len(sys.argv) > 6 else 'hero'
plan = gap.prepare(out / 'inputs', ckpt)
plan['jobs'] = [dict(plan['jobs'][0], seeds=plan['jobs'][0]['seeds'][:n])]
gap.run_arm('D3', plan, out / 'inputs', out / 'D3', sys.executable, 1, iw_form=iw_form, extra=extra, runtime=runtime)
