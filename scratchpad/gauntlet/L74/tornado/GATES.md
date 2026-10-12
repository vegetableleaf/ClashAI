# Gates: L74 learned Tornado fix

OWNS: pipeline/pending_states.py, pipeline/train_pending.py, pipeline/tests/test_pending.py, pipeline/tests/test_tornado_driver.py, scratchpad/gauntlet/L74/tornado/**

Scope: Offline implementation and no-SIM verification; pod measurements are produced only when the supplied job is run.

- [x] G1: Synthetic extraction preserves fast-follow pro labels, excludes waits and respects the inclusive boundary.
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_pending.py
  EXPECT: /8 passed, [0-9]+ warnings in [0-9.]+s/
  EVIDENCE: Verified by the final combined pytest run (51 passed, 6 skipped, exit 0), including all eight pending tests; TEST_RESULTS.txt records command/environment. Real corpus extraction also reproduced the supplied Icebow mix.

- [x] G2: Head-only gradients, ordinary-state KL, held-out drift and unchanged default behavior pass CPU checks.
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_pending.py
  EXPECT: /8 passed, [0-9]+ warnings in [0-9.]+s/
  EVIDENCE: Final combined pytest run, exit 0. Real head-only AdamW updates leave frozen state bitwise equal; positive KL gradient, strict drift bound, rejected-checkpoint negative control, saved/reloaded checkpoint and import/default parity passed.

- [x] G3: Pod plans pair both opponents and pipeline modes; incomplete or inferior results cannot yield candidate.
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_tornado_driver.py
  EXPECT: /5 passed in [0-9.]+s/
  EVIDENCE: Final combined pytest run, exit 0, all five driver tests passed. Negative controls cover setup/weight/mode mismatches, incomplete comparisons, inferior ordinary play, excessive Tornado and missing fast-follow evidence. No simulator used.

- [x] G4: Pod commands, never-deploy behavior, local measurements and execution limitations are documented.
  EVIDENCE: README.txt reviewed against the ticket and driver. Independent checkpoint load confirms 8,380 trainable parameters. local_pending.json records all measured extraction counts and source hash. No production entry point was edited. Bash startup blocked by Windows sandbox; syntax execution explicitly remains pod preflight, not a claimed local result.
