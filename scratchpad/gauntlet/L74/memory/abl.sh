#!/bin/bash
# abl.sh OUT P JOBS... -- the memory ablation (generalised skew/run_skew.sh): paired gap.py D3 chunks vs E4 on a gate E4 seed
# block's own plan (IN = its inputs dir: plan.json + cal_*.json), arms from ARMS (default "real empty"):
#   real  = MEM with its memory;   empty = MEM fed an EMPTY memory every decision (skew_worker SKEW_MODE=empty)
# env: CB (tree), MEM (grafted ckpt), IN. Writes ONLY under OUT. Same decode flags as run_skew.sh / gate_eval's live stack.
set -uo pipefail
OUT=$1; P=$2; shift 2; JOBS="$*"
PY=/workspace/venvf15/bin/python; W=/workspace/abl/skew_worker.py
E4=icebow/data/bench/rl_royale/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt
EX="--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --log-aim log_barrel --lethal-rocket ot_behind --xbow-dead-lane block --rocket-dead-target block --tau-threatened 0.2 --lethal-log on --habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays --ability-stats --ability-head-decode=sample --crown-log --record-board"
cd $CB || exit 1
export ROYALE_RUNTIME=fin15-linux ROYALE_HEROIW_FORM=hero ROYALE_HEROIW_PRESS=live PYTHONPATH=$CB HABITS_REC=1 O3_PLAYS=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  SKEW_GAP=$CB/scratchpad/gauntlet/L74/gap \
  SKEW_BASE=${SKEW_BASE:-$CB/icebow/data/bench/rl_royale/rlarm_succ48_o_s91/rlarm_succ48_o_s91_u0075_grafted.pt}
# 10-26: SKEW_GAP else skew_worker loads cb_mem's gap (memory v1 only -> 0 pairs); SKEW_BASE = real mode's diag reference (CLXIII)
one() {   # ARM JOB
  local arm=$1 j=$2 mode=$1
  read -r census seeds < <($PY -c "import json,sys; j=json.load(open('$IN/plan.json'))['jobs'][$j]; print(j['census'], ','.join(map(str,j['seeds'])))")
  local d=$OUT/$arm/$(printf %05d $j); mkdir -p $OUT/$arm
  SKEW_MODE=$mode SKEW_DUMP=$OUT/$arm/dump $PY $W --worker-all16 --out $d --seeds $seeds --opps gen --arms plain \
    --gen $MEM --opp-gen $E4 --s1 icebow/data/pipeline/gen_v1_s0/gen_s0.pt --forms-mode deck --device cpu --workers 1 --threads 1 \
    --tail-cap 7200 --tau-plain .35 --census $IN/cal_$census.json --hero-abilities --ability-policy v2 --opp-policy sample \
    --opp-T 0.1 --own-effects $EX > $d.log 2>&1 < /dev/null && echo "$(date -u +%T) $arm $j ok" || echo "$(date -u +%T) $arm $j FAIL"
}
export -f one; export OUT IN MEM E4 EX PY W
for j in $JOBS; do for a in ${ARMS:-real empty}; do echo "$a $j"; done; done | xargs -P $P -L 1 bash -c 'one $0 $1'
echo "$(date -u +%T) ALL DONE"
