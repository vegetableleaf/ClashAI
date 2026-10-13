# ORACLE v3 gates

OWNS: scratchpad/gauntlet/L74/oracle/**, scratchpad/gauntlet/L70/reader/oracle_160402012/runtime-160402012-x86_64.json, scratchpad/gauntlet/L70/reader/oracle_160402012/v3_evidence.json, scratchpad/gauntlet/L70/reader/oracle_160402012/v3_data.json

Scope: Offline target derivation under the clarified data scheduling boundary; a deployable binding or explicit evidence gaps and VM observations.

- [x] G1: Every requested lifecycle item has target evidence, confidence, and an explicit unresolved observation where needed.
  EVIDENCE: V3_REPORT item table; private consolidated binding has all 18 required identities with high static evidence and runtime_verified false. Parent reviewed native map chain, loading completion, outer replay wrapper and indirect control allocation/core branch; independent DataTables review verified arguments and arithmetic.
- [x] G2: All eleven presentation/shim sites have evidence-based classification or an investigated permitted alternative.
  EVIDENCE: V3_REPORT site table and private leaf1 result: 1 local presentation proof, 5 likely rendering with incomplete proof, 5 unresolved. Alternatives and exact settling observations retained for every row. No qualified patches or replacement bytes.
- [x] G3: Deployment and health are coded to fail closed; Python preflight rejects incomplete/spoofed bindings and scheduling itself is no longer prohibited.
  EVIDENCE: common.sh/deploy.sh/health.sh reviewed; verify_v3.py passes eight preflight subprocess cases with actual returncode 78. Python gate explicitly permits scheduling data. Shell execution is separately unverified under G6.
- [x] G4: Derived values remain ignored, original captures remain unchanged, and no forbidden operation or network access occurs.
  EVIDENCE: verify_v3.py passed private ignore/untracked checks, public literal scan with positive control, source/export/retained evidence hashes and all 11 original capture-region hashes; execution audit contains no target loading, patching, network, unpack/decryption or commit.
- [x] G5: Public report gives status, item table, site classifications, exact blockers, and offline VM run order.
  EVIDENCE: V3_REPORT.md reconciled with binding and measured VERIFICATION_V3.json; current public and private entrypoints distinguish historical v2 from v3. VM observations and bridge implementation gaps are explicit.
- [ ] G6: Linux shell syntax and actual deploy/health exit behavior are verified.
  EVIDENCE: Git Bash failed before parsing with CreateFileMapping / Win32 error 5; shellcheck unavailable. Python preflight is verified but cannot certify Linux shell execution. Exact VM commands are in V3_REPORT.md.

ABANDON: G6 Host shell startup fails before parsing; run Bash syntax, shellcheck and actual exit-78 checks on the offline VM. This is a verification handoff, not a native PASS.
