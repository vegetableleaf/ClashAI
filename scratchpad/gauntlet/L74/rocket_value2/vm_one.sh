#!/bin/bash
# One (arm, census) SIM v3 job on its seed subset (SEEDDIR/<arm>_<census>.txt from mk_subsets.py), same bundle as vm_ab2.sh.
#   TREE=t9 OUT=~/rocket_value2/c1 SEEDDIR=~/rocket_value2/seeds1 W=3 bash vm_one.sh ARM CENSUS      (CENSUS = evo | lad | air)
name=$1; s=$2
TREE=${TREE:-t9}; cd ~/rocket_value2/$TREE
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=${OUT:-~/rocket_value2/$TREE}; mkdir -p $O; W=${W:-3}; LOG=$O/sim.log
WRAP=${WRAP:-scratchpad/gauntlet/L74/rocket_value2/rv2_diag_s0.py}
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
case $s in evo) d=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json;; lad) d=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json;; air) d=$HOME/rocket_value2/air_census.json;; esac
[ -n "$CENSUS_PATH" ] && d=$CENSUS_PATH     # e.g. the air-heavy opponent pool (air_census.json) with the 'evo' seed files of boards_air
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --gate-hazard-threatened 2 --log-aim log_barrel
    --lethal-rocket ot_behind --xbow-dead-lane block --rocket-dead-target block --tau-threatened 0.2 --lethal-log on --behaviour-telemetry)
ARMFILE=${ARMFILE:-$HOME/rocket_value2/$TREE/scratchpad/gauntlet/L74/rocket_value2/arms_all.txt}
flags=$(awk -v n=$name '$1==n{$1=""; print}' $ARMFILE)
seeds=$(cat $SEEDDIR/${name}_$s.txt)
[ -z "$seeds" ] && { echo "$name $s no seeds" >> $LOG; exit 0; }
export FIRE_DIR=$O/fires_${name}_$s; mkdir -p $FIRE_DIR
case $name in plc*) export PLACEBO=1;; *) unset PLACEBO;; esac
nice -n 10 $PY $WRAP --out $O/${name}_$s --seeds $seeds --opps gen --arms plain --gen $CK \
  --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
  --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}" $flags > $O/${name}_$s.log 2>&1
echo "$name $s rc=$? $(date +%T)" >> $LOG
