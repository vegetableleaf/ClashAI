#!/bin/bash
# O0 tower-level natural experiment (L74/opp_model/OPP_MODEL.md section 6). One pod = one config: T = our tower level (15 | 16).
# CLX grafted (5d212358) vs E4 T .1 (gap.py D3 default), live-mirrored pool, fin13-linux, the stepd promotion EXTRA + sampled
# ability head (= CLX's live decode), opponents from the 13k level table; ONLY the pod-local table's own.tower differs.
#   setsid nohup bash /workspace/o0/o0_run.sh 15 > /dev/null 2>&1 < /dev/null &
set -uo pipefail
T=$1; CB=/workspace/o0/cb; O=/workspace/o0/out_t$T; P13=/workspace/venvf13/bin/python
CK=icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt
EV_EXTRA="--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays --ability-stats --ability-head-decode=sample"
mkdir -p $O; exec >> $O/run.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit' EXIT
cd $CB || exit 2
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
sha256sum $CK scratchpad/gauntlet/L74/levels/live_levels.json > $O/inputs.sha
log "start T=$T pid $$ EXTRA $EV_EXTRA"
for S in 741200 742000 743000 744000; do
  D=$O/o0_t${T}_$S
  [ "$(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)" = 480 ] && continue
  rm -rf $D; log "eval T=$T $S"
  ROYALE_RUNTIME=fin13-linux flock /workspace/cpu.lock $P13 scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $D --arms D3 \
    --seed-start $S --runtime fin13-linux --python $P13 --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json \
    --workers ${WORKERS:-26} --extra="$EV_EXTRA" > $D.log 2>&1 || log "GAP EXIT $? $S"
  log "rows $S: $(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)"
done
cd /workspace/o0 && tar czf o0_t$T.tgz.part out_t$T && mv o0_t$T.tgz.part o0_t$T.tgz && sha256sum o0_t$T.tgz > o0_t$T.tgz.sha
touch $O/ALL_DONE; log ALL_DONE
