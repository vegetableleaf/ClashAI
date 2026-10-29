#!/usr/bin/env bash
# bothways.sh -- ENG-FIX4 pod 32657: every reader-hidden-window record of the frozen FRESH2-7 gate inputs, run ASSIGN off and on
# (gate sme11f with SME_CLS_TICKS, each set's own lib), then assign_guard.py. CPUs 52-53 (Codex r8 holds 28-53).
cd /workspace/pilot/f1fix || exit 1
T=/workspace/crforge_cache/tables/16.635.3; O=/workspace/pilot/engfix4/bw; mkdir -p $O
for s in 2:624eeb45 3:fe364ceb 4:fe364ceb 5:5e8089a4 6:5e8089a4 7:5e8089a4; do n=${s%%:*}; lib=/workspace/crforge_main/${s#*:}/tickprobe/lib
  python3 -c "import json,sys
for l in open('/workspace/pilot/fresh$n/inputs_rngfree.jsonl'):
    if json.loads(l).get('reader_hidden'): sys.stdout.write(l)" > $O/f$n.jsonl
  echo "fresh$n sha $(sha256sum < /workspace/pilot/fresh$n/inputs_rngfree.jsonl | cut -c1-16) hidden_records $(wc -l < $O/f$n.jsonl)"
  [ -s $O/f$n.jsonl ] || continue
  for a in 0 1; do WORKERS=2 taskset -c 52-53 bash runH.sh EF4_bw${n}_$a $T $O/f$n.jsonl /workspace/pilot/fresh$n/frames SME_LIB=$lib SME_BANNER_GIVEN=1 SME_HIDDEN_ASSIGN=$a; done
  python3 assign_guard.py runs/EF4_bw${n}_0/results.jsonl runs/EF4_bw${n}_1/results.jsonl
done
echo BW_DONE
