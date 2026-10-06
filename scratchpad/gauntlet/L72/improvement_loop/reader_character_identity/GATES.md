# Reader character identity gates

- [ ] C1 Original-byte census and separate decoder qualification
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L71/integration/run_check.py --name l72-reader-character-identity --expect READER_CHARACTER_IDENTITY_VERIFIED -- research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/reader_character_identity/qualify.py
  EXPECT: READER_CHARACTER_IDENTITY_VERIFIED
- [ ] V1 Actual public-adapter/body/event and catalog protection checks
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L71/integration/run_check.py --name l72-reader-character-adapter --expect passed -- research/ext/Royale/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L72/improvement_loop/reader_character_identity/test_adapter.py -q
  EXPECT: passed
- [ ] R1 Independent source/result/receipt review and activation verdict
  Manual: bind original and new sources, all outputs and receipts; preserve STOP,
  selected R1e, handOFF, and no live startup. Reader activation is separately
  conditional on measured passive current-build checks in PLAN.md.
