#!/bin/bash
# W19: build the fin16 fork branch (client-dated 2026-10-19 table) into /workspace/w19/rsfork_fin16 and run the cargo gate
# with its plants (skeletons_split_off has no test yet: the parity A/B measures it; card_table_unread must turn
# card_table red).   setsid nohup bash fork_build16.sh > /workspace/w19/fork16.log 2>&1 < /dev/null &
set -uo pipefail
B=/workspace/w19; VPY=/workspace/venvf15/bin/python; source $HOME/.cargo/env
cd $B/fork && git log --oneline -1 && git status --short
rm -rf $B/target/wheels
CARGO_TARGET_DIR=$B/target nice -n 5 "$VPY" -m maturin build --release -q -j 24 2>&1 | tail -3
W=$(ls $B/target/wheels/*.whl | head -1); echo "wheel $W sha256 $(sha256sum $W | cut -d' ' -f1)"
mkdir -p $B/wheels16 && cp $W $B/wheels16/
rm -rf $B/rsfork_fin16 && "$VPY" -m pip -q install --no-deps --target $B/rsfork_fin16 $W && touch $B/FIN16_WHEEL_OK
PYTHONPATH=$B/rsfork_fin16 "$VPY" -c "import royalesim as s, json; b=s.Battle(None, [[0,1,2],[0,2,1]], calibration_overrides={'cards.CARD_TABLE': json.dumps('client160402017_20261019')}); print('table', b.card_table())"
cd crates/royalesim
CARGO_TARGET_DIR=$B/gate nice -n 5 cargo test --profile gate --no-fail-fast -j 24 > $B/cargo_fin16.log 2>&1; echo "cargo rc=$?"
grep '^test result:' $B/cargo_fin16.log | awk '{p+=$4; f+=$6; i+=$8} END {print "TOTAL passed", p, "failed", f, "ignored", i, "suites", NR}'
grep -E '^test .* FAILED|^---- ' $B/cargo_fin16.log | head -20
RUSTFLAGS='--cfg clash_plant="card_table_unread"' CARGO_TARGET_DIR=$B/gate_plant nice -n 5 cargo test --profile gate -j 24 --test card_table > $B/plant16.log 2>&1
echo "plant card_table_unread -> $(grep '^test result:' $B/plant16.log | tail -1)"
touch $B/FIN16_GATE_DONE
