# Gates: PARITY offline triage

OWNS: scratchpad/gauntlet/L74/parity/**

Scope: classify eight saved mismatch groups, repair opt-in public replay planning, re-plan the frozen cohort, quantify error growth, document evidence and a pod rerun, and leave changes uncommitted.

- [x] G1: Synthetic artefact rules and existing harness regression tests pass.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/parity/verify_triage.py
  EXPECT: PARITY_TRIAGE_TESTS_PASS
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; PARITY_TRIAGE_TESTS_PASS matched; 50 passed; output_sha256=3c6ba5ae9fe18e9b0890a2450bd599bbd3e9be0056dfc4ca8673c583fd27bff6; receipt=triage/verification.json

- [x] G2: Offline cohort analysis accounts for every changed injection and produces age and match-time metrics with trace receipts.
  CHECK: python scratchpad/gauntlet/L74/parity/triage_analysis.py --verify
  EXPECT: PARITY_TRIAGE_VERIFIED
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; PARITY_TRIAGE_VERIFIED matched; output_sha256=9edce1a1e93780eca8677531c13a4499b644fd830752e2be15e73bd4a686f5a4; receipt=triage/analysis_verification.json; driver plan also verified 100/100

- [x] G3: TRIAGE.md classifies all eight groups, separates confirmed findings from hypotheses, and contains the Phase 5 lookup list and executable pod command.
  EVIDENCE: Manual review of TRIAGE.md against source trace excerpts E1-E8: eight classifications, empty confirmed mechanic list, hypotheses and Phase 5 lookups, uncertainty and pod command documented; all eight excerpt IDs checked.

- [x] G4: Changes stay in the offline harness, use only public observations, remain default-off and uncommitted; no network, live or SIM-source changes.
  EVIDENCE: Manual scope review: all writes are under scratchpad/gauntlet/L74/parity; git diff --check exit0; flags default off covered by synthetic regression; no network tools, live execution, SIM-source writes, commit or pod launch. Remaining exact-timing/identity limits are explicit in TRIAGE.md.
