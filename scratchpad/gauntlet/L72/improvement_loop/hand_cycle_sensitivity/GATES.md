# Hand cycle sensitivity gates

OWNS: scratchpad/gauntlet/L72/improvement_loop/hand_cycle_sensitivity/**

- [ ] C1: Fixed-weight matched collection preserves inputs and weights.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_cycle_sensitivity/collect.py
  EXPECT: HAND_CYCLE_SENSITIVITY_COLLECTED
  EVIDENCE: l72-hand-cycle-collect.json exit1/67.989497s; exact blind output control failed. FAILURE.md/DIAGNOSIS.md.
- [ ] V1: Independent original schedule/features/logits/reductions reconcile.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_cycle_sensitivity/verify.py
  EXPECT: HAND_CYCLE_SENSITIVITY_VERIFIED
  EVIDENCE: pending
- [ ] R1: Outside source and receipt review explains limits and next step.
  EVIDENCE: pending

ABANDON: C1 Original collection failed the exact blind gate equality check; sources and partial outputs preserved.
ABANDON: V1 No complete collection exists; independent check was not launched.
ABANDON: R1 No successful chain exists to close; separate CPU successor is not an original pass.
