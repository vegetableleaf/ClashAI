# Gates: ORACLE v2

OWNS: scratchpad/gauntlet/L74/oracle/**, scratchpad/gauntlet/L70/reader/oracle_160402012/**

Scope: privately derive the documented execution chain for build 160402012; qualify presentation patches before enabling deployment; stop on any forbidden requirement.

- [x] G1: Every requested lifecycle item has a private value or explicit unresolved status, confidence and source evidence.
  EVIDENCE: V2_REPORT.md per-item register and private runtime-160402012-x86_64.json record static identities/candidates and all unresolved items. This is evidence coverage, not completion of all derivations.
- [ ] G2: Every patch has callers, strings, write-effect classification and verified original bytes; no forbidden patch is required.
  EVIDENCE: Eleven target code sites remain unqualified. Upstream nativeStep explicitly writes a mixed core/presentation dispatch gate. User stop condition reached; no target patch applied.
- [ ] G3: A complete versioned private binding and Linux deployment use independently qualified target values without old-build fallbacks.
  EVIDENCE: Partial upstream-envelope binding explicitly non-deployable. Scripts retain exit 78 with corrected v2 stop reason. Bash startup failed with CreateFileMapping Win32 error 5; shellcheck unavailable. No executable binding or launcher claimed.
- [x] G4: Acceptance covers upstream suites, repeated same-seed traces, cold/reset equivalence and negative controls.
  EVIDENCE: ACCEPTANCE.md revised to refined boundary; V2_REPORT.md preserves suite names, pair comparison, ten-reset/ten-cold campaign and negative controls. Contract only; no runtime pass.
- [x] G5: Private values remain ignored and public deliverables remain offset-free.
  CHECK: python scratchpad/gauntlet/L74/oracle/verify_v2.py
  EXPECT: ORACLE_V2_STOP_EVIDENCE_PASS
  EVIDENCE: Inspected standalone check run manually under PowerShell from repository root; exit zero and token matched. VERIFICATION_V2.json contains source/export/privacy checks and file hashes. No unlazy-runner approval/receipt claimed.
- [x] G6: VM run order is exact and native results are either evidenced or explicitly unexecuted.
  EVIDENCE: V2_REPORT.md gives offline preflight commands ending at the expected deployment stop. It explicitly states no valid native launch order exists yet and marks future acceptance commands conditional. VM and native tests not run.

ABANDON: G2 User stop condition reached: literal upstream path writes mixed native tick/presentation dispatch state; presentation-only classification not established.
ABANDON: G3 A deployable port cannot be emitted after the stop condition; complete mappings, ABI and presentation proofs remain required handoff work.
