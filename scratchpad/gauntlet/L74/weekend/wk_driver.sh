#!/bin/bash
# L74 weekend chain, pod side.  nohup bash wk_driver.sh [STAGE ...] > /workspace/results/wk/driver.out 2>&1 &     (default: all stages in order)
# Every stage runs under `flock /workspace/cpu.lock` (training stages: `flock /workspace/gpu.lock flock /workspace/cpu.lock`), writes
# $R/<stage>/SUMMARY.txt (a few numbers + a VERDICT line) and touches $R/<stage>/DONE whether it succeeded or failed.  CHAIN_DONE at the end.
# Layout on the pod: WK = branch l74-weekend (forks, drills, trainer), DEF = rl-defence-e3 (E4 arm + eval harness), OC = DEF + own-cycle merge.
# Nothing here touches live; icebow/data and research/ext are symlinks to /workspace/clashbot's copies.
R=/workspace/results/wk; EV=$R/evals
WK=/workspace/wk; DEF=/workspace/wt_def; OC=/workspace/wt_oc
W=$WK/scratchpad/gauntlet/L74/weekend; RLD=$DEF/scratchpad/gauntlet/L74/rl_defence
PY=/workspace/venv/bin/python
export ROYALE_RUNTIME=20261006-linux
CKR=icebow/data/bench/rl_royale
CK_OLD=$CKR/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
CK_NEW=$CKR/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt
CK_BASE=$CKR/rseries_r3c/rseries_r3c_u0030_barrel.pt
ALL="S2 S4 S3 S8 S7 S9 S10 S5 S6"
TRAIN=" S5 S6 S10 "
say() { echo "$@" >> $D/SUMMARY.txt; }

evenv() { export REPO=$1 PY ROYALE_RUNTIME OUT=$R/_evout EVAL_DIR=$EV EVAL_FLAGS=live NICE= CORES=28 GPU=0 EVAL_WORKERS=14; mkdir -p $EV; }
trenv() { export REPO=$1 PY ROYALE_RUNTIME OUT=$R/_trout EVAL_DIR=$EV EVAL_FLAGS=live NICE= CORES=28 GPU=1 ACTORS=$2 ACTOR_THREADS=1 OMP=$3 EVAL_WORKERS=14; mkdir -p $EV; }
# ev NAME CKPT SEEDS : one 960-game-style eval (evo + lad) with the E4 evals' live flags, in $REPO's harness; skipped if already complete (names get _lv)
ev() {
  [ -s $EV/${1}_lv_lad/summary.json ] && [ -s $EV/${1}_lv_evo/summary.json ] && return 0
  rm -rf $EV/${1}_lv_evo $EV/${1}_lv_lad
  (cd $REPO && bash $RL_OF/run_eval.sh $1 $2 $3)
}
RL_OF=$RLD
cmp() { $PY $W/wk_compare.py $EV "$@"; }
decks_rl() { [ -s $R/decks_rl.json ] || $PY $W/mk_weighted_decks.py $RLD/decks_runover.json $R/decks_rl.json 1.0 0 > $R/decks_rl.txt; }

