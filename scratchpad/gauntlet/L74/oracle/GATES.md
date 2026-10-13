# Gates: ORACLE Linux port

Historical v1 ledger. The refined boundary and current stop are recorded in
GATES_V2.md and V2_REPORT.md; v1 abandonment reasons do not describe v2 authority.

OWNS: scratchpad/gauntlet/L74/oracle/**, scratchpad/gauntlet/L70/reader/oracle_160402012/**

Scope: audit the native sandbox, document and implement only the Linux operations compatible with the owner's unmodified-code and offline constraints, and define native acceptance for build 160402012.

- [x] G1: PORT.md records the Windows lifecycle, Linux equivalents and every identified build dependency with source evidence.
  EVIDENCE: Manual source review, PORT.md deployment table/dependency register, private hashed inventory of all numeric source sites. Semantic completeness of a future ABI mapping is expressly not claimed.
- [ ] G2: Linux entry points are idempotent, logged, syntax checked, and fail closed before unsupported native execution.
  EVIDENCE: Source-reviewed preparation and exit-78 stop scripts written. Git Bash could not start: CreateFileMapping Win32 error 5. bash -n, shellcheck and VM execution remain unverified, with exact worker commands in PORT.md.
- [x] G3: Static derivation artifacts remain private and ignored; no offsets or third-party binaries enter deliverable public files.
  CHECK: python -X utf8 scratchpad/gauntlet/L74/oracle/verify_artifacts.py
  EXPECT: ORACLE_STATIC_CHECKS_PASS
  EVIDENCE: Inspected check executed manually from repository root via PowerShell, exit 0, success token matched. VERIFICATION.json and private privacy_receipt.json; known-positive address and tracked-file negative controls passed. No unlazy runner approval or runner receipt is claimed.
- [x] G4: Acceptance specifies native observations, build identity, own upstream acceptance suites and independent same-seed trace comparisons.
  EVIDENCE: Manual protocol/source review against ACCEPTANCE.md: identity/isolation, three upstream suites, reset and cold-process comparisons, explicit canonicalization, seed/action negative controls. No native execution claimed.
- [ ] G5: Build 160402012 runs on the KVM VM with native reproducibility demonstrated.
  EVIDENCE: Documented direct initialization writes original library code, including a persistent resource shim. User requires unmodified execution. No qualified alternative, target bindings, VM connection or native test. deploy/health stop with exit 78.

ABANDON: G2 Local Bash startup is denied by Windows sandbox; VM syntax, shellcheck and runtime validation are a required handoff, not a pass.
ABANDON: G5 Native deployment stopped at the owner's unmodified-libg constraint; no patch/bypass update or native execution was performed.
