#!/bin/bash
# Step 4 distill (DISTILL_PLAN.md) on a Linux pod, from the repo root:
#   sed -i 's/\r$//' scratchpad/gauntlet/L74/distill/run_distill.sh      # once, if the bundle came from Windows
#   nohup bash scratchpad/gauntlet/L74/distill/run_distill.sh all > /dev/null 2>&1 &
# Steps: smoke (2 recorded games + a 5-step train, ~2 min; run first) | gen (D3 teacher games, recorded) |
#        train (fine-tune the plain student) | score (960 pairs) | all (gen, train, score) |
#        dagger_smoke (2 DAgger games + a 5-step train with the KL term) | dagger (iteration 2, below).
# Env overrides: TEACHER STUDENT OUT BLOCKS WORKERS PY R REF_TEACHER (pattern with {seed}) PLAIN_D1=0 STUDENT_D3=0.
# dagger: R1 = iteration 1's results dir (gen/ = its teacher games, eval/ = its 960-pair runs); OUT = iteration 1's
#   student (acts in round 1); STUDENT = the plain init (every round trains from it; the KL anchor). Round k: the latest
#   student plays D1 on DBLOCKS x 480 fresh games (seeds 750000 + 10000 k ..), the teacher's D3 labels every decision,
#   p_teacher from P_SCHEDULE ("0.5 0"); train from STUDENT on iteration 1 + every round so far -> DOUT/dagger_r<k>.pt.
#   Then the same final union + cell KL (KL, default 1) -> dagger_r<k>_kl.pt; pro VAL (eval_gen on PRO) for plain and
#   both; both scored D1 on the 960 pairs against iteration 1's linked plain_D1 / teacher_D3 / student_D1 (iter1_D1).
#   REHEARSE=F (default 0 = off): F of every batch = pro TRAIN rows from PRO. Finished parts are skipped on a rerun.
set -Eeuo pipefail
PY=${PY:-/workspace/venv33/bin/python}; R=${R:-/workspace/results/DISTILL}; W=${WORKERS:-13}; BLOCKS=${BLOCKS:-5}
TEACHER=${TEACHER:-icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt}
STUDENT=${STUDENT:-icebow/data/bench/rl_royale/newsim_base_main/newsim_base_main_u0060.pt}
OUT=${OUT:-icebow/data/bench/rl_royale/distill/distill_r1_d3.pt}
R1=${R1:-/workspace/results/DISTILL_ADAPT}; P_SCHEDULE=${P_SCHEDULE:-0.5 0}; DBLOCKS=${DBLOCKS:-3}; KL=${KL:-1}
PRO=${PRO:-icebow/data/pipeline/gen_dataset_v32_fv5.npz}; REHEARSE=${REHEARSE:-0}; DOUT=${DOUT:-$(dirname $OUT)}
D=scratchpad/gauntlet/L74/distill; GAP=scratchpad/gauntlet/L74/gap/gap.py
export PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
mkdir -p $R
exec >> $R/run.log 2>&1
finish() { rc=$?; echo "exit_code=$rc" > $R/DONE_$STEP; [ $rc = 0 ] || echo "$(date -u +%T) $STEP FAILED (exit $rc)"; }
STEP=${1:?usage: run_distill.sh smoke|gen|train|score|all|dagger_smoke|dagger}; trap finish EXIT
for f in $TEACHER $STUDENT; do [ -f $f ] || { echo "missing $f"; exit 3; }; done

