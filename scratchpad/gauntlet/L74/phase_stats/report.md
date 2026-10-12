# X-Bow phase measurement

Offline run: 2026-10-12T14:46:51.354065+00:00. Since 20261008. All rates below have 95% CIs in brackets; total is the numerator and n is the number of independent matches/replay clusters unless stated. Big losses overlap losses. Human exposure sums player-sides; CIs cluster both sides by replay.

## Ten findings

1. Selected 771 completed main-account X-Bow matches: 396 wins, 372 losses, 3 tower-state draws; 114 big losses (a subset of losses). This includes 28 clear terminal defeats before 2:00 that the original scorecard's duration cutoff would discard.
2. Net tower HP per minute (dealt minus taken): 1x -486.27 [-630.01, -342.53]; total=-697239, n=771m; 2x -42.39 [-245.10, 160.32]; total=-41183, n=743m; 3x 1050.75 [643.44, 1458.05]; total=116335, n=165m.
3. In eventual losses, net tower HP/minute: 1x -1589.01 [-1811.51, -1366.52]; total=-1.08997e+06, n=372m; 2x -1994.65 [-2321.16, -1668.14]; total=-855729, n=344m; 3x -347.22 [-773.52, 79.08]; total=-17197, n=73m.
4. In big losses, tower HP taken/minute: 1x 5176.42 [4647.39, 5705.45]; total=1.04745e+06, n=114m; 2x 9292.64 [8171.84, 10413.44]; total=552277, n=86m; 3x 5385.37 [CI unavailable]; total=552, n=1m.
5. Among 106 matches with at least 30 seconds in each phase, 3x minus 1x net HP/min averages 1177.4 (95% CI 720.0 to 1634.9). Later-phase comparisons remain conditional on survival.
6. Own elixir at confirmed plays: 1x 6.06 (n=11102); 2x 5.17 (n=13010); 3x 4.79 (n=2166).
7. Own elixir at observed push crossings: 1x 4.22 (n=3846); 2x 4.07 (n=2895); 3x 4.17 (n=366).
8. Confirmed bot plays/minute: 1x 7.74 [7.68, 7.80]; total=11102, n=771m; 2x 13.39 [13.27, 13.52]; total=13010, n=743m; 3x 19.56 [19.07, 20.06]; total=2166, n=165m. Human X-Bow sides: 1x 8.17 [7.78, 8.55]; total=751, n=46m; 2x 14.39 [13.49, 15.28]; total=1134, n=45m; 3x 18.97 [17.33, 20.62]; total=454, n=33m.
9. Quiet defensive-spend proxy, elixir/minute: 1x 2.53 [2.37, 2.68]; total=3621, n=771m; 2x 2.12 [1.93, 2.31]; total=2057, n=743m; 3x 1.60 [1.07, 2.13]; total=177, n=165m. This measures the stated heuristic, not proven waste.
10. Rocket-on-tower geometry counts/rates per minute: 1x 0.10 [0.09, 0.12]; total=145, n=771m; 2x 0.32 [0.28, 0.36]; total=312, n=743m; 3x 1.37 [1.17, 1.57]; total=152, n=165m. Actual spell chip and enemy elixir killed are not identifiable from these snapshots.

## Selection and coverage

Selection: {"candidate_files": 1243, "excluded": {"no_end_event": 3, "no_public_decisions": 34, "no_xbow_in_own_hand": 2, "other_account_tower_signature": 433}, "included": 771}.
Human corpus: 848 files, 848 usable unique replays, 1696 player-sides, 46 sides observed playing X-Bow. Rank/top-100 provenance is owner-supplied, not independently certified by these replay pages.
Main-account proxy: initial own princess maximum HP 4424 and king 7032. Smaller tower signatures are excluded. Nearby ladder trophy reads are attached per match when available; tower signatures do not uniquely prove account identity.
Selection requires an end event, Xbow in the observed OWN hand, and at least two final tower bodies. The scorecard duration rule (last tick >=2400) is retained except for clear early terminal records: battle_over_hands_visible stop, zero surviving towers on one side and at least two on the other. These earlier defeats must not disappear from a study of 1x collapses. Their IDs and a strict scorecard-only sensitivity summary are in report.json. Last-observed tower outcomes can miss a final hit and label a tiebreak loss as a draw. Final crowns in bot metadata are scorecard proxies, not result-screen crowns.
Each selected file has checkpoint path/hash, fast-plays flag, SHA256, observed ticks and account evidence in report.json. Active/changing files are excluded. Metrics use confirmed card plays; unmatched tap attempts and hero abilities are counted separately. Observed exposure starts at the first decision; no unlogged opening is invented. Missing/gapped elixir time is excluded from cap occupancy.

## Clock verification

| Phase | Tick interval | Own regen elixir/s, mean [95% CI across match means] | Intervals / matches |
|---|---|---|---|
| 1x | [0, 2400) | 0.356000 [0.356000, 0.356000] | 230366 / 771 |
| 2x | [2400, 4800) | 0.714000 [0.714000, 0.714000] | 157764 / 738 |
| 3x | [4800, 6000) | 1.074000 [1.074000, 1.074000] | 19296 / 161 |

Ticks run at 20/s (device-clock interval measurements are retained per match). Positive uncapped own-elixir changes over <=1s verify regeneration; spend/cap intervals are excluded. Baseline-rate estimates retain intervals within 0.02 elixir/s of each phase’s empirical median, removing elixir awards/corrections; rejected counts are retained. Boundary bins around 119/120 and 239/240 seconds retain unfiltered positive rates in report.json. Regulation 2:00 through overtime 4:00 is 2x. The 5:00+ tiebreak drain is excluded from all combat metrics, but the final decision still supplies the scorecard label.

## Bot versus human plays

| Phase | Bot confirmed plays/min | Human all decks plays/min | Human X-Bow plays/min |
|---|---|---|---|
| 1x | 7.74 [7.68, 7.80]; total=11102, n=771m | 6.82 [6.62, 7.01]; total=22875, n=848m | 8.17 [7.78, 8.55]; total=751, n=46m |
| 2x | 13.39 [13.27, 13.52]; total=13010, n=743m | 12.72 [12.55, 12.89]; total=32411, n=815m | 14.39 [13.49, 15.28]; total=1134, n=45m |
| 3x | 19.56 [19.07, 20.06]; total=2166, n=165m | 18.54 [18.14, 18.95]; total=10392, n=364m | 18.97 [17.33, 20.62]; total=454, n=33m |

