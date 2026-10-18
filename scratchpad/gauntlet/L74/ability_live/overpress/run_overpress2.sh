#!/bin/bash
# Overpress evals, part 2 (lead 10-18): separate the warm start from PPO and greedy from sampled decoding.
#   ws_greedy  rlarm_gae_cue_ab_u0000 (head = BC warm start only; policy frozen in critic warm-up) grafted, greedy head
#   ws_sample  the same, head sampled (RL rollout decoding)
#   ab_sample  u0065 grafted (the promoted candidate), head sampled
# Same paired design as run_overpress.sh; shares /workspace/cpu.lock with it (one eval at a time).
set -uo pipefail
A=/workspace/ab; CB=$A/cb; P=$CB/scratchpad/gauntlet/L74/ability_live/overpress; O=$A/overpress; RL=icebow/data/bench/rl_royale
U250=$RL/rlarm_gae/rlarm_gae_u0250_grafted.pt
WS=$RL/rlarm_gae_cue_ab/rlarm_gae_cue_ab_u0000.pt; WSG=$O/rlarm_gae_cue_ab_u0000_grafted.pt
AB=$RL/rlarm_gae_cue_ab/rlarm_gae_cue_ab_u0065_grafted.pt
EXTRA='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays'
mkdir -p $O; exec >> $O/run2.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit; touch $O/DONE2' EXIT
cd $CB
export PYTHONPATH=$CB OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
until [ -f $P/gap_off.py ]; do sleep 30; done
[ -f $WSG ] || $A/venvf36/bin/python scratchpad/gauntlet/L74/weekend/graft_generic.py $WS $U250 $WSG >> $O/graft_ws.log 2>&1
[ -f $WSG ] || { log "graft failed"; exit 5; }
sha256sum $WS $WSG >> $O/ckpts.sha
for SPEC in ws_greedy:$WSG:greedy ws_sample:$WSG:sample ab_sample:$AB:sample; do
  IFS=: read n ck md <<< "$SPEC"
  MODE=; [ $md = sample ] && MODE=sample
  for S in 741200 742000; do
    [ -e $O/${n}_$S/D3/matches.jsonl ] && continue
    rm -rf $O/${n}_$S; log "$n $S mode=$md"
    OVERPRESS_AB_MODE=$MODE bash scratchpad/gauntlet/L74/cue_ab/hide_run.sh flock /workspace/cpu.lock $A/venvf36/bin/python $P/gap_off.py \
      --ckpt $ck --out $O/${n}_$S --arms D3 --seed-start $S --runtime fork36-linux --python $P/pyout.sh --iw-press live \
      --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers 26 --extra="$EXTRA" > $O/${n}_$S.log 2>&1 \
      || log "GAP EXIT $? $n $S"
  done
done
touch $O/ALL_DONE2; log ALL_DONE2
