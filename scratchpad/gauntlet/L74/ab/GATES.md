# Gates: live A/B block runner

OWNS: scratchpad/gauntlet/L74/ab/live_ab.py, scratchpad/gauntlet/L74/ab/ab_dryrun.py, scratchpad/gauntlet/L74/ab/test_live_ab.py, scratchpad/gauntlet/L74/ab/README.md, scratchpad/gauntlet/L74/ab/GATES.md, scratchpad/gauntlet/L74/ab/VERIFICATION.json

Scope: alternate checkpoint/fast arms without modifying other live settings, validate account and completion evidence, report and stop safely.

- [x] G1: Fake supervisor proves alternating blocks, exact totals, matching SHA/fast/new-log counting, partial writes, drain accounting and restoration.
  CHECK: python scratchpad/gauntlet/L74/ab/test_live_ab.py counting
  EXPECT: COUNTING_PASS
  EVIDENCE: VERIFICATION.json G1; cwd=C:\Users\benpe\ClashBot; shell=explicit argv; exit=0; EXPECT=matched; output-sha256=89ba285ed595eca6409b2359726614aad0cd68950645fefa520fd5ae99c4a926

- [x] G2: Fake supervisor proves account/deck guard, STOP_AB, check failure, stalls/deaths with at most three restarts, and STOP-only cleanup.
  CHECK: python scratchpad/gauntlet/L74/ab/test_live_ab.py safety
  EXPECT: SAFETY_PASS
  EVIDENCE: VERIFICATION.json G2; cwd=C:\Users\benpe\ClashBot; shell=explicit argv; exit=0; EXPECT=matched; output-sha256=810d58fd3e6b877cfd3837823bc67801f67721127f6dfcca0f523ed85af3d64e

- [x] G3: Reporting proves append-only per-match records, ten-match reports, Wilson and two-proportion intervals and trophy association; CLI dry-run passes offline.
  CHECK: python scratchpad/gauntlet/L74/ab/live_ab.py --dry-run
  EXPECT: DRYRUN_PASS
  EVIDENCE: VERIFICATION.json G3; cwd=C:\Users\benpe\ClashBot; shell=explicit argv; exit=0; EXPECT=matched; output-sha256=959b5032126a35c6a36f0dc3d3c1dd7a1e0ea5191dfe38341fa3b3d346227761

- [x] G4: Source review confirms unchanged live scripts/settings, no process termination/network calls, launch instructions and explicit limitations.
  EVIDENCE: Source-reviewed 2026-10-12: changes limited to new ab files; reused live scripts have empty git diff; no termination or direct network API; README records public-only projection, first-hand guard limitation, safe indefinite STOP wait, launch inputs and backup recovery.
