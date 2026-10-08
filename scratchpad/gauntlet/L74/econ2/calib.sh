#!/bin/bash
# L74 econ2 Q3: SIM opponent calibration arms. Isolated ~/econ2/repo = ~/loss_review/repo49 pipeline (main 049772e + econ_sim_patch.py)
# + LR_OPP_TAU env (opponent gate threshold; default TAU_OPP .27 = unchanged). Learner = live checkpoint towerref_w2 (41b52a83) + the
# deployed LIVE_OPTIONS decision flags (--iw-press-pstar is live-only), decide every 10 (= sim49 de10). CPU, nice; never ~/ClashBot.
# usage: ARM=name SEEDS=0:120 [OPP_T=.3] [OPP_TAU=.27] [OPP_GEN=path] [OPP_POLICY=sample] [CENSUS=evo,lad] bash calib.sh
cd ${REPO:-~/econ2/repo}
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/econ2/sim; W=${WORKERS:-16}; LOG=$O/sim.log; mkdir -p $O
CK=/home/clashbot-gauntlet/probe_rocket/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
OPP_GEN=${OPP_GEN:-icebow/data/pipeline/gen_v1_s0/gen_s0.pt}
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot)
export LR_DECIDE_EVERY=10 LR_OPP_TAU=${OPP_TAU:-0.27}
for s in ${CENSUS:-evo lad}; do d=$EVO; [ $s = lad ] && d=$LAD
  nice -n 10 $PY -m pipeline.search_s0 --out $O/${ARM}_$s --seeds ${SEEDS:-0:120} --opps gen --arms plain --gen $CK --opp-gen $OPP_GEN \
    --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
    --ability-policy v2 --behaviour-telemetry --opp-policy ${OPP_POLICY:-sample} --opp-T ${OPP_T:-0.3} "${LV[@]}" > $O/${ARM}_$s.log 2>&1
  echo "$ARM $s rc=$? T=${OPP_T:-0.3} tau=$LR_OPP_TAU gen=$OPP_GEN pol=${OPP_POLICY:-sample} $(date +%T)" >> $LOG
done
