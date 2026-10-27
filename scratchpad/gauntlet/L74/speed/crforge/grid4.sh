#!/usr/bin/env bash
# S3: the loop's memory (peak RSS, Java heap in use) at 2 x 4,096 and 2 x 2,048 matches in flight; waits for grid3.sh.
set -uo pipefail
cd /workspace/cfspeed
while kill -0 "$1" 2>/dev/null; do sleep 5; done
P=/workspace/venvf15/bin/python
$P -I cf_loop.py --envs 4096 --cohorts 2 --threads 24 --warm 60 --seconds 60 --out runs/loopmem_n4096_c2_t24.json
$P -I cf_loop.py --envs 2048 --cohorts 2 --threads 24 --warm 60 --seconds 60 --out runs/loopmem_n2048_c2_t24.json
echo GRID4_DONE
