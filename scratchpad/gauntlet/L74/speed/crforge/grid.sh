#!/usr/bin/env bash
# S3 step 1 grid (pod 32657, 48 of the 54 vCPU; ticket S2's 2 GPU trainers hold about 2.5 cores): JVMs x threads at 48
# threads in all, then single-JVM scaling, a GC variant and the Java observation builder. Steady state: 60 s warm-up per
# JVM, then the target matches. 16 envs per thread: every step ends at a barrier, and at 2 envs per thread the 1 x 48
# JVM ran at about 16.6 cores of 48 (top, 10-27 10:53; that run was stopped).
# Run: nohup ./grid.sh > runs/grid.log 2>&1 &
set -uo pipefail
cd /workspace/cfspeed
B=./bench.sh
#        label          K  T  envs warm target  de p   obs xmx
$B g_1x48             1 48  768  60 12000  10 0.3 0 8g
$B g_2x24             2 24  384  60  6000  10 0.3 0 5g
$B g_4x12             4 12  192  60  3000  10 0.3 0 3g
$B g_12x4            12  4   64  60  1000  10 0.3 0 1500m
$B g_48x1            48  1   16  60   250  10 0.3 0 768m
$B g_1x8              1  8  128  60  2400  10 0.3 0 2g
$B g_1x24             1 24  384  60  7000  10 0.3 0 5g
$B g_1x48_e2          1 48   96  60  6000  10 0.3 0 8g
$B g_1x48_pargc       1 48  768  60 12000  10 0.3 0 8g -XX:+UseParallelGC
$B g_12x4_pargc      12  4   64  60  1000  10 0.3 0 1500m -XX:+UseParallelGC
$B g_1x48_obs         1 48  768  60 12000  10 0.3 1 8g
$B g_12x4_obs        12  4   64  60  1000  10 0.3 1 1500m
$B g_1x1_obs          1  1   16  60   400  10 0.3 1 1g
$B g_1x1              1  1   16  60   400  10 0.3 0 1g
echo GRID_DONE
