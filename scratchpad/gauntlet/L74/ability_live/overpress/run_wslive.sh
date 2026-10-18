#!/bin/bash
# FIX TEST step 1 (10-18): the cue_ab warm start with the LIVE IW rule as the label source (ROYALE_HEROIW_PRESS=live)
# instead of the generic range rule the training chain used (variable unset). One change vs cue_ab: that variable
# (n_actors 12 / max_updates 1 only change speed / stop after u0000; the head is frozen in critic warm-up anyway).
# Then graft as the chain did and score it greedy on the promotion eval's 960 paired games (ws_live).
set -uo pipefail
A=/workspace/ab; CB=$A/cb; P=$CB/scratchpad/gauntlet/L74/ability_live/overpress; O=$A/overpress; RL=icebow/data/bench/rl_royale
RUN=rlarm_gae_cue_ab_wslive; U250=$RL/rlarm_gae/rlarm_gae_u0250_grafted.pt
EXTRA='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays'
mkdir -p $O; exec >> $O/run_wslive.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit; touch $O/DONE_wslive' EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
sed -e 's/^n_actors: 24$/n_actors: 12/' -e 's/^max_updates: 65$/max_updates: 1/' scratchpad/gauntlet/L74/cue_ab/cue_ab.yaml > $P/wslive.yaml
grep -q '^max_updates: 1$' $P/wslive.yaml || { log "yaml patch failed"; exit 2; }
CK=$RL/$RUN/${RUN}_u0000.pt
if [ ! -f $CK ]; then
  log "train $RUN (ROYALE_HEROIW_PRESS=live)"
  ROYALE_HEROIW_PRESS=live ROYALE_RUNTIME=20261016-linux $A/venv35/bin/python $P/train_boot.py --config $P/wslive.yaml --run $RUN \
    >> $O/train_wslive.log 2>&1 || log "TRAIN EXIT $?"
fi
[ -f $CK ] || { log "no $CK"; exit 4; }
G=$O/${RUN}_u0000_grafted.pt
[ -f $G ] || $A/venvf36/bin/python scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $U250 $G >> $O/graft_wslive.log 2>&1
[ -f $G ] || { log "graft failed"; exit 5; }
sha256sum $CK $G >> $O/ckpts.sha
for S in 741200 742000; do
  [ -e $O/ws_live_$S/SUMMARY.txt ] && continue
  rm -rf $O/ws_live_$S; log "ws_live $S"
  bash scratchpad/gauntlet/L74/cue_ab/hide_run.sh flock /workspace/cpu.lock $A/venvf36/bin/python $P/gap_off.py \
    --ckpt $G --out $O/ws_live_$S --arms D3 --seed-start $S --runtime fork36-linux --python $P/pyout.sh --iw-press live \
    --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers 26 --extra="$EXTRA" > $O/ws_live_$S.log 2>&1 \
    || log "GAP EXIT $? ws_live $S"
done
touch $O/ALL_DONE_wslive; log ALL_DONE_wslive
