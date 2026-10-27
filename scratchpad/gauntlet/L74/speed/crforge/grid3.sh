#!/usr/bin/env bash
# S3: the Java observation builder inside the core grid, rerun after the firstSeen fix (ids start at 5,000,000; the
# first obs runs of grid2 ran out of heap at 768 matches). Waits for phase2.sh. Run: nohup ./grid3.sh <pid> > runs/grid3.log 2>&1 &
set -uo pipefail
cd /workspace/cfspeed
while kill -0 "$1" 2>/dev/null; do sleep 5; done
B=./bench.sh
#        label          K  T  envs warm target  de p   obs xmx
$B o_1x48_obs         1 48  768  60 12000  10 0.3 1 8g
$B o_12x4_obs        12  4   64  60  1000  10 0.3 1 1500m
$B o_12x4            12  4   64  60  1000  10 0.3 0 1500m
$B o_1x1_obs          1  1   16  60   400  10 0.3 1 1g
$B o_1x1              1  1   16  60   400  10 0.3 0 1g
echo GRID3_DONE
