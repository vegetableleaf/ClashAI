# Gates: offline phase measurements and video follow-up

OWNS: scratchpad/gauntlet/L74/phase_stats/**

Scope: CPU-only public observations; no network or runtime modifications; all changes uncommitted.

- [x] G1: Original synthetic phase, crossing and trade tests remain green
  CHECK: python -B scratchpad/gauntlet/L74/phase_stats/verify_report.py --tests
  EXPECT: SYNTHETIC_TESTS_OK
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; SYNTHETIC_TESTS_OK; 11 passed. Hash in validation.json. Includes both HTML orientations, phase partitions, overlap threshold, archetype precedence, timing windows, unknown/censored observations, gap truncation, Tesla survival, kill order, clumping and conditional denominators.

- [x] G2: Existing reports and public source coverage remain internally consistent
  CHECK: python -B scratchpad/gauntlet/L74/phase_stats/verify_report.py
  EXPECT: ARTIFACTS_OK
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; ARTIFACTS_OK; 775 matches, 26453 bot plays, 65678 human plays. Every video numerator/exposure independently reconciled in all phase/outcome splits; 848 HTML pages parsed. Hash in validation.json.

- [x] G3: Original thirteen metrics and clock verification remain valid
  EVIDENCE: Artifact verification retained all 13 support entries, boundary-clock checks, early-terminal inclusion and match/replay rate reconciliation.

- [x] G4: All writes remain owned, CPU/offline and uncommitted
  EVIDENCE: All production output paths are HERE-rooted; helper has no writes. Standard-library allowlist and forbidden-import positive control passed. No network, GPU, runtime imports, live-control changes or commits. Test bytecode/cache/plugin autoload disabled. Scoped staged diff is empty. No external approval store written; user-authorized tests executed directly.

- [x] F1: Human orientation is corrected; X-Bow classes partition all plays in both orientations and every phase
  CHECK: python -B scratchpad/gauntlet/L74/phase_stats/verify_report.py --tests
  EXPECT: SYNTHETIC_TESTS_OK
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; SYNTHETIC_TESTS_OK; 11 passed. Hash in validation.json. Includes both HTML orientations, phase partitions, overlap threshold, archetype precedence, timing windows, unknown/censored observations, gap truncation, Tesla survival, kill order, clumping and conditional denominators.

- [x] F2: Icebow overlap cohort and small-sample fallback are implemented and phase card/placement comparisons exist
  CHECK: python -B scratchpad/gauntlet/L74/phase_stats/verify_report.py
  EXPECT: ARTIFACTS_OK
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; ARTIFACTS_OK; 775 matches, 26453 bot plays, 65678 human plays. Every video numerator/exposure independently reconciled in all phase/outcome splits; 848 HTML pages parsed. Hash in validation.json. Selected 41 overlap sides; X-Bow + Tesla fallback has 36 sides and is not needed.

- [x] F3: All eight video metrics have public proxies, phase/outcome splits, denominators, uncertainty and auditable censoring
  CHECK: python -B scratchpad/gauntlet/L74/phase_stats/verify_report.py
  EXPECT: ARTIFACTS_OK
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/ClashBot; exit=0; ARTIFACTS_OK; 775 matches, 26453 bot plays, 65678 human plays. Every video numerator/exposure independently reconciled in all phase/outcome splits; 848 HTML pages parsed. Hash in validation.json. Support a-h present. No-data and one-cluster continuous/rate intervals explicitly not estimable; unsupported human fields not invented.

- [x] F4: Report starts with corrected histogram and Video metrics and gives ten numerical findings
  EVIDENCE: Final report order and ten findings verified automatically; human 1x=67+6=73, 2x=98+36=134, 3x=26+4=30. Manual receipt review found and fixed post-gap Tesla responses; regression test passes. Four additional completed bot matches explain growth from 771 to 775; rerun used frozen candidate list.