# ---------------------------------------------------------------------------------------------------- S2
st_S2() {  # current live (E4 graft) vs old live, 960 paired, live flags
  evenv $DEF; RL_OF=$RLD
  ev live_old $CK_OLD 0:480; ev live_new $CK_NEW 0:480
  say "S2 SIM benchmark: current live (E4 u20 + add-ons) vs old live (towerref_w2); search_s0 paired 960 (evo + lad x 480), live flags, gen v1 opp T .3"
  cmp live_old_lv live_new_lv s2 >> $D/SUMMARY.txt
}
# ---------------------------------------------------------------------------------------------------- S3
st_S3() {  # prevent vs delay
  cd $WK; mkdir -p $D
  for c in evo lad; do MECH_GAP=100 bash $W/run_wk.sh prevent $D/$c 0:240 28 $c 2 $CK_NEW > $D/$c.log 2>&1; done
  $PY $W/wk_stats.py s3 $D/evo,$D/lad $D/SUMMARY.txt
}
# ---------------------------------------------------------------------------------------------------- S4
st_S4() {
  cd $W; $PY s4_elixir_split.py /workspace/wk_in/full_rocket_tower_evo_0_240,/workspace/wk_in/full_rocket_tower_lad_0_240 $D/SUMMARY.txt
}
# ---------------------------------------------------------------------------------------------------- S5
st_S5() {  # defence E5: E4's arm, seeds 7 8 9
  trenv $DEF 9 2; RL_OF=$RLD; decks_rl; cd $DEF
  ev r3cb $CK_BASE 0:480
  say "S5 defence E5 = E4's arm (branch_actors 18, outcome_towers, match-end) from the fast base, 30 updates, seeds 7 8 9; opponent decks weighted toward the unfavourable archetypes ($(head -1 $R/decks_rl.txt))"
  say "actors 9 + 18 branch workers (28 processes; E4 used 16 actors), the batch per update is fixed so only wall time differs"
  both=""
  for sd in 7 8 9; do
    run=wk_e5_s$sd; ck=$CKR/$run/${run}_u0020.pt
    SEED=$sd bash $RLD/arm_e4.sh $run max_updates=30 league_decks=$R/decks_rl.json > $D/$run.out 2>&1
    [ -f $DEF/$ck ] || { say "seed $sd: no u20 checkpoint (training failed, see $run.out)"; continue; }
    ev ${run}_u20 $ck 0:480
    say "seed $sd first half (0:480): $(cmp r3cb_lv ${run}_u20_lv | head -1)"
    if cmp r3cb_lv ${run}_u20_lv pos | grep -q '^VERDICT: positive'; then
      ev r3cb_h2 $CK_BASE 480:960; ev ${run}_u20_h2 $ck 480:960
      say "seed $sd second half (480:960): $(cmp r3cb_h2_lv ${run}_u20_h2_lv | head -1)"
      if cmp r3cb_h2_lv ${run}_u20_h2_lv pos | grep -q '^VERDICT: positive'; then
        $PY $W/graft_generic.py $DEF/$ck $DEF/$CK_OLD $DEF/$CKR/$run/${run}_u0020_g.pt
        ev ${run}_u20g $CKR/$run/${run}_u0020_g.pt 0:480
        say "seed $sd BOTH halves beat base; grafted add-ons vs current live (960):"
        cmp live_new_lv ${run}_u20g_lv >> $D/SUMMARY.txt
        both="$both $sd"
      fi
    fi
  done
  say "OT P(Rocket) compare: not run on the pod (needs the laptop's live logs); run scratchpad/gauntlet/L74/deploy/ot_rocket_compare.py on the grafted checkpoints"
  say "VERDICT: seeds that beat base on both halves: ${both:-none}"
}
# ---------------------------------------------------------------------------------------------------- S6
st_S6() {  # own-cycle by reward
  trenv $OC 20 4; RL_OF=$OC/scratchpad/gauntlet/L74/rl_defence; decks_rl; cd $OC
  $PY $W/mk_owncycle_init.py $CK_BASE $CKR/wk_oc/wk_oc_init.pt || { say "VERDICT: own-cycle init failed"; return; }
  for arm in ctl cyc; do
    b=$CK_BASE; [ $arm = cyc ] && b=$CKR/wk_oc/wk_oc_init.pt
    SEED=6 BASE=$b bash $RL_OF/run_arm.sh wk_oc_$arm max_updates=30 league_decks=$R/decks_rl.json > $D/$arm.out 2>&1
    ck=$CKR/wk_oc_$arm/wk_oc_${arm}_u0030.pt
    [ -f $OC/$ck ] || { say "$arm: no u30 checkpoint (see $arm.out)"; continue; }
    $PY $W/graft_generic.py $OC/$ck $OC/$CK_OLD $OC/$CKR/wk_oc_$arm/wk_oc_${arm}_g.pt
  done
  evenv $OC
  ev live_old $CK_OLD 0:480
  for arm in ctl cyc; do [ -f $OC/$CKR/wk_oc_$arm/wk_oc_${arm}_g.pt ] && ev wk_oc_${arm}_g $CKR/wk_oc_$arm/wk_oc_${arm}_g.pt 0:480; done
  say "S6 own-cycle by reward: RL 30 updates from the fast base, seed 6, dense-defence recipe (run_arm.sh, no branching), archetype-weighted decks; add-ons grafted; eval 960 vs old live"
  for arm in ctl cyc; do say "$arm vs old live: $(cmp live_old_lv wk_oc_${arm}_g_lv | head -1)"; done
  cmp wk_oc_ctl_g_lv wk_oc_cyc_g_lv s6 >> $D/SUMMARY.txt
}
# ---------------------------------------------------------------------------------------------------- S7
st_S7() {  # engine royalesim 0.1.25
  V=/workspace/venv25
  rm -rf $V; python3 -m venv $V && $V/bin/pip install -q royalesim==0.1.25 royalegym 2>&1 | tail -2
  echo /workspace/venv/lib/python3.12/site-packages > $V/lib/python3.12/site-packages/base.pth
  say "S7 engine: $($V/bin/pip list 2>/dev/null | grep -i -E '^royale' | tr '\n' ' ')(venv25 = new wheels first on the path, torch/numpy from the main venv)"
  mkdir -p /workspace/sd25; cd /workspace/sd25
  $V/bin/pip download -q --no-binary :all: --no-deps royalegym==0.1.22 -d . 2>&1 | tail -1; tar xzf royalegym-0.1.22.tar.gz
  (cd royalegym-0.1.22 && timeout 1500 $V/bin/python -m pytest -q -x tests 2>&1 | tail -5) > $D/royalegym_tests.txt 2>&1
  say "royalegym 0.1.22 own tests (sdist tests/, -x): $(tail -1 $D/royalegym_tests.txt); royalesim's tests are Rust (cargo), no toolchain on the pod: not run"
  evenv $DEF; RL_OF=$RLD
  ev live_old $CK_OLD 0:480                    # the 0.1.17 / 20261006 reference (skipped when S2 already ran it)
  cp $WK/pipeline/royale_runtime.py $DEF/pipeline/royale_runtime.py
  PY=$V/bin/python; export PY ROYALE_RUNTIME=unpinned-linux
  ev live_old_e25 $CK_OLD 0:480
  (cd $DEF && git checkout -- pipeline/royale_runtime.py)
  PY=/workspace/venv/bin/python; export PY ROYALE_RUNTIME=20261006-linux
  cmp live_old_lv live_old_e25_lv unpaired >> $D/SUMMARY.txt
  say "VERDICT: engine shift reported above (old live, 960, unpaired; reference = the 0.1.17 / 20261006 run in the same harness)"
}
# ---------------------------------------------------------------------------------------------------- S8
st_S8() {  # Log Bait baseline
  cd $WK; mkdir -p $D
  for c in evo lad; do bash $W/run_wk.sh logbait $D/$c 0:240 28 $c 0 $CK_OLD > $D/$c.log 2>&1; done
  $PY $W/logbait_summary.py $D/evo,$D/lad $D/SUMMARY.txt
}
# ---------------------------------------------------------------------------------------------------- S9 / S10
s9_run() {  # s9_run CKPT OUTDIR SEEDS_EVO SEEDS_LAD : pass 1 (state dump) -> moments -> pass 2 (forks), on archetype-weighted census decks
  ck=$1; O=$2; cd $WK; mkdir -p $O
  $PY $W/mk_weighted_decks.py scratchpad/gauntlet/L70/pool_forms/loadable_decks.json $O/census_evo.json 0.5 0.5 > $O/census_evo.txt
  $PY $W/mk_weighted_decks.py scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json $O/census_lad.json 0.5 0.5 > $O/census_lad.txt
  i=0
  for c in evo lad; do
    s=$3; [ $c = lad ] && s=$4
    mkdir -p $O/dump_$c
    CENSUS_FILE=$O/census_$c.json DUMP_DIR=$O/dump_$c bash $W/run_wk.sh dump $O/p1_$c $s 28 $c 0 $ck > $O/p1_$c.log 2>&1
    CB_MAIN=$WK $PY $W/moments_from_dump.py $O/dump_$c/ $O/moments_$c.json 3 200 150 > $O/moments_$c.txt 2>&1
    CENSUS_FILE=$O/census_$c.json MECH_GAP=100 ROWS_DIR=$O/rows_$c MOMENTS=$O/moments_$c.json bash $W/run_wk.sh drills $O/p2_$c $s 28 $c 2 $ck > $O/p2_$c.log 2>&1
    rm -rf $O/dump_$c
  done
}
st_S9() {
  s9_run $CK_NEW $D 1000:1300 1300:1600
  $PY $W/wk_stats.py s9 $D/p2_evo,$D/p2_lad $D/SUMMARY.txt $D/verdicts.json
  say "opponent decks: ~60% unfavourable archetypes (golem, lava hound, royal giant +/- monk, pekka bridge, hyperbait) via archetype-weighted census; seeds 1000:1600 (disjoint from S2's 0:480)"
}
st_S10() {
  V=$R/S9/verdicts.json
  if ! grep -q -E '"(do|alt)"' $V 2>/dev/null; then say "VERDICT: skipped: no S9 drill has a verdict with CI excluding 0 (or S9 failed)"; return; fi
  trenv $DEF 9 2; evenv $DEF; RL_OF=$RLD; cd $WK
  OUTC=$CKR/wk_s10/wk_s10.pt; mkdir -p $(dirname $WK/$OUTC)
  $PY $W/train_drills.py --ckpt $CK_NEW --rows $R/S9/rows_evo,$R/S9/rows_lad --matches $R/S9/p2_evo,$R/S9/p2_lad --verdicts $V --out $WK/$OUTC --epochs 3 --max-min 60 > $D/train.out 2>&1 \
    || { say "VERDICT: training did not run: $(tail -1 $D/train.out)"; return; }
  say "train: $(tail -1 $D/train.out)"
  ev live_new $CK_NEW 0:480; ev wk_s10 $WK/$OUTC 0:480
  cmp live_new_lv wk_s10_lv s10 > $D/eval.txt; cat $D/eval.txt >> $D/SUMMARY.txt
  ok=0; grep -q '^VERDICT: non-inferior' $D/eval.txt && ok=1
  s9_run $WK/$OUTC $D/re 3000:3150 3150:3300
  $PY $W/wk_stats.py s10 $R/S9/p2_evo,$R/S9/p2_lad $D/re/p2_evo,$D/re/p2_lad $V $ok "$(head -1 $D/eval.txt)" $D/fork.txt
  cat $D/fork.txt >> $D/SUMMARY.txt
}

# ---------------------------------------------------------------------------------------------------- main
if [ "$1" = __run ]; then D=$R/$2; mkdir -p $D; "st_$2"; exit $?; fi
mkdir -p $R; STAGES=${*:-$ALL}
for s in $STAGES; do
  D=$R/$s; mkdir -p $D; rm -f $D/DONE
  echo "[$(date -u +%T)] start $s" >> $R/driver.log
  if [[ "$TRAIN" == *" $s "* ]]; then
    flock /workspace/gpu.lock flock /workspace/cpu.lock bash $0 __run $s > $D/stage.log 2>&1
  else
    flock /workspace/cpu.lock bash $0 __run $s > $D/stage.log 2>&1
  fi
  rc=$?
  [ -s $D/SUMMARY.txt ] || echo "$s: no summary written (rc $rc); see stage.log" > $D/SUMMARY.txt
  echo "stage rc=$rc" >> $D/SUMMARY.txt
  touch $D/DONE; echo "[$(date -u +%T)] done $s rc=$rc" >> $R/driver.log
done
touch $R/CHAIN_DONE; echo "[$(date -u +%T)] chain done" >> $R/driver.log
