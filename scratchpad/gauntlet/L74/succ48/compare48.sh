#!/bin/bash
# compare48.sh TAG -- pod 32525: a gate48 candidate vs CLX WITH the hazard play (the live-proven baseline), paired on the same
# seeds / decks: E4 1,920 (clx_rb) and calibrated I u40 1,920 (pushcal iu40_d20t20 741200 / 742000 + clxhaz_cal 743000 / 744000),
# then behaviour (drift_check: candidate E4 vs clx_rb E4, 99% intervals).
TAG=$1; X=/workspace/pushcal; P=/workspace/venvf15/bin/python; B=$X/ev/clxhaz_cal_all; mkdir -p $B
for s in 741200 742000; do ln -sfn $X/ev/iu40_d20t20/iu40_d20t20_$s $B/clxhaz_cal_all_$s; done
for s in 743000 744000; do ln -sfn $X/ev/clxhaz_cal/clxhaz_cal_$s $B/clxhaz_cal_all_$s; done
echo "== $TAG vs CLX-with-hazard (paired; candidate = A)"
echo -n "E4  "; $P /workspace/ckev/paircmp_pooled.py "$X/ev/${TAG}_e4/${TAG}_e4_{s}/D3/matches.jsonl" "/workspace/ckev/out/clx_rb/e4/clx_rb_{s}_fin15/D3/matches.jsonl"
echo -n "cal "; $P /workspace/ckev/paircmp_pooled.py "$X/ev/${TAG}_cal/${TAG}_cal_{s}/D3/matches.jsonl" "$B/clxhaz_cal_all_{s}/D3/matches.jsonl"
mkdir -p $X/ev/clx_rb_e4_all; for s in 741200 742000 743000 744000; do ln -sfn /workspace/ckev/out/clx_rb/e4/clx_rb_${s}_fin15 $X/ev/clx_rb_e4_all/clx_rb_${s}_fin15; done
(cd /workspace/exploit/repo && $P scratchpad/gauntlet/L74/exploit/tools/drift_check.py $X/ev/${TAG}_e4 --base $X/ev/clx_rb_e4_all 2>&1 | grep -v "^base")
