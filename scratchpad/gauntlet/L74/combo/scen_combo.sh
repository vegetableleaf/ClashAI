#!/bin/bash
# L74 combo (10-17): the designed Rocket + Tornado scenarios (fastplays/scenario_model.py) under combo_arms' option sets, fast plays off,
# REPS replicates, one process per arm in parallel (nice 10) -> /workspace/combo_rules/scen_<arm>/ + SCEN_DONE_<arms>.
#   bash scen_combo.sh REPS ARM [ARM ...]        ARM = cur | new | newh | newd
set -uo pipefail
R=/workspace/combo_rules; CB=/workspace/cb_combo; PY=/workspace/venvf36/bin/python; REPS=$1; shift
cd $CB || exit 1
export PYTHONPATH=$CB ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero ROYALE_HEROIW_PRESS=live OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
one() { [ -e $R/scen_$1/matches.jsonl ] && return; nice -n 10 $PY scratchpad/gauntlet/L74/fastplays/scenario_model.py $R/scen_$1 \
  "--card-levels Rocket=16 Log=15 $($PY scratchpad/gauntlet/L74/combo/combo_arms.py ${1^^})" $REPS $R/inputs/cal_evo.json > $R/scen_$1.log 2>&1; }
for a in "$@"; do one $a & done
wait
touch $R/SCEN_DONE_$(IFS=_; echo "$*")
