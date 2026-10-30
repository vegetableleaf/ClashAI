#!/bin/bash
# pchk.sh N -- POD side (33903 /workspace/pgate), account 3 10-30: one pilot check = 480 SIM games (iu40 suite, seed 741200) of
# ck/N.pt under its TRAINED sampled gate (T .1), paired with CLXIII's base_iu40_741200 rows (threshold gate = what is live).
# Same env as GATE_AND_LIVE.md step 1. CPUs 16-31, 16 workers. Prints one result line. Driven by pilot_check.sh on the laptop.
N=$1; P=/workspace/pgate; cd $P/cb || exit 1
export GATE_CB=$P/cb GATE_PY=/workspace/venvf16/bin/python GATE_LIB=/workspace/crforge_main/5e8089a4/plain/lib \
  GATE_TABLES=/workspace/oplm/tables/16.635.3 GATE_FACADE=$P/facade GATE_EV=$P/ev CRFORGE_BARREL_DECOY_SIM=1 CRFORGE_XMX=1g \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" GATE_SAMPLE=0.1 GATE_CKPT=$P/ck/$N.pt
bash scratchpad/gauntlet/L74/plan1026/d2g/gate.sh crforge pchk_$N iu40 16-31 16 741200 > $P/pchk_$N.out 2>&1
cd $P && /workspace/venvf16/bin/python -c '
import sys
from pair_both import load, delta
a, b = load(sys.argv[1], "cal"), load(sys.argv[2], "cal")
w = sum(a.values())
n, m, lo, hi = delta(a, b)
print(f"pilot wins {w}/{len(a)}, paired vs CLXIII n={n} delta={100 * m:+.2f} pp [{100 * lo:+.2f}, {100 * hi:+.2f}]")
' "$P/ev/pchk_$N/pchk_${N}_{s}/D3/matches.jsonl" "$P/ev/base_iu40/base_iu40_{s}/D3/matches.jsonl"
