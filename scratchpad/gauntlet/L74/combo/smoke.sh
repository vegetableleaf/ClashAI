#!/bin/bash
# Pod-side checks for the combo reward (after combo/ship.sh; few CPUs: 3 one-actor smokes + 4 one-worker eval processes):
#   1. pyflakes (undefined names / syntax) on every changed module; the unit tests (test_spell_value: the tracker's tower
#      kinds against royalegym too); cfgcheck.py (every combo yaml through the trainer's validators)
#   2. REAL rl_royale --smoke, three of them: on = combo_rew.yaml (key on); off_new = the same arm WITHOUT the spell keys
#      (= Mark CXXXVIII's training config, the combo init) on this code; off_old = that config on the git-HEAD versions of the
#      five changed modules (a hard-linked copy /workspace/cb_old). off_new vs off_old: config sha AND update-0 rollouts must
#      be identical (the key absent = byte-identical training); on vs off_new: update-0 rollouts identical (the tracker is
#      measurement only), r_step / critic differ (the reward).
#   3. eval_inv.py: the promotion eval's first job with / without --spell-log (and with the live combo rules), rows identical.
#   [CB=/workspace/cb_combo] bash smoke.sh   -> /workspace/combo/smoke/{smoke.log, *.log, inv/}, SMOKE_DONE
set -uo pipefail
CB=${CB:-/workspace/cb_tt}; OLD=${CB}_old; PY=/workspace/venvf36/bin/python; O=/workspace/combo/smoke; FD=scratchpad/gauntlet/L74/combo
mkdir -p $O; exec >> $O/smoke.log 2>&1
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) smoke start"
$PY -m pyflakes pipeline/{spell_value,royale_env,e1_eval,rl_royale,search_s0}.py pipeline/tests/test_spell_value.py $FD/*.py \
  | grep -i "undefined\|syntax"; echo "pyflakes undefined-name / syntax lines above (none = clean)"
$PY -m unittest pipeline.tests.test_spell_value 2>&1 | tail -3
$PY $FD/cfgcheck.py
grep -v '^spell_value' $FD/cfg/combo_rew.yaml > $O/combo_base.yaml       # the arm minus the spell keys
rm -rf $OLD; cp -al $CB $OLD                                               # hard links: no extra disk
for f in rl_royale royale_env e1_eval search_s0; do                      # rm first: never write through a hard link
  rm -f $OLD/pipeline/$f.py && cp $FD/head/$f.py $OLD/pipeline/$f.py         # (ship.sh: git show HEAD:pipeline/<f>.py)
done
rm -f $OLD/pipeline/spell_value.py $OLD/pipeline/tests/test_spell_value.py  # not in HEAD
sha256sum $OLD/pipeline/{rl_royale,royale_env,e1_eval,search_s0}.py
for s in smoke_combo_on smoke_combo_off; do
  rm -rf scratchpad/gauntlet/L68/rl/$s icebow/data/bench/rl_royale/$s $OLD/scratchpad/gauntlet/L68/rl/$s $OLD/icebow/data/bench/rl_royale/$s
done
$PY -m pipeline.rl_royale --config $FD/cfg/combo_rew.yaml --run smoke_combo_on --smoke > $O/smoke_on.log 2>&1 &
$PY -m pipeline.rl_royale --config $O/combo_base.yaml --run smoke_combo_off --smoke > $O/smoke_off_new.log 2>&1 &
(cd $OLD && PYTHONPATH=$OLD $PY -m pipeline.rl_royale --config $O/combo_base.yaml --run smoke_combo_off --smoke \
  > $O/smoke_off_old.log 2>&1) &
rm -rf $O/inv; mkdir -p $O/inv
$PY $FD/eval_inv.py $O/inv > $O/inv.out 2>&1 &
wait
for s in smoke_on smoke_off_new smoke_off_old; do
  echo "$s: $(grep -c 'SMOKE PASS' $O/$s.log) SMOKE PASS; $(grep -o 'config sha [0-9a-f]*' $O/$s.log | head -1)"
done
cp scratchpad/gauntlet/L68/rl/smoke_combo_on/train_log.jsonl $O/on_train_log.jsonl
cp scratchpad/gauntlet/L68/rl/smoke_combo_off/train_log.jsonl $O/off_new_train_log.jsonl
cp $OLD/scratchpad/gauntlet/L68/rl/smoke_combo_off/train_log.jsonl $O/off_old_train_log.jsonl
$PY $FD/smoke_cmp.py $O/off_old_train_log.jsonl $O/off_new_train_log.jsonl $O/on_train_log.jsonl
tail -40 $O/inv.out
echo "$(date -u +%T) smoke done"; touch $O/SMOKE_DONE
