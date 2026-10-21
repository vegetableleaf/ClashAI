#!/bin/bash
# W14 final check of a picked opponent snapshot (pod-local; OPP_MODEL.md section 8):
#   bash /workspace/w14/confirm.sh TAG SNAPSHOT_PATH   (SNAPSHOT_PATH absolute, under cb_stepd)
# 1. installs it as cb_stepd/icebow/data/pipeline/o2/w14opp.pt (+ the eval copy), sha-checked;
# 2. O4-Ranked fresh blocks 742000 / 743000 / 744000 (1,440 games; block 741200 already exists from the gates);
# 3. block 741200 again with O3_POS=1 (positions + trace for the pocket / X-Bow cells);
# 4. the league config smoke: a real rl_royale --smoke of cfg/tn_base_w14opp_s74.yaml (fin15, venvf15).
set -uo pipefail
TAG=$1; SRC=$2; CB=/workspace/cb_stepd; E=/workspace/o3w12/cb
CLX=icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt
export O3B=/workspace/o3w12 EVLOCK=/workspace/w14/eval.lock
L=/workspace/w14/confirm_$TAG.log; log() { echo "$(date -u +%FT%TZ) $*" >> $L; }
want=$(sha256sum < $SRC)
for d in $CB $E; do cp $SRC $d/icebow/data/pipeline/o2/w14opp.pt.tmp && mv $d/icebow/data/pipeline/o2/w14opp.pt.tmp $d/icebow/data/pipeline/o2/w14opp.pt
  [ "$(sha256sum < $d/icebow/data/pipeline/o2/w14opp.pt)" = "$want" ] || { log "INSTALL SHA FAIL $d"; exit 3; }; done
log "installed $TAG sha $(echo $want | cut -c1-16)"
bash /workspace/w14/opp_eval_fin15.sh w14c_${TAG} $CLX icebow/data/pipeline/o2/w14opp.pt 0.1 40 - 742000 743000 744000; log "fresh blocks done"
O3_POS=1 bash /workspace/w14/opp_eval_fin15.sh w14c_${TAG}_pos $CLX icebow/data/pipeline/o2/w14opp.pt 0.1 40 - 741200; log "pos block done"
RUN=tn_base_w14opp_s74 OUTD=/workspace/w14 VENV=/workspace/venvf15 RT=fin15-linux TLOCK=/workspace/w14/smoke.lock SMOKE_ONLY=1 \
  bash /workspace/w14/w7_train.sh; log "smoke: $(tail -1 /workspace/w14/tn_base_w14opp_s74/chain.log)"
log ALL_DONE
