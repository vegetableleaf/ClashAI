# Gates: SCALE measurement harness

OWNS: scratchpad/gauntlet/L74/scale/**

Scope: Offline, uncommitted four-arm IL measurement on one L40; no network, deployment, or live edits.

- [x] G1: CPU tests prove arm construction, default-off feature identity, public causal inputs, metrics, paired verdicts, and failure receipts.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L74/scale/test_scale.py -q -p no:tmpdir -p no:cacheprovider
  EXPECT: passed
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; 15 passed; output SHA256=6aa8afea04e6db92828fa0779b47b11dac29b6a4a5cf57c0569592ff21778941; VERIFICATION.json tests.
- [x] G2: Stored native recordings establish the richer-field choice and row alignment on real fv5 rows.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/scale/scale.py --audit-only --out scratchpad/gauntlet/L74/scale/local_audit
  EXPECT: SCALE_AUDIT_PASS
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; SCALE_AUDIT_PASS; report SHA256=b47cb640ee6d2c23a124504016e19bb3826532409e050332983a59c4d43fd706; six source hashes rechecked; VERIFICATION.json real_audit.
- [ ] G3: Pod launcher writes verdict-first SUMMARY.txt and DONE on success and catchable failure, with checkpoints, predictions, logs, provenance, and ETA.
  EVIDENCE: Python driver success/failure and checkpoint receipts passed CPU integration; launcher source reviewed, but local Bash could not start (Win32 error 5).
- [ ] G4: One L40 completes the matched training and final measurements in /workspace/results/SCALE.
  EVIDENCE: pending pod execution; this Windows workspace has no local L40 or /workspace results mount and network is prohibited

ABANDON: G3 Linux launcher runtime verification requires the pod; local Git Bash cannot start due to CreateFileMapping Win32 error 5. Python driver receipt tests passed.
ABANDON: G4 L40 measurements cannot run on the local RTX 5050 and the owner prohibits network access. Prepared command and ETA are in README.md; no deployment or remote job launched.
