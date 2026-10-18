#!/bin/bash
# Re-run the two halves that died at 06:51 (three runners raced on hide_run.sh's derived-dir rename -> "Pinned RoyaleSim
# must use its compiled-in card table"). One runner, sequential.
set -uo pipefail
A=/workspace/ab; CB=$A/cb; P=$CB/scratchpad/gauntlet/L74/ability_live/overpress; O=$A/overpress
EXTRA='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays'
exec >> $O/run_rerun.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit; touch $O/DONE_rerun' EXIT
cd $CB
export PYTHONPATH=$CB OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
for SPEC in ws_live:$O/rlarm_gae_cue_ab_wslive_u0000_grafted.pt: ws_sample:$O/rlarm_gae_cue_ab_u0000_grafted.pt:sample; do
  IFS=: read n ck md <<< "$SPEC"
  S=742000; mv $O/${n}_$S $O/${n}_${S}_failed_race 2>/dev/null; mv $O/${n}_$S.log $O/${n}_${S}_failed_race.log 2>/dev/null
  log "$n $S mode=${md:-greedy}"
  OVERPRESS_AB_MODE=$md bash scratchpad/gauntlet/L74/cue_ab/hide_run.sh $A/venvf36/bin/python $P/gap_off.py \
    --ckpt $ck --out $O/${n}_$S --arms D3 --seed-start $S --runtime fork36-linux --python $P/pyout.sh --iw-press live \
    --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers 26 --extra="$EXTRA" > $O/${n}_$S.log 2>&1 \
    || log "GAP EXIT $? $n $S"
done
log ALL_DONE_rerun
