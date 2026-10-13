# Gates: IWDIAG

OWNS: pipeline/royale_heroiw.py, pipeline/royale_env.py, pipeline/royale_iw_policy.py, pipeline/e1_eval.py, pipeline/search_s0.py, pipeline/tests/test_iwdiag.py, scratchpad/gauntlet/L74/heroiw/diag/**

Scope: Build an offline four-arm diagnostic job and no-SIM verification; execution on the pod is the delivered command.

- [x] G1: Default-off form and press-policy options preserve existing behavior and reproduce live geometry plus hazard semantics
  CHECK: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/heroiw/diag/verify.py --tests
  EXPECT: IWDIAG_TESTS_OK
  EVIDENCE: 2026-10-13; PowerShell; cwd C:/Users/benpe/ClashBot; exit 0; IWDIAG_TESTS_OK matched; 44 passed in 6.14s with engine-import guard; output SHA256 b7fca30ab30f2ed01ba4a17393c35c566695665d09ea0d6e67ee597d7560f4c5.

- [x] G2: Four-arm paired schedule, metrics, failure handling and source evidence pass offline checks
  CHECK: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/heroiw/diag/verify.py
  EXPECT: IWDIAG_OFFLINE_OK
  EVIDENCE: 2026-10-13; PowerShell; cwd C:/Users/benpe/ClashBot; exit 0; IWDIAG_OFFLINE_OK matched; output SHA256 00a765a33f1c575f2f628b08ac18646bc5d41006a7f9444b8ac145d6a7d2e79e; real local input hashes and archived HEROIW schedule agree. Mock dispatch tests verify receipt rejection/no DONE on failure. Exact X-Bow damage is unavailable; labeled public impact proxy is documented. Bash parser blocked by sandbox CreateFileMapping error 5; static shell assertions pass.

- [x] G3: Device cost finding and reviewed pod launch instructions document limitations and ETA
  EVIDENCE: device_cost.json reproduces device-update ability ManaCost 2, APK-fallback deploy ManaCost 3, and selected SIM source cost 2; README documents runtime paths, flock, 25-worker cap, 1.5-3.1h estimated budget, pending pod execution, and public X-Bow attribution limitation. Live-reader git diff is empty. 3 gates met, 0 unmet, 0 abandoned; these are build/offline gates, not pod-performance acceptance.
