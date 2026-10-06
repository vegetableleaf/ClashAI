# Public decision capture gates

OWNS: scratchpad/gauntlet/L72/improvement_loop/decision_capture/**

- [x] U1 Public schema, failures, caps, mutation and hooks qualified
  CHECK: research/ext/Royale/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L72/improvement_loop/decision_capture/test_capture.py scratchpad/gauntlet/L72/improvement_loop/decision_capture/test_entry_capture.py -q
  EXPECT: passed
  EVIDENCE: l72-decision-capture-unit,42passed,8.418439s,exit0/token.
- [ ] C1 Exact captureOFF/ON engineering workload and fixed latency floor
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/decision_capture/qualify.py
  EXPECT: DECISION_CAPTURE_QUALIFIED
  EVIDENCE: l72-decision-capture-qualify13.676313s exit1 at final latency;24cases
  exact but overhead median9.786750/p9512.199670/max12.854100ms fails2/5/20.
  ABANDON: C1 synchronous storage failed frozen latency. Preserve all artifacts.
- [ ] V1 Fresh-process exact R1e replay and independent corruption rejection
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/decision_capture/replay.py
  EXPECT: DECISION_CAPTURE_REPLAYED
  EVIDENCE: pending.
- [ ] R1 Independent evidence and entry/source review
  EVIDENCE: pending read-only reviewer and bound completion receipt.
- [ ] E1 Actual isolated entry --check binds qualified R1e/settings without capture directory or live launch
  EVIDENCE: pending l72-decision-capture-entry receipt after exact replay.
- [ ] A1 Activation and strategic effect
  EVIDENCE: unactivated; no stronger-policy or ladder claim from engineering work.
