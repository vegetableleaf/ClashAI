#!/bin/bash
# L73 Exp 1 (lead 2026-10-06): play-threshold (gate tau) calibration on R1e u0155, inference only, current engine.
# Pre-registered: arms tau 0.35 (live baseline) / 0.45 / 0.54 (pro-rate match on val rows). Adopt for a LIVE A/B iff
# ghost paired delta vs 0.35 >= 0, reactive total (96 games) not lower by > 3, 2x/OT elixir-at-play +0.5, Rocket share up.
cd /c/Users/benpe/ClashBot; G=scratchpad/gauntlet/L73/econ_tau; LOG=$G/chain.log
PY=research/ext/Royale/.venv/Scripts/python.exe; RS=scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py
OLD=scratchpad/gauntlet/L68/generalist/lat26/screens/train_C.jsonl; EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json
CK=icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
export PYTHONPATH=.
log() { echo "[tau] $* $(date '+%F %T')" >> $LOG; }
wins() { echo "gen $(grep -cE 'plain +gen +seed [0-9]+ win' $1)/24 s1 $(grep -cE 'plain +s1 +seed [0-9]+ win' $1)/24"; }
for T in 0.35 0.45 0.54; do
  $PY $RS --ckpt $CK --out $G/screen_t$T.jsonl --split train --noise-off all --opp-elixir counter --action-delay 26 --extrapolate 26 \
      --seeds 0 --device cuda --forms-mode deck --tau $T --only-tags-from $OLD --behaviour-telemetry > $G/screen_t$T.out 2>&1 || log "screen $T FAILED"
  [ "$T" != "0.35" ] && { $PY $RS --pair $G/screen_t0.35.jsonl $G/screen_t$T.jsonl > $G/pair_t$T.out 2>&1; log "ghost tau $T vs 0.35 $(grep -E '"delta_pp"|"ci_lo_pp"|"ci_hi_pp"' $G/pair_t$T.out | tr -d ' \n')"; }
  $PY -m pipeline.search_s0 --out $G/react_t$T --seeds 0:24 --opps gen,s1 --arms plain --gen $CK --opp-gen $GEN1 --forms-mode deck \
      --device cuda --workers 3 --tail-cap 7200 --tau-plain $T > $G/react_t$T.log 2>&1; log "reactive tau $T $(wins $G/react_t$T.log)"
  $PY -m pipeline.search_s0 --out $G/reactevo_t$T --seeds 0:24 --opps gen,s1 --arms plain --gen $CK --opp-gen $GEN1 --forms-mode deck \
      --device cuda --workers 3 --tail-cap 7200 --tau-plain $T --census $EVO --hero-abilities --ability-policy v2 > $G/reactevo_t$T.log 2>&1; log "reactive evo tau $T $(wins $G/reactevo_t$T.log)"
done
log "DONE"
