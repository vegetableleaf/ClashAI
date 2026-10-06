# Reader character identity gates

- [x] C1 Original-byte census and separate decoder qualification
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L71/integration/run_check.py --name l72-reader-character-identity --expect READER_CHARACTER_IDENTITY_VERIFIED -- research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/reader_character_identity/qualify.py
  EXPECT: READER_CHARACTER_IDENTITY_VERIFIED
  Evidence: l72-reader-character-identity,19.644861s,exit0/token; verified.json.
- [ ] V1 Actual public-adapter/body/event and catalog protection checks
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L71/integration/run_check.py --name l72-reader-character-adapter --expect passed -- research/ext/Royale/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L72/improvement_loop/reader_character_identity/test_adapter.py -q
  EXPECT: passed
  ABANDON: V1 original suite failed its final lifecycle card-slug assertion;
  19passed/1failed. Original source/output/receipt retained,9.785971s,exit1.
- [x] V2 Separate lifecycle completion using canonical engine key
  Evidence: LIFECYCLE_RECOVERY.md; only the failed case rerun with corrected
  reference in test_lifecycle_v2.py,6.929660s,exit0,1passed. The19passed tests were
  not repeated. Original V1 failure remains.
- [x] P2 Separate passive current-client qualification
  Evidence: original passive guard failed before probe/upload,0.661686s,exit1.
  PASSIVE_V2_PLAN.md preserves it. v2 ran60.939313s,exit0/token,120/120coherent,
  73Hero+73FloatingCube,all146namesread; median242.5us/p95 520us/max897us.
- [x] E1 Isolated entry integrates observe/row and preserves raw audit
  Evidence: ENTRY_PLAN.md;4passed,7.554490s,exit0; separate --check loads exact
  selected R1e/options,5.771325s,exit0/LIVE_CHECK_PASS. No live entry started.
- [x] R1 Independent source/result/receipt review and activation verdict
  Manual: bind original and new sources, all outputs and receipts; preserve STOP,
  selected R1e, handOFF, and no live startup. Reader activation is separately
  conditional on measured passive current-build checks in PLAN.md.
  Evidence: outside review_reader_characters.py,.456867s,exit0/token; reviewed.json
  binds7earlierreceipts including2failedoriginals;1positive6badparentjoins.
- [ ] A1 Owner-worker transition and measured policy benefit
  Pending: active canonical R1e sources/processes remain untouched; new entry is
  available but unactivated. Exact decision capture/comparison and IceCube
  mechanics remain unresolved. No trained/accepted model or climbing result.
