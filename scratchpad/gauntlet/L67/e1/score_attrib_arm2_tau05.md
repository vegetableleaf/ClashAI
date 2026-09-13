# A1 arm2_tau05 (vs live rule), held-out 0:100

Run dirs: `scratchpad\gauntlet\L67\e1\attrib\arm2_tau05\slot0`. Duplicates dropped: 0.
Bootstrap: entry-clustered, 10000 draws, seed 20260912.

## Run

| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |
|---|---|---|---|---|---|---|---|
| 100 | 100 | 68 | 0 | 32 | 68.0% | 59.0% .. 77.0% (entry-weighted 68.0%) | 58.9% .. 77.1% |

| per seed k | n | winrate |
|---|---|---|
| 0 | 100 | 68.0% |

| per slot | n | winrate |
|---|---|---|
| 0 | 100 | 68.0% |

Decided BEFORE the ghost script ended (end <= last ghost tick + 200): 51/79 = 64.6%. Wins after the script ended: 17 (25.0% of wins).
Wins where the real pro lost: 29 of 46 such matches.

| ghost plays delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=10 | 10 | 4 | 40.0% | 5.9% |
| 11-30 | 71 | 47 | 66.2% | 69.1% |
| >30 | 19 | 17 | 89.5% | 25.0% |

| distinct ghost cards delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=3 | 1 | 1 | 100.0% | 1.5% |
| 4-6 | 10 | 4 | 40.0% | 5.9% |
| >6 | 89 | 63 | 70.8% | 92.6% |

| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |
|---|---|---|---|---|---|---|---|---|---|
| 12.12 | 10.88 | 89.7% | 37.4 | 0.11 | 134.4 | 185.2 | 192.4 | 0.75 | 11.2 |

Matches whose degraded-observation count != decisions: 0. Policies: {'live': 100}.

## Paired vs control `liverule`

| pairs | entries | both win | run only | control only | neither | run WR | control WR | delta | clustered 95% CI | McNemar p | survival delta s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 100 | 44 | 24 | 8 | 24 | 68.0% | 52.0% | 16.0% | 5.0% .. 27.0% | 0.007 | -4.3 +- 4.8 |

Plays/min run 12.12 vs control 13.32; accepted/min 10.88 vs 11.94. Unpaired keys: run 0, control 193.

