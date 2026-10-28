#!/bin/bash
# LOOP-SRV mix sweep, one config per process; resumable (a config whose json exists is skipped).
#   cd /workspace/loopsrv && nohup bash sweep.sh > sweep.log 2>&1 &
cd /workspace/loopsrv || exit 1
PY=/workspace/venvf15/bin/python
for run in "graphs 256x16 7 fp32" "graphs 256x32 7 fp32" "graphs 512x24 7 fp32" "graphs 512x40 7 fp32" \
           "graphs 256x32 7 tf32" "graphs 512x24 7 tf32" "eager 256x32 7 fp32" "eager 512x24 7 fp32" \
           "graphs 256x32 0 fp32" "graphs 512x24 0 fp32"; do
  set -- $run
  out=mix_$1_$2_f$3_$4.json
  [ -f "$out" ] && continue
  OMP_NUM_THREADS=2 timeout 900 $PY srv_bench.py --part mix --mode $1 --configs $2 --forced-every $3 --precision $4 \
    --out "$out" > "${out%.json}.log" 2>&1 || echo "FAILED $run"
  grep '^{' "${out%.json}.log" | cut -c1-300
done
echo SWEEP_DONE
