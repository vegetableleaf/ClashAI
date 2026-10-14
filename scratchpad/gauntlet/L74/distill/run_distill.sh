#!/bin/bash
# Step 4 distill (DISTILL_PLAN.md) on a Linux pod, from the repo root:
#   sed -i 's/\r$//' scratchpad/gauntlet/L74/distill/run_distill.sh      # once, if the bundle came from Windows
#   nohup bash scratchpad/gauntlet/L74/distill/run_distill.sh all > /dev/null 2>&1 &
# Steps: smoke (2 recorded games + a 5-step train, ~2 min; run first) | gen (D3 teacher games, recorded) |
#        train (fine-tune the plain student) | score (960 pairs) | all (gen, train, score).
# Env overrides: TEACHER STUDENT OUT BLOCKS WORKERS PY R REF_TEACHER (pattern with {seed}) PLAIN_D1=0 STUDENT_D3=0.
set -Eeuo pipefail
PY=${PY:-/workspace/venv33/bin/python}; R=${R:-/workspace/results/DISTILL}; W=${WORKERS:-13}; BLOCKS=${BLOCKS:-5}
TEACHER=${TEACHER:-icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt}
STUDENT=${STUDENT:-icebow/data/bench/rl_royale/newsim_base_main/newsim_base_main_u0060.pt}
OUT=${OUT:-icebow/data/bench/rl_royale/distill/distill_r1_d3.pt}
D=scratchpad/gauntlet/L74/distill; GAP=scratchpad/gauntlet/L74/gap/gap.py
export PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
mkdir -p $R
exec >> $R/run.log 2>&1
finish() { rc=$?; echo "exit_code=$rc" > $R/DONE_$STEP; [ $rc = 0 ] || echo "$(date -u +%T) $STEP FAILED (exit $rc)"; }
STEP=${1:?usage: run_distill.sh smoke|gen|train|score|all}; trap finish EXIT
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
one() {   # one(run name, ckpt, arm): gap.py on both evaluation seed sets
  for S in 741200 742000; do
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
case $STEP in
  smoke) smoke ;; gen) gen ;; train) train ;; score) score ;;
  all) gen; train; score ;;
  *) echo "unknown step $STEP"; exit 2 ;;
esac
echo "$(date -u +%T) $STEP done"
