# W13 -- where does ICEBOW Mark CLX lose on Ranked? (2026-10-21, data to 07:08 EDT)

Labels: **(a) measured** (number given), **(b) plausible, untested** (measurement proposed), **(c) contradicted** (evidence
given). CIs: Wilson 95% for rates, Newcombe 95% for differences. All tables: `report.out` (rebuilt by `report.py`).

## 0. Data and how it was built

- **CLX Ranked: 233 matches**, 10-20 13:28 -> 10-21 07:08 (main account, our princess 4858). Ranked started at 13:28, not in the
  evening: every main-account CLX match from `live_play_20261020_132855` on reads `trophies n/a`, with one LIVE_OPTIONS /
  decision-options hash (a81f578b) throughout. The evening-only part (18:00 on, n = 185) is 44.3% [37.4, 51.5].
- **CLX ladder 13.5-14k: 138 matches**, 10-19 14:02 -> 23:59 (tower level 16; graded trophy delta; |delta| > 100 dropped).
- Dropped: 13 rows with no frames / other account, 5 `n/a` matches of 10-19 17:37-17:56 (mode unknown), 1 bad delta.
- **SIM**: CLX on fin15, all16, 1,920 games vs W7's calibrated opponent (`sim_w12`) and 1,920 vs the E4 gate opponents
  (`sim_e4`), from `C:/Users/benpe/pod_backup_weekend/tonight1020/clx_fin15`.
- Pipeline:
  - `index.py` (Codex worker): results incl. Ranked `n/a`, decision timing per match, cache build;
  - `anatomy.py`: crown path, decisive fall, chip attribution, 180 s state, X-Bow rows;
  - `sim.py`: the same definitions on the SIM rows;
  - `report.py`: all tables;
  - `latency_windows.py`, `elixir_rate.py`: the checks in sections 4 and 2.
- **Checks (a)**:
  - the Ranked record equals the runner's own session counters: W2045 L1885 -> W2157 L2006 = +112 / +121;
  - index results agree with `card_use.results()` on all 139 graded rows;
  - frame crowns agree with the end event on 352 / 371 (the 19 differences are 3-crown games, king counted vs not).

Terms used below:
- **OT** = overtime. If crowns are level at 3:00, the first tower to fall wins; the second OT minute is triple elixir (live:
  1.00 elixir/s, measured in `elixir_rate.out`). If crowns are still level at 5:00, every tower **drains** by the same
  amount, so the lowest tower falls first: the **tiebreak drain**.
- **Chip** = small tower damage that adds up over the match.
- **BEAT** = opponent win condition is a tank or bridge spam: Giant, E-Giant, Royal Hogs, Battle Ram, PEKKA, Golem, Goblin
  Giant, Lava, Royal Giant, Elixir Golem, Rune Giant, Giant Skeleton, 3M, Boss Bandit (`report.py` BEAT).

## 1. Record

| sample | W-L | win % [CI] |
|---|---|---|
| Ranked | 112-121 | **48.1 [41.7, 54.5]** |
| Ladder 13.5-14k | 86-52 | 62.3 [54.0, 70.0] |
| SIM vs W7 opponent | 1228-692 | 64.0 [61.8, 66.1] |
| SIM vs E4 | 1389-531 | 72.3 [70.3, 74.3] |

- (a) Ranked by time block:
  - 13:28-17:59: 62.5% (n 48);
  - 18:00-21:59: 41.2% (n 51);
  - 22:00-07:08: 45.5% (n 134).
- (b) The drop after the first 48 matches fits a skill-matched climb into stronger opponents. Rank is not logged, so this is
  untested.
- (a) **The W7 SIM opponent is calibrated to the ladder, not to Ranked** (T11, live minus SIM w12):

| cell | ladder - SIM | Ranked - SIM |
|---|---|---|
| overall win | -1.6 [-10.2, +6.3] | **-15.9 [-22.6, -9.1]** |
| win vs BEAT | +1.5 [-14.4, +15.9] | **-32.2 [-41.0, -21.3]** |
| win vs the rest | -4.8 [-14.9, +4.5] | -7.7 [-16.1, +0.2] |
| win, OT decided before the drain | -12.0 [-25.1, -0.6] | **-24.9 [-35.2, -14.7]** |
| lost first princess | +0.2 [-7.5, +8.7] | **+13.5 [+6.8, +20.2]** |
| lost in regulation | -5.0 [-10.3, +2.0] | -0.6 [-5.5, +5.1] |

- (a) Not the tower level: 87% of Ranked opponents have max (4858) towers. Against max-tower opponents CLX wins 65.3% on the
  ladder (n 101) but 48.8% on Ranked (n 203).

## 2. Crown paths (share of all matches; T2, T2b, T3)