### 1x: card rates, bot versus humans

| Card, per minute | Bot | Human all decks | Human X-Bow sides |
|---|---|---|---|
| Skeletons | 1.41 [1.39, 1.44]; total=2026, n=771m | 0.48 [0.44, 0.51]; total=1597, n=848m | 1.45 [1.34, 1.55]; total=133, n=46m |
| Log | 1.26 [1.23, 1.29]; total=1812, n=771m | 0.21 [0.18, 0.23]; total=688, n=848m | 1.11 [1.00, 1.22]; total=102, n=46m |
| Knight | 1.30 [1.27, 1.32]; total=1858, n=771m | 0.18 [0.16, 0.20]; total=603, n=848m | 1.12 [1.01, 1.23]; total=103, n=46m |
| Ice Wizard | 1.34 [1.32, 1.36]; total=1920, n=771m | 0.08 [0.06, 0.09]; total=256, n=848m | 0.35 [0.19, 0.51]; total=32, n=46m |
| Tornado | 0.48 [0.45, 0.51]; total=690, n=771m | 0.07 [0.06, 0.08]; total=228, n=848m | 0.15 [0.06, 0.24]; total=14, n=46m |
| Tesla | 1.04 [1.02, 1.07]; total=1498, n=771m | 0.07 [0.06, 0.09]; total=249, n=848m | 0.63 [0.49, 0.78]; total=58, n=46m |
| X-Bow | 0.76 [0.73, 0.79]; total=1092, n=771m | 0.02 [0.01, 0.03]; total=73, n=848m | 0.79 [0.67, 0.92]; total=73, n=46m |
| Rocket | 0.14 [0.13, 0.16]; total=206, n=771m | 0.01 [0.00, 0.01]; total=27, n=848m | 0.02 [0.00, 0.05]; total=2, n=46m |

### 2x: card rates, bot versus humans

| Card, per minute | Bot | Human all decks | Human X-Bow sides |
|---|---|---|---|
| Skeletons | 2.37 [2.32, 2.41]; total=2299, n=743m | 0.86 [0.80, 0.91]; total=2184, n=815m | 2.27 [2.10, 2.45]; total=179, n=45m |
| Log | 1.91 [1.85, 1.96]; total=1852, n=743m | 0.41 [0.36, 0.45]; total=1035, n=815m | 1.66 [1.48, 1.84]; total=131, n=45m |
| Knight | 2.37 [2.33, 2.41]; total=2301, n=743m | 0.39 [0.34, 0.43]; total=992, n=815m | 1.98 [1.76, 2.20]; total=156, n=45m |
| Ice Wizard | 2.44 [2.40, 2.48]; total=2369, n=743m | 0.17 [0.14, 0.20]; total=426, n=815m | 0.55 [0.29, 0.80]; total=43, n=45m |
| Tornado | 0.85 [0.80, 0.90]; total=824, n=743m | 0.15 [0.13, 0.17]; total=375, n=815m | 0.29 [0.13, 0.45]; total=23, n=45m |
| Tesla | 1.79 [1.74, 1.83]; total=1735, n=743m | 0.18 [0.15, 0.21]; total=454, n=815m | 1.40 [1.16, 1.63]; total=110, n=45m |
| X-Bow | 1.26 [1.21, 1.30]; total=1222, n=743m | 0.05 [0.04, 0.07]; total=134, n=815m | 1.70 [1.49, 1.91]; total=134, n=45m |
| Rocket | 0.42 [0.38, 0.46]; total=408, n=743m | 0.04 [0.03, 0.06]; total=112, n=815m | 0.30 [0.13, 0.47]; total=24, n=45m |

### 3x: card rates, bot versus humans

| Card, per minute | Bot | Human all decks | Human X-Bow sides |
|---|---|---|---|
| Skeletons | 3.33 [3.15, 3.52]; total=369, n=165m | 1.41 [1.28, 1.55]; total=793, n=364m | 2.88 [2.49, 3.28]; total=69, n=33m |
| Log | 2.91 [2.71, 3.10]; total=322, n=165m | 0.82 [0.70, 0.94]; total=459, n=364m | 2.84 [2.37, 3.32]; total=68, n=33m |
| Knight | 3.38 [3.21, 3.55]; total=374, n=165m | 0.59 [0.49, 0.68]; total=329, n=364m | 2.59 [2.14, 3.04]; total=62, n=33m |
| Ice Wizard | 3.54 [3.39, 3.69]; total=392, n=165m | 0.30 [0.22, 0.37]; total=168, n=364m | 1.17 [0.52, 1.82]; total=28, n=33m |
| Tornado | 1.50 [1.31, 1.69]; total=166, n=165m | 0.20 [0.16, 0.25]; total=114, n=364m | 0.42 [0.11, 0.73]; total=10, n=33m |
| Tesla | 2.58 [2.39, 2.78]; total=286, n=165m | 0.36 [0.28, 0.43]; total=199, n=364m | 2.38 [1.86, 2.91]; total=57, n=33m |
| X-Bow | 0.86 [0.69, 1.02]; total=95, n=165m | 0.05 [0.03, 0.08]; total=30, n=364m | 1.25 [0.78, 1.73]; total=30, n=33m |
| Rocket | 1.46 [1.27, 1.66]; total=162, n=165m | 0.10 [0.06, 0.14]; total=57, n=364m | 0.54 [0.13, 0.96]; total=13, n=33m |

### Placement comparisons

All lane × zone rates and X-Bow cell histograms for both cohorts are in report.json. Below are the placements most directly comparable without board state.

