# PARITY: own-troop position error is a ~1 s harness timing offset, not pathing

Date 2026-10-13. Data: the artefact-repaired PARITY rerun on disk
`pod_backup_weekend/podD/x_PARITY_fixed/results/PARITY_v2_fixed_injection/new/*.json` (100 live icebow matches
replayed through the RoyaleSim fork `clashbot`@cacb700, 0 mechanics patches) plus its frame sources
`.../x_PARITY_v2/results/PARITY_v2/sources/`. Read-only analysis; scripts in this directory. Positions are native
millitiles / 1000 = tiles; "forward" = toward the enemy, normalised per side.

Subset: **own-side, confirmed-tap units** (known card, spawn cell and tap tick; position is level-independent, so the
uniform-level-15 HP assumption cannot affect it).

## Measured
| Check | Result |
|---|---|
| Buildings, position error 1-4 s after the tap (`own_early.py`) | Tesla 0.02-0.08 tiles (n 263), X-Bow 0.08-0.19 (n 280): ~0 |
| Troops, same | Knight 0.54 -> 1.37 tiles (n 352), Skeletons 0.97 -> 2.82 (n 817), growing with age |
| Direction of the troop error | almost all forward ("sim ahead"); lateral 0.05-0.15 tiles |
| Motion onset after the tap, troops the live game shows walking >= 1 tile forward (`onset_speed.py`) | live median 2.90 s (both); sim 2.00 s Knight / 1.95 s Skeletons; paired median sim-minus-live -1.00 / -0.50 s |
| Elixir at the tap (`queue_direct.py`) | the gap is the same at full elixir (Skeletons n 214, Knight n 89); only 8 plays were queued |
| Best per-unit sim delay tau (`time_align.py`) | Knight **+1.25 s** (IQR 1.05-1.40), Skeletons **+1.05 s** (IQR 1.00-1.40) |
| 2-D error before -> after the shift | Knight **1.289 -> 0.115** tiles (74/123 under 0.25); Skeletons 1.919 -> 0.527 (64/266 under 0.25) |

Resolution limit: source frames are ~0.5 s apart, so onsets are quantised to ~0.5 s. The sign is robust; the size is
known to about +-0.5 s.

## Reading
- A single ~1.05-1.25 s time shift removes almost all of the own-troop error. Aligned, the sim's **Knight walks the real
  path to 0.115 tiles median**. So the dominant error is *timing*, not pathing geometry or speed.
- **Mechanism (consistent with the evidence):** the harness deploys our play at the **tap** tick
  (`core.py:65` `tick=p['tick']`; `driver.py:154-168` advances to that tick and calls `battle.step`). The real client
  spawns the unit later: the tap->confirmed gap is >= 1.15 s for every card, buildings included, and FORK.md:171
  already notes "Own confirmed spawn is also later than the tap". The fitted tau (~1.1-1.25 s) matches that gap.
  So this is a **harness artefact**.
- **Contradicted:** "the fork has no troop deploy delay". The sim's own onset is ~2.0 s after the tap, so it applies a
  deploy delay; the real game is ~1 s later still.
- **Contradicted:** "the elixir queue causes it". The gap is fully present at full elixir.
- **Not established:** a walking-speed difference. The raw 2-4 s speeds (sim faster) are confounded by the later live
  onset, and a 27%-faster Knight could not align to 0.115 tiles with a pure time shift.
- **Plausible, untested:** the Skeletons' 0.53-tile residual is swarm-member mis-pairing (3-skeleton formation spacing;
  FORK.md lists "exact spawn pairing within swarms" as a known limit), not a pathing bug. Test: pair members by
  position instead of spawn ordinal.

## Consequence
The 1.29-1.39-tile PARITY headline is substantially inflated by this artefact for our own units, and the sim's
single-unit movement is closer to the real game than it implied. None of this is the owner's tick-exact bar: 0.5 s
frames and reconstructed boards cannot prove tick identity.

## Next
1. Inject own plays at the observed spawn tick (tap + per-play delay from the live logs) and re-run PARITY; re-measure
   the headline and the residuals (pod CPU job).
2. Re-pair swarm members by position; re-measure Skeletons.
3. Exact per-tick confirmation of the remaining residuals needs a reference engine; not attempted here.
