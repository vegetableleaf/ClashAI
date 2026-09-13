# A1 arm 1: live rule + CLEAN observations (vs live rule), held-out 0:100

Run dirs: `scratchpad\gauntlet\L67\e1\attrib\arm1_clean_obs\slot0`. Duplicates dropped: 0.
Bootstrap: entry-clustered, 10000 draws, seed 20260912.

## Run

| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |
|---|---|---|---|---|---|---|---|
| 100 | 100 | 92 | 0 | 8 | 92.0% | 86.0% .. 97.0% (entry-weighted 92.0%) | 86.7% .. 97.3% |

| per seed k | n | winrate |
|---|---|---|
| 0 | 100 | 92.0% |

| per slot | n | winrate |
|---|---|---|
| 0 | 100 | 92.0% |

Decided BEFORE the ghost script ended (end <= last ghost tick + 200): 74/81 = 91.4%. Wins after the script ended: 18 (19.6% of wins).
Wins where the real pro lost: 42 of 46 such matches.

| ghost plays delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=10 | 4 | 3 | 75.0% | 3.3% |
| 11-30 | 80 | 75 | 93.8% | 81.5% |
| >30 | 16 | 14 | 87.5% | 15.2% |

| distinct ghost cards delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=3 | 1 | 1 | 100.0% | 1.1% |
| 4-6 | 6 | 5 | 83.3% | 5.4% |
| >6 | 93 | 86 | 92.5% | 93.5% |

| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |
|---|---|---|---|---|---|---|---|---|---|
| 11.51 | 10.15 | 88.2% | 35.6 | 0.68 | 59.8 | 185.8 | 184.4 | 0.77 | 11.1 |

Matches whose degraded-observation count != decisions: 0. Policies: {'live': 100}.

## Paired vs control `liverule`

| pairs | entries | both win | run only | control only | neither | run WR | control WR | delta | clustered 95% CI | McNemar p | survival delta s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 100 | 52 | 40 | 0 | 8 | 92.0% | 52.0% | 40.0% | 31.0% .. 50.0% | 1.82e-12 | -3.7 +- 5.2 |

Plays/min run 11.51 vs control 13.32; accepted/min 10.15 vs 11.94. Unpaired keys: run 0, control 193.