| Phase / placement, per minute | Bot | Human all decks | Human X-Bow sides |
|---|---|---|---|
| 1x Bridge X-Bow | 0.63 [0.60, 0.66]; total=907, n=771m | 0.01 [0.00, 0.01]; total=30, n=848m | 0.33 [0.20, 0.45]; total=30, n=46m |
| 1x Defensive X-Bow | 0.13 [0.11, 0.15]; total=185, n=771m | 0.00 [0.00, 0.00]; total=3, n=848m | 0.03 [0.00, 0.07]; total=3, n=46m |
| 1x Rocket tower geometry | 0.10 [0.09, 0.12]; total=145, n=771m | 0.00 [0.00, 0.00]; total=9, n=848m | 0.00 [0.00, 0.04]; total=0, n=46m |
| 2x Bridge X-Bow | 1.03 [0.98, 1.08]; total=999, n=743m | 0.02 [0.01, 0.03]; total=46, n=815m | 0.58 [0.33, 0.84]; total=46, n=45m |
| 2x Defensive X-Bow | 0.23 [0.20, 0.26]; total=222, n=743m | 0.01 [0.00, 0.01]; total=16, n=815m | 0.20 [0.08, 0.33]; total=16, n=45m |
| 2x Rocket tower geometry | 0.32 [0.28, 0.36]; total=312, n=743m | 0.01 [0.01, 0.01]; total=25, n=815m | 0.05 [0.00, 0.11]; total=4, n=45m |
| 3x Bridge X-Bow | 0.71 [0.56, 0.87]; total=79, n=165m | 0.03 [0.01, 0.05]; total=16, n=364m | 0.67 [0.25, 1.09]; total=16, n=33m |
| 3x Defensive X-Bow | 0.14 [0.08, 0.21]; total=16, n=165m | 0.00 [0.00, 0.01]; total=2, n=364m | 0.08 [0.00, 0.20]; total=2, n=33m |
| 3x Rocket tower geometry | 1.37 [1.17, 1.57]; total=152, n=165m | 0.04 [0.02, 0.06]; total=21, n=364m | 0.21 [0.00, 0.42]; total=5, n=33m |

## Bot: all

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Observed minutes (n matches) | 1433.8 (n=771) | 971.5 (n=743) | 110.7 (n=165) |
| Own elixir at decisions | 5.08 (n=158087) | 4.53 (n=99214) | 4.41 (n=10130) |
| Own elixir at plays | 6.06 (n=11102) | 5.17 (n=13010) | 4.79 (n=2166) |
| Enemy units on our side at play | 0.95 (n=11102) | 1.51 (n=13010) | 1.70 (n=2166) |
| Enemy nominal elixir on our side | 3.18 (n=11102) | 4.95 (n=13010) | 5.56 (n=2166) |
| Own bodies alive at play | 1.29 (n=11102) | 2.41 (n=13010) | 3.34 (n=2166) |
| Elixir at push crossing | 4.22 (n=3846) | 4.07 (n=2895) | 4.17 (n=366) |
| Response seconds, observed responses | 2.71 (n=2505) | 2.13 (n=2124) | 1.38 (n=289) |
| X-Bow elixir | 8.82 (n=1092) | 7.58 (n=1222) | 7.03 (n=95) |
| X-Bow following 20s tower damage, all sources | 1543.88 (n=1092) | 1011.71 (n=1222) | 849.28 (n=95) |
| Cap seconds/min, both endpoints at 10 | 1.39 [1.22, 1.55]; total=1990.9, n=771m | 0.40 [0.23, 0.58]; total=393.2, n=743m | 0.08 [0.01, 0.16]; total=9.15, n=165m |
| Plays/min | 7.74 [7.68, 7.80]; total=11102, n=771m | 13.39 [13.27, 13.52]; total=13010, n=743m | 19.56 [19.07, 20.06]; total=2166, n=165m |
| Cheap quiet cycles/min | 1.03 [0.97, 1.09]; total=1482, n=771m | 1.01 [0.91, 1.10]; total=977, n=743m | 1.12 [0.70, 1.54]; total=124, n=165m |
| Quiet defensive plays/min | 0.91 [0.85, 0.96]; total=1301, n=771m | 0.74 [0.68, 0.81]; total=721, n=743m | 0.52 [0.34, 0.71]; total=58, n=165m |
| Quiet defensive elixir/min | 2.53 [2.37, 2.68]; total=3621, n=771m | 2.12 [1.93, 2.31]; total=2057, n=743m | 1.60 [1.07, 2.13]; total=177, n=165m |
| Overcommit engagements/min | 0.07 [0.06, 0.08]; total=99, n=771m | 0.20 [0.17, 0.23]; total=195, n=743m | 0.40 [0.27, 0.52]; total=44, n=165m |
| Overcommit excess elixir/min | 0.10 [0.07, 0.13]; total=145.633, n=771m | 0.43 [0.35, 0.51]; total=414.717, n=743m | 1.10 [0.72, 1.47]; total=121.3, n=165m |
| Tower HP dealt/min | 1430.69 [1351.43, 1509.94]; total=2.05138e+06, n=771m | 1940.75 [1823.30, 2058.20]; total=1.88547e+06, n=743m | 2222.19 [1883.75, 2560.64]; total=246034, n=165m |
| Tower HP taken/min | 1916.96 [1779.31, 2054.61]; total=2.74862e+06, n=771m | 1983.14 [1822.74, 2143.55]; total=1.92665e+06, n=743m | 1171.45 [976.36, 1366.54]; total=129699, n=165m |
| Crowns gained/min | 0.10 [0.09, 0.12]; total=150, n=771m | 0.33 [0.30, 0.37]; total=325, n=743m | 0.58 [0.44, 0.71]; total=64, n=165m |
| Crowns lost/min | 0.18 [0.15, 0.21]; total=257, n=771m | 0.37 [0.32, 0.41]; total=358, n=743m | 0.41 [0.29, 0.53]; total=45, n=165m |
| Positive trade PROXY/min | 2.24 [2.18, 2.31]; total=3216, n=771m | 1.90 [1.82, 1.99]; total=1850, n=743m | 1.54 [1.29, 1.78]; total=170, n=165m |
| Negative trade PROXY/min | 0.23 [0.20, 0.25]; total=329, n=771m | 0.45 [0.40, 0.49]; total=433, n=743m | 0.65 [0.50, 0.80]; total=72, n=165m |
| Net nominal trade PROXY/min | 19.71 [18.35, 21.07]; total=28256.3, n=771m | 17.16 [15.35, 18.96]; total=16667.5, n=743m | 11.13 [6.98, 15.27]; total=1231.92, n=165m |
| X-Bow observed tower locks/min | 0.49 [0.46, 0.52]; total=705, n=771m | 0.58 [0.54, 0.62]; total=564, n=743m | 0.29 [0.20, 0.38]; total=32, n=165m |
| Rocket tower targets/min | 0.10 [0.09, 0.12]; total=145, n=771m | 0.32 [0.28, 0.36]; total=312, n=743m | 1.37 [1.17, 1.57]; total=152, n=165m |
| Enemy big-spell contact episodes/min | 0.04 [0.03, 0.05]; total=52, n=771m | 0.08 [0.06, 0.10]; total=77, n=743m | 0.27 [0.14, 0.40]; total=30, n=165m |
| Enemy other-spell contact episodes/min | 0.14 [0.11, 0.16]; total=196, n=771m | 0.40 [0.34, 0.45]; total=386, n=743m | 0.95 [0.73, 1.17]; total=105, n=165m |
| Spell-associated HP taken/min, not causal | 50.19 [35.32, 65.06]; total=71964, n=771m | 90.99 [67.31, 114.68]; total=88400, n=743m | 244.75 [161.47, 328.03]; total=27098, n=165m |
| Unattributed HP taken/min | 1866.77 [1730.09, 2003.45]; total=2.67665e+06, n=771m | 1892.15 [1733.99, 2050.31]; total=1.83825e+06, n=743m | 926.70 [746.67, 1106.73]; total=102601, n=165m |

