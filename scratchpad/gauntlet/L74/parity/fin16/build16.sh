#!/bin/bash
# A1 (10-27, pod 32657): build fork branch fin16 (fin15 305aaafc + patches/0001 (= W23 b2809aa1) + patches/0002 (W19 arm))
# from the bundle into a wheel + runtime dirs, then the cargo gate + the card_table plant (fin15's fork_build.sh recipe).
#   setsid nohup bash build16.sh > /dev/null 2>&1 < /dev/null &
# -> /workspace/f16/build16.log, wheels16/, rsfork_fin15 + rsfork_fin16 (pip --target), WHEEL_OK, GATE_DONE
B=/workspace/f16; exec > $B/build16.log 2>&1
set -Eeuo pipefail
trap "touch $B/BUILD_FAILED" ERR
source $HOME/.cargo/env
VPY=/workspace/venvf15/bin/python; J=${JOBS:-40}
"$VPY" -m pip -q install 'maturin>=1.15,<2.0'
D=$B/src_fin16; rm -rf $D; git clone -q -b fin16 $B/in/fin16.bundle $D
cd $D; echo "$(date -u +%T) head $(git log --oneline -1) tree $(git rev-parse HEAD^{tree})"
"$VPY" tools/extract_arena.py > /dev/null && "$VPY" tools/extract_cards.py --vintage 2018 > /dev/null && cp data/derived/cards-15.535.json data/derived/cards.json && "$VPY" tools/extract_globals.py > /dev/null && "$VPY" tools/stage_wheel_data.py
git status --short | head
CARGO_TARGET_DIR=$B/target nice -n 10 "$VPY" -m maturin build --release -q -j $J 2>&1 | tail -3
mkdir -p $B/wheels16; W=$(ls $B/target/wheels/*.whl | head -1); cp $W $B/wheels16/; W=$B/wheels16/$(basename $W)
echo "wheel $W sha256 $(sha256sum $W | cut -d' ' -f1)"
# move the build checkout away: a wheel whose BUILD_DATA_DIR exists reads it (FIN15.md "Trap"); the gate runs in the moved copy
rm -rf $B/src_fin16_gate; mv $D $B/src_fin16_gate; D=$B/src_fin16_gate
rm -rf $B/rsfork_fin16 $B/rsfork_fin15
"$VPY" -m pip -q install --no-deps --target $B/rsfork_fin16 $W
"$VPY" -m pip -q install --no-deps --target $B/rsfork_fin15 $B/in/royalesim-0.1.36-cp310-abi3-manylinux_2_34_x86_64.whl
for r in fin15 fin16; do PYTHONPATH=$B/rsfork_$r "$VPY" -c "import royalesim as s; print('$r provenance', s.Battle.provenance(), 'table source', s.card_table_source())"; done
PYTHONPATH=$B/rsfork_fin16 "$VPY" -c "import royalesim as s, json; b=s.Battle(None, [[0,1,2],[0,2,1]], calibration_overrides={'cards.CARD_TABLE': json.dumps('client160402017_20261019')}); print('fin16 10-19 arm table', b.card_table())"
touch $B/WHEEL_OK; echo "$(date -u +%T) wheel built"
set +e; trap - ERR    # the gate and the plant report through the log (the plant is MEANT to fail)
cd $D/crates/royalesim
CARGO_TARGET_DIR=$B/gate nice -n 10 cargo test --profile gate --no-fail-fast -j $J > $B/cargo_fin16.log 2>&1; echo "cargo test rc=$?"
grep '^test result:' $B/cargo_fin16.log | awk '{p+=$4; f+=$6; i+=$8} END {print "TOTAL passed", p, "failed", f, "ignored", i, "suites", NR}'
grep -E '^test .* FAILED|^---- ' $B/cargo_fin16.log | head -20
RUSTFLAGS='--cfg clash_plant="card_table_unread"' CARGO_TARGET_DIR=$B/gate_plant nice -n 10 cargo test --profile gate -j $J --test card_table > $B/plant16.log 2>&1
echo "plant card_table_unread -> rc=$? (want != 0): $(grep '^test result:' $B/plant16.log | tail -1)"
echo "$(date -u +%T) done"; touch $B/GATE_DONE
