# Gates: LIVEPHI

Scope: offline public-state predictor, chronological evaluation, default-off learner integration; no policy training, network or deployment.

- [x] G1: dataset preserves phase_stats selection and labels, match/date isolation and public feature provenance
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/livephi/verify.py dataset
  EXPECT: DATASET VERIFIED
  EVIDENCE: exit=0; matched=true; cwd=C:\Users\benpe\ClashBot; shell=direct Python via PowerShell; output_sha256=a43c2f3f875e16bc82d3e2ce168dc9e5975dd72de8895a9267af43f58f8793c7; receipt=VERIFICATION.json

- [x] G2: CPU predictor and paired evaluation include calibration, jitter, partial dependence and pro checks
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/livephi/verify.py evaluation
  EXPECT: EVALUATION VERIFIED
  EVIDENCE: exit=0; matched=true; cwd=C:\Users\benpe\ClashBot; shell=direct Python via PowerShell; output_sha256=837d3ed82b6932e69d37560b60dacdc6eb58bea62457d054225a6b78f55b53cd; receipt=VERIFICATION.json

- [x] G3: default-off hash parity, frozen loading, causal shaping and terminal potential pass unit tests
  CHECK: research/ext/Royale/.venv/Scripts/python.exe -m pytest pipeline/tests/test_live_phi.py pipeline/tests/test_reward_shaping.py pipeline/tests/test_value_phi.py::TestMath scratchpad/gauntlet/L74/livephi/test_data.py -q -p no:cacheprovider
  EXPECT: /^\d+ passed(?:, \d+ warnings?)? in .+$/m
  EVIDENCE: exit=0; matched=true; cwd=C:\Users\benpe\ClashBot; shell=direct Python via PowerShell; output_sha256=1c47d40beb7e9380465a7e162a69608e8b7a23252c502a037e604186b5055cc2; receipt=VERIFICATION.json

Predeclared verdict: candidate only if paired match-bootstrap AUC difference live_phi minus value_phi has 95% lower bound > 0 overall or 1x; held-out ECE <= 0.05, Brier <= constant training-prior predictor; no positive elixir banking dependence (upper 95% CI of mean P(win) change 5->10 <= 0.01). Otherwise reject. This is an offline diagnostic, never policy-performance evidence.

Protocol: latest calendar-date block nearest 20% is test; latest date block nearest 20% of the earlier matches is validation/calibration. No test-based fitting or tuning. Fixed MLP, 30 epochs maximum, one CPU thread, 540-second training deadline. Bootstrap 500 draws by match, identical draws for all predictors. Draws and post-300-second drain rows excluded. Report all exclusions.
