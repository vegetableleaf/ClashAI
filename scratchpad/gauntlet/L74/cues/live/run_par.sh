#!/bin/bash
# run_par.sh (pod dir /workspace/w_cue = this dir + cb/ = HEAD pipeline + the parity harness; logs.txt = log names): cue-feature parity, 4 processes, nice 10, royalesim 0.1.35 (the training runtime), the parity team's seeds
cd /workspace/w_cue
export CB=/workspace/w_cue/cb PYTHONPATH=/workspace/w_cue/cb PARITY_SIM_PATH=/workspace/rs0.1.35 PARITY_ATTACKS=/workspace/in/attacks6.json PARITY_BUFFS=/workspace/in/buffs6.json OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
mkdir -p out
cat logs.txt | xargs -P 4 -I{} sh -c 'nice -n 10 python3 pcollect.py /workspace/caplogs6/{} out > out/{}.log 2>&1'
touch out/DONE