| path (exclusive) | Ranked | ladder | SIM w12 | Ranked - SIM w12 |
|---|---|---|---|---|
| win, never trailed | 47.2% | 60.9% | 62.0% | -14.8 [-21.4, -8.0] |
| loss, led then gave it back | 1.7% | 2.2% | 2.9% | -1.1 [-2.5, +1.5] |
| loss decided in 1x (0-120 s) | 11.6% | 2.9% | 10.5% | +1.1 [-2.7, +6.0] |
| loss decided in 2x (120-180 s) | 6.9% | 10.1% | 7.2% | -0.4 [-3.3, +3.8] |
| loss decided in OT 2x minute | 9.9% | 7.2% | 5.6% | **+4.2 [+0.9, +8.8]** |
| loss decided in OT 3x minute | 6.4% | 4.3% | 2.5% | **+3.9 [+1.3, +7.9]** |
| loss by tiebreak drain / tower HP | 15.5% | 10.9% | 7.3% | **+8.1 [+3.8, +13.4]** |

- (a) **The whole Ranked-vs-SIM loss gap is in overtime.**
  - Losses in matches that ended in regulation: Ranked 18.9%, SIM 19.5% (-0.6 [-5.5, +5.1]).
  - Losses in matches that reached OT: Ranked 33.0% (77 of 233), SIM 16.5% (317 of 1,920).
  - That is +16.5 pp, the whole total loss gap (+15.9 pp).
- (a) Overtime itself:
  - Ranked reaches OT in 62.7% of matches; CLX wins 47.3% [39.3, 55.3] of them. SIM: 55.2% reach OT, CLX wins 70.1%.
  - Before the drain (OT 2x minute, then 3x minute): Ranked 52.4% / 53.1% vs SIM 75.8% / 80.7%.
  - At the drain: 37.3% vs 49.1%.
- (a) **At 0-0 the OT is decided by the lowest standing princess HP at 3:00** (live, T3b):

| state at 3:00 (Ranked, n 132) | share | CLX win |
|---|---|---|
| behind by > 0.10 of a tower | 50.0% | 28.8% [19.3, 40.6] |
| level (within 0.10) | 18.9% | 44.0% [26.7, 62.9] |
| ahead by > 0.10 | 31.1% | 90.2% [77.5, 96.1] |

  - On the ladder only 30.4% of 0-0 overtimes start behind.
  - The opponents finish exactly the weak tower: 39 / 40 Ranked OT falls before the drain hit CLX's lowest princess at 3:00.
- (a) The 3:00 deficit comes from both sides of the race, mostly CLX's offence. 0-0 OT losses vs wins (Ranked, regulation,
  in princess units, chip proxy T3c):

  | | taken | dealt | of which X-Bow |
  |---|---|---|---|
  | wins | 0.48 | 0.60 | 0.47 |
  | losses | 0.70 | 0.37 | 0.26 |

  - Bridge X-Bow lock rate, Ranked vs ladder: 45.3% [42.1, 48.5] vs 57.3% [52.8, 61.6]; in losses 31.2% (T10).
  - Damage per bridge X-Bow: 0.211 vs 0.257. Opponent answer elixir per bridge X-Bow: 5.73 vs 6.42.
  - So Ranked defenders deny the X-Bow more, and do it more cheaply.
- (c) **Giving back a lead is not a CLX problem.** CLX led in 119 Ranked matches and gave the lead back and lost in 7: 5.9%
  [2.9, 11.6], vs 5.2% in the SIM. The 15-20% figure was CLIII's, so the lead-protect / redirect arms aimed at a gap CLX no
  longer has.
- (c) **"The SIM opponent is passive in OT" is contradicted.** Opponent troop elixir per minute (T3d), SIM w12 vs Ranked:

  | window | SIM w12 | Ranked |
  |---|---|---|
  | 2:00-3:00 | 36.6 | 30.4 |
  | OT minute 1 | 35.3 | 32.6 |
  | OT minute 2 | 50.2 | 43.7 |

  Live counts may miss some plays, which would bias Ranked low.
- (b) "The SIM lacks the triple-elixir OT minute": unlikely. The engine has the law (RoyaleSim `tests/triple_elixir.rs`), but
  the fin15 fork pin was not checked on the laptop.

## 3. Ranked loss causes, ranked by losses (121 losses; T5 / T8 / T12)

Each loss gets one cluster, from its decisive fall: the own fall after which the opponent led for good. The window is the
20 s before that fall. "Committed" = >= 6 elixir of bridge / pocket X-Bow or tower Rocket in the 40 s before, with own elixir
< 5 at -20 s. Example ticks are GAME ticks (clock tick + 78).

