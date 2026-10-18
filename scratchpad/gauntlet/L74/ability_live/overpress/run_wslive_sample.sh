#!/bin/bash
# FIX TEST step 2: the live-label warm start (ws_live) decoded as trained (sampled) on the same 960 paired games.
# Waits for run_rerun.sh (one eval at a time: hide_run.sh races otherwise).
set -uo pipefail
A=/workspace/ab; CB=$A/cb; P=$CB/scratchpad/gauntlet/L74/ability_live/overpress; O=$A/overpress
EXTRA='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays'
exec >> $O/run_wslive_sample.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit; touch $O/DONE_wslive_sample' EXIT
until [ -e $O/DONE_rerun ]; do sleep 30; done
cd $CB
export PYTHONPATH=$CB OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
for S in 741200 742000; do
  log "ws_live_sample $S"
  OVERPRESS_AB_MODE=sample bash scratchpad/gauntlet/L74/cue_ab/hide_run.sh $A/venvf36/bin/python $P/gap_off.py \
    --ckpt $O/rlarm_gae_cue_ab_wslive_u0000_grafted.pt --out $O/ws_live_sample_$S --arms D3 --seed-start $S --runtime fork36-linux \
    --python $P/pyout.sh --iw-press live --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers 26 \
    --extra="$EXTRA" > $O/ws_live_sample_$S.log 2>&1 || log "GAP EXIT $? ws_live_sample $S"
done
log ALL_DONE_wslive_sample
