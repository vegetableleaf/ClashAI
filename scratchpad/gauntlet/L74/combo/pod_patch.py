"""L74 combo (10-17): the ONE pod-only measurement line in the cb_combo checkout (never main, never live): livecal.worker installs
measure_shim when COMBO_MEASURE=1 (unset = the worker exactly as before).
    python pod_patch.py CHECKOUT        (idempotent: an already-patched file is left alone; any other mismatch aborts)"""
import sys
from pathlib import Path

OLD = "    S.live_cfg = no_stall\n    args = sys.argv[2:]\n"
NEW = ("    S.live_cfg = no_stall\n"
       "    if os.environ.get('COMBO_MEASURE') == '1':   # L74 combo pod_patch (measurement only, pod checkout)\n"
       "        sys.path.insert(0, str(ROOT / 'scratchpad/gauntlet/L74/combo'))\n"
       "        import measure_shim\n"
       "        measure_shim.install(S)\n"
       "    args = sys.argv[2:]\n")

p = Path(sys.argv[1]) / 'scratchpad/gauntlet/L74/livecal/livecal.py'
s = p.read_text(encoding='utf-8')
if NEW in s:
    print('already', p)
elif s.count(OLD) != 1:
    raise SystemExit(f'{p}: anchor found {s.count(OLD)} times')
else:
    if '\nimport os' not in s:
        raise SystemExit(f'{p}: no "import os"')
    p.write_text(s.replace(OLD, NEW), encoding='utf-8', newline='\n')
    print('patched', p)
