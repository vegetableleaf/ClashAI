#!/bin/bash
# L74 fastplays pod: the model on the designed scenarios (scenario_model.py), four arms in parallel (nice 10: the eval chain
# keeps priority), 7 scenarios x 2 times x REPS replicates each.  -> /workspace/results/fastplays/scen_<arm>/, SCEN_DONE
#   s_offc  D3 + the live combo rules (= live today, fast plays off)    s_onc  + --pipeline-decisions (= live fast plays on)
#   s_off   D3 only (the model alone)                                    s_on   + --pipeline-decisions
set -uo pipefail
R=/workspace/results/fastplays; CB=/workspace/cb_tt; PY=/workspace/venvf36/bin/python; REPS=${REPS:-16}
FAST='--pipeline-decisions --pipeline-tau-delta 0'
COMBO='--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river on'
cd $CB || exit 1
export PYTHONPATH=$CB ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero ROYALE_HEROIW_PRESS=live OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
one() { [ -e $R/scen_$1/matches.jsonl ] && return; nice -n 10 $PY scratchpad/gauntlet/L74/fastplays/scenario_model.py $R/scen_$1 \
  "--card-levels Rocket=16 Log=15 $2" $REPS > $R/scen_$1.log 2>&1; }
one s_offc "$COMBO" & one s_onc "$COMBO $FAST" & one s_off "" & one s_on "$FAST" &
wait
touch $R/SCEN_DONE
