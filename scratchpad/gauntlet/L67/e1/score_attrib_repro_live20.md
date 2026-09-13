# A1 reproduction: live rule, held-out 0:20, new boot vs baseline_k0

Run dirs: `scratchpad\gauntlet\L67\e1\attrib\repro_live20\slot0`. Duplicates dropped: 0.
Bootstrap: entry-clustered, 10000 draws, seed 20260912.

## Run

| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |
|---|---|---|---|---|---|---|---|
| 20 | 20 | 13 | 0 | 7 | 65.0% | 45.0% .. 85.0% (entry-weighted 65.0%) | 44.1% .. 85.9% |

| per seed k | n | winrate |
|---|---|---|
| 0 | 20 | 65.0% |

| per slot | n | winrate |
|---|---|---|
| 0 | 20 | 65.0% |

Decided BEFORE the ghost script ended (end <= last ghost tick + 200): 11/18 = 61.1%. Wins after the script ended: 2 (15.4% of wins).
Wins where the real pro lost: 7 of 11 such matches.

| ghost plays delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=10 | 2 | 0 | 0.0% | 0.0% |
| 11-30 | 13 | 8 | 61.5% | 61.5% |
| >30 | 5 | 5 | 100.0% | 38.5% |

| distinct ghost cards delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=3 | 0 | 0 | n/a | 0.0% |
| 4-6 | 1 | 0 | 0.0% | 0.0% |
| >6 | 19 | 13 | 68.4% | 100.0% |

| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |
|---|---|---|---|---|---|---|---|---|---|
| 13.30 | 11.98 | 90.0% | 41.7 | 0.00 | 208.7 | 188.1 | 202.4 | 1.00 | 11.8 |

Matches whose degraded-observation count != decisions: 0. Policies: {'live': 20}.

## Paired vs control `liverule`

| pairs | entries | both win | run only | control only | neither | run WR | control WR | delta | clustered 95% CI | McNemar p | survival delta s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 20 | 13 | 0 | 0 | 7 | 65.0% | 65.0% | 0.0% | 0.0% .. 0.0% | 1 | 0.0 +- 0.0 |

Plays/min run 13.30 vs control 13.30; accepted/min 11.98 vs 11.98. Unpaired keys: run 0, control 273.

