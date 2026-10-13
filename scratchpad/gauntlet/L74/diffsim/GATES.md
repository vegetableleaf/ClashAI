# Gates: DIFFSIM

OWNS: scratchpad/gauntlet/L74/diffsim/**

Scope: offline differential harness, public adapters, deterministic suites, minimization, attribution and honest progress reports.

- [x] G1: Synthetic comparisons find the first changed field and preserve spawn identities and target references.
  CHECK: python scratchpad/gauntlet/L74/diffsim/verify.py
  EXPECT: DIFFSIM_VERIFIED
  EVIDENCE: shell=PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; EXPECT matched DIFFSIM_VERIFIED; 26 tests, 0 failures/errors/skips, no engine imports; output_sha256=6e179c6e2a76bed8f768a31f26ec4c6c3f3972ab02d3f4659b7aa733497e3614; output_bytes=11746; source hashes in VERIFICATION.json
- [x] G2: FakeEngine planted interaction reduces to a replayable one-minimal scenario; generators and attribution are deterministic.
  CHECK: python scratchpad/gauntlet/L74/diffsim/verify.py
  EXPECT: DIFFSIM_VERIFIED
  EVIDENCE: shell=PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; EXPECT matched DIFFSIM_VERIFIED; 26 tests, 0 failures/errors/skips, no engine imports; output_sha256=6e179c6e2a76bed8f768a31f26ec4c6c3f3972ab02d3f4659b7aa733497e3614; output_bytes=11746; source hashes in VERIFICATION.json
- [x] G3: Adapter contract mocks, legal policy, isolated workers, metrics denominators and dated history pass offline integration tests.
  CHECK: python scratchpad/gauntlet/L74/diffsim/verify.py
  EXPECT: DIFFSIM_VERIFIED
  EVIDENCE: shell=PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; EXPECT matched DIFFSIM_VERIFIED; 26 tests, 0 failures/errors/skips, no engine imports; output_sha256=6e179c6e2a76bed8f768a31f26ec4c6c3f3972ab02d3f4659b7aa733497e3614; output_bytes=11746; source hashes in VERIFICATION.json
- [x] G4: Public API mapping, offline pod launcher and native prerequisites are documented; no engine or live source edits.
  EVIDENCE: Manual source/API review complete. README documents machine/build/schema prerequisites and native partial profile; launcher performs no installation/network/lifecycle actions. Only new diffsim directory written; existing tracked status unchanged and nested RoyaleSim tracked tree clean. Local Bash Win32 error 5 and unavailable fork/native runtime explicitly handed off, not claimed tested.

Runtime qualification is a handoff: neither a Linux fork wheel nor a current native VM is available here. Passing these gates proves the harness tests, not real-game exactness or the wheel sanity run.
