#!/bin/bash
# SPEED2 (2) plan: producer RSS vs matches in flight (16 / 64 / 128) and over waves, forwards on serve.py graphs (the
# box's path), -Xmx 16g (producer.py's default) vs 2g.
MSG=/workspace/speed2/msg_warm.pkl
M=16 J=16 EXTRA="--waves 3 --serve graphs" bash /workspace/speed2/memsweep.sh $MSG s16 16g
M=64 J=64 EXTRA="--waves 2 --serve graphs" bash /workspace/speed2/memsweep.sh $MSG s64 16g 2g
M=128 J=128 EXTRA="--waves 1 --serve graphs" bash /workspace/speed2/memsweep.sh $MSG s128 16g 2g
touch /workspace/speed2/out/mem/PLAN_DONE
