# OWN_TIMING -- own-troop parity divergence is a harness timing offset (2026-10-13)

Offline, read-only analysis of the PARITY fixed-injection rerun
(`pod_backup_weekend/podD/x_PARITY_fixed/results/PARITY_v2_fixed_injection/new/`, runtime 0.1.33, 100 live matches;
rows carry raw paired live/sim x,y in native units, 1000 per tile). Own plays only (`source == confirmed_own_tap`):
known tap tick, card and spawn point, so none of the opponent-injection artefacts that sank TRIAGE's eight groups.
Each script takes the `new/` dir (plus the `sources/` dir for `queue_direct.py`) and prints its table.

## Results

| Script | Question | Answer |
|---|---|---|
| `own_early.py` | Error vs time since tap | Buildings (Tesla, X-Bow) match: <= 0.2 tiles at every age. Troops drift AHEAD (toward the enemy) and it grows: Knight +0.13 -> +1.89 tiles, Skeletons +0.51 -> +2.39 from 1 s to 4 s+. Lateral error stays ~0.1. |
| `queue_split.py` | Grows with tap->confirm gap? | No dose-response. Weak test: the gap is >= 1.15 s for EVERY card, buildings included. |
| `onset_speed.py` | When does walking start? (live walkers >= 1 tile forward) | Live median 2.90 s after tap, sim ~1.95-2.00 s: the sim starts 0.5 s (Skeletons) / 1.0 s (Knight) earlier. Frames are ~0.5 s apart, so the sign is robust and the size is +- 0.5 s. Its speed table is confounded by that onset gap. |
| `queue_direct.py` | Elixir-queue cause? (elixir at the tap from `sources/`) | CONTRADICTED: the gap is fully present at full elixir (Skeletons -0.50 s n 214, Knight -1.00 s n 89); almost no plays were queued. |
| `time_align.py` | Pure timing offset? Best per-unit shift tau |