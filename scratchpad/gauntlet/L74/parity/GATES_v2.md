# Gates: PARITY v2

OWNS: scratchpad/gauntlet/L74/parity/**

Scope: Default-off mechanics replay, logged own hands, public opponent injection, unsupported-old pairing, complete skip receipts, no-SIM tests and frozen-cohort planning. No network, live scripts, SIM execution or commits.

- [x] G1: Logged-hand construction and cycle-agnostic injection preserve observation timing and public-only inputs.
  CHECK: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/parity/verify_v2.py --tests
  EXPECT: PARITY_V2_TESTS_PASS
  EVIDENCE: Direct user-authorized PowerShell check from C:/Users/benpe/ClashBot; exit 0, PARITY_V2_TESTS_PASS; 27 no-SIM cases. Output SHA256 938547f7dcf9287cc98c488140f33de93e751efa6f6ed37d0210701baa8c92c2. verification_v2.json retains the exact command and output; covers negative controls, repeated plays, snapshot hash validation/rollback, unsupported fallback and common-row pairing.
- [x] G2: Frozen-cohort planning accounts for every match, decision and command, with reasons for every skip.
  CHECK: python scratchpad/gauntlet/L74/parity/verify_v2.py --planning
  EXPECT: PARITY_V2_PLANNING_PASS
  EVIDENCE: Direct user-authorized PowerShell check from C:/Users/benpe/ClashBot; exit 0, PARITY_V2_PLANNING_PASS. Frozen source hashes verified: 100 usable, 32442 decisions, 3594 own commands, 2888 opponent injections, zero planning skips, zero logged next cards. Expected 100 new/fork-only and zero all-three; no SIM evidence claimed. Output SHA256 b7322879922cbd8ecbab2e70d3cbdda6202ff4a44041ae0115cedc14401faf63. planning_v2.json names every match and the hydrated sources.
- [x] G3: Default-off adapter, runtime comparison groups, ranking and pod instructions satisfy the offline scope.
  CHECK: python scratchpad/gauntlet/L74/parity/verify_v2.py --contract
  EXPECT: PARITY_V2_CONTRACT_PASS
  EVIDENCE: Direct user-authorized PowerShell check from C:/Users/benpe/ClashBot; exit 0, PARITY_V2_CONTRACT_PASS. Python AST, default-off flag, retained ranking, launcher and old/new source API contracts checked; engine and harness SHA256 in verification_v2.json. Manual review: all edits confined to parity; no live scripts, engine patches, network or commits; pod command in V2.md. Runtime execution is outside this no-SIM ticket.
