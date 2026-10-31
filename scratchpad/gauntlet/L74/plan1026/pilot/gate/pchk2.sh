#!/bin/bash
# pchk2.sh N CPUS -- POD side (33308 /workspace/pgate2), account 3 10-31: one pilot2 check = 480 SIM games (iu40, seed 741200) of
# ck/N.pt under its trained sampled gate (T .1) with the live decision stack (stripped LIVE_OPTIONS: Log finisher only), paired with
# CLXIII's base2_iu40_741200 rows (CLXIII on the same stripped stack, threshold gate = what is live). Current-code tree.
N=$1; C=${2:-0-47}; P=/workspace/pgate2; cd /workspace/loop/cb || exit 1
export GATE_CB=/workspace/loop/cb GATE_PY=/workspace/venvf16/bin/python GATE_LIB=/workspace/crforge_main/5e8089a4/plain/lib \
  GATE_TABLES=/workspace/crforge_cache/tables/16.635.3 GATE_FACADE=$P/facade GATE_EV=$P/ev CRFORGE_BARREL_DECOY_SIM=1 CRFORGE_XMX=1g \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" GATE_SAMPLE=0.1 GATE_CKPT=$P/ck/$N.pt
W=$(( $(echo $C | cut -d- -f2) - $(echo $C | cut -d- -f1) + 1 ))
bash scratchpad/gauntlet/L74/plan1026/d2g/gate.sh crforge p2chk_$N iu40 $C $W 741200 > $P/p2chk_$N.out 2>&1
cd $P && /workspace/venvf16/bin/python -c '
import sys
from pair_both import load, delta
a, b = load(sys.argv[1], "cal"), load(sys.argv[2], "cal")
n, m, lo, hi = delta(a, b)
print(f"wins {sum(a.values())}/{len(a)}, paired vs CLXIII(stripped) n={n} delta={100 * m:+.2f} pp [{100 * lo:+.2f}, {100 * hi:+.2f}]")
' "$P/ev/p2chk_$N/p2chk_${N}_{s}/D3/matches.jsonl" "$P/ev/base2_iu40/base2_iu40_{s}/D3/matches.jsonl"
