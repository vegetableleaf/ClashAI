# Gates: S9XL2 faster replay

Scope: skip empty XL2 replays and share DEV passes without changing scored results, seed ranges, labels, or legacy stages.

- [x] G1: original XL2 tests and new sparse replay, shared branch, and workload accounting tests pass without SIM
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L74/weekend/tests -q -p no:cacheprovider
  EXPECT: /[0-9]+ passed/
  EVIDENCE: Authored CHECK run directly in PowerShell, cwd=C:/Users/benpe/cb_drills2; exit=0; EXPECT=matched; 51 passed in 2.39s (39 original plus 12 new); output-sha256=842230e0ee6c7e06b162a4fed3963631bde7ddd92192c0edad6233176470ecf6. Real fork bookkeeping and RNG save/restore on stub engine, no SIM.

- [x] G2: legacy definitions and stage scripts are unchanged
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/weekend/tests/check_xl2.py
  EXPECT: XL2 static checks passed
  EVIDENCE: Authored CHECK run directly in PowerShell, cwd=C:/Users/benpe/cb_drills2; exit=0; EXPECT=matched; output-sha256=cbdfcf30e5ae4b53dffb413d39ad63edbf432d0eca973ee4324c1987cb662af1. Additional git diff against 2430d8f for run_wk.sh, run_xl2.sh and mech_fork.py was empty; no shell edits require new syntax validation. git diff --check passed.

- [x] G3: TEST-only labels, output paths, public model inputs and dump-derived work estimates satisfy the ticket
  EVIDENCE: Reviewed final diff: s9 only opts into evaluate_many for DEV; choose/label, seeds, opponent census, dump sampling and public features unchanged; TEST still single selected variant persisted before evaluation; incomplete batch cannot start TEST. Stub equality includes original continuation, per-variant records/row metadata, RNG streams, D10, no-arm and unsnapshottable cases. Per-variant filenames and SUMMARY text preserved; workload.json/stage.log contain before/after counts before forks. XL2.md gives formulas and full-cap budgets (128000 total old replays; 22842-44500 new; 145000->105000 target branches), qualifies 2.1-2.7x illustrative runtime estimate and does not claim measured 10x. No SIM/network/index writes; all changes restricted to weekend XL2 files. Three gates met, none unmet or abandoned.
