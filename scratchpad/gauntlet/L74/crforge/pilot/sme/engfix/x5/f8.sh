#!/usr/bin/env bash
# f8.sh -- ENG-FIX5 pod 32657: FRESH8 strict fresh gate, ASSIGN on (default) then off, then the guard (CPUs 28-53).
cd /workspace/pilot/f1fix || exit 1
L=/workspace/crforge_main/5e8089a4/tickprobe/lib; T=/workspace/crforge_cache/tables/16.635.3; F=/workspace/pilot/fresh8
WORKERS=10 taskset -c 28-53 bash runH.sh F8_main $T $F/inputs_rngfree.jsonl $F/frames SME_LIB=$L SME_BANNER_GIVEN=1
WORKERS=10 taskset -c 28-53 bash runH.sh F8_off $T $F/inputs_rngfree.jsonl $F/frames SME_LIB=$L SME_BANNER_GIVEN=1 SME_HIDDEN_ASSIGN=0
python3 assign_guard.py runs/F8_off/results.jsonl runs/F8_main/results.jsonl > runs/F8_guard.txt 2>&1; echo "guard rc=$?" >> runs/F8_guard.txt
echo F8_DONE
