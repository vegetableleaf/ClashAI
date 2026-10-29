#!/bin/bash
# d3_one.sh NAME CKPT_ON_33903 -- one 480-game D3 block on 33903 on the live tables 16.635.3 (same settings as arm_d3.sh)
N=$1; CK=$2
ssh -o BatchMode=yes -o ConnectTimeout=30 -i ~/.ssh/runpod_clashbot root@157.157.221.29 -p 33903 "cd /workspace/oplm/d3 && CB=/workspace/opp/cb PY=/workspace/venvf16/bin/python CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 G2_ON=on OPP_T=1.0 WORKERS=30 CPUS=0-179 OPP_CKPT=$CK bash /workspace/opp/cb/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh $N /workspace/oplm/d3/rows/$N 741200 > $N.out 2>&1; F=rows/$N/${N}_741200/D3/matches.jsonl; echo \"\$(date -u +%FT%TZ) $N [16.635.3] CLXIII W \$(grep -c '\"outcome\": \"win\"' \$F) / \$(grep -c outcome \$F)\""
