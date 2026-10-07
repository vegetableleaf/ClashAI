#!/bin/bash
# L73 R2 = R1f recipe (chain2.sh step 5, engine 20261006) + two BUNDLED changes (owner accepts the confound):
#   (A) train as the bot plays live: tau 0.27 -> 0.35, T 0.5 -> 0.3. ONE knob each: actor_cfg (rl_royale.py ~135) feeds
#       the learner's sampler AND the frozen league opponents ({**actor_cfg(base, "rollout"), policy: league_opp_policy},
#       ~1150; e1_eval.sample_decide_batch reads c["tau"], c["T"]); the PPO loss / KL ref / monitors use the same cfg.
#   (B) ladder-matched opponent decks: loadable_decks_ladder.json (build_ladder.py; sides = target weight, alpha 1 floor 0),
#       icebow mirror cut to ~4.4% (league_icebow_share 0.02, league_mix s1 0.02).
# Acceptance after training (chain2b evaluate/pair): u0080, u0120 vs R1e u0155 -- ghost screen tau .35 (regression guard)
# + reactive 48 seeds (gen,s1 opps) on the evo census AND the ladder file. R1e reactive is re-run at 48 seeds (chain2
# ran 0:24); R1e's ghost screen is reused from chain2 (same engine, tau .35, same flags).
# Does NOT start until scratchpad/gauntlet/L73/rl_r2/GO exists (the lead creates it after the shaping decision + GPU check).
cd /c/Users/benpe/ClashBot
O=scratchpad/gauntlet/L73/rl_r2; LOG=$O/r2.log; C2=scratchpad/gauntlet/L73/chain2
PY=research/ext/Royale/.venv/Scripts/python.exe; IPY=icebow/.venv/Scripts/python.exe
RS=scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py
OLD=scratchpad/gauntlet/L68/generalist/lat26/screens/train_C.jsonl; EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json
LAD=$O/loadable_decks_ladder.json
GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt; DATA=icebow/data/pipeline/gen_dataset_v32_fv5.npz
V32=icebow/data/pipeline/gen_v32_s0/gen_s0.pt
R1E=icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt
RUN=rseries_r2l; CKB=icebow/data/bench/rl_royale/$RUN
log() { echo "[r2] $* $(date '+%F %T')" >> $LOG; }
ci() { grep -E '"delta_pp"|"ci_lo_pp"|"ci_hi_pp"' $1 | tr -d ' \n'; }
cihi() { grep -E '"ci_hi_pp"' $1 | grep -oE '[-0-9.]+' | tail -1; }
nwin() { grep -cE "plain +$2 +seed [0-9]+ win" $1; }
tot() { echo $(( $(nwin $O/react${2}_$1.log gen) + $(nwin $O/react${2}_$1.log s1) )); }   # name, ""=evo census | "lad"
sim() { env ROYALE_RUNTIME=20261006 "PYTHONPATH=C:/Users/benpe/ClashBot/research/ext/Royale-20261006/runtime;C:/Users/benpe/ClashBot" "$@"; }
react() {  # name ckpt suffix census
  sim $PY -m pipeline.search_s0 --out $O/react$3_$1 --seeds 0:48 --opps gen,s1 --arms plain --gen $2 --opp-gen $GEN1 --forms-mode deck \
      --device cuda --workers 3 --tail-cap 7200 --tau-plain 0.35 --census $4 --hero-abilities --ability-policy v2 > $O/react$3_$1.log 2>&1
}
evaluate() {  # name ckpt [skip-screen]
  [ -n "$3" ] || sim $PY $RS --ckpt $2 --out $O/screen_$1.jsonl --split train --noise-off all --opp-elixir counter --action-delay 26 \
      --extrapolate 26 --seeds 0 --device cuda --forms-mode deck --tau 0.35 --only-tags-from $OLD --behaviour-telemetry \
      > $O/screen_$1.out 2>&1 || log "screen $1 FAILED"
  react $1 $2 "" $EVO; react $1 $2 lad $LAD
  log "eval $1 (tau .35, 48 seeds): census gen $(nwin $O/react_$1.log gen)/48 s1 $(nwin $O/react_$1.log s1)/48 = $(tot $1)/96;" \
      "ladder gen $(nwin $O/reactlad_$1.log gen)/48 s1 $(nwin $O/reactlad_$1.log s1)/48 = $(tot $1 lad)/96"
}
pair() { sim $PY $RS --pair $2 $O/screen_$1.jsonl > $O/pair_$1_vs_r1e.out 2>&1; log "ghost $1 vs r1e $(ci $O/pair_$1_vs_r1e.out)"; }

until [ -f $O/GO ]; do sleep 60; done
log "GO found; start"
[ -f $LAD ] || { log "ladder deck file missing -- stop"; exit 1; }

# RL R2. Overrides as an ARRAY: league_mix must reach yaml.safe_load as ONE argv WITH spaces after the colons
# ("{latest:0.35}" parses as a key 'latest:0.35' with a null value; validate_league then refuses it).
CFG=scratchpad/gauntlet/L69/rl/r1_rl_royale.yaml
OVR=(init=$V32 proagree_data_gen=$DATA league=true noise_off=all opp_elixir=counter action_delay_ticks=26 extrapolate_ticks=26
     max_updates=120 "screen_seeds=[0]" league_learner_icebow_share=1.0 forms_mode=deck advantage=gae gae_gamma_unit=tick
     critic_warmup_updates=5 hero_abilities=true ability_policy=v2 n_actors=5
     tau=0.35 T=0.3 league_decks=$LAD league_deck_alpha=1.0 league_deck_floor=0 league_icebow_share=0.02
     "league_mix={latest: 0.35, older: 0.25, init: 0.2, s1: 0.02}")
log "R2 start: ${OVR[*]}"
sim $PY -m pipeline.rl_royale --config $CFG --run $RUN "${OVR[@]}" > $O/r2.out 2> $O/r2.err
rc=$?; log "R2 exited $rc"
[ "$rc" -ne 0 ] && { log "RL FAILED -- acceptance not run"; exit $rc; }

# acceptance (same engine). R1e baseline at 48 seeds on both deck files; its ghost screen from chain2.
evaluate r1e $R1E skip
for u in 0080 0120; do
  ck=$CKB/${RUN}_u$u.pt; [ -f $ck ] || { log "u$u missing"; continue; }
  evaluate r2_u$u $ck; pair r2_u$u $C2/screen_r1e.jsonl
  log "R2 u$u vs R1e: ghost ci_hi $(cihi $O/pair_r2_u${u}_vs_r1e.out); reactive census $(tot r2_u$u)/96 vs $(tot r1e)/96," \
      "ladder $(tot r2_u$u lad)/96 vs $(tot r1e lad)/96"
done
printf '%s\n' "ClashAI R2 done (tau .35 T .3 + ladder decks, engine 20261006): $(grep -E '\[r2\] (eval|ghost|R2 u|R2 exited)' $LOG | sed 's/ 2026-10-[0-9]* [0-9:]*$//' | tr '\n' ' ' | cut -c1-1800)" > $O/_msg.txt
$IPY scratchpad/gauntlet/L69/discord/post.py $O/_msg.txt >> $LOG 2>&1
log "R2_DONE"
