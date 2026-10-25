#!/bin/bash
# arm_chain.sh ARM WORKERS -- pod-side (10-25 night, owner: u100, gate vs CLXIII, memory must be USED):
#   1. drift-tested training of cfg ARM to u100 (exploit/drift_test.sh; tripwires stop a leaking / drifting arm)
#   2. PASS -> the 3,840-game gate (E4 + calibrated I u40, 4 seed blocks; pushcal/gate_eval.sh, the CLXIII rows' command) on
#      this pod, paired vs CLXIII (pair_both.py; PASS = pooled 95% CI low > 0)
#   3. memory ablation: 2 x 480 games of seed block 741200, the candidate with real memory vs the SAME model fed an EMPTY
#      memory every decision (skew_worker SKEW_MODE=empty), paired (pair_arms.py): uses-memory = real - empty
# Writes /workspace/abl/res_ARM.txt (the lines the laptop's night_decide.sh reads). Training tree /workspace/cb_arm.
set -uo pipefail
ARM=$1; W=${2:-68}; CB=/workspace/cb_arm; X=/workspace/pushcal; A=/workspace/abl; PY=/workspace/venvf15/bin/python
R=$A/res_$ARM.txt; mkdir -p $A; : > $R
say() { echo "$(date -u +%FT%TZ) $*" | tee -a $R; }
say "train $ARM (drift test, u100)"
CB=$CB bash /workspace/exploit/drift_test.sh $ARM 100 > $A/drift_$ARM.out 2>&1
V=$(cat /workspace/exploit/drift/$ARM/VERDICT 2>/dev/null); say "DRIFT $V $(cat /workspace/exploit/drift/$ARM/STOP_REASON 2>/dev/null)"
[ "$V" = PASS ] || exit 1
G=/workspace/exploit/ckpt/rlarm_${ARM}_u0100_grafted.pt
[ -f $G ] || { say "no $G"; exit 2; }
say "CKPT $G $(sha256sum $G | cut -c1-64)"
TAG=g48m_${ARM}_u0100; Q=$X/q_$TAG.txt
printf '%s\n' "${TAG}_e4|e4||741200 742000 743000 744000" "${TAG}_cal|iu40|--opp-decide-every 20 --opp-tau 0.2|741200 742000 743000 744000" > $Q
CB=$CB G=$G LOCK=/workspace/cpu.lock WORKERS=$W bash $X/gate_eval.sh $Q > $X/$TAG.log 2>&1
E=$X/ev; B=g48_succ48_o_s91_u0075
$PY $X/pair_both.py "$E/${TAG}_e4/${TAG}_e4_{s}/D3/matches.jsonl" "$E/${TAG}_cal/${TAG}_cal_{s}/D3/matches.jsonl" \
  "$E/${B}_e4/${B}_e4_{s}/D3/matches.jsonl" "$E/${B}_cal/${B}_cal_{s}/D3/matches.jsonl" | sed 's/^/GATE /' | tee -a $R
IN=$E/${TAG}_e4/${TAG}_e4_741200/inputs
CB=$CB MEM=$G IN=$IN ARMS="real empty" bash $A/abl.sh $A/$ARM $((W - 2)) $(seq 0 39) > $A/abl_$ARM.out 2>&1
PAIR_ARMS=real,empty $PY $A/pair_arms.py $A/$ARM | sed 's/^/ABL /' | tee -a $R
say "DONE"
