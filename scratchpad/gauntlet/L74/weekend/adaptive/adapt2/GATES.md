# Gates: ADAPT2 continuation

OWNS: scratchpad/gauntlet/L74/weekend/adaptive/**, pipeline/tests/test_adaptive_opponents.py

Scope: opt-in continuation, unchanged defaults, isolated ADAPT2 wrapper, offline evidence and exact pod staging instructions. No SIM, network, deployment or commits.

- [x] G1: defaults, checkpoint restoration, pool growth, naming and continuation orchestration pass offline pytest
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/weekend/adaptive/check_offline.py
  EXPECT: ADAPTIVE_OFFLINE_ACCEPTANCE_PASSED
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/wt_adapt2; exit=0; EXPECT matched; 96 passed, 1 existing Windows named-pipe test deselected, 22 transformer warnings, 43.42s. TEST_RESULTS.txt SHA256=07412376ad044d003d1bcfdeeed11ca3a9e910fb02c042c494c8c9bc9e5f2bf6. Golden default plan/config/eval hash was independently captured from git 2bfafbf.

- [x] G2: wrapper preserves the fixed evaluation, wait gate, ordered locks, process budget and failure outputs
  EVIDENCE: Manual source review plus passing pytest contract: wait before GPU then CPU locks, 20 actors/workers with no branch workers, EXIT/INT/TERM failure summary and DONE, original graft/eval/report functions unchanged. LF-only shell verified. Git Bash cannot start (CreateFileMapping error 5), so no executed shell or pod claim. ETA uses ADAPT logs (7.59h roll/update + 1.46h eval plus overhead).

- [x] G3: handoff lists measured laptop file sizes and an exact pod command; changes remain scoped and uncommitted
  EVIDENCE: README.txt and POD_FILES.tsv list the exact launch and 26 measured source/destination/size entries, 748615393 bytes. Real ADAPT main update=60 with 12 snapshots and 3 exploiters; exp1-3 numbered/latest model tensors match at update 15. Ghost pool hash matches ADAPT and frozen split. git diff --check exit=0; status limited to this ticket's driver, test, wrapper and adapt2 evidence folder; HEAD remains 2bfafbf on l74-adapt2. No SIM/network/pod/deployment/commit executed.

Acceptance: 3 met, 0 unmet, 0 abandoned. Shell syntax validation is manual.
