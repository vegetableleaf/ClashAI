# A1 arm4_no_stall (vs live rule), held-out 0:100

Run dirs: `scratchpad\gauntlet\L67\e1\attrib\arm4_no_stall\slot0`. Duplicates dropped: 0.
Bootstrap: entry-clustered, 10000 draws, seed 20260912.

## Run

| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |
|---|---|---|---|---|---|---|---|
| 100 | 100 | 52 | 0 | 48 | 52.0% | 42.0% .. 62.0% (entry-weighted 52.0%) | 42.2% .. 61.8% |

| per seed k | n | winrate |
|---|---|---|
| 0 | 100 | 52.0% |

| per slot | n | winrate |
|---|---|---|
| 0 | 100 | 52.0% |

Decided BEFORE the ghost script ended (end <= last ghost tick + 200): 37/79 = 46.8%. Wins after the script ended: 15 (28.8% of wins).
Wins where the real pro lost: 26 of 46 such matches.

| ghost plays delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=10 | 9 | 3 | 33.3% | 5.8% |
| 11-30 | 68 | 32 | 47.1% | 61.5% |
| >30 | 23 | 17 | 73.9% | 32.7% |

| distinct ghost cards delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=3 | 1 | 1 | 100.0% | 1.9% |
| 4-6 | 8 | 2 | 25.0% | 3.8% |
| >6 | 91 | 49 | 53.8% | 94.2% |

| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |
|---|---|---|---|---|---|---|---|---|---|
| 13.32 | 11.94 | 89.6% | 42.1 | 0.00 | 210.4 | 189.5 | 198.7 | 0.68 | 11.6 |

Matches whose degraded-observation count != decisions: 0. Policies: {'live': 100}.

## Paired vs control `liverule`

| pairs | entries | both win | run only | control only | neither | run WR | control WR | delta | clustered 95% CI | McNemar p | survival delta s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 100 | 52 | 0 | 0 | 48 | 52.0% | 52.0% | 0.0% | 0.0% .. 0.0% | 1 | 0.0 +- 0.0 |

Plays/min run 13.32 vs control 13.32; accepted/min 11.94 vs 11.94. Unpaired keys: run 0, control 193.

