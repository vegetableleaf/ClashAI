#!/bin/bash
# S11: Log Bait specialist (owner 2026-10-10).  Started by s11_gate.sh under `flock gpu.lock flock cpu.lock` after CHAIN_DONE; touches
# $D/DONE and writes $D/SUMMARY.txt whether it succeeded or failed.  Nothing here edits the weekend chain's worktrees.
S=$(cd "$(dirname "$0")" && pwd)          # /workspace/s11 (this folder's copy)
R=/workspace/results/wk; D=$R/S11_bait; EV=$D/evals; mkdir -p $EV
WK=/workspace/wk; DEF=/workspace/wt_def; W=$WK/scratchpad/gauntlet/L74/weekend; RLD=$DEF/scratchpad/gauntlet/L74/rl_defence
PY=/workspace/venv/bin/python; export ROYALE_RUNTIME=20261006-linux
CKR=icebow/data/bench/rl_royale; RUN=wk_bait
BASE=$CKR/rseries_r3c/rseries_r3c_u0030_barrel.pt
GEN=$CKR/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
trap '[ -s $D/SUMMARY.txt ] || echo "S11: no summary written; see $D/stage.log" > $D/SUMMARY.txt; touch $D/DONE' EXIT
rm -f $D/DONE
echo "[$(date -u +%T)] S11 start" >> $D/stage.log

# ---- 1. train: run_arm.sh's command with the Log Bait wrapper (60 updates, save_every 10), archetype-weighted decks
$PY $W/mk_weighted_decks.py $RLD/decks_runover.json $D/decks_rl.json 1.0 0 > $D/decks_rl.txt
cd $DEF
mapfile -t OVR < <(tr -d "\r" < scratchpad/gauntlet/L73/opt3/r3_overrides.txt | grep -v "^\s*#" | grep -v "^\s*$")
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 nice -n 10 $PY $S/bait_base_rl.py \
  --config scratchpad/gauntlet/L69/rl/r1_rl_royale.yaml --run $RUN "${OVR[@]}" \
  init=$BASE shaping=none league_decks=$D/decks_rl.json \
  dense_w_lost=0.5 dense_w_dealt=0.15 dense_w_broke=0.3 dense_w_mat=0.3 \
  shaping_critic_scale=3.5 critic_warmup_updates=3 lr=3.0e-5 seed=11 learner_device=cuda \
  n_actors=20 actor_threads=1 branch_gate=false screen_every=1000 max_updates=60 save_every=10 > $D/train.out 2>&1
echo "[$(date -u +%T)] training rc=$?" >> $D/stage.log

# ---- 2. graft the deck-agnostic add-on heads (graft_generic.py = deploy/graft_heads.py with paths as arguments)
for u in 30 60; do
  ck=$CKR/$RUN/${RUN}_u00$u.pt
  [ -f $DEF/$ck ] && $PY $W/graft_generic.py $DEF/$ck $DEF/$GEN $DEF/$CKR/$RUN/${RUN}_u00${u}_g.pt >> $D/stage.log 2>&1
done

# ---- 3. evals: 480 paired games each (seeds 0:240 on the evo census + 0:240 on the ladder census), learner = Log Bait base forms
bev() {  # bev NAME CKPT(abs)
  for c in evo lad; do
    [ -s $EV/${1}_$c/summary.json ] && continue
    rm -rf $EV/${1}_$c
    case $c in evo) DK=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json ;; lad) DK=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json ;; esac
    (cd $WK && OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN=$WK nice -n 10 $PY $S/bait_base_s0.py --out $EV/${1}_$c --seeds 0:240 --opps gen \
      --arms plain --gen $2 --opp-gen icebow/data/pipeline/gen_v1_s0/gen_s0.pt --forms-mode deck --device cpu --workers 28 --tail-cap 7200 \
      --tau-plain 0.35 --census $DK --hero-abilities --ability-policy v2 --opp-policy sample --opp-T 0.3 --own-effects) > $EV/${1}_$c.log 2>&1
  done
  echo "[$(date -u +%T)] eval $1 done" >> $D/stage.log
}
bev base $DEF/$BASE; bev gen $DEF/$GEN
for n in u30:u0030 u60:u0060 u30g:u0030_g u60g:u0060_g; do
  f=$DEF/$CKR/$RUN/${RUN}_${n#*:}.pt; [ -f $f ] && bev ${n%%:*} $f
done
cd $W && $PY $S/s11_summary.py $EV $D/SUMMARY.txt $D/train.out > $D/summary.out 2>&1
mkdir -p $D/ckpt; cp $DEF/$CKR/$RUN/${RUN}_u00*.pt $D/ckpt/ 2>/dev/null
echo "[$(date -u +%T)] S11 done" >> $D/stage.log
