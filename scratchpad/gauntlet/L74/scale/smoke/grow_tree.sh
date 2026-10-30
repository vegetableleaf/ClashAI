#!/bin/bash
# GROW-SMOKE: own tree /workspace/grow/cb = links to /workspace/speed2/cb (10-28 tree, icebow/data -> /workspace/icebow_data)
# except pipeline/ and the loop dir (origin/main archive in /workspace/grow/src) and a real L68/rl (run dirs).
set -e
SRC=/workspace/speed2/cb; T=/workspace/grow/cb; A=/workspace/grow/src
mkdir -p $T; cd $T
for x in $SRC/*; do b=$(basename "$x"); case $b in pipeline|scratchpad) ;; *) [ -e "$b" ] || ln -s "$x" "$b";; esac; done
cp -a $A/pipeline $T/pipeline
farm() { mkdir -p $T/$1; for x in $SRC/$1/*; do b=$(basename "$x"); [ "$b" = "$2" ] || [ -e "$T/$1/$b" ] || ln -s "$x" "$T/$1/$b"; done; }
farm scratchpad gauntlet; farm scratchpad/gauntlet L74; farm scratchpad/gauntlet/L74 plan1026
farm scratchpad/gauntlet/L74/plan1026 pilot; farm scratchpad/gauntlet/L74/plan1026/pilot loop
cp -a $A/scratchpad/gauntlet/L74/plan1026/pilot/loop $T/scratchpad/gauntlet/L74/plan1026/pilot/loop
rm -f $T/scratchpad/gauntlet/L68; farm scratchpad/gauntlet/L68 rl; mkdir -p $T/scratchpad/gauntlet/L68/rl
sed '/^fastloop:/,$d; /oplc_ftR_l0003_a10b_u0160/d' $A/scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml > /workspace/grow/pilot_smoke.yaml
ls -la $T | head -40
# origin/main java: obsid + facade real copies (producer.compile_java reads them)
G=scratchpad/gauntlet/L74
rm -f $T/$G/speed $T/$G/crforge
farm $G/speed crforge; farm $G/speed/crforge obsid; farm $G/crforge facade
cp -a $A/$G/speed/crforge/obsid $T/$G/speed/crforge/obsid; cp -a $A/$G/crforge/facade $T/$G/crforge/facade
