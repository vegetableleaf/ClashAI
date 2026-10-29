#!/bin/bash
# P2-OPP2: fine-tune ft_s0 -> _sim.pt (live Ranked: band 6, mode 1, era 2) -> level A on live_cal -> smoke -> level B ftR (4 x 480)
set -euo pipefail
cd /workspace/opp/cb; export PYTHONPATH=/workspace/opp/cb PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=0
PY=/workspace/venvf16/bin/python; O=/workspace/opp/cb/scratchpad/gauntlet/L74/plan1026/opp; F=/workspace/opp/live/ft_s0
$PY $O/attach_sim.py --ckpt $F/opp_ft_s0.pt --data /workspace/opp/live/mix_train --out $F/opp_ft_s0_R_sim.pt --band 6 --mode 1 --era 2
$PY $O/level_a.py --ckpt $F/opp_ft_s0.pt --data /workspace/opp/live/live_cal --memory-tables /workspace/opp/live/live_cal_memory.npz --split 2 --bs 256 --out $F/level_a_live_cal.json > $F/level_a_live_cal.log 2>&1
rm -rf /workspace/opp/smoke/ftR
CB=/workspace/opp/cb LIB=/workspace/crforge_main/fe364ceb/plain FAC=/workspace/opp/fac_cb DIAG=1 bash $O/pod_smoke.sh $F/opp_ft_s0_R_sim.pt /workspace/opp/smoke/ftR 741200,741201,741202,741203 1.0 > /workspace/opp/logs/smoke_ftR.log 2>&1
grep -q "\"rc\": 0, \"rows\": 4" /workspace/opp/logs/smoke_ftR.log
cd /workspace/opp/score && CB=/workspace/opp/cb LIB=/workspace/crforge_main/fe364ceb/plain OPP_CKPT=$F/opp_ft_s0_R_sim.pt OPP_T=1.0 WORKERS=40 G2_ON=on bash /workspace/opp/cb/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh ftR /workspace/opp/score/rows/ftR 741200 742000 742800 743600 >> /workspace/opp/score/ftR.out 2>&1
