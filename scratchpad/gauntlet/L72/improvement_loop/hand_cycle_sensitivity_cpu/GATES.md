# Hand cycle sensitivity gates

OWNS: scratchpad/gauntlet/L72/improvement_loop/hand_cycle_sensitivity_cpu/**

- [x] C1: Fixed-weight matched collection preserves inputs and weights.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_cycle_sensitivity_cpu/collect.py
  EXPECT: HAND_CYCLE_CPU_COLLECTED
  EVIDENCE: l72-hand-cycle-cpu-collect.json, exit0/matched,138.614803s; collected.json.
- [x] V1: Independent original schedule/features/logits/reductions reconcile.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_cycle_sensitivity_cpu/verify.py
  EXPECT: HAND_CYCLE_CPU_VERIFIED
  EVIDENCE: l72-hand-cycle-cpu-verify.json, exit0/matched,10.153172s; verified.json,2positive8corruptions.
- [x] R1: Outside source and receipt review explains limits and next step.
  EVIDENCE: l72-hand-cycle-cpu-reviewed.json, exit0/matched,.922926s; reviewed.json/REVIEW.md.
