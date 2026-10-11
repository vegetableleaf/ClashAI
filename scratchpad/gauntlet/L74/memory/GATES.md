# Gates: match memory phase A

OWNS: pipeline/**, scratchpad/gauntlet/L74/memory/**, HANDOFF.md

Scope: offline implementation, CPU tests, and reviewable pod driver; no SIM or network execution.

- [x] G1: Public history is causal, capped, public-only and identical across adapters.
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/memory/check_offline.py
  EXPECT: MEMORY_OFFLINE_ACCEPTANCE_PASSED
  EVIDENCE: PowerShell; cwd=C:\Users\benpe\cb_memory; exit=0; match=true; output_sha256=7a3246ca16a5e82f137ca88fdff2547e347a2a4fb00f386a73d1795731004d4d; 124 passed, 1 named-pipe test deselected; verification.json and TEST_RESULTS.txt.
- [x] G2: Converted checkpoints preserve every output and flag-off hashes; round trips are strict.
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/memory/check_offline.py
  EXPECT: MEMORY_OFFLINE_ACCEPTANCE_PASSED
  EVIDENCE: PowerShell; cwd=C:\Users\benpe\cb_memory; exit=0; match=true; output_sha256=7a3246ca16a5e82f137ca88fdff2547e347a2a4fb00f386a73d1795731004d4d; 124 passed, 1 named-pipe test deselected; verification.json and TEST_RESULTS.txt.
- [x] G3: Memory-only imitation freezes the base and anchors policy distributions; RL carries histories.
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/memory/check_offline.py
  EXPECT: MEMORY_OFFLINE_ACCEPTANCE_PASSED
  EVIDENCE: PowerShell; cwd=C:\Users\benpe\cb_memory; exit=0; match=true; output_sha256=7a3246ca16a5e82f137ca88fdff2547e347a2a4fb00f386a73d1795731004d4d; 124 passed, 1 named-pipe test deselected; verification.json and TEST_RESULTS.txt.
- [x] G4: Pod driver plans four locked phases, three exploiter cycles, paired yardstick and ablation.
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/memory/check_offline.py
  EXPECT: MEMORY_OFFLINE_ACCEPTANCE_PASSED
  EVIDENCE: PowerShell; cwd=C:\Users\benpe\cb_memory; exit=0; match=true; output_sha256=7a3246ca16a5e82f137ca88fdff2547e347a2a4fb00f386a73d1795731004d4d; 124 passed, 1 named-pipe test deselected; verification.json and TEST_RESULTS.txt.
- [x] G5: Changes preserve existing offline contracts and do not alter live launch scripts or LIVE_OPTIONS.
  EVIDENCE: Offline regression suite passed. Git diff reviewed: GenPilot library adapter only; no live launch scripts or LIVE_OPTIONS changed. No network/SIM/GPU/live action or commits. Temporary test cleanup was blocked by automatic approval review.
- [x] G6: Pod commands, compute estimates and unmeasured runtime limitations are documented.
  EVIDENCE: README.txt records exact launch/converter/check commands, four per-phase compute estimates, disk sizing, locks, receipts, observational limits and unmeasured pod runtime.
