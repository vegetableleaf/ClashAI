#!/bin/bash
# fork3_run.sh RUN CPUS N_ACTORS ARM [extra rl_royale overrides...] -- P3-FORK3 audit runs on pod 32657 (from /workspace/cf3).
# ARM: base = the cfaud3 pilot league (CLXIII copies + w14opp_I + externals); ftR / oplcB = every matchup vs that human-like
# opponent (league_exploiters share 1.0, the live training census, T 1 = its imitation temperature as calib_eval.sh;
# opp_style off: a timing-head seat refuses the drawn style knobs, e1_eval.timing_cfg).
# Engine: crforge 5e8089a4 (plain lib, facade c003fc74 compiled to build_5e), tables 16.402.22. The policy never steps
# (critic_warmup_updates = max_updates). Triggers: the Rocket family + the two P6 macros (rocket_cycle runs to the match end,
# its 600 / 900-tick values come from the horizon sweep). Returns at once (guarded.sh); log logs/RUN.log, dump logs/RUN.jsonl.
set -e
RUN=$1; CPUS=$2; NA=$3; ARM=$4; shift 4
case $ARM in
  base) OPP=() ;;
  ftR) OPP=("league_exploiters=[{ckpt: /workspace/cf3/opp/opp_ft_s0_R_sim.pt, decks: scratchpad/gauntlet/L74/mix/decks_live_train.json, share: 1.0, T: 1.0}]" opp_style=off) ;;
  oplcB) OPP=("league_exploiters=[{ckpt: /workspace/cf3/opp/oplc_ftR_l003_a10_u0120.pt, decks: scratchpad/gauntlet/L74/mix/decks_live_train.json, share: 1.0, T: 1.0}]" opp_style=off) ;;
  *) echo "bad ARM $ARM"; exit 1 ;;
esac
DEFP="{rocket_cycle: 1.0, def_xbow: 0.3, rocket: 0.006, rocket_played: 1.0, rocket_tornado: 0.5, tornado_redirect: 0.004, wincon: 0.0, siege: 0.0, xbow_after_fail: 0.05, xbow: 0.0, idle_full: 0.0, log_bait: 0.0, random: 0.0}"
CFP=${CFP:-$DEFP}
cd /workspace/cf3
CRFORGE_LIB=/workspace/crforge_main/5e8089a4/plain/lib CRFORGE_FACADE_BUILD=/workspace/cf3/build_5e \
CF_DUMP=/workspace/cf3/logs/$RUN.jsonl TREE=${TREE:-/workspace/cf3/cfh9} GUARD_GB=${GUARD_GB:-100} \
./guarded.sh crforge $RUN $CPUS --config scratchpad/gauntlet/L74/plan1026/cf/cf_pilot_clxiii.yaml \
  max_updates=${MAXU:-5} critic_warmup_updates=${MAXU:-5} n_actors=$NA E=32 G=4 screen_every=1000 proagree_every=1000 \
  learner_device=cuda ability_bc_matches=64 screen_entries=8 "screen_seeds=[0]" cf_diag=true cf_diag_plays=true \
  cf_rocket_empty=true cf_max_alts=4 "cf_horizon_sweep=[150,300,450,600,750,900,1200]" cf_horizon_ticks=900 cf_audit_p=0.3 \
  cf_cap_ticks=60000 "cf_horizon_by={rocket_cycle: 7000}" "cf_p=$CFP" \
  "${OPP[@]}" "$@"
