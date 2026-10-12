# Gates: offline phase measurements

OWNS: scratchpad/gauntlet/L74/phase_stats/**

Scope: CPU-only, public-observation measurements, selected live matches and offline human HTML; no runtime changes or network.

- [x] G1: synthetic phase, crossing and trade tests pass
  CHECK: python -B scratchpad/gauntlet/L74/phase_stats/verify_report.py --tests
  EXPECT: SYNTHETIC_TESTS_OK
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; matched SYNTHETIC_TESTS_OK; 3 passed. Runtime imports and pytest plugins disabled. Commands and artifact fingerprints in validation.json.
- [x] G2: rerunnable script produces internally consistent reports and source coverage
  CHECK: python -B scratchpad/gauntlet/L74/phase_stats/verify_report.py
  EXPECT: ARTIFACTS_OK
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; matched ARTIFACTS_OK; 771 bot matches, 26278 confirmed bot plays, 65678 human plays; all 848 HTML pages parsed; denominators and rate arithmetic independently reconciled; hashes in validation.json.
- [x] G3: all thirteen metrics measured or explicitly bounded by public-data feasibility, phase boundaries verified empirically, rates have CIs
  EVIDENCE: report.json metric_support has all 13 requested metrics, exact unidentifiable quantities null and proxies named. Raw 119/120/239/240-second bins verify 0.356/0.714/1.074 rates. 28 short terminal defeats retained with strict-scorecard sensitivity; 1 legacy outcome disagreement. Rate CIs use match/replay clusters; one-cluster intervals explicitly unavailable. Report and receipts reviewed after correcting unknown-body tower identity and mirrored deployment x.
- [x] G4: task-authored writes are confined to the owned directory; runtime code remains unmodified by this task; changes are uncommitted
  EVIDENCE: All six production-script write sites are HERE-rooted; standard-library-only import AST whitelist passed with forbidden-import positive control. Tests import only this analysis module. No network or live-control actions. Scoped git status is untracked and scoped staged diff is empty. Provisional exploration files removed only within owned directory. No external unlazy approval store was written; authorized checks executed directly with receipts in validation.json.
