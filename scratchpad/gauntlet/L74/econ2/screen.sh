#!/bin/bash
# Q3 screening: 240 matches per arm (seeds 0:120 x evo + lad), two chains of 16 workers. Baseline = sim49 de10 seeds < 120.
cd ~/econ2/econ2
V32=icebow/data/pipeline/gen_v32_s0/gen_s0.pt
( ARM=c_T15 OPP_T=0.15 bash calib.sh; ARM=c_T60 OPP_T=0.6 bash calib.sh; ARM=c_T100 OPP_T=1.0 bash calib.sh; ARM=c_live OPP_POLICY=live bash calib.sh ) &
( ARM=c_tau20 OPP_TAU=0.20 bash calib.sh; ARM=c_tau35 OPP_TAU=0.35 bash calib.sh; ARM=c_v32 OPP_GEN=$V32 bash calib.sh; ARM=c_v32T60 OPP_GEN=$V32 OPP_T=0.6 bash calib.sh ) &
wait
echo SCREEN_DONE >> ~/econ2/sim/sim.log