| # | situation cluster | losses | % | vs BEAT | category | evidence |
|---|---|---|---|---|---|---|
| 1 | **Chip race lost, decided in OT**: tiebreak drain (36) or OT finish of a tower already < 30% 20 s before (22) | 58 | 47.9 | 27 | **(b) opponent model**, part (a) | SIM wins OT before the drain 77.5% vs Ranked 52.6% (-24.9 pp); vs the ladder still -12.0 [-25.1, -0.6], the (a) residual. 50% of 0-0 OTs start behind (28.8% win). X-Bow lock 45% vs 57% on the ladder |
| 2 | **Punished offensive commit**: healthy tower (mean 0.89 at -20 s in regulation) lost to a counter-push after an X-Bow / Rocket commit, low elixir (mean 1.96 at -20 s) | 24 | 19.8 | 17 | **(c) policy**, plus (b) | The SIM teaches early losses at the live rate (1x losses 10.5% vs 11.6%), but it is 32 pp too lenient vs BEAT, where 17 of the 24 happen |
| 3 | **Push through a healthy tower**, no prior commit: big (>= 9 elixir in lane) 10, small 13 | 23 | 19.0 | 14 | (c) + (b) | Tank / bridge pushes (Battle Ram, E-Giant, Golem, Balloon, Miner + Barrel) at 0.8-1.0 tower HP |
| 4 | **Chipped tower finished in regulation** (< 30% at -20 s) | 16 | 13.2 | 4 | (c) / (b) | MK + Bats / Witch / Royal Recruits, Mortar chip |
| - | live execution (reader / tap / CPU) | ~0 | - | - | **(d) not supported** | Section 4 |

Examples (log, decisive fall, opponent cards in the window). More examples in `report.out` T12.

- **Cluster 1**
  - `live_play_20261020_142524` (R tower at 257.9 s, game tick 5235). Tower at 0.21. Hog + Minions + Lightning. CLX rocketed
    the enemy tower 3 s before the fall.
  - `live_play_20261020_143334` (L tower, 241.4 s, tick 4905). Tower at 0.09. Barrel, then E-Wiz + Log.
  - `live_play_20261020_151757` (L tower, tiebreak drain 300.9 s, tick 6096). CLX's bridge X-Bow at -17 s did not move the
    race.
- **Cluster 2**
  - `live_play_20261020_185147` (R tower, 58.6 s, tick 1249). Healthy tower, 1.6 elixir. Battle Ram + Mega Knight.
  - `live_play_20261020_201818` (R tower, 73.2 s, tick 1542). 0.96 elixir. Giant + Mini PEKKA + Fireball.
  - `live_play_20261020_182456` (R tower, 214.0 s, tick 4358). Bridge X-Bow at -12 s, then Royal Giant + Fisherman.
- **Cluster 3**
  - `live_play_20261020_145359` (R tower, 120.4 s, tick 2485). Lone Battle Ram, CLX at 10 elixir.
  - `live_play_20261020_152320` (R tower, 87.0 s, tick 1817). Golem + Executioner + Phoenix, 1.15 elixir.
- **Cluster 4**
  - `live_play_20261020_211617` (L tower, 159.6 s, tick 3269). MK + Minions + Boss Bandit, tower at 0.05.

By deck (T4 / T7):

- (a) BEAT is 83 of 233 Ranked matches and **62 of 121 losses**: CLX wins 25.3% [17.2, 35.6]. Against the rest it wins
  60.7% [52.7, 68.1].
- (a) The SIM gives 57.5% vs BEAT, and the ladder gave 59.0%.
- (a) The worst Ranked cells:
  - Giant 1/11;
  - Golem 1/6;
  - Royal Hogs 2/11;
  - E-Giant 3/13;
  - Battle Ram 3/10;
  - PEKKA 5/14;
  - Mega Knight 16/33 (the most losses of any single key, 17).
- (a) Of these, Giant, E-Giant, Royal Hogs and Battle Ram are **not** in `pipeline.archetypes.unfavorable`. The owner's x3
  weighting today applies only to imitation rows (`stepd/row_weights.py`); RL deck sampling is census tempering
  (`rl_royale.deck_weights`).

## 4. CPU starvation vs losses (T6, `latency_windows.out`)

- (a) No match ran at the 40 ms design speed. Ranked per-match medians: 60-80 ms for most matches; 90 ms in the 10-20
  13:28-21:59 block (90 of 99 matches had CPU-STARVED events); 68 ms from 22:00 on.
- (a) Match level, win rate by median decision time:

  | median decision time | n | win % |
  |---|---|---|
  | 60-80 ms | 106 | 44.3 |
  | 80-100 ms | 82 | 48.8 |
  | >= 100 ms | 28 | 64.3 |

  - Any CPU-STARVED event vs none: 50.9% vs 45.5%, **+5.4 [-7.3, +17.9]**. The starved matches won slightly more.
  - Inside each time block there is no consistent sign.