smoke() {
  rm -rf $R/smoke
  $PY $D/gen_distill.py --ckpt $TEACHER --out $R/smoke/gen --smoke --workers 1 --python $PY > $R/smoke.log 2>&1
  [ "$(find $R/smoke/gen -name 'distill_*.npz' | wc -l)" = 2 ] || { echo "smoke: expected 2 game files"; exit 4; }
  $PY $D/train_distill.py --data $R/smoke/gen --init $STUDENT --out $R/smoke/student.pt --max-steps 5 --val-pct 50     >> $R/smoke.log 2>&1
  echo "$(date -u +%T) smoke OK: $(grep -o '"play_rows": [0-9]*' $R/smoke/student.log.jsonl | head -1)"
}
gen() {
  echo "$(date -u +%T) gen: $BLOCKS x 480 D3 games, teacher $(sha256sum $TEACHER | cut -c1-16)"
  flock /workspace/cpu.lock $PY $D/gen_distill.py --ckpt $TEACHER --out $R/gen --blocks $BLOCKS --workers $W --python $PY \
    > $R/gen.log 2>&1
  echo "$(date -u +%T) gen done: $(find $R/gen -name 'distill_*.npz' | wc -l) game files, $(du -sh $R/gen | cut -f1)"
}
train() {
  echo "$(date -u +%T) train: init $(sha256sum $STUDENT | cut -c1-16)"
  $PY $D/train_distill.py --data $R/gen --init $STUDENT --out $OUT > $R/train.log 2>&1
  sha256sum $TEACHER $STUDENT $OUT > $R/ckpts.sha
  echo "$(date -u +%T) train done -> $OUT"
}
one() {   # one(run name, ckpt, arm): gap.py on both evaluation seed sets (a finished seed set is kept)
  for S in 741200 742000; do
    [ -f $R/eval/$1_$S/SUMMARY.txt ] && continue
    rm -rf $R/eval/$1_$S
    flock /workspace/cpu.lock $PY $GAP --ckpt $2 --out $R/eval/$1_$S --arms $3 --seed-start $S --workers $W --python $PY \
      > $R/eval_$1_$S.log 2>&1
  done
}
score() {
  [ -f $OUT ] || { echo "missing $OUT (train first)"; exit 3; }
  echo "$(date -u +%T) score"
  one student_D1 $OUT D1
  one teacher_D3 $TEACHER D3
  [ "${PLAIN_D1:-1}" = 0 ] || one plain_D1 $STUDENT D1
  [ "${STUDENT_D3:-0}" = 0 ] || one student_D3 $OUT D3
  $PY $D/score_distill.py $R/eval ${REF_TEACHER:+--ref-teacher "$REF_TEACHER"} > $R/SUMMARY.txt
  cat $R/SUMMARY.txt
}
reh() { [ "$REHEARSE" = 0 ] || echo "--rehearse $PRO --rehearse-frac $REHEARSE"; }
dagger_check() {
  [ "$(readlink -f $R)" != "$(readlink -f $R1)" ] || { echo "R must differ from R1 (iteration 1's results)"; exit 3; }
  for f in $OUT $PRO; do [ -f $f ] || { echo "missing $f"; exit 3; }; done
}
dagger_smoke() {
  dagger_check
  rm -rf $R/dsmoke
  $PY $D/gen_distill.py --ckpt $OUT --teacher $TEACHER --p-teacher 0.5 --out $R/dsmoke/gen --seed-start 760000 --smoke \
    --workers 1 --python $PY > $R/dsmoke.log 2>&1
  [ "$(find $R/dsmoke/gen -name 'distill_*.npz' | wc -l)" = 2 ] || { echo "dagger_smoke: expected 2 game files"; exit 4; }
  $PY $D/train_distill.py --data $R/dsmoke/gen --init $STUDENT --out $R/dsmoke/student.pt --max-steps 5 --val-pct 50 \
    --cell-kl $KL $(reh) >> $R/dsmoke.log 2>&1
  echo "$(date -u +%T) dagger_smoke OK: $(grep -o '"dagger_decisions": [0-9]*, "gate_agree": [0-9]*' $R/dsmoke/student.log.jsonl | head -1)"
}
dagger() {
  dagger_check
  [ -d $R1/gen ] && [ -d $R1/eval ] || { echo "missing $R1/gen or $R1/eval (iteration 1)"; exit 3; }
  local data=$R1/gen acting=$OUT k=0 p g ck kl
  for p in $P_SCHEDULE; do
    k=$((k+1)); g=$R/gen_r$k; ck=$DOUT/dagger_r$k.pt
    if [ ! -f $g/DONE ]; then
      rm -rf $g
      echo "$(date -u +%T) dagger round $k: $DBLOCKS x 480 games, acting $(sha256sum $acting | cut -c1-16), p_teacher $p"
      flock /workspace/cpu.lock $PY $D/gen_distill.py --ckpt $acting --teacher $TEACHER --p-teacher $p --out $g \
        --blocks $DBLOCKS --seed-start $((750000 + 10000*k)) --workers $W --python $PY > $R/gen_r$k.log 2>&1
      touch $g/DONE
    fi
    for b in $g/b*/; do   # the acting player's results (p 0: the student's own D1 on these seeds)
      $PY $GAP --out $b --summarize-only | grep '^D1:' | sed "s|^|round $k $(basename $b) acting |" || true
    done
    data="$data $g"
    if [ ! -f $ck ]; then
      $PY $D/train_distill.py --data $data --init $STUDENT --out $ck $(reh) > $R/train_r$k.log 2>&1
      echo "$(date -u +%T) round $k trained -> $ck"
    fi
    acting=$ck
  done
  kl=$DOUT/dagger_r${k}_kl.pt
  [ -f $kl ] || $PY $D/train_distill.py --data $data --init $STUDENT --out $kl --cell-kl $KL $(reh) > $R/train_r${k}_kl.log 2>&1
  sha256sum $TEACHER $STUDENT $OUT $DOUT/dagger_r*.pt > $R/ckpts.sha
  for x in plain:$STUDENT dagger:$acting daggerkl:$kl; do
    [ -f $R/pro_${x%%:*}.json ] || $PY -m pipeline.eval_gen --ckpt ${x#*:} --data $PRO --out $R/pro_${x%%:*}.json \
      > $R/pro_${x%%:*}.log 2>&1
  done
  mkdir -p $R/eval
  for S in 741200 742000; do
    for x in teacher_D3:teacher_D3 plain_D1:plain_D1 iter1_D1:student_D1; do
      [ -e $R/eval/${x%%:*}_$S ] || ln -s $(readlink -f $R1/eval/${x#*:}_$S) $R/eval/${x%%:*}_$S
    done
  done
  echo "$(date -u +%T) dagger score"
  one dagger_D1 $acting D1
  one daggerkl_D1 $kl D1
  $PY $D/score_distill.py $R/eval --pro plain=$R/pro_plain.json --pro dagger=$R/pro_dagger.json \
    --pro daggerkl=$R/pro_daggerkl.json > $R/SUMMARY.txt
  cat $R/SUMMARY.txt
}
case $STEP in
  smoke) smoke ;; gen) gen ;; train) train ;; score) score ;;
  all) gen; train; score ;;
  dagger_smoke) dagger_smoke ;; dagger) dagger ;;
  *) echo "unknown step $STEP"; exit 2 ;;
esac
echo "$(date -u +%T) $STEP done"
