#!/bin/bash
# fullgate2.sh N CPUS -- POD side (33308 /workspace/pgate2), account 3 10-31: the owner's promotion bar for a pilot2 checkpoint =
# 3,840 SIM games (iu40 + e4, seeds 741200 742000 743000 744000) of ck/N.pt under its trained sampled gate (T .1) on the stripped
# live stack, paired with CLXIII's base2 rows (same tree, same stack, threshold gate = live). Last line: PASS iff pooled CI low > 0.
# Resumable (gate.sh skips full seed dirs). The iu40 seed-741200 block reuses the check's rows when present (same command).
N=$1; C=${2:-0-47}; P=/workspace/pgate2; cd /workspace/loop/cb || exit 1
export GATE_CB=/workspace/loop/cb GATE_PY=/workspace/venvf16/bin/python GATE_LIB=/workspace/crforge_main/5e8089a4/plain/lib \
  GATE_TABLES=/workspace/crforge_cache/tables/16.635.3 GATE_FACADE=$P/facade GATE_EV=$P/ev CRFORGE_BARREL_DECOY_SIM=1 CRFORGE_XMX=1g \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" GATE_SAMPLE=0.1 GATE_CKPT=$P/ck/$N.pt
W=$(( $(echo $C | cut -d- -f2) - $(echo $C | cut -d- -f1) + 1 )); G=scratchpad/gauntlet/L74/plan1026/d2g/gate.sh; S="741200 742000 743000 744000"
mkdir -p $P/ev/g2_iu40_$N && [ -d $P/ev/p2chk_$N/p2chk_${N}_741200 ] && [ ! -e $P/ev/g2_iu40_$N/g2_iu40_${N}_741200 ] && \
  cp -r $P/ev/p2chk_$N/p2chk_${N}_741200 $P/ev/g2_iu40_$N/g2_iu40_${N}_741200
bash $G crforge g2_iu40_$N iu40 $C $W $S > $P/g2_$N.out 2>&1; bash $G crforge g2_e4_$N e4 $C $W $S >> $P/g2_$N.out 2>&1
cd $P && /workspace/venvf16/bin/python pair_both.py "ev/g2_e4_$N/g2_e4_${N}_{s}/D3/matches.jsonl" "ev/g2_iu40_$N/g2_iu40_${N}_{s}/D3/matches.jsonl" \
  "ev/base2_e4/base2_e4_{s}/D3/matches.jsonl" "ev/base2_iu40/base2_iu40_{s}/D3/matches.jsonl"
