#!/bin/bash
# Pod 30988: start D1 (d1_data_pod.sh) once the CPUs are free AND the fin13 runtime is ready.
#   free  = Codex's SIM re-eval finished (/workspace/codex1018/results/ALL_DONE, DONE or FAILED) and no gap.py / livecal
#           worker is left (the eval holds /workspace/cpu.lock per seed set; D1 then takes the lock for its whole run)
#   ready = /workspace/stepd/fin13/FIN13_OK (-> RT fin13-linux, venvf13); its FAILED marker -> fork36-linux, venvf36 (logged)
# No pod stop, no watchdog, no deadline.
set -uo pipefail
O=/workspace/stepd; F=$O/fin13; C=/workspace/codex1018/results
log() { echo "[d1w] $* $(date -u +%FT%TZ)" >> $O/d1_waiter.log; }
log "waiting (pid $$)"
until { [ -e $C/ALL_DONE ] || [ -e $C/DONE ] || [ -e $C/FAILED ]; } && ! pgrep -f "livecal/livecal[.]py|gap/gap[.]py" > /dev/null; do sleep 60; done
log "cpus free"
until [ -e $F/FIN13_OK ] || [ -e $F/FAILED ]; do sleep 30; done
if [ -e $F/FIN13_OK ]; then RT=fin13-linux; PY=/workspace/venvf13/bin/python; else RT=fork36-linux; PY=/workspace/venvf36/bin/python; log "fin13 FAILED: D1 on fork36-linux"; fi
log "D1 start RT=$RT"
cd /workspace/cb_stepd
RT=$RT PY=$PY WORKERS=${WORKERS:-22} flock /workspace/cpu.lock bash $O/bin/d1_data_pod.sh > $O/d1_launch.out 2>&1
log "D1 exit $?"
