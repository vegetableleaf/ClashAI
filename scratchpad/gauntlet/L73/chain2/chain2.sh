#!/bin/bash
# L73 chain2 (lead, PRE-REGISTERED 2026-10-06 21:5x, before any result): after gen_v3.2 trains ->
#   1 frozen barrel branch on gen_v3.2 (L73/barrel_branch) -> 2 barrel counterfactual v32 vs v32b
#   3 fresh baselines ALL on engine 20261006 (ROYALE_RUNTIME=20261006): R1e u0155 (live), gen_v3.1c, gen_v3.2, gen_v3.2+branch;
#     each = ghost screen (tau .35, 299 pinned replays) + reactive gen_v1/S1 x 24 seeds on old census AND evo census (96 games)
#   4 RULES (fixed now):
#     identity: continue with gen_v3.2 unless CLEARLY worse than gen_v3.1c = ghost ci_hi < 0 AND reactive total < v31c - 3
#     branch:   use v32b as RL base iff val Log lane = barrel target >= 90% of val rows AND val flips >= 80% of val rows
#               AND ghost v32b vs v32 ci_hi >= 0 AND reactive total >= v32 - 3; else base = v32
#   5 RL R1f = R1e recipe (155 updates, 5 actors, GAE tick, evo census + v2 abilities) from the base, engine 20261006
#   6 acceptance u0080/u0155: ghost vs R1e (same engine) + 96 reactive; tau .45 vs .35 on R1f u0155 (rule from L73 Exp 1:
#     adopt .45 iff reactive +>=3 of 96 AND ghost ci_hi >= 0 AND elixir-at-play up)
#   Deploy decision is the lead's, by these rules: R1f ckpt deploys iff ghost vs R1e ci_hi >= 0 AND reactive total >= R1e - 3.
cd /c/Users/benpe/ClashBot
O=scratchpad/gauntlet/L73/chain2; LOG=$O/chain2.log
PY=research/ext/Royale/.venv/Scripts/python.exe; IPY=icebow/.venv/Scripts/python.exe
RS=scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py
OLD=scratchpad/gauntlet/L68/generalist/lat26/screens/train_C.jsonl; EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json
GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt; DATA=icebow/data/pipeline/gen_dataset_v32_fv5.npz
R1E=icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt; V31C=icebow/data/pipeline/gen_v31c_s0/gen_s0.pt
V32=icebow/data/pipeline/gen_v32_s0/gen_s0.pt; V32B=scratchpad/gauntlet/L73/barrel_branch/v32/gen_branch_s0.pt
log() { echo "[c2] $* $(date '+%F %T')" >> $LOG; }
ci() { grep -E '"delta_pp"|"ci_lo_pp"|"ci_hi_pp"' $1 | tr -d ' \n'; }
cihi() { grep -E '"ci_hi_pp"' $1 | grep -oE '[-0-9.]+' | tail -1; }
nwin() { grep -cE "plain +$2 +seed [0-9]+ win" $1; }
total() { echo $(( $(nwin $O/react_$1.log gen) + $(nwin $O/react_$1.log s1) + $(nwin $O/reactevo_$1.log gen) + $(nwin $O/reactevo_$1.log s1) )); }
sim() { env ROYALE_RUNTIME=20261006 "PYTHONPATH=C:/Users/benpe/ClashBot/research/ext/Royale-20261006/runtime;C:/Users/benpe/ClashBot" "$@"; }
evaluate() {  # name ckpt
  sim $PY $RS --ckpt $2 --out $O/screen_$1.jsonl --split train --noise-off all --opp-elixir counter --action-delay 26 --extrapolate 26 \
      --seeds 0 --device cuda --forms-mode deck --tau 0.35 --only-tags-from $OLD --behaviour-telemetry > $O/screen_$1.out 2>&1 || log "screen $1 FAILED"
  sim $PY -m pipeline.search_s0 --out $O/react_$1 --seeds 0:24 --opps gen,s1 --arms plain --gen $2 --opp-gen $GEN1 --forms-mode deck \
      --device cuda --workers 3 --tail-cap 7200 > $O/react_$1.log 2>&1
  sim $PY -m pipeline.search_s0 --out $O/reactevo_$1 --seeds 0:24 --opps gen,s1 --arms plain --gen $2 --opp-gen $GEN1 --forms-mode deck \
      --device cuda --workers 3 --tail-cap 7200 --census $EVO --hero-abilities --ability-policy v2 > $O/reactevo_$1.log 2>&1
  log "eval $1: reactive gen $(nwin $O/react_$1.log gen)/24 s1 $(nwin $O/react_$1.log s1)/24 evo gen $(nwin $O/reactevo_$1.log gen)/24 s1 $(nwin $O/reactevo_$1.log s1)/24 total $(total $1)/96"
}
pair() { sim $PY $RS --pair $O/screen_$2.jsonl $O/screen_$1.jsonl > $O/pair_$1_vs_$2.out 2>&1; log "ghost $1 vs $2 $(ci $O/pair_$1_vs_$2.out)"; }

until grep -q "\[v32\] train exit" scratchpad/gauntlet/L73/gen_v32/chain.log; do sleep 60; done
grep -q "\[v32\] train exit 0" scratchpad/gauntlet/L73/gen_v32/chain.log || { log "gen_v3.2 TRAIN FAILED -- stop"; exit 1; }
[ -f $V32 ] || { log "gen_v3.2 checkpoint missing -- stop"; exit 1; }
log "start; base checkpoint $V32"

