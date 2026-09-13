# E2 e2_v6aug_s1_tau0083 vs v6lat live rule, held-out 0:100

Run dirs: `scratchpad\gauntlet\L67\e1\attrib\e2_v6aug_s1_tau0083\slot0`. Duplicates dropped: 0.
Bootstrap: entry-clustered, 10000 draws, seed 20260912.

## Run

| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |
|---|---|---|---|---|---|---|---|
| 100 | 100 | 45 | 0 | 55 | 45.0% | 35.0% .. 55.0% (entry-weighted 45.0%) | 35.2% .. 54.8% |

| per seed k | n | winrate |
|---|---|---|
| 0 | 100 | 45.0% |

| per slot | n | winrate |
|---|---|---|
| 0 | 100 | 45.0% |

Decided BEFORE the ghost script ended (end <= last ghost tick + 200): 27/74 = 36.5%. Wins after the script ended: 18 (40.0% of wins).
Wins where the real pro lost: 21 of 46 such matches.

| ghost plays delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=10 | 8 | 3 | 37.5% | 6.7% |
| 11-30 | 73 | 32 | 43.8% | 71.1% |
| >30 | 19 | 10 | 52.6% | 22.2% |

| distinct ghost cards delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=3 | 2 | 2 | 100.0% | 4.4% |
| 4-6 | 8 | 1 | 12.5% | 2.2% |
| >6 | 90 | 42 | 46.7% | 93.3% |

| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |
|---|---|---|---|---|---|---|---|---|---|
| 13.54 | 12.13 | 89.6% | 42.5 | 0.00 | 245.4 | 188.2 | 192.5 | 0.84 | 13.6 |

Matches whose degraded-observation count != decisions: 0. Policies: {'live': 100}.

## Paired vs control `v6lat_live`

| pairs | entries | both win | run only | control only | neither | run WR | control WR | delta | clustered 95% CI | McNemar p | survival delta s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 100 | 33 | 12 | 19 | 36 | 45.0% | 52.0% | -7.0% | -18.0% .. 4.0% | 0.281 | -1.3 +- 5.0 |

Plays/min run 13.54 vs control 13.32; accepted/min 12.13 vs 11.94. Unpaired keys: run 0, control 193.

