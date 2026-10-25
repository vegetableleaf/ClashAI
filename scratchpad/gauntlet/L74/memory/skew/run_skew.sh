#!/bin/bash
# run_skew.sh OUT P JOBS... -- the memory skew ablation on pod 33912 (lead 10-25): 3 paired arms of gap.py D3 chunks vs E4,
# the running mem_o_s105_u0000 eval's own plan (same seeds / censuses / opponent), nice 10, P processes at once.
#   real  = mem model (S3 v1 adapter, grafted), dumps + per-decision diag vs empty memory / base
#   empty = mem model fed an EMPTY memory every decision (memory still built + dumped)
#   base  = CLXIII grafted (no memory)
#   delta = mem model with mem.out.bias shifted so an EMPTY memory adds 0 (make_delta.py); ARMS env picks the arms
# Reads /workspace/cb_mem + the running eval's inputs; writes ONLY under OUT.
set -uo pipefail
OUT=$1; P=$2; shift 2; JOBS="$*"
CB=/workspace/cb_mem; PY=/workspace/venvf15/bin/python; W=/workspace/skew/skew_worker.py
IN=/workspace/exploit/ev/mem_o_s105_u0000/e4/mem_o_s105_u0000_741200/inputs
MEM=/workspace/s3/mem_best_grafted.pt; BASE=/workspace/exploit/ckpt/rlarm_succ48_o_s91_u0075_grafted.pt
E4=icebow/data/bench/rl_royale/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt
EX="--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --log-aim log_barrel --lethal-rocket ot_behind --xbow-dead-lane block --rocket-dead-target block --tau-threatened 0.2 --lethal-log on --habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays --ability-stats --ability-head-decode=sample --crown-log --record-board"
cd $CB || exit 1
export ROYALE_RUNTIME=fin15-linux ROYALE_HEROIW_FORM=hero ROYALE_HEROIW_PRESS=live PYTHONPATH=$CB HABITS_REC=1 O3_PLAYS=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 SKEW_BASE=$BASE
one() {   # ARM JOB
  local arm=$1 j=$2 ck=$MEM mode
  case $arm in real) mode=real ;; empty) mode=empty ;; base) mode=none; ck=$BASE ;; shadow) mode=shadow ;;
    delta) mode=real; ck=/workspace/skew/mem_best_grafted_delta.pt ;; esac
  read -r census seeds < <($PY -c "import json,sys; j=json.load(open('$IN/plan.json'))['jobs'][$j]; print(j['census'], ','.join(map(str,j['seeds'])))")
  local d=$OUT/$arm/$(printf %05d $j); mkdir -p $OUT/$arm
  SKEW_MODE=$mode SKEW_DUMP=$OUT/$arm/dump nice -n 10 $PY $W --worker-all16 --out $d --seeds $seeds --opps gen --arms plain \
    --gen $ck --opp-gen $E4 --s1 icebow/data/pipeline/gen_v1_s0/gen_s0.pt --forms-mode deck --device cpu --workers 1 --threads 1 \
    --tail-cap 7200 --tau-plain .35 --census $IN/cal_$census.json --hero-abilities --ability-policy v2 --opp-policy sample \
    --opp-T 0.1 --own-effects $EX > $d.log 2>&1 < /dev/null && echo "$(date -u +%T) $arm $j ok" || echo "$(date -u +%T) $arm $j FAIL"
}
export -f one; export OUT IN MEM BASE E4 EX PY W
for j in $JOBS; do for a in ${ARMS:-real empty base}; do echo "$a $j"; done; done | xargs -P $P -L 1 bash -c 'one $0 $1'
echo "$(date -u +%T) ALL DONE"