## Bot: wins

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Observed minutes (n matches) | 742.3 (n=396) | 539.2 (n=396) | 61.2 (n=92) |
| Own elixir at decisions | 5.27 (n=81751) | 4.58 (n=55024) | 4.41 (n=5628) |
| Own elixir at plays | 6.30 (n=5709) | 5.32 (n=7182) | 4.81 (n=1186) |
| Enemy units on our side at play | 0.71 (n=5709) | 1.05 (n=7182) | 1.60 (n=1186) |
| Enemy nominal elixir on our side | 2.33 (n=5709) | 3.41 (n=7182) | 5.06 (n=1186) |
| Own bodies alive at play | 1.33 (n=5709) | 2.58 (n=7182) | 3.40 (n=1186) |
| Elixir at push crossing | 4.37 (n=2015) | 4.06 (n=1697) | 4.07 (n=219) |
| Response seconds, observed responses | 2.46 (n=1249) | 2.10 (n=1235) | 1.40 (n=166) |
| X-Bow elixir | 8.77 (n=593) | 7.54 (n=720) | 7.05 (n=48) |
| X-Bow following 20s tower damage, all sources | 1572.14 (n=593) | 1196.65 (n=720) | 1283.96 (n=48) |
| Cap seconds/min, both endpoints at 10 | 1.38 [1.18, 1.59]; total=1027.1, n=396m | 0.19 [0.02, 0.36]; total=104.05, n=396m | 0.08 [0.00, 0.17]; total=4.75, n=92m |
| Plays/min | 7.69 [7.62, 7.77]; total=5709, n=396m | 13.32 [13.16, 13.48]; total=7182, n=396m | 19.38 [18.69, 20.07]; total=1186, n=92m |
| Cheap quiet cycles/min | 1.16 [1.08, 1.25]; total=863, n=396m | 1.23 [1.09, 1.38]; total=665, n=396m | 1.11 [0.53, 1.69]; total=68, n=92m |
| Quiet defensive plays/min | 1.03 [0.96, 1.11]; total=768, n=396m | 0.88 [0.79, 0.98]; total=477, n=396m | 0.59 [0.33, 0.85]; total=36, n=92m |
| Quiet defensive elixir/min | 2.91 [2.70, 3.12]; total=2161, n=396m | 2.49 [2.23, 2.76]; total=1344, n=396m | 1.75 [1.01, 2.49]; total=107, n=92m |
| Overcommit engagements/min | 0.08 [0.06, 0.10]; total=60, n=396m | 0.20 [0.16, 0.24]; total=106, n=396m | 0.38 [0.22, 0.53]; total=23, n=92m |
| Overcommit excess elixir/min | 0.11 [0.08, 0.15]; total=84.5333, n=396m | 0.40 [0.30, 0.49]; total=213.117, n=396m | 1.05 [0.57, 1.53]; total=64.2, n=92m |
| Tower HP dealt/min | 1520.51 [1407.73, 1633.29]; total=1.12864e+06, n=396m | 2425.10 [2254.44, 2595.75]; total=1.30756e+06, n=396m | 3027.59 [2496.20, 3558.99]; total=185256, n=92m |
| Tower HP taken/min | 985.82 [902.39, 1069.24]; total=731746, n=396m | 930.46 [839.92, 1021.01]; total=501684, n=396m | 845.31 [627.65, 1062.97]; total=51724, n=92m |
| Crowns gained/min | 0.13 [0.10, 0.15]; total=96, n=396m | 0.50 [0.45, 0.55]; total=272, n=396m | 1.05 [0.81, 1.28]; total=64, n=92m |
| Crowns lost/min | 0.01 [0.00, 0.02]; total=9, n=396m | 0.04 [0.03, 0.06]; total=23, n=396m | 0.00 [0.00, 0.06]; total=0, n=92m |
| Positive trade PROXY/min | 2.29 [2.20, 2.37]; total=1699, n=396m | 2.07 [1.95, 2.18]; total=1115, n=396m | 1.86 [1.50, 2.22]; total=114, n=92m |
| Negative trade PROXY/min | 0.26 [0.22, 0.30]; total=193, n=396m | 0.47 [0.41, 0.53]; total=256, n=396m | 0.54 [0.36, 0.72]; total=33, n=92m |
| Net nominal trade PROXY/min | 17.27 [15.60, 18.94]; total=12816.5, n=396m | 17.81 [15.37, 20.25]; total=9603.5, n=396m | 15.11 [8.63, 21.60]; total=924.85, n=92m |
| X-Bow observed tower locks/min | 0.53 [0.49, 0.57]; total=395, n=396m | 0.72 [0.67, 0.78]; total=390, n=396m | 0.38 [0.24, 0.51]; total=23, n=92m |
| Rocket tower targets/min | 0.11 [0.08, 0.13]; total=78, n=396m | 0.38 [0.33, 0.43]; total=204, n=396m | 1.67 [1.39, 1.94]; total=102, n=92m |
| Enemy big-spell contact episodes/min | 0.05 [0.03, 0.07]; total=38, n=396m | 0.09 [0.06, 0.13]; total=51, n=396m | 0.20 [0.08, 0.32]; total=12, n=92m |
| Enemy other-spell contact episodes/min | 0.16 [0.13, 0.19]; total=120, n=396m | 0.43 [0.35, 0.50]; total=230, n=396m | 0.93 [0.63, 1.23]; total=57, n=92m |
| Spell-associated HP taken/min, not causal | 45.86 [30.82, 60.90]; total=34044, n=396m | 74.78 [56.23, 93.34]; total=40322, n=396m | 230.94 [118.85, 343.03]; total=14131, n=92m |
| Unattributed HP taken/min | 939.95 [857.78, 1022.12]; total=697702, n=396m | 855.68 [765.93, 945.43]; total=461362, n=396m | 614.37 [445.93, 782.82]; total=37593, n=92m |

