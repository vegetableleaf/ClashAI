#!/usr/bin/env bash
# ENG-SME step 3: collect the 16 tower-troop seed files + 2 controls from 33308 and score (score.py; troop effect vs gate/).
set -euo pipefail
SSH="ssh -o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot -p 33308 root@157.157.221.29"
cd /c/Users/benpe/ClashBot; G=scratchpad/gauntlet/L74/plan1026/d2g/results; O=$G/gate_tt; mkdir -p $O
for e in cf rs; do for m in e4 iu40; do for s in 741200 742000 743000 744000; do
  $SSH "cat /workspace/d2tt/ev/tt_${e}_$m/tt_${e}_${m}_$s/D3/matches.jsonl" > $O/${e}_${m}_$s.jsonl; done; done
  $SSH "cat /workspace/d2tt/ev/ctl_${e}_e4/ctl_${e}_e4_741200/D3/matches.jsonl" > $O/ctl_${e}_e4_741200.jsonl; done
wc -l $O/*.jsonl | tail -1
$SSH 'for f in /workspace/d2tt/ev/*/*/SUMMARY.txt; do echo "== $f"; cat $f; done' > $O/summaries.txt
SC=scratchpad/gauntlet/L74/plan1026/d2g/score.py
for m in e4 iu40; do python $SC "$O/cf_${m}_{s}.jsonl" "$O/rs_${m}_{s}.jsonl" > $O/score_$m.txt; done
{ for e in cf rs; do for m in e4 iu40; do echo "== ${e}_$m: first = with troops, second = earlier no troops"
  python $SC "$O/${e}_${m}_{s}.jsonl" "$G/gate/${e}_${m}_{s}.jsonl" | head -4; done; done; } > $O/troop_effect.txt
{ for e in cf rs; do python -I .foreman/scratch/a2/sme/s3/ctl_cmp.py $O/ctl_${e}_e4_741200.jsonl $G/gate/${e}_e4_741200.jsonl 2>/dev/null \
    || python -I /c/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/scratchpad/ctl.py $O/ctl_${e}_e4_741200.jsonl $G/gate/${e}_e4_741200.jsonl; done; } > $O/control_cmp.txt
head -4 $O/score_e4.txt; head -4 $O/score_iu40.txt; cat $O/control_cmp.txt
