#!/bin/bash
# OPP-LEARN-C pod smokes (33903 CPUs 200-203): base = HEAD c5383b3 pipeline, new = + OPP-LEARN-C patch.
S=scratchpad/gauntlet/L74/plan1026/opp/learner/pod_smoke.sh
B=/workspace/opplearnc/cbc_base; N=/workspace/opplearnc/cbc
bash $N/$S $N oplc_bot1 scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_bot_smoke.yaml
bash $B/$S $B oplc_base1 scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml
bash $N/$S $N oplc_new1 scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml
echo CHAIN_DONE > /workspace/opplearn/logs/chainc.done
