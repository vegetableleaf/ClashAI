#!/bin/bash
# L74 CAL (owner 2026-10-11): calibrate harder sim opponents against live.  Pod 1, from /workspace/wk_xl2:
#   setsid nohup flock /workspace/cpu.lock bash scratchpad/gauntlet/L74/weekend/cal_run.sh > /workspace/results/wk/CAL/cal.out 2>&1 &
# Per opponent set: OLD and E4 as the learner, search_s0 plain arm with the S2 benchmark's live flags (run_eval.sh / live_flags.sh LV_LIVE),
# evo census seeds 30000:30240 + lad census 30240:30480.  Resumable (a finished run dir is skipped).  Writes SUMMARY.txt, PICK.env, DONE.
set -u
R=/workspace/results/wk; C=$R/CAL; EV=$C/ev; mkdir -p "$EV"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PY=${PY:-/workspace/venv/bin/python}
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN=$PWD
W=${CAL_WORKERS:-28}; N=${CAL_N:-240}
CKR=icebow/data/bench/rl_royale
OLD=$CKR/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
E4=$CKR/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt
GEN=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
S1=icebow/data/pipeline/s1_icebow_v6aug_s1.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot_behind
    --xbow-dead-lane block --gate-hazard-threatened 2 --rocket-dead-target block --tau-threatened 0.2 --lethal-log on)
log() { echo "$(date '+%F %T') $*" | tee -a "$C/cal.log"; }
finish() {
  rc=$?
  [ -s "$C/PICK.env" ] || echo "FAILED: CAL ended before the pick (rc=$rc); see cal.log. No PICK.env: the re-run waits for the owner. VERDICT: no pick" >> "$C/SUMMARY.txt"
  touch "$C/DONE"
}
trap finish EXIT
: > "$C/sets.tsv"

# run_one SET ROLE(old|e4) CENSUS(evo|lad) OPPS OPP_GEN T DECKS
run_one() {
  local out="$EV/$1_$2_$3" ck=$OLD s0 s1 d=$7
  [ "$2" = e4 ] && ck=$E4
  [ -s "$out/summary.json" ] && return 0
  rm -rf "$out"
  s0=30000; [ "$3" = lad ] && s0=$((30000 + N))
  log "run $1 $2 $3 (opps $4 $5 T $6)"
  $PY -m pipeline.search_s0 --out "$out" --seeds $s0:$((s0 + N)) --opps "$4" --arms plain --gen "$ck" --opp-gen "$5" --forms-mode deck \
    --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census "$d" --hero-abilities --ability-policy v2 --behaviour-telemetry \
    --opp-policy sample --opp-T "$6" "${LV[@]}" > "$out.log" 2>&1
  rc=$?
  [ $rc -eq 0 ] && [ -s "$out/summary.json" ] || { log "FAILED $1 $2 $3 rc=$rc"; exit 1; }
}
# run_set NAME OPPS OPP_GEN T DECKS_LABEL ELIGIBLE EVO_FILE LAD_FILE
run_set() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" >> "$C/sets.tsv"
  for c in evo lad; do
    d=$7; [ $c = lad ] && d=$8
    for role in old e4; do run_one "$1" $role $c "$2" "$3" "$4" "$d"; done
  done
}

run_set a gen $GEN 0.3 census 1 $EVO $LAD                      # reference: the S2 benchmark opponent
run_set b gen $OLD 0.1 census 1 $EVO $LAD                      # OLD as the opponent, near-greedy
run_set c gen $E4 0.1 census 1 $EVO $LAD                       # E4 as the opponent, near-greedy
run_set d s1 $GEN 0.1 "icebow mirror" 0 $EVO $LAD              # S1 specialist plays the icebow deck: mirror, reported but not eligible
bc=$($PY "$HERE/cal_summary.py" bestbc "$EV" "$C/sets.tsv") || exit 1
log "best of b/c: $bc"
bgen=$OLD; [ "$bc" = c ] && bgen=$E4
$PY "$HERE/mk_weighted_decks.py" scratchpad/gauntlet/L70/pool_forms/loadable_decks.json "$C/census_evo.json" 0.5 0.5 > "$C/census_evo.txt"
$PY "$HERE/mk_weighted_decks.py" scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json "$C/census_lad.json" 0.5 0.5 > "$C/census_lad.txt"
run_set e gen $bgen 0.1 "weighted(b/$bc)" 1 "$C/census_evo.json" "$C/census_lad.json"   # e = the better of b/c on the S9 archetype-weighted decks
$PY "$HERE/cal_summary.py" final "$EV" "$C/sets.tsv" "$C/SUMMARY.txt" "$C/PICK.env" > "$C/final.out" 2>&1 || exit 1
log "done: $(grep '^PICK' "$C/SUMMARY.txt")"
