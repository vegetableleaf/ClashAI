#!/bin/bash
# ckpt_eval.sh TAG CKPT -- 10-22 (lead), pod-local on 157.157.221.29:32621: the long run's 100-update checkpoint eval.
# graft (as stepd_chain.sh) -> E4 promotion eval (gap.py D3, the chain's EXTRA, std 741200 742000 + fresh 743000 744000) ->
# the same seeds vs W14's I u40 (opp_eval_fin15.sh, T 0.1, decide 40). Both under /workspace/cpu_b.lock so a training
# chain holding /workspace/cpu.lock is not blocked. Output: /workspace/ckev/out/TAG.tgz + .sha; DONE file at the end.
set -uo pipefail
TAG=$1; CK=$2; CB=/workspace/cb_stepd; P=/workspace/venvf15/bin/python; O=/workspace/ckev/out/$TAG; LK=/workspace/cpu_b.lock
U250=icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt; OPP=$CB/icebow/data/pipeline/o2/w14opp_I.pt
mkdir -p $O; exec >> $O/run.log 2>&1; log() { echo "$(date -u +%FT%TZ) $*"; }
cd $CB || exit 1
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
G=${CK%.pt}_grafted.pt; [ -f $G ] || $P scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $U250 $G >> $O/graft.log 2>&1
[ -f $G ] || { log "graft failed"; exit 5; }; sha256sum $CK $G > $O/ckpt.sha; log "grafted $G"
EV_EXTRA="--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays --ability-stats --ability-head-decode=sample --crown-log"
for S in 741200 742000 743000 744000; do
  D=$O/e4/${TAG}_${S}_fin15; mkdir -p $(dirname $D); log "E4 $S"
  ROYALE_RUNTIME=fin15-linux flock $LK $P scratchpad/gauntlet/L74/gap/gap.py --ckpt $G --out $D --arms D3 --seed-start $S \
    --runtime fin15-linux --python $P --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers ${WORKERS:-26} \
    --extra="$EV_EXTRA" --levels all16 > $D.log 2>&1 || log "GAP EXIT $? $S"
  log "E4 $S rows $(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)"
done
O3B=/workspace/o3w12 EVLOCK=$LK bash /workspace/o3w12/opp_eval_fin15.sh ${TAG}_Iu40 $G $OPP 0.1 40 - 741200 742000 743000 744000
mkdir -p $O/iu40; cp -r /workspace/o3w12/out/${TAG}_Iu40/* $O/iu40/ 2>/dev/null
tar czf /workspace/ckev/out/$TAG.tgz -C /workspace/ckev/out $TAG && (cd /workspace/ckev/out && sha256sum $TAG.tgz > $TAG.tgz.sha)
log "DONE"; touch $O/DONE
