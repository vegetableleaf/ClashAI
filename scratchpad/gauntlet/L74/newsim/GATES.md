# Gates: NEWSIM

OWNS: pipeline/**, scratchpad/gauntlet/L74/newsim/**, scratchpad/gauntlet/L74/weekend/**

Scope: Integrate adaptive training with the opt-in Hero IW runtime, mixed learner pipelining, human census and a failure-safe two-arm pod launcher. No pod launch or deployment.

- [ ] G1: Adaptive branch content is integrated and default-off regressions pass.
  CHECK: python scratchpad/gauntlet/L74/newsim/verify_offline.py pipeline/tests
  EXPECT: NEWSIM_OFFLINE_OK
  EVIDENCE: Content audit verified 65 incoming paths and default-off tests passed. Full-suite check blocked: 12 collection errors; remaining modules yielded 783 passed, 512 failed, 48 skipped. Missing runtime, public catalogs, local fixtures and Windows IPC; details in VERIFICATION.json.

- [x] G2: Seeded learner pipelining, census dedupe and launcher contracts pass offline.
  CHECK: python scratchpad/gauntlet/L74/newsim/verify_offline.py scratchpad/gauntlet/L74/newsim/test_newsim.py
  EXPECT: NEWSIM_OFFLINE_OK
  EVIDENCE: PowerShell in C:/Users/benpe/wt_newsim; verify_offline.py focused run exited 0, NEWSIM_OFFLINE_OK matched; 132 passed, 1 deselected, 24 warnings, 62.97 seconds. Log SHA256 in VERIFICATION.json. Includes all 36 NEWSIM tests.

- [x] G3: Launcher carries smoke, train, graft, paired evaluations, failure receipts and backup checkpoint.
  EVIDENCE: Real driver control flow exercised with fake training/eval stages: 3 cycles, 6 training stages, 16 eval stages, 960 pairs per comparison, final checkpoint and 4 sets of logs inside results. Gate-failure path writes SUMMARY/DONE. Source audit checks no live changes. Actual pod execution is intentionally not this ticket; local Bash cannot initialize under sandbox.

- [x] G4: Census counts, file manifest, ETA and commands are delivered with current evidence and explicit missing inputs.
  EVIDENCE: README.md and NEEDED_FILES.txt contain both arms, 12-16h planning ETA, exact data paths and CSV SHA. Rebuilt CSV: 1064 battles, 2128 sides; offline name check retains 1919 sides/370 decks, drops 209 unknown-card sides. Actual new-runtime rejection counts remain a pod output.

- [ ] G5: The two branch tips are joined by a Git merge commit on l74-newsim.
  EVIDENCE: Git merge refused ORIG_HEAD.lock under protected C:/Users/benpe/ClashBot/.git/worktrees/wt_newsim. Branch remains a10e4fd; incoming 72468ff content is integrated uncommitted. No push.

ABANDON: G1 Full-suite acceptance cannot be certified in this checkout without the missing runtime/catalogs/local fixtures. Do not report a full-suite pass; provision inputs and rerun on an appropriate no-SIM test selection or owner-authorized SIM host.
ABANDON: G5 Linked-worktree Git metadata is read-only and approval is unavailable. Preserve the uncommitted integrated files and finalize merge metadata in a writable session.
