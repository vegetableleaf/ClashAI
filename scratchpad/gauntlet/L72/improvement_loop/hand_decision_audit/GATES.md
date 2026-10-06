# Cached hand decision audit gates

OWNS: scratchpad/gauntlet/L72/improvement_loop/hand_decision_audit/**

- [ ] C1: New cached row effects and complete replay summaries are source-bound.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_decision_audit/collect.py
  EXPECT: HAND_DECISIONS_COLLECTED
  EVIDENCE: pending
- [ ] V1: Independent scalar reconstruction matches every row and count and rejects corruptions.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_decision_audit/verify.py
  EXPECT: HAND_DECISIONS_VERIFIED
  EVIDENCE: pending
- [ ] R1: Review binds completed evidence and explains limits and next work.
  EVIDENCE: pending