## Bot: losses

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Observed minutes (n matches) | 685.9 (n=372) | 429.0 (n=344) | 49.5 (n=73) |
| Own elixir at decisions | 4.88 (n=75749) | 4.47 (n=43914) | 4.41 (n=4502) |
| Own elixir at plays | 5.80 (n=5346) | 5.00 (n=5777) | 4.77 (n=980) |
| Enemy units on our side at play | 1.22 (n=5346) | 2.09 (n=5777) | 1.81 (n=980) |
| Enemy nominal elixir on our side | 4.11 (n=5346) | 6.89 (n=5777) | 6.16 (n=980) |
| Own bodies alive at play | 1.25 (n=5346) | 2.19 (n=5777) | 3.26 (n=980) |
| Elixir at push crossing | 4.04 (n=1814) | 4.09 (n=1183) | 4.33 (n=147) |
| Response seconds, observed responses | 2.98 (n=1245) | 2.20 (n=877) | 1.35 (n=123) |
| X-Bow elixir | 8.88 (n=496) | 7.63 (n=498) | 7.01 (n=47) |
| X-Bow following 20s tower damage, all sources | 1510.26 (n=496) | 737.88 (n=498) | 405.36 (n=47) |
| Cap seconds/min, both endpoints at 10 | 1.39 [1.13, 1.66]; total=954.8, n=372m | 0.67 [0.33, 1.01]; total=289.15, n=344m | 0.09 [0.00, 0.22]; total=4.4, n=73m |
| Plays/min | 7.79 [7.69, 7.89]; total=5346, n=372m | 13.47 [13.26, 13.67]; total=5777, n=344m | 19.79 [19.07, 20.50]; total=980, n=73m |
| Cheap quiet cycles/min | 0.90 [0.81, 0.98]; total=615, n=372m | 0.72 [0.61, 0.84]; total=310, n=344m | 1.13 [0.53, 1.73]; total=56, n=73m |
| Quiet defensive plays/min | 0.77 [0.70, 0.85]; total=530, n=372m | 0.57 [0.48, 0.66]; total=243, n=344m | 0.44 [0.19, 0.70]; total=22, n=73m |
| Quiet defensive elixir/min | 2.12 [1.90, 2.33]; total=1453, n=372m | 1.65 [1.40, 1.91]; total=710, n=344m | 1.41 [0.66, 2.17]; total=70, n=73m |
| Overcommit engagements/min | 0.06 [0.04, 0.07]; total=38, n=372m | 0.20 [0.16, 0.24]; total=86, n=344m | 0.42 [0.22, 0.63]; total=21, n=73m |
| Overcommit excess elixir/min | 0.09 [0.05, 0.13]; total=60.1, n=372m | 0.46 [0.33, 0.60]; total=199.1, n=344m | 1.15 [0.55, 1.75]; total=57.1, n=73m |
| Tower HP dealt/min | 1341.10 [1230.21, 1451.99]; total=919916, n=372m | 1315.90 [1181.75, 1450.05]; total=564538, n=344m | 1227.16 [924.69, 1529.62]; total=60778, n=73m |
| Tower HP taken/min | 2930.11 [2693.46, 3166.77]; total=2.00989e+06, n=372m | 3310.55 [2997.40, 3623.70]; total=1.42027e+06, n=344m | 1574.38 [1237.62, 1911.14]; total=77975, n=73m |
| Crowns gained/min | 0.08 [0.06, 0.10]; total=54, n=372m | 0.12 [0.09, 0.15]; total=53, n=344m | 0.00 [0.00, 0.07]; total=0, n=73m |
| Crowns lost/min | 0.36 [0.31, 0.41]; total=248, n=372m | 0.78 [0.69, 0.87]; total=335, n=344m | 0.91 [0.64, 1.18]; total=45, n=73m |
| Positive trade PROXY/min | 2.19 [2.10, 2.28]; total=1503, n=372m | 1.70 [1.57, 1.82]; total=728, n=344m | 1.13 [0.84, 1.42]; total=56, n=73m |
| Negative trade PROXY/min | 0.20 [0.16, 0.23]; total=135, n=372m | 0.40 [0.33, 0.47]; total=172, n=344m | 0.79 [0.55, 1.03]; total=39, n=73m |
| Net nominal trade PROXY/min | 22.41 [20.25, 24.57]; total=15373.2, n=372m | 16.39 [13.69, 19.09]; total=7031.65, n=344m | 6.20 [1.87, 10.53]; total=307.067, n=73m |
| X-Bow observed tower locks/min | 0.45 [0.41, 0.49]; total=309, n=372m | 0.40 [0.35, 0.45]; total=171, n=344m | 0.18 [0.06, 0.30]; total=9, n=73m |
| Rocket tower targets/min | 0.10 [0.08, 0.12]; total=67, n=372m | 0.25 [0.20, 0.30]; total=107, n=344m | 1.01 [0.74, 1.28]; total=50, n=73m |
| Enemy big-spell contact episodes/min | 0.02 [0.01, 0.03]; total=14, n=372m | 0.06 [0.04, 0.09]; total=26, n=344m | 0.36 [0.12, 0.61]; total=18, n=73m |
| Enemy other-spell contact episodes/min | 0.11 [0.07, 0.14]; total=73, n=372m | 0.36 [0.28, 0.44]; total=155, n=344m | 0.97 [0.64, 1.30]; total=48, n=73m |
| Spell-associated HP taken/min, not causal | 55.28 [28.80, 81.76]; total=37920, n=372m | 112.07 [63.78, 160.35]; total=48078, n=344m | 261.81 [136.28, 387.35]; total=12967, n=73m |
| Unattributed HP taken/min | 2874.83 [2639.69, 3109.97]; total=1.97197e+06, n=372m | 3198.48 [2889.89, 3507.08]; total=1.37219e+06, n=344m | 1312.56 [976.75, 1648.38]; total=65008, n=73m |

