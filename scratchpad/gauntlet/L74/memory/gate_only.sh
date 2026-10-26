#!/bin/bash
# gate_only.sh ARM U NAME WORKERS -- pod-side (10-26 night): arm_chain.sh's gate + memory ablation for an EARLIER checkpoint of a
# drift-tested arm (model selection along the run: mem_e_s107 was clean at u50 and leaked by u75). Writes
# /workspace/abl/res_NAME.txt in arm_chain's format (DRIFT line = that checkpoint's own drift check verdict).
set -uo pipefail
ARM=$1; U=$(printf %04d $2); NAME=$3; W=${4:-68}; CB=/workspace/cb_arm; X=/workspace/pushcal; A=/workspace/abl; PY=/workspace/venvf15/bin/python
R=$A/res_$NAME.txt; : > $R
say() { echo "$(date -u +%FT%TZ) $*" | tee -a $R; }
C=/workspace/exploit/drift/$ARM/check_u$U.txt
grep -q "FAIL" $C && { say "DRIFT FAIL (u$U check: $(grep -m1 -- '->' $C | cut -c1-120))"; exit 1; }
say "DRIFT PASS (u$U check clean: $C)"
G=/workspace/exploit/ckpt/rlarm_${ARM}_u${U}_grafted.pt
[ -f $G ] || { say "no $G"; exit 2; }
say "CKPT $G $(sha256sum $G | cut -c1-64)"
TAG=g48m_${NAME}; Q=$X/q_$TAG.txt
printf '%s\n' "${TAG}_e4|e4||741200 742000 743000 744000" "${TAG}_cal|iu40|--opp-decide-every 20 --opp-tau 0.2|741200 742000 743000 744000" > $Q
CB=$CB G=$G LOCK=/workspace/cpu_b.lock WORKERS=$W bash $X/gate_eval.sh $Q > $X/$TAG.log 2>&1
E=$X/ev; B=g48_succ48_o_s91_u0075
$PY $X/pair_both.py "$E/${TAG}_e4/${TAG}_e4_{s}/D3/matches.jsonl" "$E/${TAG}_cal/${TAG}_cal_{s}/D3/matches.jsonl" \
  "$E/${B}_e4/${B}_e4_{s}/D3/matches.jsonl" "$E/${B}_cal/${B}_cal_{s}/D3/matches.jsonl" | sed 's/^/GATE /' | tee -a $R
IN=$E/${TAG}_e4/${TAG}_e4_741200/inputs
CB=$CB MEM=$G IN=$IN ARMS="real empty" bash $A/abl.sh $A/$NAME $((W - 2)) $(seq 0 39) > $A/abl_$NAME.out 2>&1
PAIR_ARMS=real,empty $PY $A/pair_arms.py $A/$NAME | sed 's/^/ABL /' | tee -a $R
say "DONE"
