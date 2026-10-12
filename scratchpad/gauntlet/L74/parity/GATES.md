# Gates: PARITY foundation

OWNS: scratchpad/gauntlet/L74/parity/**, pipeline/royale_runtime.py

Scope: local upstream-tracking fork, default-off runtime, public replay comparison, offline tests and pod launcher; no live edits, network, commits or pushes.

- [x] G1: Local clashbot branch starts at cached origin/HEAD with no mechanics patches.
  CHECK: python scratchpad/gauntlet/L74/parity/verify.py --fork
  EXPECT: PARITY_FORK_PASS
  EVIDENCE: Direct authorized PowerShell check, C:/Users/benpe/ClashBot, exit 0, PARITY_FORK_PASS. HEAD=cacb7005f0e441797c533e91ab4f44820f9919d4 equals cached origin/HEAD; tracked tree clean, zero patches. verification.json binds the receipt.
- [x] G2: Extraction, identity matching, errors, ranking and runtime isolation pass without SIM.
  CHECK: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/parity/verify.py --tests
  EXPECT: PARITY_TESTS_PASS
  EVIDENCE: Direct authorized PowerShell check, C:/Users/benpe/ClashBot, exit 0, PARITY_TESTS_PASS, 17 pytest cases. verification.json records the exact command and output SHA256. Additional existing runtime-selection regression: 5 passed, 14 deselected, no SIM. Initial pytest temp-directory permission failure was fixed by using a scoped ordinary fixture directory; no engine success is claimed.
- [x] G3: Real public logs produce a deterministic selected cohort and disclose reconstruction gaps.
  CHECK: python scratchpad/gauntlet/L74/parity/verify.py --selection
  EXPECT: PARITY_SELECTION_PASS
  EVIDENCE: Direct authorized PowerShell check, C:/Users/benpe/ClashBot, exit 0, PARITY_SELECTION_PASS. 100 matches, 12 exclusions, 32442 decision ticks, 3594 own confirmed plays, 2888 enemy proxies; 34 complete public deck candidate pairs, 66 incomplete. verification.json records every selected source hash and cohort hash 6802002005bf23e81f185e6f4baaa99f3fa851d6e71f49493508eaabb274be8b. Assumed level 15 is explicitly not measured truth.
- [x] G4: Offline build and bounded pod launcher, patch evidence workflow and limitations are documented.
  CHECK: python scratchpad/gauntlet/L74/parity/verify.py --contract
  EXPECT: PARITY_CONTRACT_PASS
  EVIDENCE: Direct authorized PowerShell contract check, C:/Users/benpe/ClashBot, exit 0, PARITY_CONTRACT_PASS; Python syntax and source contracts pass, file hashes in verification.json. Manual source review confirms offline dependencies, fresh output, flock, max 24 workers, failure SUMMARY/DONE, pin provenance and patch evidence workflow. Bash failed before parsing with CreateFileMapping/Win32 error 5; actual execution belongs to G5.
- [ ] G5: Linux wheels build and all three actual engines produce parity measurements on pod.
  EVIDENCE: pending; runtime execution requires a provisioned Linux pod; this ticket forbids network.

ABANDON: G5 No Linux pod/runtime execution was authorized or available under the no-network constraint; local Bash could not start (Win32 error 5). FORK.md supplies offline build/run commands, prerequisites, ETA and data limits. This is an explicit runtime-validation handoff, not passing parity measurements.
