#!/bin/bash
# Pod 2 (L74 CAL re-run): the D5,D6 half of S9XL2b, with the CAL pick.  Waits for CAL/PICK.env (copied by the laptop relay) WITHOUT holding
# a lock, then queues behind S11 on cpu.lock.   cd /workspace/wk_xl2 && setsid nohup bash <this file> > /workspace/results/wk/xl2b_pod2.out 2>&1 &
R=/workspace/results/wk
mkdir -p $R/S9XL2b
while [ ! -s $R/CAL/PICK.env ]; do sleep 30; done
set -a; . $R/CAL/PICK.env; set +a
export XL2_SUFFIX=b XL2_PART=.pod2 XL2_DRILLS=D5,D6 XL2_WORKERS=13
exec flock /workspace/cpu.lock bash scratchpad/gauntlet/L74/weekend/wk_driver.sh __run S9XL2 > $R/S9XL2b/stage.log 2>&1
