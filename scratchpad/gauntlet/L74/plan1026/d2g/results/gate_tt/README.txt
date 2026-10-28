ENG-SME_3 D2 CLXIII tower-troop re-baseline
IN PROGRESS. No acceptance claim or score yet.
Pod: root@157.157.221.29 port 33308
New tree: /workspace/d2tt/cb
New facade: /workspace/d2tt/build
Shared read-only library: /workspace/d2/stage/lib
Tables: /workspace/crforge_cache/tables/16.402.22
Original gate: /workspace/d2/gate.sh
Control gate: /workspace/d2tt/gate_ctl.sh
Tower-troop gate: /workspace/d2tt/gate_tt.sh
Outputs: /workspace/d2tt/ev/TAG/TAG_SEED/D3/matches.jsonl
CODE_HEAD:
b24e6b1 + origin/main 2205952dd01c298c9535338b326052481b3e94df: pipeline/crforge_core.py pipeline/tests/test_crforge_core.py scratchpad/gauntlet/L74/crforge/facade/CfCore.java (CRLF, as /workspace/d2/cb)
Facade CfCore.class SHA256:
af4c9d13148ffc204072be7373b1f3be027d34862684d4d83ea549ce761862b2

CPU selection: ps -eo psr,pcpu --no-headers; sum pcpu per 16-core block,
start multiples of 16 with the full block inside 32..247.
C1=64-79 C2=80-95 C3=112-127 C4=160-175
Each selected block sum=0.00; ties ordered by ascending block start.
Prelaunch 1-minute load=43.53; free -g available=197 GB.

Round A start for all four TAGs: 2026-10-28T17:52:15Z
ctl_cf_e4 PID 129086; end pending
ctl_rs_e4 PID 129088; end pending
tt_cf_e4 PID 129090; end pending
tt_rs_e4 PID 129092; end pending
tt_cf_iu40 and tt_rs_iu40 not started.

Evidence and command scripts: .foreman/scratch/a2/sme/s3/
step4_cpu.txt includes initial and final diffs, CODE_HEAD, class hash and CPU snapshot.
cpu_blocks.txt includes all eligible block sums.
round_a_launch.txt and initial_check.txt record launch and checkpoint verification.
check_*.txt contain subsequent full pod check outputs.
Steps 7-9 scripts below are prepared, NOT YET EXECUTED.

Step 4 final diffs (from recorded output):
6c6
< CB=/workspace/d2/cb; PYX=/workspace/venvf16/bin/python; G=icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt
---
> CB=/workspace/d2tt/cb; PYX=/workspace/venvf16/bin/python; G=icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt
11c11
<   CRFORGE_LIB=/workspace/d2/stage/lib CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/d2/build
---
>   CRFORGE_LIB=/workspace/d2/stage/lib CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/d2tt/build
19c19
<   D=/workspace/d2/ev/$TAG/${TAG}_${S}
---
>   D=/workspace/d2tt/ev/$TAG/${TAG}_${S}
12c12
< EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log"
---
> EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --ability-stats --ability-head-decode=sample --crown-log"

Exact commands: round_a.sh
cd /workspace/d2tt || exit 1
mkdir -p ev
date -u +%FT%TZ
(setsid nohup bash gate_ctl.sh crforge ctl_cf_e4 e4 64-79 16 741200 > ev/ctl_cf_e4.out 2>&1 < /dev/null & echo "ctl_cf_e4 PID $!")
(setsid nohup bash gate_ctl.sh royalesim ctl_rs_e4 e4 80-95 16 741200 > ev/ctl_rs_e4.out 2>&1 < /dev/null & echo "ctl_rs_e4 PID $!")
(setsid nohup bash gate_tt.sh crforge tt_cf_e4 e4 112-127 16 741200 742000 743000 744000 > ev/tt_cf_e4.out 2>&1 < /dev/null & echo "tt_cf_e4 PID $!")
(setsid nohup bash gate_tt.sh royalesim tt_rs_e4 e4 160-175 16 741200 742000 743000 744000 > ev/tt_rs_e4.out 2>&1 < /dev/null & echo "tt_rs_e4 PID $!")

