# Hand cycle sensitivity gates

OWNS: scratchpad/gauntlet/L72/improvement_loop/hand_cycle_sensitivity/**

- [ ] C1: Fixed-weight matched collection preserves inputs and weights.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_cycle_sensitivity/collect.py
  EXPECT: HAND_CYCLE_SENSITIVITY_COLLECTED
  EVIDENCE: pending
- [ ] V1: Independent original schedule/features/logits/reductions reconcile.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_cycle_sensitivity/verify.py
  EXPECT: HAND_CYCLE_SENSITIVITY_VERIFIED
  EVIDENCE: pending
- [ ] R1: Outside source and receipt review explains limits and next step.
  EVIDENCE: pending
