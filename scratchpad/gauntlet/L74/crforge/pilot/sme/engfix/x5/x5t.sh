#!/usr/bin/env bash
# x5t.sh -- ENG-FIX5 pod 32657: FRESH8 records extracted WITHOUT one new flag (the flag's firings), gate sme11f, 5e8089a4.
cd /workspace/pilot/f1fix || exit 1
E=/workspace/pilot/engfix5; L=/workspace/crforge_main/5e8089a4/tickprobe/lib
for v in pend gen ras; do
  WORKERS=1 taskset -c 28-53 bash runH.sh X5_t_$v /workspace/crforge_cache/tables/16.635.3 $E/t_$v.jsonl /workspace/pilot/fresh8/frames SME_LIB=$L SME_BANNER_GIVEN=1 &
done
wait
for v in pend gen ras; do
  python3 -c "import json
for l in open('runs/X5_t_$v/results.jsonl'):
    x=json.loads(l); print('X5_t_$v', x['match'][10:], x['flags'], x['counts'], x['first_div'], 'missed', x['plants']['missed'], x['refused_plays'], str(x['first_detail'])[:200])"
done
echo X5T_DONE