Exact commands: round_b.sh
cd /workspace/d2tt || exit 1
grep -q "GATE DONE ctl_cf_e4" ev/ctl_cf_e4.out || exit 1
grep -q "GATE DONE ctl_rs_e4" ev/ctl_rs_e4.out || exit 1
date -u +%FT%TZ
(setsid nohup bash gate_tt.sh crforge tt_cf_iu40 iu40 64-79 16 741200 742000 743000 744000 > ev/tt_cf_iu40.out 2>&1 < /dev/null & echo "tt_cf_iu40 PID $!")
(setsid nohup bash gate_tt.sh royalesim tt_rs_iu40 iu40 80-95 16 741200 742000 743000 744000 > ev/tt_rs_iu40.out 2>&1 < /dev/null & echo "tt_rs_iu40 PID $!")

Exact commands: collect.sh
#!/bin/bash
set -euo pipefail
cd /c/Users/benpe/ClashBot
D=scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt
mkdir -p "$D"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20 -i ~/.ssh/runpod_clashbot -p 33308 root@157.157.221.29)
: > "$D/summaries.txt"
for mode in e4 iu40; do
  for engine in cf rs; do
    tag=tt_${engine}_${mode}
    for seed in 741200 742000 743000 744000; do
      remote=/workspace/d2tt/ev/$tag/${tag}_$seed
      "${SSH[@]}" "cat $remote/D3/matches.jsonl" > "$D/${engine}_${mode}_$seed.jsonl"
      printf '== %s_%s\n' "$tag" "$seed" >> "$D/summaries.txt"
      "${SSH[@]}" "cat $remote/SUMMARY.txt" >> "$D/summaries.txt"
    done
  done
done
for engine in cf rs; do
  tag=ctl_${engine}_e4
  remote=/workspace/d2tt/ev/$tag/${tag}_741200
  "${SSH[@]}" "cat $remote/D3/matches.jsonl" > "$D/${tag}_741200.jsonl"
  printf '== %s_741200\n' "$tag" >> "$D/summaries.txt"
  "${SSH[@]}" "cat $remote/SUMMARY.txt" >> "$D/summaries.txt"
done
wc -l "$D/"*.jsonl

Exact commands: score_all.sh
#!/bin/bash
set -euo pipefail
cd /c/Users/benpe/ClashBot
python scratchpad/gauntlet/L74/plan1026/d2g/score.py "scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt/cf_e4_{s}.jsonl" "scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt/rs_e4_{s}.jsonl" > scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt/score_e4.txt
python scratchpad/gauntlet/L74/plan1026/d2g/score.py "scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt/cf_iu40_{s}.jsonl" "scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt/rs_iu40_{s}.jsonl" > scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt/score_iu40.txt
{
for pair in cf_e4 rs_e4 cf_iu40 rs_iu40; do
  printf '== %s: first = with troops, second = earlier no troops\n' "$pair"
  python scratchpad/gauntlet/L74/plan1026/d2g/score.py "scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt/${pair}_{s}.jsonl" "scratchpad/gauntlet/L74/plan1026/d2g/results/gate/${pair}_{s}.jsonl"
done
} > scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt/troop_effect.txt
python .foreman/scratch/a2/sme/s3/ctl_cmp.py > scratchpad/gauntlet/L74/plan1026/d2g/results/gate_tt/control_cmp.txt

Progress update 2026-10-28T18:26:56Z (supersedes pending entries above):
ctl_cf_e4 end=2026-10-28T18:22:57Z, rows=480
ctl_rs_e4 end=2026-10-28T18:17:38Z, rows=480
tt_cf_iu40 start=2026-10-28T18:26:56Z PID=149315 CPUs=64-79
tt_rs_iu40 start=2026-10-28T18:26:56Z PID=149317 CPUs=80-95
Both IU40 first-line hashes verified against required CLXIII hash.
Both E4 tower-troop jobs finished seed 741200 at 480 rows and started 742000.
Round B command: ssh -o BatchMode=yes -o ConnectTimeout=20 -i ~/.ssh/runpod_clashbot -p 33308 root@157.157.221.29 'bash -s' < .foreman/scratch/a2/sme/s3/round_b.sh
Round A command: ssh -o BatchMode=yes -o ConnectTimeout=20 -i ~/.ssh/runpod_clashbot -p 33308 root@157.157.221.29 'bash -s' < .foreman/scratch/a2/sme/s3/round_a.sh
ENG-SME_3 STATUS: BLOCKED
Scheduled SSH check after check_20261028T183640Z.txt failed, exit 255:
ssh: connect to host 157.157.221.29 port 33308: Connection refused

