#!/bin/bash
# r7 closer: clashbot36 a697d1f9 + S-PULSE-TWICE + S-EK-HITTICK + S-HOLD-REACH (cand3.bundle) -> wheel /workspace/rsfork_fin14c, cargo test gate
B=/workspace/w_r7close; L=$B/fork_build.log; exec > $L 2>&1
set -Eeuo pipefail
trap "touch $B/fork_build.FAILED" ERR
source $HOME/.cargo/env
VPY=/workspace/vfork/bin/python
D=$B/fork; T=$B/target
rm -rf $D; git clone -q -b clashbot36 $B/cand3.bundle $D
cd $D; echo "$(date -u +%T) head $(git log --oneline -1)"
df -BG /workspace | tail -1
"$VPY" tools/extract_arena.py > /dev/null && "$VPY" tools/extract_cards.py --vintage 2018 > /dev/null && cp data/derived/cards-15.535.json data/derived/cards.json && "$VPY" tools/extract_globals.py > /dev/null && "$VPY" tools/stage_wheel_data.py
rm -rf $T/wheels
CARGO_TARGET_DIR=$T nice -n 10 "$VPY" -m maturin build --release -q -j 16 2>&1 | tail -3
W=$(ls $T/wheels/*.whl | head -1); echo "wheel $(sha256sum $W | cut -c1-16)"; cp $W $B/
O=/workspace/rsfork_fin14c; [ ! -e $O ] || { echo "$O exists"; exit 1; }
"$VPY" -m pip -q install --no-deps --target $O $W
PYTHONPATH=$O python3 -c "import royalesim, json, pathlib; p=pathlib.Path(royalesim.__file__).parent; c=json.loads(next(p.rglob('calibration.json')).read_text()); print('calib', c['targeting']['HIDDEN_HOLD_REACH']['value'], c['status']['IDLE_BUFF_HIT_TICK']['value'], c['status']['BUFF_PULSE_REDUCTION']['value'], c['hide']['FIRED_UNDER_WINDOW_MS']['value'])"
touch $B/wheel.DONE; echo "$(date -u +%T) wheel built"
rm -rf $T
df -BG /workspace | tail -1
set +e
cd crates/royalesim
CARGO_TARGET_DIR=$B/target_gate nice -n 10 cargo test --profile gate --no-fail-fast -j 16 > $B/cargo_test.log 2>&1; rc=$?
echo "cargo test rc=$rc"
grep '^test result:' $B/cargo_test.log | awk '{p+=$4; f+=$6; i+=$8} END {print "TOTAL passed", p, "failed", f, "ignored", i, "suites", NR}'
grep -E '^test .* FAILED|^---- ' $B/cargo_test.log | head -20
df -BG /workspace | tail -1
rm -rf $B/target_gate
echo "$(date -u +%T) done"; touch $B/fork_build.DONE
