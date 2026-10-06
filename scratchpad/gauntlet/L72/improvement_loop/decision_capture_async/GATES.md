# Bounded writer gates

- [ ] U1 Bounded queue, stable snapshots, overflow/IO/close and decision preservation
  CHECK: research/ext/Royale/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L72/improvement_loop/decision_capture_async/test_async.py -q
  EXPECT: passed
  EVIDENCE: pending.
- [ ] C1 Same24 original cases exact against reused OFF cache; unchanged latency floor
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/decision_capture_async/qualify.py
  EXPECT: ASYNC_CAPTURE_QUALIFIED
  EVIDENCE: pending.
- [ ] V1 Fresh exact R1e replay and artifact bindings
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/decision_capture_async/replay.py
  EXPECT: ASYNC_CAPTURE_REPLAYED
  EVIDENCE: pending.
- [ ] E1 Isolated entry --check, no capture directory/live actions
  EVIDENCE: pending.
- [ ] R1 Independent evidence/source review
  EVIDENCE: pending.
- [ ] A1 Actual capture activation and tactical comparison
  EVIDENCE: unactivated; owner canonical worker protected.