- (a) Inside the decisive 20 s before a lost tower, the median decision time was 70 ms, vs 75.5 ms in the window before CLX's
  own first tower take in wins. The share of decisions over 80 ms was 0.35 vs 0.45.
- (a) Unconfirmed plays per match: 2.74 in losses vs 2.87 in wins. Median confirm latency: 1.30 s vs 1.26 s.
- Verdict:
  - (c) at the measured resolution, starvation (60-110 ms) does not explain the losses;
  - (b) a 40 ms vs 100 ms effect is untested, because no 40 ms matches exist;
  - the comparison is confounded by time (rank climb).

## 5. Top 3 levers for the next round (one change each; no new reward terms)

**L1. Ranked-calibrated opponent (opponent model; the change = the league / eval opponent checkpoint).**
- What: repeat W7's O-series with the 233 Ranked logs as the target.
  - O1 rows from these logs; R6 recipe with `league_opp_live`.
  - Pick T / decide-every / updates so that CLX vs it falls inside the Ranked CIs: win 48.1 [41.7, 54.5], vs BEAT 25.3
    [17.2, 35.6], win \| OT 47.3 [39.3, 55.3], lost-first-princess 48.1 [41.7, 54.5].
  - Then tn_base with that opponent in place of W7, at the same 0.3 share.
- Why: section 1 T11. W7 matches the ladder on every cell and misses Ranked by 16-32 pp exactly where the losses are. Every
  gate so far selected successors against a ladder-strength opponent.
- Worked if:
  - (i) the calibration cells land inside the CIs (eval only, about 2 x 960 games);
  - (ii) a successor beats CLX vs that opponent with CI low > 0 (std + fresh);
  - (iii) live Ranked win > 48.1% over >= 150 matches.
- (b) Untested whether the R6 recipe can reach Ranked strength. It may need lower T, a faster decide interval, or more
  updates vs the frozen stack.

**L2. Overtime-state starts (curriculum; the change = an opt-in env key, default off = byte-identical).**
- What: start a share of training episodes (e.g. 0.25) at clock 3600, 0-0.
  - Princess HP drawn from the live Ranked 3:00 distribution (`rows.json`: `reg_own_min` / `reg_opp_min` / `reg_*_sum`; half
    start behind by > 0.1).
  - Elixir drawn from live.
  - The engine already has scenario resets: RoyaleSim `py.rs` `reset(seed, decks, shuffle, start_tick, elixir_milli,
    tower_hp, spawns, ...)`. Check that the fin15 fork exposes it.
- Why: 77 of 121 Ranked losses come in matches that reached OT. At 0-0, being behind at 3:00 means 28.8% vs 90.2% ahead. Normal episodes
  rarely reach "OT, behind": only 55% of SIM games reach OT at all.
- Worked if:
  - on a FIXED set of OT-start states (paired, both models), P(win) beats CLX with CI low > 0 in the "behind" stratum;
  - full-match evals are not clearly worse (CI top >= 0);
  - live: win \| OT > 47.3% and P(win \| 0-0 OT, behind) > 28.8%.
- Order: after L1. Against the W7 opponent the SIM's OT is too lenient (77.5% vs 52.6%), so OT starts there would teach
  lenient OT play.

**L3. Tank / bridge-spam weight in RL deck sampling (the change = deck-draw weight).**
- What: x3 RL sampling weight for opponent decks whose win condition is Giant, E-Giant, Royal Hogs, Battle Ram, PEKKA or
  Golem. These are the Ranked-worst cells; four of them are outside today's unfavourable list.
- Why: BEAT = 62 of 121 losses at 25.3%, and the SIM is 32 pp easier there. 17 of the 24 "punished commit" losses are vs
  BEAT.
- Worked if:
  - the SIM per-win-condition breakdown (vs the L1 opponent) shows a BEAT cell with CI low > 0 vs CLX, and the rest is not
    clearly worse;
  - live Ranked BEAT win > 25.3% on >= 80 BEAT matches.
- (b) Weighting alone may do little against the current, too-easy SIM versions of these decks. Run it on the L1 base.

Not recommended:
- more lead-protection or tower-Rocket terms: (c) give-back is 5.9%, and the Rocket / Tornado arms lost to CLX (tonight1020);
- CPU fixes as a win lever: (c) section 4. Still worth fixing for hygiene.

## 6. Caveats

- The chip attribution is a proxy: a damage step is split over enemy bodies within 8 tiles (13 for siege), and a spell gets
  it when one lands in its window.
- BEAT and win conditions come from revealed cards only. SIM rows have no positions and no 3:00 tower HP, so the SIM side of
  T3b / T10 is missing. Measurement owed: add the 3:00 princess HP and per-X-Bow lock to the SIM crown log.
- One ladder match (`live_play_20261019_182640`) has a results-screen LOSS at 1-0 crowns; it was kept as graded.
- Ranked matches after 07:08 are not included.
