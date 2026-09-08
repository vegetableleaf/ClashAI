**GAUNTLET loop L67c** — option A finished (your ruling: A first, then decide B)

**Did:** mined FirstLight's public 252k-replay dataset for exact-icebow games, drove them through our engine, built corpus v6, trained 3 seeds, graded on the unchanged v3 VAL + the degraded twin.

**Found (measured, 3 seeds, same 3,796-play VAL that produced 18.17 / 19.84 / 20.93):**
| metric | v5 (1,638) | v6 (2,241) | Δ |
|---|---|---|---|
| exact cell | 20.93 ± 0.49 | 21.04 ± 0.22 | **+0.11** |
| card top-1 | 63.04 ± 0.28 | 64.99 ± 0.57 | **+1.96** |
| mean dist | 3.571 | 3.478 tiles | −0.09 |
| cell NLL | 3.224 | 3.167 | −0.057 |

**The headline is a NULL.** +0.45 doublings predicted +0.7 pp and returned +0.11 pp, inside the ±0.5 seed band. The S2 scaling line does NOT transfer to this foreign corpus. What did move is the card head: +1.96 pp against seed spreads of 0.28/0.57 (~4 sd), with NLL and placement error agreeing. **More data buys WHICH card, not WHERE.** That is the real finding, and it says our placement ceiling is not a data-volume problem.

Degraded VAL: 16.35 ± 0.56 vs v5's 16.76 ± 0.24 = no change. A clean corpus doubling does nothing for the live shift.

**RETRACTIONS (2):** the dataset holds **766** exact-icebow replays of 252,238 (0.30%) — not ~2,070 (L67b, one outlier shard) nor ~625 (28-shard estimate). And my corpus-assembly script printed "0 crowns mismatch" from a bad key check; the real figure is 473/603 (78.4%).

**B decision (you delegated it): ON.** A closed the data axis for placement; the live shift (−4.2 pp) is untouched by A and is still the largest measured loss on the S4 path; B needs no new data. Design: base held at v6 so augmentation is the only variable, val rows stay clean, graded clean AND degraded — both reported whichever way they go. Running now, 3 seeds, done ~01:30 local.

**Overnight:** B + wiring the student into the live path (adapter to `from_live`, which has zero callers today) with an offline dry run on recorded frames. I will NOT run ladder matches on your account unattended — the first real match is yours to start in the morning.

**Cost:** drive 2.05 h on two slots, 3 seeds ~5 h. Commits 7037cb7, 41768d9.
