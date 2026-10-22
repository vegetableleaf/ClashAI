#!/bin/bash
# W19 fin16 chain: wheel from the fork branch fin16 (fin15 305aaafc + W23 4f7e14f data + W19 be0766c arm), then the round-3
# A/B (fights.py with PARITY_TABLE_1019=1: captures from 10-19 06:00 on replay on the 10-19 table) on both cohorts, and
# beside it the cargo gate + the card_table plant.   setsid nohup bash fin16_chain.sh > /workspace/w19/fin16_chain.log 2>&1 &
set -uo pipefail
B=/workspace/w19; VPY=/workspace/venvf15/bin/python; source $HOME/.cargo/env
cd $B/fork && git log --oneline -1 && git status --short
rm -rf $B/target/wheels $B/rsfork_fin16 $B/FIN16_WHEEL_OK
CARGO_TARGET_DIR=$B/target nice -n 5 "$VPY" -m maturin build --release -q -j 24 2>&1 | tail -2
W=$(ls $B/target/wheels/*.whl | head -1); echo "wheel sha256 $(sha256sum $W | cut -d' ' -f1)"
mkdir -p $B/wheels16 && cp $W $B/wheels16/ && "$VPY" -m pip -q install --no-deps --target $B/rsfork_fin16 $W && touch $B/FIN16_WHEEL_OK
PYTHONPATH=$B/rsfork_fin16 "$VPY" -c "import royalesim as s, json; b=s.Battle(None, [[0,1,2],[0,2,1]], calibration_overrides={'cards.CARD_TABLE': json.dumps('client160402017_20261019')}); print('table', b.card_table())"
rm -rf $B/res/R3 && cp $B/in/fights_r3.py $B/cb22_r3/scratchpad/gauntlet/L74/parity/fights.py
( PARITY_TABLE_1019=1 CODE=$B/cb22_r3 SIM=$B/rsfork_fin16 OUT=$B/res/R3 COHORTS="c22 c13" W=3 K=0 bash $B/cb22/scratchpad/gauntlet/L74/parity/w19/base_run.sh ) &
cd $B/fork/crates/royalesim
CARGO_TARGET_DIR=$B/gate nice -n 10 cargo test --profile gate --no-fail-fast -j 16 > $B/cargo_fin16.log 2>&1; echo "cargo rc=$?"
grep '^test result:' $B/cargo_fin16.log | awk '{p+=$4; f+=$6; i+=$8} END {print "TOTAL passed", p, "failed", f, "ignored", i, "suites", NR}'
grep -E '^test .* FAILED|^---- ' $B/cargo_fin16.log | head -20
RUSTFLAGS='--cfg clash_plant="card_table_unread"' CARGO_TARGET_DIR=$B/gate_plant nice -n 10 cargo test --profile gate -j 16 --test card_table > $B/plant16.log 2>&1
echo "plant card_table_unread -> $(grep '^test result:' $B/plant16.log | tail -1)"
touch $B/FIN16_GATE_DONE
wait; echo "R3 done"; touch $B/FIN16_CHAIN_DONE
