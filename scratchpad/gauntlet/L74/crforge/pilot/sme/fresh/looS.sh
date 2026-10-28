#!/usr/bin/env bash
# looS.sh -- SME-FRESH per-flag SME activation: runL.sh on the fresh RNG-free set with one comparator / fitter flag off per run
# (all in parallel), plus L_base (no override) as the control that must equal F1. Pod 33920, FRESH=/workspace/pilot/fresh.
F=/workspace/pilot/fresh; T=/workspace/crforge_cache/tables/16.635.3; IN=$F/fresh1/inputs/inputs_rngfree.jsonl; FR=$F/fresh1/frames
bash $F/runL.sh L_base $T $IN $FR &
for X in TORN_STEP STEP_CLOCK TORN_CMD3 KIND_T BP_MIXPH BP_SNAP BP_FITNEXT MECH_CROSS HIDDEN BANNER LATE9 MADE9 HP_PLACEHOLDER TORN_CMD; do
  bash $F/runL.sh L_$X $T $IN $FR SME_$X=0 &
done
bash $F/runL.sh L_REPR $T $IN $FR SME_REPR= &
wait; echo alldone
