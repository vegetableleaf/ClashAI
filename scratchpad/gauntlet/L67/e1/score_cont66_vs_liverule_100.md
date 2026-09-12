# E1 5cs.66 rule (tau .5, no mask, clean obs) vs live rule, held-out 0:100

Run dirs: `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L67\e1\cont66_100\slot0`. Duplicates dropped: 0.
Bootstrap: entry-clustered, 10000 draws, seed 20260912.

## Run

| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |
|---|---|---|---|---|---|---|---|
| 100 | 100 | 89 | 0 | 11 | 89.0% | 83.0% .. 95.0% (entry-weighted 89.0%) | 82.9% .. 95.1% |

| per seed k | n | winrate |
|---|---|---|
| 0 | 100 | 89.0% |

| per slot | n | winrate |
|---|---|---|
| 0 | 100 | 89.0% |

Decided BEFORE the ghost script ended (end <= last ghost tick + 200): 70/79 = 88.6%. Wins after the script ended: 19 (21.3% of wins).
Wins where the real pro lost: 42 of 46 such matches.

| ghost plays delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=10 | 3 | 3 | 100.0% | 3.4% |
| 11-30 | 80 | 72 | 90.0% | 80.9% |
| >30 | 17 | 14 | 82.4% | 15.7% |

| distinct ghost cards delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=3 | 1 | 1 | 100.0% | 1.1% |
| 4-6 | 6 | 6 | 100.0% | 6.7% |
| >6 | 93 | 82 | 88.2% | 92.1% |

| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |
|---|---|---|---|---|---|---|---|---|---|
| 10.13 | 9.03 | 89.2% | 32.1 | 0.00 | 0.0 | 190.3 | 188.9 | 0.78 | 12.1 |

Matches whose degraded-observation count != decisions: 0. Policies: {'live': 100}.

## Paired vs control `liverule`

| pairs | entries | both win | run only | control only | neither | run WR | control WR | delta | clustered 95% CI | McNemar p | survival delta s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 100 | 49 | 40 | 3 | 8 | 89.0% | 52.0% | 37.0% | 26.0% .. 48.0% | 3.02e-09 | 0.8 +- 5.4 |

Plays/min run 10.13 vs control 13.32; accepted/min 9.03 vs 11.94. Unpaired keys: run 0, control 193.