## Bot: big losses

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Observed minutes (n matches) | 202.4 (n=114) | 59.4 (n=86) | 0.1 (n=1) |
| Own elixir at decisions | 4.59 (n=22353) | 4.47 (n=5970) | 2.44 (n=6) |
| Own elixir at plays | 5.35 (n=1554) | 4.36 (n=749) | 2.71 (n=1) |
| Enemy units on our side at play | 1.62 (n=1554) | 3.69 (n=749) | 4.00 (n=1) |
| Enemy nominal elixir on our side | 5.81 (n=1554) | 12.77 (n=749) | 16.00 (n=1) |
| Own bodies alive at play | 1.25 (n=1554) | 1.81 (n=749) | 0.00 (n=1) |
| Elixir at push crossing | 3.69 (n=502) | 4.15 (n=95) | unavailable |
| Response seconds, observed responses | 3.53 (n=360) | 2.05 (n=77) | unavailable |
| X-Bow elixir | 8.89 (n=169) | 7.72 (n=48) | unavailable |
| X-Bow following 20s tower damage, all sources | 1850.73 (n=169) | 819.94 (n=48) | unavailable |
| Cap seconds/min, both endpoints at 10 | 2.00 [1.35, 2.65]; total=404.7, n=114m | 3.13 [1.32, 4.95]; total=186.15, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Plays/min | 7.68 [7.46, 7.90]; total=1554, n=114m | 12.60 [11.83, 13.38]; total=749, n=86m | 9.76 [CI unavailable]; total=1, n=1m |
| Cheap quiet cycles/min | 0.60 [0.48, 0.72]; total=122, n=114m | 0.37 [0.15, 0.59]; total=22, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Quiet defensive plays/min | 0.51 [0.40, 0.62]; total=103, n=114m | 0.24 [0.11, 0.36]; total=14, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Quiet defensive elixir/min | 1.42 [1.10, 1.73]; total=287, n=114m | 0.79 [0.38, 1.21]; total=47, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Overcommit engagements/min | 0.02 [0.00, 0.05]; total=5, n=114m | 0.12 [0.04, 0.20]; total=7, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Overcommit excess elixir/min | 0.02 [0.00, 0.05]; total=4.8, n=114m | 0.30 [0.05, 0.55]; total=18.0333, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Tower HP dealt/min | 1848.02 [1635.81, 2060.23]; total=373948, n=114m | 1039.93 [750.15, 1329.72]; total=61805, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Tower HP taken/min | 5176.42 [4647.39, 5705.45]; total=1.04745e+06, n=114m | 9292.64 [8171.84, 10413.44]; total=552277, n=86m | 5385.37 [CI unavailable]; total=552, n=1m |
| Crowns gained/min | 0.11 [0.07, 0.15]; total=22, n=114m | 0.27 [0.16, 0.38]; total=16, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Crowns lost/min | 0.84 [0.71, 0.96]; total=169, n=114m | 2.68 [2.31, 3.04]; total=159, n=86m | 19.51 [CI unavailable]; total=2, n=1m |
| Positive trade PROXY/min | 1.92 [1.77, 2.07]; total=388, n=114m | 0.67 [0.47, 0.88]; total=40, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Negative trade PROXY/min | 0.10 [0.06, 0.14]; total=20, n=114m | 0.15 [0.06, 0.24]; total=9, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Net nominal trade PROXY/min | 23.15 [19.17, 27.13]; total=4684.53, n=114m | 6.46 [3.07, 9.84]; total=383.7, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| X-Bow observed tower locks/min | 0.59 [0.52, 0.66]; total=120, n=114m | 0.34 [0.21, 0.46]; total=20, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Rocket tower targets/min | 0.09 [0.05, 0.13]; total=18, n=114m | 0.20 [0.10, 0.31]; total=12, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Enemy big-spell contact episodes/min | 0.00 [0.00, 0.01]; total=1, n=114m | 0.02 [0.00, 0.05]; total=1, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Enemy other-spell contact episodes/min | 0.11 [0.05, 0.18]; total=23, n=114m | 0.27 [0.10, 0.44]; total=16, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Spell-associated HP taken/min, not causal | 105.91 [31.24, 180.58]; total=21431, n=114m | 215.66 [27.83, 403.48]; total=12817, n=86m | 0.00 [CI unavailable]; total=0, n=1m |
| Unattributed HP taken/min | 5070.51 [4540.25, 5600.77]; total=1.02602e+06, n=114m | 9076.98 [7979.08, 10174.87]; total=539460, n=86m | 5385.37 [CI unavailable]; total=552, n=1m |

## Cards played per minute

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| IceWizard | 1.34 [1.32, 1.36]; total=1920, n=771m | 2.44 [2.40, 2.48]; total=2369, n=743m | 3.54 [3.39, 3.69]; total=392, n=165m |
| Knight | 1.30 [1.27, 1.32]; total=1858, n=771m | 2.37 [2.33, 2.41]; total=2301, n=743m | 3.38 [3.21, 3.55]; total=374, n=165m |
| Log | 1.26 [1.23, 1.29]; total=1812, n=771m | 1.91 [1.85, 1.96]; total=1852, n=743m | 2.91 [2.71, 3.10]; total=322, n=165m |
| Rocket | 0.14 [0.13, 0.16]; total=206, n=771m | 0.42 [0.38, 0.46]; total=408, n=743m | 1.46 [1.27, 1.66]; total=162, n=165m |
| Skeletons | 1.41 [1.39, 1.44]; total=2026, n=771m | 2.37 [2.32, 2.41]; total=2299, n=743m | 3.33 [3.15, 3.52]; total=369, n=165m |
| Tesla | 1.04 [1.02, 1.07]; total=1498, n=771m | 1.79 [1.74, 1.83]; total=1735, n=743m | 2.58 [2.39, 2.78]; total=286, n=165m |
| Tornado | 0.48 [0.45, 0.51]; total=690, n=771m | 0.85 [0.80, 0.90]; total=824, n=743m | 1.50 [1.31, 1.69]; total=166, n=165m |
| Xbow | 0.76 [0.73, 0.79]; total=1092, n=771m | 1.26 [1.21, 1.30]; total=1222, n=743m | 0.86 [0.69, 1.02]; total=95, n=165m |

