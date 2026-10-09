#!/bin/bash
# SIM v3 480 paired (GEN v1 opponent sampling T .3, seeds 0:240 x census EVO + ladder LAD) for the rocket_value2 variants.
# Every arm = the deployed LIVE_OPTIONS bundle's decision flags (live-only flags left out: SIM has no input latency) + the arm's flags.
#   TREE=t2 ARMS="base rv9" W=6 SEEDS=0:240 OUT=~/rocket_value2/outA bash vm_ab2.sh
#   WRAP=scratchpad/gauntlet/L74/rocket_value2/rv2_diag_s0.py (default; full-board windows around every Rocket play, logging only; PLACEBO=1 aims the rule fires at a harmless corner)
#   DECK_FILTER: optional extra census json pair override  EVO= LAD=
# Arm flags come from $ARMFILE (lines "name flags...") so a variant needs no edit here.
TREE=${TREE:-t2}; cd ~/rocket_value2/$TREE
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=${OUT:-~/rocket_value2/$TREE}; mkdir -p $O; W=${W:-6}; LOG=$O/sim.log; SEEDS=${SEEDS:-0:240}
WRAP=${WRAP:-scratchpad/gauntlet/L74/rocket_value2/rv2_diag_s0.py}
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=${EVO:-scratchpad/gauntlet/L70/pool_forms/loadable_decks.json}; LAD=${LAD:-scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json}
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --gate-hazard-threatened 2 --log-aim log_barrel
    --lethal-rocket ot_behind --xbow-dead-lane block --rocket-dead-target block --tau-threatened 0.2 --lethal-log on --behaviour-telemetry)
ARMFILE=${ARMFILE:-$HOME/rocket_value2/$TREE/scratchpad/gauntlet/L74/rocket_value2/arms.txt}
run() { local name=$1 s=$2; d=$EVO; [ $s = lad ] && d=$LAD
  local flags; flags=$(awk -v n=$name '$1==n{$1=""; print}' $ARMFILE)
  export FIRE_DIR=$O/fires_${name}_$s; mkdir -p $FIRE_DIR
  case $name in plc*) export PLACEBO=1;; *) unset PLACEBO;; esac
  [ -n "$TIMES" ] && [ -f $TIMES$s.json ] && [ "$name" = base ] && export WIN_TIMES=$TIMES$s.json || unset WIN_TIMES
  local seeds=$SEEDS   # SEEDDIR/<arm>_<census>.txt = the seeds on which the arm can differ from BASE at all (mk_subsets.py); empty = none
  if [ -n "$SEEDDIR" ] && [ -f $SEEDDIR/${name}_$s.txt ]; then seeds=$(cat $SEEDDIR/${name}_$s.txt)
    [ -z "$seeds" ] && { echo "$name $s no fires (identical to base)" >> $LOG; return; }; fi
  nice -n 10 $PY $WRAP --out $O/${name}_$s --seeds $seeds --opps gen --arms plain --gen $CK \
    --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
    --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}" $flags > $O/${name}_$s.log 2>&1
  echo "$name $s rc=$? $(date +%T)" >> $LOG; }
for a in ${ARMS:-base}; do for s in ${CENSUSES:-evo lad}; do run $a $s & done; done
wait
echo DONE >> $LOG
