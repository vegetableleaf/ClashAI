# Tornado pull parity (2026-10-14, overnight; `tornado_pull.py` on PARITY_ALL B_spawn, 1,367 matches)

1,589 own Tornado casts with enemy units within 6.5 tiles of the cast point (both engines present). Distance to the
cast point, live vs sim (tiles). Association only: unit mix and survival differ between time bins.

| Unit | at cast live / sim | 1 s later live / sim | pull in 1 s live / sim |
|---|---|---|---|
| Goblin Gang | 2.45 / 2.88 | 1.79 / 2.81 | 0.66 / **0.07** |
| Baby Dragon | 3.41 / 3.71 | 0.23 / 1.42 | 3.18 / 2.29 |
| Royal Hogs | 3.82 / 4.16 | 1.66 / 2.46 | 2.16 / 1.70 |
| Mega Knight | 3.47 / 3.40 | 1.17 / 1.44 | 2.30 / 1.96 |
| Hog Rider | 4.52 / 4.93 | 0.90 / 1.51 | 3.62 / 3.42 |
| Minion Horde | 3.00 / 2.79 | 1.66 / 1.51 | 1.34 / 1.28 |
| Witch | 2.63 / 2.90 | 1.08 / 1.22 | 1.55 / 1.68 |
| Electro Giant | 3.66 / 3.75 | 1.60 / 1.69 | 2.06 / 2.06 |

- **Measured:** several fast / flying units end farther from the centre in the sim (Goblin Gang, Baby Dragon, Royal Hogs,
  Mega Knight, Electro Dragon, Lava Hound); Minion Horde, Witch, Electro Giant, Golem match.
- **Contradicted:** "the sim uses different masses": 16 of 16 checked units have identical Mass in the device tables and
  the sim's 160402017 table.
- **Plausible, untested:** the gap is mostly inherited starting-position error (sim units start farther from the cast
  point, so more of them sit outside the Tornado radius). Next: restrict to units inside the radius in BOTH engines at
  the cast frame and compare the pull; per-tick logs would remove the 0.5 s frame limit.
