# Gates: pods1020 mechanical setup

OWNS: scratchpad/gauntlet/L74/pods1020/STATUS.md, scratchpad/gauntlet/L74/pods1020/GATES.md, scratchpad/gauntlet/L74/pods1020/prepare.sh, scratchpad/gauntlet/L74/pods1020/verify.sh, scratchpad/gauntlet/L74/pods1020/preflight.py

Scope: stage two new full step-d pods from committed code and established bundles, verify runtime/data/checkpoints/all16 smoke/CUDA, and commit/push the evidence without starting assigned jobs.

Prerequisites: Git Bash, OpenSSH, runpod_clashbot key, Python on the pods.
The independent audit agent is read-only and owns no files or pod mutations.

- [x] G1: P1 has verified committed code, inputs, fin13/fork36 runtimes, CUDA, and a successful all16 smoke
  CHECK: bash scratchpad/gauntlet/L74/pods1020/verify.sh 64.247.206.80 48148
  EXPECT: POD_READY
  EVIDENCE: exit=0; shell=C:\windows\system32\cmd.exe; cwd=C:\Users\benpe\ClashBot; path=48739c576c48/43 entries; EXPECT=matched; output-sha256=ce8a15b3f5a8eb1cd49a0d43cd67e7222d1c588cdece4d6b26eb5ac16e93fffd; output-bytes=585

- [x] G2: P2 has verified committed code, inputs, fin13/fork36 runtimes, CUDA, and a successful all16 smoke
  CHECK: bash scratchpad/gauntlet/L74/pods1020/verify.sh 64.247.206.80 40548
  EXPECT: POD_READY
  EVIDENCE: exit=0; shell=C:\windows\system32\cmd.exe; cwd=C:\Users\benpe\ClashBot; path=48739c576c48/43 entries; EXPECT=matched; output-sha256=45912ac48221a18d3078a31cc0f43fef5dbf84fec0cf68e947b83f9e47d8493b; output-bytes=585

- [x] G3: both pods remain idle for the lead; only the required smokes ran, with no assigned jobs or GO files launched
  EVIDENCE: 2026-10-20 10:40 UTC final G1/G2 verification found no training/evaluation/waiter processes or GO files; original smoke invocations exited zero. Process detection positively observed the smoke trainers at 10:28 UTC (3652/3967). Command audit confirms no arm, fine-tune, evaluation chain, pod stop, or live change.

- [x] G4: readiness evidence and added scripts are committed and pushed using only explicit ticket paths
  EVIDENCE: Commit faa313d contains exactly STATUS.md, prepare.sh, preflight.py, and verify.sh under pods1020; staged count 4, staged secret scan and whitespace check passed. git push origin main succeeded (c78bb52..faa313d). This acceptance ledger is the sole follow-up path.
