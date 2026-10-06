# Paired hand learning gates

OWNS: scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/learning/**

- [x] P1: Source-bound schedule and qualified public inputs exist before optimization.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/learning/prepare.py
  EXPECT: HAND_LEARNING_PREPARED
  EVIDENCE: prepared.json; l72-hand-learning-prepare exit0/token10.185066s.
- [x] T1: Both registered arms complete exactly1000 finite updates with final-only artifacts.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/learning/train.py
  EXPECT: HAND_LEARNING_TRAINED
  EVIDENCE: trained.json; l72-hand-learning-train exit0/token511.197607s.
- [x] V1: Independent full schedule/log/tensor/optimizer reconciliation passes.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/learning/verify_training.py
  EXPECT: HAND_LEARNING_TRAINING_VERIFIED
  EVIDENCE: training_verified.json; l72-hand-learning-verify_training exit0/token11.786247s;104 states each step1000,1positive7corruptions per arm.
- [x] E1: Each final arm produces exactly54723 development predictions.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/learning/evaluate.py
  EXPECT: HAND_LEARNING_EVALUATED
  EVIDENCE: evaluated.json; l72-hand-learning-evaluate exit0/token360.347511s.
- [x] V2: Independent original-label and per-replay results establish every required verdict and audit slice.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/learning/verify_results.py
  EXPECT: HAND_LEARNING_RESULTS_VERIFIED
  EVIDENCE: results_verified.json; l72-hand-learning-verify_results exit0/token111.251231s;3positive16corruptions. Continuation FAILED, not accepted/deployed.
- [x] R1: Evidence, once-only model report and handoff are reviewed/published.
  EVIDENCE: reviewed_evidence.json/reviewed_results.json/REVIEW.md; reviewed-evidence1.763518s, discord3.080620s, reviewed.257716s all exit0/token;4 HTTP200 parts delivered once. Scoped HANDOFF commit accompanies this ledger.
