# Why PARITY loses ~57k rows to "sim_terminated" (2026-10-14 overnight; PARITY_T B_spawn, 100 matches)

- 84 / 100 SIM replays end before the live match: median 6.3 s early (p25 1.5 s, p75 65 s); 22 end > 60 s early.
- How the SIM ended: 60 at ~3:00 regulation, 12 in overtime, 12 before 3:00 (three-crown).
- Of 23 SIM endings at 3:00 while the live match went on into overtime, the SIM had a crown lead in 16, often a DIFFERENT
  tower down than live (e.g. live 1-0 vs SIM 0-1). Plausible: early SIM endings are downstream of divergence
  (different towers fall), not an overtime bug. Not established: the live "tower destroyed" proxy (hp <= 0 or row
  missing) is unreliable (11 cases show a live lead yet the live match continued past 3:00).
- Consequence: late-match rows are only comparable with a per-tick reference that restarts the SIM from the live state
  (state injection) -- part of the per-tick logging plan, not a harness fix.
