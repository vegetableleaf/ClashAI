#!/usr/bin/env bash
# x5gen.sh -- ENG-FIX5 pod 32657: SME_SAMETICK_GEN probe, OFF vs ON inputs of the 7 changed records (gate sme11f, 5e8089a4,
# SME_BANNER_GIVEN=1, runH defaults = ASSIGN on), CPUs 28-53.
cd /workspace/pilot/f1fix || exit 1
E=/workspace/pilot/engfix5; L=/workspace/crforge_main/5e8089a4/tickprobe/lib
for m in off on; do
  WORKERS=4 taskset -c 28-53 bash runH.sh X5_gen_dev_$m /workspace/crforge_cache/tables/16.402.22 $E/gen_dev_$m.jsonl /workspace/pilot/sme_live/frames2 SME_LIB=$L SME_BANNER_GIVEN=1
  WORKERS=3 taskset -c 28-53 bash runH.sh X5_gen_fr_$m /workspace/crforge_cache/tables/16.635.3 $E/gen_fresh3_$m.jsonl $E/fr_gen SME_LIB=$L SME_BANNER_GIVEN=1
done
for r in X5_gen_dev_off X5_gen_dev_on X5_gen_fr_off X5_gen_fr_on; do
  python3 -c "import json
for l in open('runs/$r/results.jsonl'):
    x=json.loads(l); print('$r', x['match'][10:], x['flags'], x['counts'], x['first_div'], 'missed', x['plants']['missed'], str(x['first_detail'])[:160])"
done
echo X5GEN_DONE
