# Gates: APKTABLES

OWNS: scratchpad/gauntlet/L74/apktables/**

Scope: Offline private APK extraction, source-attributed card comparisons, future-build checks and synthetic tests. SIM and live sources remain read-only.

- [x] G1: Synthetic decoder and comparison regressions pass.
  CHECK: python scratchpad/gauntlet/L74/apktables/verify.py
  EXPECT: APKTABLES_SYNTHETIC_PASS
  EVIDENCE: out/test_receipt.json; 33 tests, zero failures/errors/skips; PowerShell, repository root, Python 3.13, exit 0, APKTABLES_SYNTHETIC_PASS matched; output SHA256 0adcd0007d819bba4678e9d5f6da29b1b95ca3591278428454487b3d6780cdfe.

- [x] G2: All targeted APK CSV/TOML extraction outcomes and SIM comparisons are recorded, including icebow, hero, ranked opponents and levels.
  EVIDENCE: out/final_audit.json and out/builds/20261012T213645257844Z-79944/REPORT.md; 421 files (119 CSV, 302 TOML), zero decode failures/conflicts; all 63 main cards (icebow plus top 60) and 36 observed forms covered; six reference comparisons. Selected table has 91 equal, 8 mismatched, zero missing across 99 entries. Hero ability/auxiliary spawner interpretation explicitly excluded. Both explicit configured levels within caps. Four normalization limitations retained; Ghost evolution basic stats recovered. Fresh decoded/input hashes verified, exit 0 APKTABLES_FINAL_AUDIT_PASS.

- [x] G3: Repeated and changed synthetic APK builds exercise baseline preservation and exact changes.
  CHECK: python scratchpad/gauntlet/L74/apktables/verify.py
  EXPECT: APKTABLES_SYNTHETIC_PASS
  EVIDENCE: Same 33-test receipt as G1 includes changed APK, repeated identical APK and failed decode preserving the baseline. Final real snapshot self-comparison has zero file/card changes and no interpretation drift, recorded in out/final_audit.json. Development projection changes remain distinguished from APK changes in archived reports.

- [x] G4: Generated data is ignored; SIM/live files and APK inputs are unchanged by this task; no commit or network.
  EVIDENCE: out/final_audit.json verifies all APK, decoded, reference, census and LIVE_OPTIONS hashes. git check-ignore confirms out/ via this directory's .gitignore and share/ via existing .git/info/exclude. Scoped git status shows only eight new source/docs/test files; no output data. All task writes confined here, all commands local, no live source edits, staging or commits.
