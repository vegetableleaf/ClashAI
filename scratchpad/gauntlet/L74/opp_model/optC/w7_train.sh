#!/bin/bash
# W7 option C arm (L74/opp_model/OPP_MODEL.md section 7) on P1: the real rl_royale smoke of the arm's yaml, then training,
# both under /workspace/cpu.lock (one CPU job at a time on this host). Pod-local; checkpoints every save_every updates in
# cb_stepd/icebow/data/bench/rl_royale/rlarm_<RUN>/, train log cb_stepd/scratchpad/gauntlet/L68/rl/rlarm_<RUN>/train_log.jsonl.
#   RUN=oppC1_icemix_s74 setsid nohup bash /workspace/w7/w7_train.sh > /dev/null 2>&1 < /dev/null &
# SMOKE_ONLY=1: stop after the smoke. A rerun resumes from _latest.pt. SMOKE_EXTRA="k=v ...": extra smoke overrides
# (W7 R4: outlived_pp=100 -- the smoke's forced 8-entry held-out screen tripped that guard by chance; the real run has no screen).
set -uo pipefail
RUNN=${RUN:?RUN=<yaml name under L74/opp_model/cfg>}; CB=/workspace/cb_stepd; O=/workspace/w7/$RUNN; PY=/workspace/venvf13/bin/python
# RUNNAME=<an earlier arm> (W7 R4): train under that arm's run name, i.e. --resume it with THIS yaml (a logged config change)
Y=scratchpad/gauntlet/L74/opp_model/cfg/$RUNN.yaml; R=rlarm_${RUNNAME:-$RUNN}
mkdir -p $O; exec >> $O/chain.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit; touch $O/DONE' EXIT
cd $CB || exit 2
unset ROYALE_HEROIW_PRESS                      # the yaml's heroiw_press sets it for the trainer
export PYTHONPATH=$CB ROYALE_RUNTIME=fin13-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
grep -q '^live_levels: all16$' $Y || { log "not all16: $Y"; exit 2; }
sha256sum $Y pipeline/rl_royale.py $(sed -n 's/^init: //p' $Y) $(sed -n 's/^- \(icebow.*\.pt\)$/\1/p' $Y) > $O/inputs.sha || exit 2
rm -f $O/DONE
if [ ! -f $O/SMOKE_OK ]; then
  log "smoke $RUNN (waiting for cpu.lock)"
  flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $Y --run smoke_$RUNN --smoke critic_warmup_updates=1 ${SMOKE_EXTRA:-} > $O/smoke.log 2>&1
  grep -q 'SMOKE PASS' $O/smoke.log || { log "SMOKE FAIL (see smoke.log)"; exit 3; }
  touch $O/SMOKE_OK; log "SMOKE PASS"
fi
[ -n "${SMOKE_ONLY:-}" ] && exit 0
RES=; [ -f icebow/data/bench/rl_royale/$R/${R}_latest.pt ] && RES=--resume
log "train $R $RES (waiting for cpu.lock)"
flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $Y --run $R $RES >> $O/train.log 2>&1 || log "TRAIN EXIT $?"
log "train done"
