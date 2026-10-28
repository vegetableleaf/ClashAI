#!/usr/bin/env bash
# Re-run run_live.sh while logs still arrive; when all 1,678 train logs (logs/) and 868 calibration logs (logs_cal/) are on
# disk, one more wave (retries any log that was mid-copy) + the final npz step.   bash loop_until_copied.sh
set -u
D=$(dirname "$0"); V1=/workspace/v1live
ntrain() { ls $V1/logs | awk 'substr($0,11,15) < "20261025_000000"' | wc -l; }
while [ "$(ntrain)" -lt 1678 ] || [ "$(ls $V1/logs_cal | wc -l)" -lt 868 ]; do
  bash $D/run_live.sh 24 12; sleep 120
done
sleep 30
bash $D/run_live.sh 24 12
bash $D/run_live.sh 24 12 final
echo LOOP_DONE
