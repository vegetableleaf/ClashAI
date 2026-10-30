#!/bin/bash
# SPEED2 (2) plan 2: the JVM's core-scaled memory (G1 / JIT thread counts follow the VISIBLE CPUs: 8 under my taskset, 120+
# on 33308 / the box) and a low-footprint JVM. 16 and 64 matches, forwards on serve.py graphs, 2 waves.
MSG=/workspace/speed2/msg_warm.pkl
M=16 J=16 EXTRA="--waves 2 --serve graphs" bash /workspace/speed2/memsweep.sh $MSG s16apc160 16g:-XX:ActiveProcessorCount=160
M=64 J=64 EXTRA="--waves 2 --serve graphs" bash /workspace/speed2/memsweep.sh $MSG s64apc160 16g:-XX:ActiveProcessorCount=160
M=16 J=16 EXTRA="--waves 2 --serve graphs" bash /workspace/speed2/memsweep.sh $MSG s16low 400m:"-XX:+UseSerialGC -XX:ActiveProcessorCount=4"
M=64 J=64 EXTRA="--waves 2 --serve graphs" bash /workspace/speed2/memsweep.sh $MSG s64low 700m:"-XX:+UseSerialGC -XX:ActiveProcessorCount=4"
touch /workspace/speed2/out/mem/PLAN2_DONE