# 1-2 barrel branch + counterfactual (icebow venv, no engine)
env -u ROYALE_RUNTIME PYTHONPATH=. $IPY -u scratchpad/gauntlet/L73/barrel_branch/train_branch.py --base $V32 --data $DATA \
    --out-dir scratchpad/gauntlet/L73/barrel_branch/v32 --device cuda > $O/branch.out 2>&1; log "branch exit $?"
env -u ROYALE_RUNTIME CUDA_VISIBLE_DEVICES=-1 PYTHONPATH=. $IPY scratchpad/gauntlet/L73/barrel_lane/model_counterfactual.py --data $DATA \
    --out model_counterfactual_v32.json --ckpt v32=$V32 --ckpt v32b=$V32B > $O/counterfactual.out 2>&1
log "counterfactual $(grep -E '^v32b? ' $O/counterfactual.out | sed -E 's/.*"val_only": (\{[^}]*\}).*/\1/' | tr '\n' ' ')"

# 3 baselines + candidates on engine 20261006
for n in r1e:$R1E v31c:$V31C v32:$V32; do evaluate ${n%%:*} ${n#*:}; done
[ -f $V32B ] && evaluate v32b $V32B
pair v32 v31c; pair v32 r1e; [ -f $V32B ] && pair v32b v32

# 4 rules
if [ "$(awk -v h="$(cihi $O/pair_v32_vs_v31c.out)" 'BEGIN{print (h<0)}')" = 1 ] && [ $(total v32) -lt $(( $(total v31c) - 3 )) ]; then
  log "IDENTITY RULE: gen_v3.2 CLEARLY WORSE than gen_v3.1c -- stop for the lead"; exit 2; fi
BASE=$V32
if [ -f $V32B ]; then
  ok=$(icebow/.venv/Scripts/python.exe - <<'PY'
import json; d=json.load(open('scratchpad/gauntlet/L73/barrel_lane/model_counterfactual_v32.json'))['v32b']['val_only']
print(int(d['A_log_lane_eq_target'] >= .9*d['rows'] and d['flips_when_barrel_mirrored'] >= .8*d['rows']))
PY
)
  hi=$(cihi $O/pair_v32b_vs_v32.out)
  if [ "$ok" = 1 ] && [ "$(awk -v h="$hi" 'BEGIN{print (h>=0)}')" = 1 ] && [ $(total v32b) -ge $(( $(total v32) - 3 )) ]; then BASE=$V32B; fi
fi
log "BRANCH RULE -> RL base $BASE (counterfactual ok=$ok, ghost ci_hi=$hi, reactive v32b $(total v32b) vs v32 $(total v32))"

# 5 RL
CFG=scratchpad/gauntlet/L69/rl/r1_rl_royale.yaml
OVR="init=$BASE proagree_data_gen=$DATA league=true noise_off=all opp_elixir=counter action_delay_ticks=26 extrapolate_ticks=26 max_updates=155 screen_seeds=[0] league_learner_icebow_share=1.0 forms_mode=deck league_decks=$EVO advantage=gae gae_gamma_unit=tick critic_warmup_updates=5 hero_abilities=true ability_policy=v2 n_actors=5"
log "R1f start"
sim $PY -m pipeline.rl_royale --config $CFG --run rseries_r1f32 $OVR > $O/r1f.out 2> $O/r1f.err
rc=$?; log "R1f exited $rc"
[ "$rc" -ne 0 ] && { log "RL FAILED -- acceptance not run"; exit $rc; }

# 6 acceptance on the same engine
CKB=icebow/data/bench/rl_royale/rseries_r1f32
for u in 0080 0155; do
  ck=$CKB/rseries_r1f32_u$u.pt; [ -f $ck ] || { log "u$u missing"; continue; }
  evaluate r1f_u$u $ck; pair r1f_u$u r1e
  log "R1f u$u vs R1e: ghost ci_hi $(cihi $O/pair_r1f_u${u}_vs_r1e.out), reactive $(total r1f_u$u) vs $(total r1e)"
done
ck=$CKB/rseries_r1f32_u0155.pt
if [ -f $ck ]; then
  sim $PY $RS --ckpt $ck --out $O/screen_r1f_t45.jsonl --split train --noise-off all --opp-elixir counter --action-delay 26 --extrapolate 26 \
      --seeds 0 --device cuda --forms-mode deck --tau 0.45 --only-tags-from $OLD --behaviour-telemetry > $O/screen_r1f_t45.out 2>&1
  sim $PY -m pipeline.search_s0 --out $O/react_r1f_t45 --seeds 0:24 --opps gen,s1 --arms plain --gen $ck --opp-gen $GEN1 --forms-mode deck \
      --device cuda --workers 3 --tail-cap 7200 --tau-plain 0.45 > $O/react_r1f_t45.log 2>&1
  sim $PY -m pipeline.search_s0 --out $O/reactevo_r1f_t45 --seeds 0:24 --opps gen,s1 --arms plain --gen $ck --opp-gen $GEN1 --forms-mode deck \
      --device cuda --workers 3 --tail-cap 7200 --tau-plain 0.45 --census $EVO --hero-abilities --ability-policy v2 > $O/reactevo_r1f_t45.log 2>&1
  pair r1f_t45 r1f_u0155
  log "TAU .45 vs .35 on R1f u0155: reactive $(total r1f_t45) vs $(total r1f_u0155)"
fi
printf '%s\n' "ClashAI chain2 done (engine 20261006): $(grep -E 'eval |ghost |RULE|R1f u|TAU' $LOG | sed 's/ 2026-10-[0-9]* [0-9:]*$//' | tr '\n' ' ' | cut -c1-1800)" > $O/_msg.txt
$IPY scratchpad/gauntlet/L69/discord/post.py $O/_msg.txt >> $LOG 2>&1
log "CHAIN2_DONE"
