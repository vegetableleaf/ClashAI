# Gates: adaptive opponents

OWNS: pipeline/adaptive_opponents.py, pipeline/rl_royale.py, pipeline/rl_royale.yaml, pipeline/e1_eval.py, pipeline/tests/test_adaptive_opponents.py, scratchpad/gauntlet/L74/weekend/adaptive/**

Scope: default-off PFSP and opponent styles, persisted league state, a bounded exploiter driver, and public-history findings. No SIM, network, deployment, or live-file edits.

- [x] G1: offline tests cover ratings, sampling, styles, resume state, cycles, default hashes and public history
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/weekend/adaptive/check_offline.py
  EXPECT: ADAPTIVE_OFFLINE_ACCEPTANCE_PASSED
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/cb_drills2; exit=0; EXPECT matched; 87 passed, 1 deselected (sandbox named-pipe test), 22 existing transformer warnings; TEST_RESULTS.txt SHA256=c1117df97cd0f56725a29cd0521e33522b1b31602adaf1dd3b14cc5adda1eaa6, 1556 bytes. HEAD YAML config_sha equals working YAML config_sha=c34d81fc42252b0f2e8df5169e5718df0199309569ba4d9f2cfe3d7c65ef22e2.

- [x] G2: pod driver shell syntax and wait/lock/failure contract reviewed
  EVIDENCE: Manual review of all 30 shell lines: balanced quotes, substitutions, function, if/elif/fi and while/done; LF bytes verified. Automated contract test passed for ICEBOW_DONE before GPU/CPU flock and EXIT/TERM traps writing SUMMARY/DONE. Bash/WSL cannot start in this sandbox; no parser or pod-runtime pass claimed.

  Validation method change: Git Bash fails at CreateFileMapping (Win32 error 5)
  and WSL fails E_ACCESSDENIED before reading the script. Shell syntax is a
  manual review here; the pytest shell contract test checks sentinel order,
  lock order, EXIT/TERM traps, SUMMARY and DONE paths. No bash execution or
  simulator execution is claimed. This does not gate pod performance evidence.

- [x] G3: driver and history report satisfy owner constraints on inspection
  EVIDENCE: README.txt traces 3-play opp_past and 8-distinct-card opp_cycle to dataset/model/public-observer code; no shape change. Mocked full driver verifies three 20/15 cycles, immutable frozen-main hashes, fast-base exploiter resets, external enrollment, restart and 960-pair report; CAL flags independently compared to cal_run.sh. Driver uses 20 workers, public counters, 60 percent unfavourable census, old-live graft and fixed set-c T=.1. git diff --check exit=0; no live scripts/LIVE_OPTIONS edited, no SIM/network/deployment/commit executed.

Acceptance: 3 met, 0 unmet, 0 abandoned. Shell validation is explicitly manual.
Housekeeping: host approval policy rejected recursive removal of test_tmp;
nonrecursive removal also hit directory ACL errors. Empty failed-test temp
directories remain under this adaptive directory; they contain no deliverables.
