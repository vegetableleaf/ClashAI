# A1 arm3_no_mask (vs live rule), held-out 0:100

Run dirs: `scratchpad\gauntlet\L67\e1\attrib\arm3_no_mask\slot0`. Duplicates dropped: 0.
Bootstrap: entry-clustered, 10000 draws, seed 20260912.

## Run

| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |
|---|---|---|---|---|---|---|---|
| 100 | 100 | 63 | 0 | 37 | 63.0% | 53.0% .. 72.0% (entry-weighted 63.0%) | 53.5% .. 72.5% |

| per seed k | n | winrate |
|---|---|---|
| 0 | 100 | 63.0% |

| per slot | n | winrate |
|---|---|---|
| 0 | 100 | 63.0% |

Decided BEFORE the ghost script ended (end <= last ghost tick + 200): 38/71 = 53.5%. Wins after the script ended: 25 (39.7% of wins).
Wins where the real pro lost: 26 of 46 such matches.

| ghost plays delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=10 | 8 | 4 | 50.0% | 6.3% |
| 11-30 | 65 | 43 | 66.2% | 68.3% |
| >30 | 27 | 16 | 59.3% | 25.4% |

| distinct ghost cards delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=3 | 1 | 1 | 100.0% | 1.6% |
| 4-6 | 7 | 4 | 57.1% | 6.3% |
| >6 | 92 | 58 | 63.0% | 92.1% |

| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |
|---|---|---|---|---|---|---|---|---|---|
| 23.30 | 12.10 | 51.9% | 78.0 | 0.00 | 0.0 | 200.9 | 203.1 | 0.74 | 12.3 |

Matches whose degraded-observation count != decisions: 0. Policies: {'live': 100}.

## Paired vs control `liverule`

| pairs | entries | both win | run only | control only | neither | run WR | control WR | delta | clustered 95% CI | McNemar p | survival delta s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 100 | 45 | 18 | 7 | 30 | 63.0% | 52.0% | 11.0% | 2.0% .. 21.0% | 0.0433 | 11.3 +- 4.2 |

Plays/min run 23.30 vs control 13.32; accepted/min 12.10 vs 11.94. Unpaired keys: run 0, control 193.

