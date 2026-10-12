# Gates: PRO2

OWNS: scratchpad/gauntlet/L74/pro2/**

Scope: offline sanitized replay conversion, existing-format SIM row launcher, tests and measured handoff; no training/config edits or network.

- [x] G1: Two trimmed real fixtures, frame round trips and dedupe pass without SIM.
  CHECK: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/pro2/verify.py --tests
  EXPECT: PRO2_TESTS_PASS
  EVIDENCE: Direct authorized check via PowerShell in C:/Users/benpe/ClashBot, exit 0; PRO2_TESTS_PASS; 20 passed. verification.json records interpreter/command/output SHA256 4a24bf462a1cdeb101c58326d9f068a7422e04602407c9872c2cee9677dda828. No SIM imported.
- [x] G2: All owner input files are accounted for; deck/phase and existing overlap counts are saved.
  CHECK: python scratchpad/gauntlet/L74/pro2/audit.py
  EXPECT: PRO2_SOURCE_AUDIT_PASS
  EVIDENCE: Direct authorized audit via PowerShell in C:/Users/benpe/ClashBot, exit 0; PRO2_SOURCE_AUDIT_PASS. conversion_summary.json: 1083 accounted, 1069 unique new, 14 duplicates, 0 existing ID matches; 1064 CSV-ready. Time-based overlap unavailable on new sources.
- [x] G3: Existing source-to-fv5 chain is documented in ten lines; pod script reports row provenance and fidelity limitations.
  CHECK: python scratchpad/gauntlet/L74/pro2/verify.py --contract
  EXPECT: PRO2_CONTRACT_PASS
  EVIDENCE: Direct authorized verify.py --tests --contract via PowerShell in C:/Users/benpe/ClashBot, exit 0; PRO2_CONTRACT_PASS. verification.json: exactly 10 chain lines, Python compilation succeeds. Synthetic adapter passes unchanged fv5 builder; shell execution and actual SIM remain unverified.
- [ ] G4: Pod SIM execution produces verified rows and divergence measurements.
  EVIDENCE: pending; unavailable runtime, explicitly handed off to pod per ticket.

ABANDON: G4 Simulator runtime unavailable in the laptop sandbox; no network authorized. Pod command and data limitations are in README.md. This is a handoff, not successful row-build completion.
