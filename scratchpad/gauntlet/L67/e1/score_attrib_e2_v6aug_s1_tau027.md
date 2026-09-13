# E2 e2_v6aug_s1_tau027 vs v6lat live rule, held-out 0:100

Run dirs: `scratchpad\gauntlet\L67\e1\attrib\e2_v6aug_s1_tau027\slot0`. Duplicates dropped: 0.
Bootstrap: entry-clustered, 10000 draws, seed 20260912.

## Run

| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |
|---|---|---|---|---|---|---|---|
| 100 | 100 | 74 | 0 | 26 | 74.0% | 65.0% .. 82.0% (entry-weighted 74.0%) | 65.4% .. 82.6% |

| per seed k | n | winrate |
|---|---|---|
| 0 | 100 | 74.0% |

| per slot | n | winrate |
|---|---|---|
| 0 | 100 | 74.0% |

Decided BEFORE the ghost script ended (end <= last ghost tick + 200): 47/71 = 66.2%. Wins after the script ended: 27 (36.5% of wins).
Wins where the real pro lost: 33 of 46 such matches.

| ghost plays delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=10 | 4 | 3 | 75.0% | 4.1% |
| 11-30 | 77 | 60 | 77.9% | 81.1% |
| >30 | 19 | 11 | 57.9% | 14.9% |

| distinct ghost cards delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=3 | 1 | 1 | 100.0% | 1.4% |
| 4-6 | 6 | 5 | 83.3% | 6.8% |
| >6 | 93 | 68 | 73.1% | 91.9% |

| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |
|---|---|---|---|---|---|---|---|---|---|
| 12.69 | 11.40 | 89.8% | 41.9 | 0.40 | 141.9 | 198.2 | 193.7 | 0.80 | 14.0 |

Matches whose degraded-observation count != decisions: 0. Policies: {'live': 100}.

## Paired vs control `v6lat_live`

| pairs | entries | both win | run only | control only | neither | run WR | control WR | delta | clustered 95% CI | McNemar p | survival delta s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 100 | 45 | 29 | 7 | 19 | 74.0% | 52.0% | 22.0% | 11.0% .. 33.0% | 0.000313 | 8.7 +- 5.4 |

Plays/min run 12.69 vs control 13.32; accepted/min 11.40 vs 11.94. Unpaired keys: run 0, control 193.