## Lane × zone placements per minute

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| left.bridge | 1.64 [1.56, 1.71]; total=2349, n=771m | 2.89 [2.71, 3.06]; total=2803, n=743m | 4.84 [4.09, 5.59]; total=536, n=165m |
| left.enemy_side | 0.12 [0.10, 0.13]; total=167, n=771m | 0.39 [0.34, 0.43]; total=375, n=743m | 1.17 [0.92, 1.41]; total=129, n=165m |
| left.own_back | 0.80 [0.74, 0.86]; total=1143, n=771m | 1.10 [1.00, 1.19]; total=1064, n=743m | 1.21 [0.86, 1.56]; total=134, n=165m |
| left.own_front | 1.43 [1.36, 1.49]; total=2047, n=771m | 2.12 [2.00, 2.23]; total=2058, n=743m | 2.01 [1.72, 2.31]; total=223, n=165m |
| right.bridge | 1.20 [1.13, 1.27]; total=1723, n=771m | 2.89 [2.73, 3.06]; total=2812, n=743m | 4.99 [4.26, 5.71]; total=552, n=165m |
| right.enemy_side | 0.14 [0.12, 0.15]; total=194, n=771m | 0.36 [0.31, 0.41]; total=350, n=743m | 1.02 [0.81, 1.23]; total=113, n=165m |
| right.own_back | 0.63 [0.58, 0.68]; total=907, n=771m | 0.94 [0.85, 1.03]; total=912, n=743m | 1.24 [0.88, 1.60]; total=137, n=165m |
| right.own_front | 1.79 [1.72, 1.86]; total=2572, n=771m | 2.71 [2.59, 2.83]; total=2636, n=743m | 3.09 [2.69, 3.49]; total=342, n=165m |

## Own spell targeting geometry per minute

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Log.both | 0.66 [0.63, 0.69]; total=947, n=771m | 0.97 [0.92, 1.03]; total=945, n=743m | 1.51 [1.28, 1.74]; total=167, n=165m |
| Log.neither | 0.06 [0.05, 0.08]; total=91, n=771m | 0.13 [0.11, 0.16]; total=130, n=743m | 0.25 [0.12, 0.38]; total=28, n=165m |
| Log.tower | 0.15 [0.13, 0.17]; total=218, n=771m | 0.05 [0.04, 0.07]; total=52, n=743m | 0.07 [0.02, 0.13]; total=8, n=165m |
| Log.units | 0.39 [0.36, 0.42]; total=556, n=771m | 0.75 [0.69, 0.80]; total=725, n=743m | 1.07 [0.88, 1.27]; total=119, n=165m |
| Rocket.both | 0.02 [0.01, 0.02]; total=22, n=771m | 0.05 [0.03, 0.06]; total=44, n=743m | 0.09 [0.04, 0.14]; total=10, n=165m |
| Rocket.neither | 0.01 [0.01, 0.02]; total=18, n=771m | 0.03 [0.02, 0.04]; total=28, n=743m | 0.01 [0.00, 0.03]; total=1, n=165m |
| Rocket.tower | 0.09 [0.07, 0.10]; total=123, n=771m | 0.28 [0.24, 0.31]; total=268, n=743m | 1.28 [1.09, 1.48]; total=142, n=165m |
| Rocket.units | 0.03 [0.02, 0.04]; total=43, n=771m | 0.07 [0.05, 0.09]; total=68, n=743m | 0.08 [0.01, 0.15]; total=9, n=165m |
| Tornado.both | 0.10 [0.08, 0.11]; total=142, n=771m | 0.18 [0.15, 0.20]; total=172, n=743m | 0.42 [0.31, 0.54]; total=47, n=165m |
| Tornado.neither | 0.14 [0.12, 0.16]; total=199, n=771m | 0.12 [0.10, 0.14]; total=115, n=743m | 0.12 [0.06, 0.18]; total=13, n=165m |
| Tornado.tower | 0.01 [0.00, 0.01]; total=9, n=771m | 0.01 [0.00, 0.02]; total=10, n=743m | 0.03 [0.00, 0.06]; total=3, n=165m |
| Tornado.units | 0.24 [0.21, 0.26]; total=340, n=771m | 0.54 [0.50, 0.59]; total=527, n=743m | 0.93 [0.74, 1.12]; total=103, n=165m |

## Enemy spell tower-contact candidates per minute

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Arrows | 0.05 [0.03, 0.07]; total=72, n=771m | 0.16 [0.12, 0.20]; total=155, n=743m | 0.39 [0.22, 0.55]; total=43, n=165m |
| BarbLog | 0.02 [0.01, 0.03]; total=30, n=771m | 0.03 [0.02, 0.05]; total=33, n=743m | 0.06 [0.01, 0.12]; total=7, n=165m |
| Earthquake | 0.00 [0.00, 0.00]; total=0, n=771m | 0.00 [0.00, 0.00]; total=0, n=743m | 0.00 [0.00, 0.03]; total=0, n=165m |
| Fireball | 0.03 [0.02, 0.04]; total=40, n=771m | 0.05 [0.03, 0.07]; total=49, n=743m | 0.14 [0.05, 0.22]; total=15, n=165m |
| Lightning | 0.00 [0.00, 0.00]; total=1, n=771m | 0.00 [0.00, 0.00]; total=2, n=743m | 0.00 [0.00, 0.03]; total=0, n=165m |
| Log | 0.06 [0.04, 0.07]; total=83, n=771m | 0.18 [0.14, 0.21]; total=171, n=743m | 0.42 [0.25, 0.58]; total=46, n=165m |
| Poison | 0.00 [0.00, 0.00]; total=0, n=771m | 0.00 [0.00, 0.00]; total=0, n=743m | 0.00 [0.00, 0.03]; total=0, n=165m |
| Rocket | 0.01 [0.00, 0.01]; total=11, n=771m | 0.03 [0.01, 0.04]; total=26, n=743m | 0.14 [0.03, 0.24]; total=15, n=165m |
| Snowball | 0.01 [0.00, 0.01]; total=11, n=771m | 0.03 [0.01, 0.04]; total=27, n=743m | 0.08 [0.01, 0.15]; total=9, n=165m |
| Vines | 0.00 [0.00, 0.00]; total=0, n=771m | 0.00 [0.00, 0.00]; total=0, n=743m | 0.00 [0.00, 0.03]; total=0, n=165m |
| Zap | 0.00 [0.00, 0.00]; total=0, n=771m | 0.00 [0.00, 0.00]; total=0, n=743m | 0.00 [0.00, 0.03]; total=0, n=165m |

## Definitions and limits

