#!/bin/bash
# W8 fin15 (P2): build one fork branch from a bundle into a runtime dir + the cargo gate (as diag_night/r7_closer/fork_build.sh).
#   BUNDLE=/workspace/w8/in/fin15.bundle BRANCH=fin15 NAME=rsfork_fin15 [GATE=0] [PLANTS="mana_regen_exact:mana_regen_step ..."] \
#     nohup bash fork_build.sh > /dev/null 2>&1 < /dev/null &
# -> /workspace/w8/$NAME.{log,DONE,FAILED}, wheel in /workspace/w8/wheels/$NAME/, runtime /workspace/$NAME (pip --target),
#    cargo_$NAME.log (gate), plant_$NAME_<plant>.log (each plant must turn its test red).
B=/workspace/w8; NAME=${NAME:?}; L=$B/$NAME.log; exec > $L 2>&1
set -Eeuo pipefail
trap "touch $B/$NAME.FAILED" ERR
source $HOME/.cargo/env
VPY=${VPY:-/workspace/venvf36/bin/python}
D=$B/src_$NAME; T=$B/target_$NAME; J=${JOBS:-20}
rm -rf $D; git clone -q -b ${BRANCH:?} ${BUNDLE:?} $D
cd $D; echo "$(date -u +%T) head $(git log --oneline -1) tree $(git rev-parse HEAD^{tree} | cut -c1-8)"
"$VPY" tools/extract_arena.py > /dev/null && "$VPY" tools/extract_cards.py --vintage 2018 > /dev/null && cp data/derived/cards-15.535.json data/derived/cards.json && "$VPY" tools/extract_globals.py > /dev/null && "$VPY" tools/stage_wheel_data.py
rm -rf $T/wheels
CARGO_TARGET_DIR=$T nice -n 10 "$VPY" -m maturin build --release -q -j $J 2>&1 | tail -3
mkdir -p $B/wheels/$NAME; W=$(ls $T/wheels/*.whl | head -1); cp $W $B/wheels/$NAME/; W=$B/wheels/$NAME/$(basename $W)
echo "wheel $W sha256 $(sha256sum $W | cut -d' ' -f1)"
O=/workspace/$NAME; [ ! -e $O ] || { echo "$O exists"; exit 1; }
"$VPY" -m pip -q install --no-deps --target $O $W
PYTHONPATH=$O python3 -c "import royalesim, json, pathlib; p=pathlib.Path(royalesim.__file__).parent; c=json.loads(next(p.rglob('calibration.json')).read_text()); print('calib MANA_REGEN_STEP', c['match'].get('MANA_REGEN_STEP', {}).get('value'))"
touch $B/$NAME.wheel_DONE; echo "$(date -u +%T) wheel built"
rm -rf $T
set +e; trap - ERR    # the gate and the plants report through the log (a plant is MEANT to fail)
if [ "${GATE:-1}" = 1 ]; then
  cd $D/crates/royalesim
  CARGO_TARGET_DIR=$B/gate_$NAME nice -n 10 cargo test --profile gate --no-fail-fast -j $J > $B/cargo_$NAME.log 2>&1; rc=$?
  echo "cargo test rc=$rc"
  grep '^test result:' $B/cargo_$NAME.log | awk '{p+=$4; f+=$6; i+=$8} END {print "TOTAL passed", p, "failed", f, "ignored", i, "suites", NR}'
  grep -E '^test .* FAILED|^---- ' $B/cargo_$NAME.log | head -20 || true
  for pt in ${PLANTS:-}; do
    plant=${pt%%:*}; test=${pt##*:}
    RUSTFLAGS="--cfg clash_plant=\"$plant\"" CARGO_TARGET_DIR=$B/gate_plant nice -n 10 cargo test --profile gate -j $J --test $test > $B/plant_${NAME}_$plant.log 2>&1
    echo "plant $plant -> --test $test rc=$? (want != 0): $(grep '^test result:' $B/plant_${NAME}_$plant.log | tail -1)"
  done
  rm -rf $B/gate_$NAME $B/gate_plant
fi
echo "$(date -u +%T) done"; touch $B/$NAME.DONE
