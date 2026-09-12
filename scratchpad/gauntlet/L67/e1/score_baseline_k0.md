# E1 option B -- S1 vs held-out ghosts (live rule)

Run dirs: `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L67\e1\baseline_k0\slot0`, `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L67\e1\baseline_k0\slot1`. Duplicates dropped: 0.
Bootstrap: entry-clustered, 10000 draws, seed 20260912.

## Run

| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |
|---|---|---|---|---|---|---|---|
| 293 | 293 | 152 | 0 | 141 | 51.9% | 46.1% .. 57.7% (entry-weighted 51.9%) | 46.2% .. 57.6% |

| per seed k | n | winrate |
|---|---|---|
| 0 | 293 | 51.9% |

| per slot | n | winrate |
|---|---|---|
| 0 | 293 | 51.9% |

Decided BEFORE the ghost script ended (end <= last ghost tick + 200): 108/229 = 47.2%. Wins after the script ended: 44 (28.9% of wins).
Wins where the real pro lost: 68 of 132 such matches.

| ghost plays delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=10 | 27 | 8 | 29.6% | 5.3% |
| 11-30 | 185 | 93 | 50.3% | 61.2% |
| >30 | 81 | 51 | 63.0% | 33.6% |

| distinct ghost cards delivered | n | wins | winrate | share of wins |
|---|---|---|---|---|
| <=3 | 1 | 1 | 100.0% | 0.7% |
| 4-6 | 25 | 8 | 32.0% | 5.3% |
| >6 | 267 | 143 | 53.6% | 94.1% |

| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |
|---|---|---|---|---|---|---|---|---|---|
| 13.36 | 12.02 | 89.9% | 42.4 | 0.01 | 210.9 | 190.3 | 195.5 | 0.77 | 12.3 |

Matches whose degraded-observation count != decisions: 0. Policies: {'live': 293}.

