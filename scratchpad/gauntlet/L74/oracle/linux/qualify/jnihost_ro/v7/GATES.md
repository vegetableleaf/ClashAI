# Gates: ORACLE v7

OWNS: scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/v7/**

Scope: An offset-free, unpatched staged host, private runtime bindings, single-attempt collector, evidence-bound review and offline verification. Actual Android execution is a separate required gate.

- [x] G1: Default load-only and ordered stop-on-first-failure behavior pass positive and negative offline tests.
  CHECK: python scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/v7/test_v7.py
  EXPECT: ORACLE_V7_TESTS_OK
  EVIDENCE: shell=PowerShell invoking Python directly; cwd=C:\Users\benpe\ClashBot; exit=0; EXPECT matched; output_sha256=f693a52d49de2495551e006b64086209990bc7ecf372de11ca0b863738ebf95e; private log retained under oracle .local/jnihost-v7-final-verification.

- [x] G2: Public source is offset-free and contains no target memory-write or client lifecycle API.
  CHECK: python scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/v7/verify.py
  EXPECT: ORACLE_V7_PRIVACY_OK
  EVIDENCE: shell=PowerShell invoking Python directly; cwd=C:\Users\benpe\ClashBot; exit=0; EXPECT matched; output_sha256=af0a369c45b93c891371895070b848b890db887224a7c001f2a50dd3baab7f1f; private log retained under oracle .local/jnihost-v7-final-verification.

- [x] G3: Both DEX files and the observer compile with the installed offline Android toolchain; import/export and class ownership checks pass.
  CHECK: python scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/v7/check_build.py --build-dir scratchpad/gauntlet/L74/oracle/.local/jnihost-ro-compile-v7-final
  EXPECT: ORACLE_V7_BUILD_HASHES_OK
  EVIDENCE: shell=PowerShell invoking Python directly; cwd=C:\Users\benpe\ClashBot; exit=0; EXPECT matched; output_sha256=afe41c78f0af1fcbcba55dbe9f02ff4fabf4b4a3f4a63b80202dc3974dc2db94; private log retained under oracle .local/jnihost-v7-final-verification.

- [x] G4: Run order, ABI arguments, upstream prerequisite differences, stop semantics and attribution limits are documented against local evidence.
  EVIDENCE: README.md and REVIEW.md checked against upstream lifecycle/native/Java sources, target binding and retained v3/v4 classifications. No runtime claim or patch qualification; bootstrap and Location selector gaps explicit.

- [ ] G5: One isolated Android attempt records the actual last successful stage and first blocker, with receipt-backed attribution or explicit unknown cause.
  EVIDENCE: Required worker handoff; see abandonment below.

- [ ] G6: The worker shell script parses on Linux before the Android attempt.
  CHECK: bash -n scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/v7/worker.sh && echo ORACLE_V7_SHELL_SYNTAX_OK
  EXPECT: ORACLE_V7_SHELL_SYNTAX_OK
  EVIDENCE: Required worker handoff; see abandonment below.

ABANDON: G5 Isolated Linux Android worker unavailable in this Windows session; no network access authorized. Run one README attempt on that worker and retain the first-stop evidence.

ABANDON: G6 Local Git Bash exits before parsing with CreateFileMapping Win32 error 5. Run bash -n on the Linux worker before its attempt.
