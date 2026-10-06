# Hand and retention integration gates

OWNS: pipeline/model_tower.py, pipeline/model_gen.py, pipeline/opponent_hand_v2.py, pipeline/model_hand_belief.py, pipeline/model_hand_belief_v2.py, pipeline/live_hand.py, pipeline/live_hand_v2.py, pipeline/tests/test_hand_integration.py, scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/**

- [x] L1: Explicit candidate loading preserves frozen tower predictions and legacy behavior and rejects malformed architecture state.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/check_loader.py
  EXPECT: TOWER_LIVE_LOADER_VERIFIED
  EVIDENCE: loader_verified.json; l72-tower-live-loader and l72-tower-live-check-v2 exit0/token.
- [x] H1: Mirror/event/hand features respect current memory schemas, uncertainty, causality and privacy.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/check_hand.py
  EXPECT: HAND_SUCCESSOR_VERIFIED
  EVIDENCE: l72-hand-successor exit0/token, eight tests; live event completeness remains conditional.
- [x] S1: Original expert sequences and public beliefs are joined and independently verified without future/private input.
  EVIDENCE: sequence_data/reviewed.json; 268718 rows, all labels/features/windows/replays exact.
- [x] M1: Versioned learned representation preserves initial eligible-parent predictions and supports strict load/save/live inputs.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/check_model_v4.py
  EXPECT: HAND_MODEL_QUALIFIED
  EVIDENCE: model_verified.json; l72-hand-model-qualified-v4 exit0/token127.186727s,512 row/orientation/arm comparisons,9malformed controls. All three old failures preserved.
- [x] T1: Frozen matched training/evaluation and independent recount establish the candidate's complete verdict.
  EVIDENCE: learning/reviewed_evidence.json and REVIEW.md;1000 updates per arm,104 optimizer states each,54723 predictions each, all original labels/per-replay counts verified. Candidate continuation FAILED, not accepted/deployed.
- [x] R1: Publish verified results, once-only new-model report and accurate remaining work.
  EVIDENCE: learning/reviewed_results.json; four HTTP200 report parts delivered once13:38:31EDT, exact text/IDs/receipts bound. HANDOFF and scoped commit accompany ledger. All broader final acceptance work remains OPEN.
