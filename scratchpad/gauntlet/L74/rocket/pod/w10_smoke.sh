#!/bin/bash
# W10 pod side: an ISOLATED hard-link copy /workspace/w10/cb of /workspace/cb_stepd with the shipped rocket_tower files as NEW
# files (never the linked originals; cb_stepd untouched), the unit tests, then the REAL rl_royale smoke of
# stepd_l16_rocket_s74.yaml on fin13-linux under /workspace/cpu.lock. Output /workspace/w10/{tests.log,smoke.log,RESULT}.
#   setsid nohup bash /workspace/w10/ship/w10_smoke.sh > /dev/null 2>&1 < /dev/null &
# RUNTIME=fin15-linux PY=/workspace/venvf15/bin/python: the same on fin15 (tonight's base may switch).
set -uo pipefail
B=/workspace/w10; SH=$B/ship; CB=$B/cb; PY=${PY:-/workspace/venvf13/bin/python}; RT=${RUNTIME:-fin13-linux}
exec >> $B/run.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
cd $SH && sha256sum -c SHA256 || { log "ship sha mismatch"; echo SHA_FAIL > $B/RESULT; exit 2; }
rm -rf $CB && cp -al /workspace/cb_stepd $CB || exit 2
for f in reward_terms.py rl_royale.py e1_eval.py; do rm -f $CB/pipeline/$f; cp $SH/$f $CB/pipeline/$f; done
rm -f $CB/pipeline/tests/test_rocket_tower_1020.py; cp $SH/test_rocket_tower_1020.py $CB/pipeline/tests/
Y=scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_rocket_s74.yaml; rm -f $CB/$Y; cp $SH/stepd_l16_rocket_s74.yaml $CB/$Y
cd $CB || exit 2
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
log "commit $(cat $SH/COMMIT) runtime $RT tests"
$PY -m pytest -q -p no:cacheprovider pipeline/tests/test_rocket_tower_1020.py > $B/tests.log 2>&1; log "tests exit $? ($(tail -1 $B/tests.log))"
log "smoke (waiting for cpu.lock)"
flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $Y --run smoke_w10_rocket --smoke critic_warmup_updates=1 ${SMOKE_EXTRA:-} > $B/smoke.log 2>&1
if grep -q 'SMOKE PASS' $B/smoke.log; then echo SMOKE_PASS > $B/RESULT; log "SMOKE PASS"
else echo SMOKE_FAIL > $B/RESULT; log "SMOKE FAIL (see smoke.log)"; fi
grep -o '"rocket_reward_per_match": [0-9.e-]*\|"rocket_princess_dmg_per_match": [0-9.e-]*' $B/smoke.log | tail -4 >> $B/run.log
