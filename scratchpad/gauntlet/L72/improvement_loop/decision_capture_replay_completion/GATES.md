# Replay completion gates

- [x] P1 Parent registration binds all sources, records, references and receipts.
  EVIDENCE: Registration243de41 binds167 source/artifact files.
- [x] V1 One fresh CPU4 R1e replay verifies both saved sets and all controls.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/decision_capture_replay_completion/verify.py
  EXPECT: DECISION_CAPTURE_REPLAY_COMPLETED
  RECEIPT: l72-decision-capture-replay-completion
  EVIDENCE: l72-decision-capture-replay-completion15.877696s,exit0/token;24cases48records42freshcalls228heads exact.
- [x] R1 Independent source/artifact/receipt review and accurate handoff.
  EVIDENCE: l72-decision-capture-reviewed0.450526s,exit0/token; reviewed.json binds all five prior receipts and both latency failures.
- [ ] L1 Synchronous and async latency qualification.
  EVIDENCE: both prior attempts remain FAILED; this leaf cannot pass L1.
- [ ] A1 Live capture activation and tactical/ladder benefit.
  EVIDENCE: unactivated, live_eligible=false; no tactical/model-strength evidence.
