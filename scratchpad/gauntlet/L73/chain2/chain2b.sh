#!/bin/bash
# L73 chain2b (lead 2026-10-07 ~09:00): owner stopped R1f at u0105 (last saved) ("let's stop r1f now"); acceptance of the saved
# u0080 / u0090 vs R1e on engine 20261006 (same evaluate/pair as chain2, baselines reused). Then tau .45 vs .35 on the
# better one (by reactive total, tie -> ghost delta). Deploy bar (owner 10-06 night): reactive >= R1e + 3 of 96 AND
# ghost ci_hi >= 0 AND a behaviour gap moves toward pros.
cd /c/Users/benpe/ClashBot
O=scratchpad/gauntlet/L73/chain2; LOG=$O/chain2.log
PY=research/ext/Royale/.venv/Scripts/python.exe; IPY=icebow/.venv/Scripts/python.exe
RS=scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py
OLD=scratchpad/gauntlet/L68/generalist/lat26/screens/train_C.jsonl; EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json
GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt; CKB=icebow/data/bench/rl_royale/rseries_r1f32
log() { echo "[c2b] $* $(date '+%F %T')" >> $LOG; }
ci() { grep -E '"delta_pp"|"ci_lo_pp"|"ci_hi_pp"' $1 | tr -d ' \n'; }
cihi() { grep -E '"ci_hi_pp"' $1 | grep -oE '[-0-9.]+' | tail -1; }
dpp() { grep -E '"delta_pp"' $1 | grep -oE '[-0-9.]+' | tail -1; }
nwin() { grep -cE "plain +$2 +seed [0-9]+ win" $1; }
total() { echo $(( $(nwin $O/react_$1.log gen) + $(nwin $O/react_$1.log s1) + $(nwin $O/reactevo_$1.log gen) + $(nwin $O/reactevo_$1.log s1) )); }
sim() { env ROYALE_RUNTIME=20261006 "PYTHONPATH=C:/Users/benpe/ClashBot/research/ext/Royale-20261006/runtime;C:/Users/benpe/ClashBot" "$@"; }
evaluate() {  # name ckpt [tau]
  t=${3:-0.35}
  sim $PY $RS --ckpt $2 --out $O/screen_$1.jsonl --split train --noise-off all --opp-elixir counter --action-delay 26 --extrapolate 26 \
      --seeds 0 --device cuda --forms-mode deck --tau $t --only-tags-from $OLD --behaviour-telemetry > $O/screen_$1.out 2>&1 || log "screen $1 FAILED"
  sim $PY -m pipeline.search_s0 --out $O/react_$1 --seeds 0:24 --opps gen,s1 --arms plain --gen $2 --opp-gen $GEN1 --forms-mode deck \
      --device cuda --workers 3 --tail-cap 7200 --tau-plain $t > $O/react_$1.log 2>&1
  sim $PY -m pipeline.search_s0 --out $O/reactevo_$1 --seeds 0:24 --opps gen,s1 --arms plain --gen $2 --opp-gen $GEN1 --forms-mode deck \
      --device cuda --workers 3 --tail-cap 7200 --tau-plain $t --census $EVO --hero-abilities --ability-policy v2 > $O/reactevo_$1.log 2>&1
  log "eval $1 (tau $t): reactive gen $(nwin $O/react_$1.log gen)/24 s1 $(nwin $O/react_$1.log s1)/24 evo gen $(nwin $O/reactevo_$1.log gen)/24 s1 $(nwin $O/reactevo_$1.log s1)/24 total $(total $1)/96"
}
pair() { sim $PY $RS --pair $O/screen_$2.jsonl $O/screen_$1.jsonl > $O/pair_$1_vs_$2.out 2>&1; log "ghost $1 vs $2 $(ci $O/pair_$1_vs_$2.out)"; }
log "start (R1f stopped by owner at u0105 (last saved); testing u0080, u0105)"
for u in 0080 0105; do evaluate r1f_u$u $CKB/rseries_r1f32_u$u.pt; pair r1f_u$u r1e; pair r1f_u$u v32
  log "R1f u$u vs R1e: ghost ci_hi $(cihi $O/pair_r1f_u${u}_vs_r1e.out), reactive $(total r1f_u$u) vs $(total r1e)"; done
B=0080; if [ $(total r1f_u0105) -gt $(total r1f_u0080) ] || { [ $(total r1f_u0105) -eq $(total r1f_u0080) ] && \
  [ "$(awk -v a="$(dpp $O/pair_r1f_u0105_vs_r1e.out)" -v b="$(dpp $O/pair_r1f_u0080_vs_r1e.out)" 'BEGIN{print (a>b)}')" = 1 ]; }; then B=0105; fi
log "best R1f checkpoint u$B"
evaluate r1f_t45 $CKB/rseries_r1f32_u$B.pt 0.45; pair r1f_t45 r1f_u$B
log "TAU .45 vs .35 on R1f u$B: reactive $(total r1f_t45) vs $(total r1f_u$B)"
printf '%s\n' "ClashAI chain2b (R1f stopped at u0105 (last saved)): $(grep -E '\[c2b\] (eval|ghost|R1f u|best|TAU)' $LOG | sed 's/ 2026-10-[0-9]* [0-9:]*$//' | tr '\n' ' ' | cut -c1-1800)" > $O/_msg2b.txt
$IPY scratchpad/gauntlet/L69/discord/post.py $O/_msg2b.txt >> $LOG 2>&1
log "CHAIN2B_DONE"