- Rate CIs: ratio-of-sums, match-cluster delta-method normal 95% intervals; human sides cluster by replay. Nonnegative lower bounds are truncated at zero. Zero events use a rule-of-three-style upper bound. Small groups and rare events have approximate coverage; one-cluster CIs are unavailable. Means have their actual observation n; repeated decisions are not independent matches.
- Lane uses own-frame x<9 left, otherwise right. Zones use y<15 enemy side, 15–18 bridge, >18–<24 own front, >=24 own back; own edge is y=32. The broader X-Bow offensive bridge class is y=16–21; deeper bows are defensive. Cells are floor(tile x), floor(tile y). Pro blue coordinates are rotated 180 degrees; bot raw bodies rotate only for observer side 0. Bot play/model xy has mirrored x: placement x=18−18*xy[0], y=32*xy[1]. This is checked against actual post-confirmation public X-Bow/Tesla body coordinates; placement alignment errors are reported.
- At-play board and elixir use the last PUBLIC decision at or before the confirmed tap attempt, max age 2s for board. Raw elixir is preferred over the play-event forecast; both are retained. Tower HP means include present towers only; destroyed/missing towers are explicit in event receipts. Units are bodies (buildings included at play); Hero Ice Wizard floating-cube duplicates are removed by category/position.
- Nominal body elixir = catalog card cost / standard spawn count. It is NOT actual opponent spend: spawned tokens, split cards, evolutions, death spawns, abilities, duplicate identities and transformations can violate it. Unknown IDs are counted and receive no imputed value. Exact enemy committed/killed elixir and exact elixir trades are unavailable.
- Push starts when the same observed enemy body moves from y<16 to y>=16 within <=3s, in a lane without an active engagement. Ends after 3s with no enemy on our side in that lane. First-seen intrusions are counted separately and do not masquerade as bridge crossings. Elixir is the first post-crossing public sample, with interval uncertainty exported; flying river crossings are included.
- Response = first confirmed own-side card play in that lane (central plays may cover either lane), excluding offensive bridge X-Bows, from crossing until engagement end. Each play goes to at most one engagement. Pre-positioned defence is not a response; no response is censored, not zero. All nominal own spending here excludes abilities. Completed engagements with no unknown entrant value yield trade PROXY = nominal entrant value minus reactive card spend; it does not establish killed value. Engagement totals are assigned to onset phase, so cross-phase spending differs from play-phase totals.
- Quiet cycle = cost <=3 and no visible enemy body at y>=12 (our half plus a 4-tile enemy-side buffer). Quiet defence proxy uses that same threat test and an own-side y>=18 Tesla/IceWizard/Knight/Skeletons/Tornado play. Reported elixir is spend flagged by this heuristic, not proven waste. Overcommit proxy = max(0, reactive spend − nominal entrant value − 2); excludes censored/unknown-value engagements.
- Tower identification requires card_id=-1 AND fixed tower coordinates within 0.2 tiles; moving unknown bodies also use -1 in these logs. Legacy ID-only scorecard outcomes are retained for comparison. Damage uses monotonically decreasing public HP through tick<6000; absence is accepted only with no later reappearance and two missing decisions (or the terminal closed observation). Remaining princess HP removed automatically after king death is excluded from combat damage. HP increases are flagged. Damage is assigned to the observation phase, so boundary damage may shift by one sampling interval. Crowns derive from princess destruction or three for king destruction. Missing opening/end observations can undercount damage and crowns.
- Observed X-Bow lock requires an own X-Bow projectile aimed at a live enemy tower and exactly one own X-Bow alive near that placement. No observed lock means unknown/undetected, not proven no lock. Follow-up damage is total enemy tower HP loss in the next <=20 seconds after placement; locked-target damage is also exported. It includes other attackers/spells and is right-censored near match end. No source-specific damage is claimed.
- Own spell target types are deployment-time geometric footprints, not proven targets/hits. Log/Barbarian Barrel use a forward strip; other spells use explicit approximate radii plus tower radius 1 tile or unit margin 0.5. Rocket-on-tower counts include both tower-only and tower+units. Following 8s target tower HP loss is all-source association; true chip and enemy elixir killed are null.
- Enemy spell counts are sampled projectile-target/spell-body tower-contact EPISODES, not certified hits or casts. Dedupe same spell/tower until >2s observation gap; multi-tower spells count contacts per tower. Radius/target geometry can misclassify; invisible instant spells can be missed completely. Zero observed Poison/Earthquake/Vines is not zero actual usage. Tower HP drops from first sighting through last sighting+5s are spell-associated; damage intervals are deduplicated across candidates. GoblinBarrel/Graveyard/Clone/Mirror/RoyalDelivery summon/copy contacts are separate and do not qualify damage as direct-spell-associated. Remaining damage is unattributed, NOT certified unit damage. Exact spell-versus-unit damage is unavailable.
- Cap occupancy is the observed time with both interval endpoints at >=9.999 elixir and <=2s apart; endpoint-any cap seconds provide a sensitivity measure, not a strict mathematical upper bound if unseen spend/regen happens. No interpolation bridges larger gaps. Multiply by measured phase regen for nominal leaked elixir; no opportunity-cost claim.
- The subset surviving to 3x differs from early-ending matches. Paired comparisons require >=30s in each phase and accompany aggregate findings. Checkpoint/fast flags are tags, not randomized treatments. Missing historical pipeline_decisions is interpreted as false by the scorecard convention, with fast_flag_recorded=false explicitly retained. No causal model-quality or policy-change recommendation follows from these measurements.

## What the human HTML supports

Directly supported: card, tick, side and placement; match end marker; final crowns from captured URL; per-phase plays/card rates, lane/zone, X-Bow cell/bridge/defensive histograms, and Rocket tower-target geometry. Both sides are reported for all decks, X-Bow sides separately, with win/loss/big-loss splits in report.json. Duplicate timeline and map entries are reconciled by using map markers once; ability markers are excluded from card counts.
Unsupported: decision-time or actual play-time elixir; per-phase cap/leak time (HTML has only whole-match aggregate leakage); living units, troop HP and tower HP; push crossings, response timing, defence commitments or trades; X-Bow tower locks and following damage; spell target units/kills/actual chip; threat-conditioned cycling or wasted spend; phase-resolved crowns and damage; enemy spell hits and spell-versus-unit damage. No simulator reconstruction or inferred opponent hidden state was substituted.
The human corpus has no checkpoint or fast-plays flags. X-Bow classification requires an observed X-Bow play and may miss decks that never played it. These opponents, levels, deck mix and selection rules differ from the bot sample; the comparison is descriptive.

## Audit files

`report.json` contains all rate denominators/CIs, outcome splits, checkpoint × fast-plays splits, per-match phase summaries, coverage and input hashes. `plays.jsonl` holds confirmed bot play states and X-Bow/spell receipts. `pushes.jsonl` holds engagements. `enemy_spells.jsonl` holds public contact candidates. `pro_plays.jsonl` holds parsed human plays. No opponent hidden state is exported.

Rerun: `python phase_stats.py --since 20261008`. Tests: use an installed pytest interpreter with `-B -m pytest -q -p no:cacheprovider test_phase_stats.py`; disable plugin autoload.
