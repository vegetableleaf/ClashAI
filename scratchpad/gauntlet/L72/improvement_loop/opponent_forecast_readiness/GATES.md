# Opponent forecast readiness gates

OWNS: scratchpad/gauntlet/L72/improvement_loop/opponent_forecast_readiness/**

- [ ] C1: New training-only targets/history preserve provenance and all exclusions.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/opponent_forecast_readiness/collect.py
  EXPECT: OPPONENT_FORECAST_TARGETS_COLLECTED
  EVIDENCE: pending
- [ ] V1: Independent raw joins/prefixes/replay counts and leakage controls match.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/opponent_forecast_readiness/verify.py
  EXPECT: OPPONENT_FORECAST_TARGETS_VERIFIED
  EVIDENCE: pending
- [ ] R1: Outside evidence review publishes limitations and the next supported work.
  EVIDENCE: pending
