# Parity round-7 CLOSER (headless API-key worker; the lead's session is at its usage cap)

Repo C:\Users\benpe\ClashBot (Windows laptop; Git Bash). Round 7 = four diagnosis buckets plus verifiers, run as a Workflow in the
lead's session (run wf_21fd22dc-130; journal C:\Users\benpe\.claude\projects\C--Users-benpe-ClashBot\f4e7cd66-2122-4134-a1d2-d45291b5bc2a\subagents\workflows\wf_21fd22dc-130\journal.jsonl).
Those workers may die with that session. Your job: make sure round 7's work is not lost.

1. WAIT before touching anything. Wait until the journal has a final result for every bucket (r7a, r7b, r7c, r7d) and their
   verifiers, OR until no file under scratchpad/gauntlet/L74/parity/diag_night/r7*/ and no /workspace/w_r7*, /workspace/results/r7*,
   /workspace/results/v7_* on pods P1 (216.81.151.5:15617) and P3 (64.247.206.76:19899) has changed for 60 minutes.
   - Poll every 10 minutes.
   - ssh -i ~/.ssh/runpod_clashbot root@HOST -p PORT
2. Collect everything into scratchpad/gauntlet/L74/parity/diag_night/R7_SUMMARY.md:
   - from the journal results and, where missing, from the r7* dirs and pod result dirs: each bucket's patches, measured both
     cohorts vs FIN12, verifier verdicts
3. LAND only patches with an independent 'land' verdict. For a patch with no verifier, verify it yourself first:
   - apply it on a clean HEAD tree
   - `grep '^-[^-]' X.patch | grep -oE 'H-[A-Z-]+'` must print nothing
   - re-run its arm on the affected logs on a pod vs FIN12 with diag_night/r5c/cmp.py (STAMPED=1 and 0)
   - more up than down; every break explained, or noise (ceiling <= 0.75)
   Harness patches: apply in sequence to scratchpad/gauntlet/L74/parity/fights.py (+ tests), pyflakes, parity tests on a pod
   (PYTHONPATH=<tree>:/workspace/pyt ... pytest; 5 bundle-only failures are known), then commit with explicit paths + a HANDOFF
   entry via scratchpad/gauntlet/L74/parity/night1016/add_handoff.sh ENTRY "subject", and push.
   Fork patches: git am onto the clashbot36 branch in the worktree C:/Users/benpe/rsfork36 (head a697d1f9; append-only conflicts:
   keep both sides), cargo test on P3 with disk guards (keep >= 8 GB free; delete your target dir), and bundle to
   C:/Users/benpe/AppData/Local/Temp/claude/parity1016/clashbot36_fin14.bundle.
4. Then FIN13: HEAD code + the new fork wheel + all new captures (export_incr.py in
   C:\Users\benpe\AppData\Local\Temp\claude\C--Users-benpe-ClashBot\f4e7cd66-2122-4134-a1d2-d45291b5bc2a\scratchpad\; the recipe is
   in HANDOFF's FIN11 / FIN12 entries). Score --stamped, run coverage.py, and record the numbers in HANDOFF.
Rules:
- never stop a pod, and never arm a watchdog / deadline / runpodctl timer
- never touch the live process, MuMu, LIVE_OPTIONS or CKPT_OVERRIDE
- never run "python -" (hook-blocked)
- kill only by exact PID, after checking what the process is
- the laptop is CPU-starved: heavy work on pods
- never commit secrets; never commit HANDOFF.md's stale working copy: add_handoff.sh works from HEAD
- write progress to diag_night/R7_STATUS.md
Final output: a plain-English report.