Ticket says stop and report anything not covered. No reconnect, restart,
process stop, pod stop, source edit, or live-play action was attempted.
Current pod/process state is unknown.
Last successful check: 2026-10-28T18:36:40Z
Controls complete: ctl_cf_e4_741200=480; ctl_rs_e4_741200=480.
Tower troops:
tt_cf_e4 seed741200=480 seed742000=0
tt_rs_e4 seed741200=480 seed742000=189
tt_cf_iu40 seed741200=0
tt_rs_iu40 seed741200=0
Four gate PIDs alive then: 129090, 129092, 149315, 149317.
No output failure markers then; load=139.99; free -g available=166 GB.
No rows collected to laptop. No scores, troop effects or control comparison
results exist; prepared scripts were not executed.
README.txt records provenance, diffs, launches, and prepared commands.
Never rerun these TAGs without confirming their processes are no longer alive.

ENG-SME_3d resume (supersedes previous blocked state):
Start all four TT TAGs: 2026-10-28T18:57:17Z
W=12; C1=144-155 C2=156-167 C3=168-179 C4=180-191
Each selected block sum pcpu=0.000. Snapshot: resume_cpu.txt; ranking: resume_blocks.txt.
2026-10-28T18:57:17Z
tt_cf_e4 PID 3582
tt_rs_e4 PID 3584
tt_cf_iu40 PID 3586
tt_rs_iu40 PID 3588

Exact resume command:
ssh -o BatchMode=yes -o ConnectTimeout=20 -i ~/.ssh/runpod_clashbot -p 33308 root@157.157.221.29 'bash -s' < .foreman/scratch/a2/sme/s3/resume_launch.sh
cd /workspace/d2tt || exit 1
date -u +%FT%TZ
(setsid nohup bash gate_tt.sh crforge tt_cf_e4 e4 144-155 12 741200 742000 743000 744000 >> ev/tt_cf_e4.out 2>&1 < /dev/null & echo "tt_cf_e4 PID $!")
(setsid nohup bash gate_tt.sh royalesim tt_rs_e4 e4 156-167 12 741200 742000 743000 744000 >> ev/tt_rs_e4.out 2>&1 < /dev/null & echo "tt_rs_e4 PID $!")
(setsid nohup bash gate_tt.sh crforge tt_cf_iu40 iu40 168-179 12 741200 742000 743000 744000 >> ev/tt_cf_iu40.out 2>&1 < /dev/null & echo "tt_cf_iu40 PID $!")
(setsid nohup bash gate_tt.sh royalesim tt_rs_iu40 iu40 180-191 12 741200 742000 743000 744000 >> ev/tt_rs_iu40.out 2>&1 < /dev/null & echo "tt_rs_iu40 PID $!")
ENG-SME_3d STATUS: BLOCKED
2026-10-28T20:53Z scheduled SSH check timed out (exit 255).
First five-minute retry succeeded at 2026-10-28T20:58:07Z:
20:58:07 up 4 min, 0 user, load average: 8.51, 3.92, 1.54
All gate processes gone. Container restarted again. No second relaunch attempted.
Evidence: check_20261028T205806Z.txt and resume_restart_logs.txt.
Resume start all four TAGs: 2026-10-28T18:57:17Z.
W=12; C1=144-155 C2=156-167 C3=168-179 C4=180-191.
PIDs launched: 3582 3584 3586 3588.
Both controls: 480 rows each, GATE DONE.
All four TT TAGs: seeds 741200, 742000, 743000 have 480 rows each.
Seed 744000: tt_cf_e4=285; tt_rs_e4=287; tt_cf_iu40=286; tt_rs_iu40=480.
tt_rs_iu40 GATE DONE at 2026-10-28T20:38:46Z.
13/16 tower-troop seed files complete; 3/16 partial.
Steps 7-9 not executed; no win rates, paired deltas or identical counts calculated.
README contains prior provenance/commands and this resume/blocker record.
No pod stop, live-play action, git commit/push/stash/reset, or modification under /workspace/d2/.
