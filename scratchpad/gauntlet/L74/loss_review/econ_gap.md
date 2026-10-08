# Live vs SIM economy gap (L74 econ_gap) -- 2026-10-08 16:12

Same checkpoint + decision options in both. SIM = v3 benchmark (vs gen v1 sampling T .3, the W4 benchmark), 480 matches per arm, isolated VM repo (econ_sim_patch.py adds a decision/frame dump and an opponent-counter bias knob; nothing else changes). Live = decision logs of that family. Definitions in econ_gap.py; pressure = enemy body value on my half (own y <= 16).

## Bottom line

* The live economy gap is real for the same checkpoint + options (section 1). It is NOT a different gate: per decision, the same model plays with the same probability as in SIM once the situation is matched on phase, pressure on my half, enemy value anywhere on the board and elixir (section 10b).
* Live opponents keep more enemy units on the board and push onto my half more often at the SAME elixir spend (section 5), and the bot spends into that presence; this explains about a third of the mean-elixir gap. Small live-only drains add to it: Hero Ice Wizard ability (~0.1 elixir at push start), and in the anti-leak-ON stack2k matches forced plays (~0.4).
* Decision cadence is NOT the live cause: live decides 1.57-1.62 times/s, the SIM 1.60. The SIM test shows cadence WOULD matter if it rose: deciding every 4 ticks costs -0.50 [-0.68, -0.29] elixir at push start and -9 net paired results (n.s.) -> any live change that raises the decision rate (e.g. pipelined plays) should be checked for this.
* The +0.34 opponent-counter over-read, reader duplicates and gate noise are contradicted as causes. Most of the push-start gap (about 1.0 of 1.6 elixir for stack2k) is left unexplained at this state resolution: it forms in the seconds before a live push (section 10's simulator reproduces SIM but not live there).
* Current live checkpoint (towerref_w2, live n=26, logs span several option sets): elixir at push start live 3.47 vs SIM with the deployed options 4.50.

## Attribution (live minus SIM, same checkpoint + options)

Targets: elixir at push start (median) stack2k -1.60 [-1.87, -1.34], R1e -1.00; mean own elixir stack2k -0.86, R1e -0.64; taps at < 5 elixir/min stack2k +1.29 (R1e +0.65).

| candidate | what was measured | size | label |
|---|---|---|---|
| (1) decision cadence / gate noise | live 1.57-1.62 decisions/s vs SIM 1.60-1.61; live gaps < 10 ticks 6-8%; mean abs p change per decision live .033-.038 vs SIM .043-.046; fresh-crossing share 93-98% both (not discriminating) ; SIM decide-4 vs decide-10 (deployed options): push-start elixir -0.50 [-0.68, -0.29], paired better/worse 40/49 | live does NOT decide faster than SIM -> ~0 of the live gap | (c) |
| (2a) Hero Ice Wizard ability (live only) | 0.39-0.56 presses/min x 1.14 elixir; simulator: SIM policy + ability on live timeline | push start -0.08..-0.09 (presses in the 10 s before a push); mean elixir -0.07 (stack), -0.03 (R1e) | (a) small |
| (2b) anti-leak forced plays (live stack2k only: 77/102 matches ON) | 0.42 forced plays/min when ON; push start ON 3.1 vs OFF 3.5 | ~0.4 of the 1.6 stack2k gap in ON matches; 0 for R1e/towerref (OFF) | (b) (OFF n=26) |
| (2c) evolution forms | Tesla and Knight evolved in both live hands and the SIM deck | 0 | (c) |
| (3) opponent pressure | enemy value arriving on my half 1x 28.8 vs 18.3 /min; pushes/min 1.32 vs 1.02-1.06; same opponent spend (counter drops 25-27/min both); time with >= 8 elixir of enemy units anywhere on the board 37-41% vs 26-28%; push-frequency re-weighting explains 4-8% of the push-start gap; simulator (SIM policy, live vs SIM timeline): mean elixir -0.31 (stack), -0.24 (R1e); push start 0.13 / 0.13 | about 1/3 of the mean-elixir gap; ~0 of the push-start gap in the simulator | (a) live presses harder; (b) as the cause of the push-start gap |
| (4) state differences seen by the gate | P(play issued) per decision in matched phase x my-half pressure x WHOLE-board x elixir strata: stack2k 11.0% vs 10.6%, R1e 11.7% vs 11.8% (coarser strata without the whole board: live +0.7-0.9 pp, i.e. the excess is the board mix of (3)); simulator policy swap on the live timeline: mean elixir -0.22 / -0.19 | the same model makes the same per-decision choice in the same coarse state; small cell-level differences remain | (c) for 'the gate reads live states differently' at this resolution |
| (5) reader / extrapolation artefacts | duplicated enemy bodies 0.7-0.9% of sightings (2.9 elixir/min of my-half value, ~8% of arrivals); one-state ids 6.5-8% (excluded); counter +0.34 over-read in SIM: push start -0.04 [-0.22, 0.18], wins 310 vs 310 | ~0 | (c) |
| unexplained | the elixir simulator reproduces SIM (push start 5.17 vs actual 4.87) but overshoots live (push start 4.77 vs actual 3.76): what happens in the seconds before a live push (card availability, hand order, how pushes form) is not captured by phase x pressure x board x elixir | ~1/3 of the mean-elixir gap and most of the push-start gap | (b) |

## 1. The gap

| source | matches | elixir at push start (median) | pushes met < 4 | pushes/min | push value | enemy value arriving on my half /min (1x) | taps at < 5 elixir /min | taps /min | elixir at deploy 1x / 2x / OT | IW ability /min | my spend in 10 s before push | forced (anti-leak) plays /min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LIVE stack2k_cellref | 103 | 3.2 | 62% | 1.32 | 9.8 | 28.8 | 4.75 | 10.6 | 6.54 / 6.05 / 5.95 | 0.56 | 6.8 | 0.31 |
|   LIVE stack2k anti-leak ON | 77 | 3.1 | 65% | 1.34 | 9.8 | 27.3 | 4.74 | 10.6 | 6.56 / 6.01 / 5.98 | 0.56 | 6.9 | 0.42 |
|   LIVE stack2k anti-leak OFF | 26 | 3.5 | 54% | 1.24 | 9.5 | 33.4 | 4.80 | 10.7 | 6.48 / 6.14 / 5.90 | 0.56 | 6.5 | 0.00 |
| SIM stack2k_cellref | 480 | 4.8 | 37% | 1.06 | 9.0 | 18.3 | 3.66 | 10.6 | 7.10 / 6.60 / 6.72 | 0.00 | 7.8 | 0.00 |
| SIM stack + counter +0.34 | 480 | 4.8 | 37% | 1.07 | 9.0 | 18.4 | 3.59 | 10.6 | 7.11 / 6.60 / 6.78 | 0.00 | 7.9 | 0.00 |
| LIVE R1e | 354 | 2.5 | 74% | 1.32 | 10.0 | 28.9 | 6.62 | 11.0 | 6.18 / 5.12 / 4.62 | 0.39 | 6.5 | 0.00 |
| SIM R1e | 480 | 3.5 | 58% | 1.02 | 9.0 | 19.3 | 6.34 | 11.1 | 6.66 / 5.49 / 4.82 | 0.00 | 7.7 | 0.00 |
| LIVE towerref_w2 | 26 | 3.5 | 55% | 1.28 | 10.7 | 33.8 | 4.04 | 9.5 | 6.65 / 6.13 / 6.05 | 0.39 | 6.6 | 0.00 |

Arrival per minute is shown for 1x only (both sides of the comparison reach 2x/OT at different rates). 'taps' = my card plays at the decision tick (live: the tap; SIM: the decision before the 26-tick delay), elixir = raw elixir there. Elixir at deploy: SIM engine value; live tap + 26 ticks of regen.

* stack2k: elixir at push start live - SIM = -1.60 [-1.87, -1.34] (bootstrap over pushes); taps at < 5 elixir/min live 4.75 vs SIM 3.66.
* stack2k anti-leak OFF: elixir at push start live - SIM = -1.26 [-1.90, -0.57] (bootstrap over pushes); taps at < 5 elixir/min live 4.80 vs SIM 3.66.
* R1e: elixir at push start live - SIM = -1.00 [-1.15, -0.83] (bootstrap over pushes); taps at < 5 elixir/min live 6.62 vs SIM 6.34.

## 2. Decomposition of the low-elixir tap rate (Shapley over three factors)

taps at < 5 elixir per minute = 60 x sum over strata s = (phase, pressure bucket) and elixir e < 5 of  w(s) x occ(e | s) x h(s, e):  w = share of time in each phase x pressure stratum (**opponent pressure mix**), occ = share of that time spent at elixir e (**elixir occupancy**: how low the bank sits, itself a consequence of earlier spending), h = taps per second at that elixir and stratum (**play hazard**: how readily the bot spends when it is there). Exact identity; the live-minus-SIM difference is split by Shapley values (average over the 6 orders).

| pairing | live | SIM | gap | pressure mix | elixir occupancy | play hazard |
|---|---|---|---|---|---|---|
| stack2k | 5.03 | 3.74 | 1.29 | 0.10 (8%) | 0.94 (73%) | 0.25 (19%) |
| stack2k  quiet (pb <= 1) | 1.87 | 1.81 | 0.06 | -0.58 | 0.60 | 0.04 |
| stack2k  pressured (pb >= 2) | 3.16 | 1.93 | 1.23 | 0.68 | 0.34 | 0.21 |
| stack2k anti-leak OFF | 5.07 | 3.74 | 1.33 | 0.16 (12%) | 0.93 (70%) | 0.25 (19%) |
| stack2k anti-leak OFF  quiet (pb <= 1) | 1.79 | 1.81 | -0.02 | -0.54 | 0.58 | -0.06 |
| stack2k anti-leak OFF  pressured (pb >= 2) | 3.28 | 1.93 | 1.35 | 0.69 | 0.35 | 0.31 |
| R1e | 7.12 | 6.47 | 0.65 | -0.44 (-68%) | 0.92 (142%) | 0.17 (26%) |
| R1e  quiet (pb <= 1) | 3.08 | 3.51 | -0.42 | -1.00 | 0.65 | -0.07 |
| R1e  pressured (pb >= 2) | 4.04 | 2.97 | 1.07 | 0.56 | 0.27 | 0.24 |

Pressure mix (share of time by phase x pressure bucket 0/1/2/3), live vs SIM:

* stack2k: 1x: 34%/3%/11%/8% vs 34%/5%/7%/4%; 2x: 13%/1%/7%/6% vs 13%/3%/6%/4%; OT: 7%/1%/4%/4% vs 12%/3%/6%/4%
* stack2k anti-leak OFF: 1x: 33%/2%/10%/9% vs 34%/5%/7%/4%; 2x: 12%/1%/6%/6% vs 13%/3%/6%/4%; OT: 10%/1%/5%/4% vs 12%/3%/6%/4%
* R1e: 1x: 37%/3%/11%/8% vs 35%/5%/8%/4%; 2x: 14%/1%/6%/6% vs 14%/3%/5%/4%; OT: 7%/1%/3%/3% vs 11%/3%/5%/3%

## 3. What the gate does in the SAME situation (decisions at model elixir < 5, matched phase x pressure x elixir strata, weighted to live)

| pairing | decisions | mean p_play live / SIM | P(p > tau) live / SIM | decisions per second live / SIM | median abs change in p per decision (quiet / pb2 / pb3) live vs SIM |
|---|---|---|---|---|---|
| stack2k | 14826 | 0.193 / 0.189 | 10.8% / 9.5% | 1.60 / 1.61 | 0.00 / 0.02 / 0.02 vs 0.00 / 0.02 / 0.02 |
| stack2k  quiet, < 5 elixir | 6656 | 0.167 / 0.160 | 7.3% / 6.4% | | |
| stack2k  pressured, < 5 elixir | 8170 | 0.214 / 0.212 | 13.7% / 12.0% | | |
| stack2k  all elixir levels | 34464 | 0.210 / 0.207 | 11.6% / 10.8% | | |
| stack2k anti-leak OFF | 3704 | 0.188 / 0.194 | 10.3% / 9.7% | 1.59 / 1.61 | 0.00 / 0.00 / 0.02 vs 0.00 / 0.02 / 0.02 |
| stack2k anti-leak OFF  quiet, < 5 elixir | 1679 | 0.165 / 0.171 | 7.2% / 6.7% | | |
| stack2k anti-leak OFF  pressured, < 5 elixir | 2025 | 0.206 / 0.214 | 12.9% / 12.2% | | |
| stack2k anti-leak OFF  all elixir levels | 8883 | 0.212 / 0.214 | 11.7% / 11.0% | | |
| R1e | 61123 | 0.152 / 0.157 | 13.6% / 13.8% | 1.57 / 1.60 | 0.00 / 0.00 / 0.02 vs 0.00 / 0.02 / 0.02 |
| R1e  quiet, < 5 elixir | 30176 | 0.128 / 0.131 | 10.1% / 10.2% | | |
| R1e  pressured, < 5 elixir | 30947 | 0.176 / 0.183 | 17.1% / 17.4% | | |
| R1e  all elixir levels | 112506 | 0.160 / 0.157 | 13.5% / 12.7% | | |

By elixir bucket (model elixir for the gate rows; raw elixir for time share and taps per second), all pressure levels, matched strata weighted to live:

| pairing | elixir | P(p > tau) live / SIM | taps per second live / SIM | share of time live / SIM |
|---|---|---|---|---|
| stack2k | 0 | 4.9% / 0.9% | 0.061 / 0.039 | 2.1% / 1.5% |
| stack2k | 1 | 5.1% / 4.7% | 0.097 / 0.102 | 8.0% / 4.7% |
| stack2k | 2 | 13.6% / 10.8% | 0.184 / 0.174 | 13.2% / 8.6% |
| stack2k | 3 | 11.5% / 10.1% | 0.179 / 0.175 | 14.7% / 11.3% |
| stack2k | 4 | 10.1% / 9.6% | 0.167 / 0.171 | 14.5% / 13.0% |
| stack2k | 5 | 10.3% / 9.8% | 0.183 / 0.178 | 13.3% / 12.9% |
| stack2k | 6 | 10.2% / 9.0% | 0.174 / 0.197 | 11.8% / 13.2% |
| stack2k | 7 | 10.9% / 11.6% | 0.245 / 0.262 | 10.0% / 12.3% |
| stack2k | 8 | 18.4% / 19.9% | 0.309 / 0.248 | 6.6% / 8.8% |
| stack2k | 9 | 14.1% / 11.6% | 0.223 / 0.110 | 5.9% / 13.7% |
| stack2k anti-leak OFF | 0 | 18.2% / 0.4% | 0.044 / 0.039 | 1.7% / 1.5% |
| stack2k anti-leak OFF | 1 | 4.0% / 4.7% | 0.142 / 0.102 | 7.7% / 4.7% |
| stack2k anti-leak OFF | 2 | 12.8% / 11.1% | 0.173 / 0.174 | 12.9% / 8.6% |
| stack2k anti-leak OFF | 3 | 11.0% / 10.2% | 0.174 / 0.175 | 14.4% / 11.3% |
| stack2k anti-leak OFF | 4 | 9.7% / 9.8% | 0.173 / 0.171 | 14.8% / 13.0% |
| stack2k anti-leak OFF | 5 | 10.3% / 10.0% | 0.197 / 0.178 | 13.3% / 12.9% |
| stack2k anti-leak OFF | 6 | 11.2% / 9.3% | 0.178 / 0.197 | 12.0% / 13.2% |
| stack2k anti-leak OFF | 7 | 11.3% / 12.1% | 0.248 / 0.262 | 9.8% / 12.3% |
| stack2k anti-leak OFF | 8 | 19.9% / 20.3% | 0.286 / 0.248 | 6.2% / 8.8% |
| stack2k anti-leak OFF | 9 | 13.9% / 10.4% | 0.196 / 0.110 | 7.1% / 13.7% |
| R1e | 0 | 5.4% / 2.9% | 0.085 / 0.071 | 3.5% / 3.4% |
| R1e | 1 | 7.6% / 7.1% | 0.113 / 0.140 | 12.7% / 9.6% |
| R1e | 2 | 14.2% / 15.1% | 0.233 / 0.257 | 18.1% / 14.0% |
| R1e | 3 | 15.7% / 15.4% | 0.215 / 0.227 | 15.3% / 14.1% |
| R1e | 4 | 13.6% / 14.1% | 0.199 / 0.194 | 13.3% / 12.4% |
| R1e | 5 | 12.1% / 10.9% | 0.182 / 0.163 | 11.0% / 10.6% |
| R1e | 6 | 10.8% / 9.1% | 0.205 / 0.215 | 9.6% / 9.9% |
| R1e | 7 | 13.7% / 13.5% | 0.240 / 0.214 | 7.0% / 8.6% |
| R1e | 8 | 19.6% / 18.7% | 0.265 / 0.218 | 4.5% / 5.8% |
| R1e | 9 | 14.3% / 7.6% | 0.212 / 0.090 | 5.0% / 11.5% |

* stack2k plays fired with the gate barely over threshold (0 <= p - tau < .05): live 61.5% of 3052 vs SIM 38.8% of 16775
* stack2k decision spacing (ticks: share) live 10: 75%, 11: 7%, 30: 3%, 28: 3% | SIM 10: 89%, 30: 11%
* stack2k anti-leak OFF plays fired with the gate barely over threshold (0 <= p - tau < .05): live 61.5% of 805 vs SIM 38.8% of 16775
* stack2k anti-leak OFF decision spacing (ticks: share) live 10: 73%, 11: 7%, 30: 4%, 28: 2% | SIM 10: 89%, 30: 11%
* R1e plays fired with the gate barely over threshold (0 <= p - tau < .05): live 59.5% of 10641 vs SIM 30.1% of 16821
* R1e decision spacing (ticks: share) live 10: 72%, 11: 7%, 28: 5%, 2: 2% | SIM 10: 89%, 30: 11%

## 4. Live-only spends, counter bias, reader artefacts

* stack2k Hero Ice Wizard ability: 0.56 presses/min, median elixir drop 1.14 (n=201); presses in the 10 s before a push start 0.076 per push -> adds back about 0.09 elixir at push start. SIM has no Hero Ice Wizard.
  reader artefacts: duplicated enemy bodies (same card within .25 tiles, same state) 0.93% of body sightings, their value on my half 2.87/min vs arriving enemy value 36.0/min; one-state ids 6.5% of enemy ids.
* R1e Hero Ice Wizard ability: 0.39 presses/min, median elixir drop 1.14 (n=464); presses in the 10 s before a push start 0.066 per push -> adds back about 0.08 elixir at push start. SIM has no Hero Ice Wizard.
  reader artefacts: duplicated enemy bodies (same card within .25 tiles, same state) 0.66% of body sightings, their value on my half 2.87/min vs arriving enemy value 34.8/min; one-state ids 8.2% of enemy ids.
* Opponent-counter over-read (+0.34, measured live): SIM stack +0.34 minus SIM stack: elixir at push start -0.04 [-0.22, 0.18]; taps at < 5 elixir/min -0.07; wins 310 vs 310 of 480 / 480.

## 5. Opponent pressure: live opponents vs the SIM opponent

| source | enemy value arriving on my half /min 1x / 2x / OT | opponent spend /min (public counter drops) | SIM opponent exact spend /min | pushes /min | recovery time before a push (median s) |
|---|---|---|---|---|---|
| LIVE stack2k | 28.8 / 44.6 / 47.3 | 26.8 | - | 1.32 | 22.0 |
| SIM stack2k | 18.3 / 34.9 / 39.5 | 26.2 | 31.2 | 1.06 | 25.5 |
| LIVE R1e | 28.9 / 44.3 / 41.3 | 25.3 | - | 1.32 | 22.9 |
| SIM R1e | 19.3 / 33.5 / 36.8 | 25.7 | 30.6 | 1.02 | 26.2 |

Elixir balance per minute (income = regen over the phase minutes; spend = card costs; ability = presses x 1.14):

| source | income | card spend | Hero ability | wasted at the cap | income - spend - ability - waste |
|---|---|---|---|---|---|
| LIVE stack2k | 30.6 | 31.7 | 0.64 | 0.66 | -2.43 |
| SIM stack2k | 31.9 | 31.4 | 0.00 | 2.61 | -2.09 |
| LIVE R1e | 30.3 | 30.4 | 0.44 | 0.53 | -1.07 |
| SIM R1e | 31.5 | 31.4 | 0.00 | 2.36 | -2.28 |

## 6. How much of the push-start gap does the opponent's push frequency explain?

* stack2k: MEAN elixir at push start live 3.41 vs SIM 4.69 (gap -1.27). SIM re-weighted to live's phase x recovery-time mix: 4.64 -> frequency/phase mix explains -0.05 of -1.27 (4%); live pushes in strata with SIM data 100%.
  * by stratum: 1x first: live 3.4 (n=92) vs SIM 4.5 (n=368); 1x 10-20s: live 3.4 (n=24) vs SIM 4.9 (n=39); 1x 20-40s: live 3.4 (n=51) vs SIM 4.4 (n=123); 1x 40-+s: live 3.1 (n=31) vs SIM 4.1 (n=110); 2x 5-10s: live 3.8 (n=26) vs SIM 4.5 (n=53); 2x 10-20s: live 3.3 (n=38) vs SIM 4.5 (n=140); 2x 20-40s: live 3.7 (n=43) vs SIM 4.8 (n=246); 2x 40-+s: live 3.3 (n=36) vs SIM 4.9 (n=157); OT 10-20s: live 3.8 (n=34) vs SIM 4.9 (n=172); OT 20-40s: live 3.5 (n=31) vs SIM 5.0 (n=225)
* stack2k anti-leak OFF: MEAN elixir at push start live 3.68 vs SIM 4.69 (gap -1.01). SIM re-weighted to live's phase x recovery-time mix: 4.61 -> frequency/phase mix explains -0.08 of -1.01 (8%); live pushes in strata with SIM data 100%.
  * by stratum: 1x first: live 3.7 (n=22) vs SIM 4.5 (n=368)
* R1e: MEAN elixir at push start live 2.96 vs SIM 3.74 (gap -0.78). SIM re-weighted to live's phase x recovery-time mix: 3.85 -> frequency/phase mix explains 0.11 of -0.78 (-14%); live pushes in strata with SIM data 100%.
  * by stratum: 1x first: live 3.2 (n=308) vs SIM 4.0 (n=365); 1x 0-5s: live 3.5 (n=28) vs SIM 4.3 (n=10); 1x 5-10s: live 2.8 (n=49) vs SIM 4.2 (n=33); 1x 10-20s: live 3.3 (n=98) vs SIM 4.8 (n=38); 1x 20-40s: live 2.9 (n=167) vs SIM 4.1 (n=129); 1x 40-+s: live 3.4 (n=102) vs SIM 4.0 (n=117); 2x 5-10s: live 3.0 (n=78) vs SIM 3.2 (n=56); 2x 10-20s: live 2.6 (n=131) vs SIM 3.6 (n=115); 2x 20-40s: live 2.7 (n=168) vs SIM 3.9 (n=202); 2x 40-+s: live 3.0 (n=135) vs SIM 3.8 (n=162); OT 5-10s: live 2.9 (n=53) vs SIM 3.4 (n=71); OT 10-20s: live 2.5 (n=82) vs SIM 3.1 (n=134); OT 20-40s: live 2.8 (n=92) vs SIM 3.4 (n=174); OT 40-+s: live 2.9 (n=36) vs SIM 3.3 (n=119)

## 7. Pressure and elixir by opponent class (live R1e + stack2k + towerref; SIM opponents classified the same way from their decks)

| class | live matches | live win rate | live enemy value on my half /min | live push-start elixir (median of match medians) | SIM matches | SIM enemy value /min | SIM push-start elixir |
|---|---|---|---|---|---|---|---|
| Hog (incl. Royal Hogs) | 89 | 49% | 26.1 | 3.1 | 164 | 14.8 | 4.5 |
| Giant (incl. Goblin/Electro) | 59 | 54% | 40.0 | 2.6 | 114 | 31.7 | 4.0 |
| Golem | 57 | 32% | 57.7 | 3.2 | 116 | 35.9 | 4.7 |
| Ram/Bridge spam | 50 | 52% | 31.7 | 2.9 | 148 | 24.2 | 4.4 |
| Spawners (Witch/huts) | 49 | 73% | 37.5 | 3.1 | 66 | 29.8 | 4.7 |
| Other/no clear wincon | 40 | 60% | 27.1 | 3.3 | 56 | 21.8 | 3.3 |
| Balloon | 24 | 46% | 27.5 | 3.2 | 64 | 15.9 | 4.2 |
| X-Bow/Mortar | 23 | 39% | 31.3 | 3.0 | 48 | 17.5 | 3.6 |
| Mega Knight | 17 | 47% | 40.4 | 3.4 | 18 | 29.6 | 5.3 |
| Royal Giant | 13 | 62% | 22.7 | 3.5 | 38 | 36.2 | 4.8 |
| Lava Hound | 13 | 23% | 78.1 | 4.6 | 34 | 46.0 | 5.4 |
| Graveyard | 12 | 75% | 56.7 | 3.2 | 44 | 49.2 | 5.7 |
| Bait | 12 | 50% | 24.7 | 2.3 | 22 | 28.3 | 3.3 |
| Miner | 10 | 60% | 25.4 | 2.7 | 28 | 22.0 | 3.6 |

## 8. Where the bank leaks: behaviour at full elixir (>= 9)

Strata = phase x my-half pressure bucket x whole-board enemy value bucket (0 < .5 / 1 .5-4 / 2 4-8 / 3 >= 8 elixir of enemy bodies anywhere). taps at >= 9 per minute = 60 x sum time-share(s) x hazard(s); Shapley split into board-state mix vs hazard.

| pairing | time at >= 9 elixir (share of match) live / SIM | taps at >= 9 /min live / SIM | split: state mix / hazard | per-decision P(p > tau) at model elixir >= 9, matched strata live / SIM | whole-board bucket shares at >= 9 (0/1/2/3) live vs SIM |
|---|---|---|---|---|---|
| stack2k | 5.6% / 13.5% | 0.71 / 0.89 | -0.45 / 0.28 | 13.8% / 15.8% (n=2969) | 50%/15%/23%/12% vs 72%/12%/12%/4% |
| stack2k anti-leak OFF | 6.7% / 13.5% | 0.75 / 0.89 | -0.15 / 0.01 | 13.5% / 17.2% (n=869) | 40%/11%/25%/24% vs 72%/12%/12%/4% |
| R1e | 4.6% / 11.3% | 0.57 / 0.61 | -0.29 / 0.25 | 14.1% / 12.4% (n=7752) | 61%/13%/20%/6% vs 80%/10%/7%/2% |

## 9. Whole-match board presence (SIM's own presence -> bank relation, applied at live presence)

| pairing | enemy on board (share of time) live / SIM | mean own elixir live / SIM | SIM slope (elixir per +10 pp presence) | SIM predicted at live presence | share of the mean-elixir gap explained | push-start elixir: live / SIM / SIM predicted at live presence | share of the push-start gap explained |
|---|---|---|---|---|---|---|---|
| stack2k | 81% / 78% | 4.96 / 5.82 | -0.38 | 5.70 | 14% | 3.76 / 4.87 / 4.91 | -3% |
| stack2k anti-leak OFF | 84% / 78% | 5.09 / 5.82 | -0.38 | 5.60 | 30% | 4.32 / 4.87 / 4.96 | -16% |
| R1e | 80% / 77% | 4.42 / 5.05 | -0.49 | 4.92 | 22% | 3.03 / 3.94 / 3.92 | 2% |

Push-start values here are means of per-match medians (matches with >= 1 push). The prediction extrapolates SIM's linear relation to live's presence level (live presence sits at the busy end of SIM's range), so treat the explained share as an estimate (b).

## 10. Counterfactual: the SIM policy facing the LIVE opponents' pressure timeline

A deliberately simple elixir simulator (econ_report.simulate) replays each match's own pressure timeline (my-half pressure and whole-board enemy value bucket every state, push starts) and decides every 10 ticks with a per-decision play probability estimated from one source's decisions (phase x pressure x whole board x model-elixir), costs from that source's cost-given-elixir table. Rows 1-2 check the simulator against the real numbers; rows 3-5 swap one ingredient at a time. Columns: mean of per-match median elixir at push start | mean own elixir | plays at < 5 elixir per minute.

| pairing | scenario | push-start elixir | mean elixir | plays < 5 /min |
|---|---|---|---|---|
| stack2k | ACTUAL live | 3.76 | 4.96 | - |
| stack2k | ACTUAL SIM | 4.87 | 5.82 | - |
| stack2k | sim: SIM policy, SIM pressure (check) | 5.17 | 5.78 | 3.90 |
| stack2k | sim: live policy, live pressure, + Hero ability (check) | 4.77 | 5.19 | 4.94 |
| stack2k | sim: SIM policy, LIVE pressure | 5.30 | 5.48 | 4.25 |
| stack2k | sim: SIM policy, LIVE pressure, + Hero ability | 5.14 | 5.41 | 4.37 |
| stack2k | sim: LIVE policy, SIM pressure | 4.92 | 5.56 | 4.38 |
| R1e | ACTUAL live | 3.03 | 4.42 | - |
| R1e | ACTUAL SIM | 3.94 | 5.05 | - |
| R1e | sim: SIM policy, SIM pressure (check) | 4.37 | 5.11 | 6.52 |
| R1e | sim: live policy, live pressure, + Hero ability (check) | 4.37 | 4.65 | 6.78 |
| R1e | sim: SIM policy, LIVE pressure | 4.50 | 4.87 | 6.63 |
| R1e | sim: SIM policy, LIVE pressure, + Hero ability | 4.52 | 4.84 | 6.63 |
| R1e | sim: LIVE policy, SIM pressure | 4.29 | 4.92 | 6.35 |

## 10b. Gate verdict vs actual play, per decision, matched strata (weighted to live)

| pairing | elixir | decisions | P(p > tau) live / SIM | P(play issued) live / SIM | live plays issued with p <= tau (forced / hazard / other) |
|---|---|---|---|---|---|
| stack2k | < 5 | 14826 | 10.8% / 9.5% | 8.6% / 7.8% | 0.31/min forced |
| stack2k | >= 5 | 19638 | 12.2% / 11.8% | 12.8% / 11.7% | 0.31/min forced |
| stack2k | all | 34464 | 11.6% / 10.8% | 11.0% / 10.1% | 0.31/min forced |
| stack2k anti-leak OFF | < 5 | 3704 | 10.3% / 9.7% | 8.9% / 8.0% | 0.00/min forced |
| stack2k anti-leak OFF | >= 5 | 5179 | 12.7% / 11.9% | 12.7% / 11.8% | 0.00/min forced |
| stack2k anti-leak OFF | all | 8883 | 11.7% / 11.0% | 11.1% / 10.2% | 0.00/min forced |
| R1e | < 5 | 61123 | 13.6% / 13.8% | 10.6% / 10.8% | 0.00/min forced |
| R1e | >= 5 | 51383 | 13.4% / 11.4% | 13.1% / 11.4% | 0.00/min forced |
| R1e | all | 112506 | 13.5% / 12.7% | 11.8% / 11.1% | 0.00/min forced |

Same, with the WHOLE-board enemy value bucket added to the strata (phase x my-half pressure x whole-board 0/1/2/3 x model elixir):

| pairing | elixir | decisions | P(p > tau) live / SIM | P(play issued) live / SIM | whole-board bucket time shares 0/1/2/3 live vs SIM |
|---|---|---|---|---|---|
| stack2k | < 5 | 14796 | 10.8% / 9.7% | 8.6% / 8.0% |  |
| stack2k | >= 5 | 19609 | 12.2% / 12.6% | 12.7% / 12.5% |  |
| stack2k | all | 34405 | 11.6% / 11.4% | 11.0% / 10.6% | 19%/11%/32%/38% vs 22%/21%/29%/28% |
| stack2k anti-leak OFF | < 5 | 3640 | 10.4% / 10.1% | 8.9% / 8.4% |  |
| stack2k anti-leak OFF | >= 5 | 5115 | 12.5% / 13.4% | 12.5% / 13.3% |  |
| stack2k anti-leak OFF | all | 8755 | 11.6% / 12.0% | 11.0% / 11.3% | 17%/7%/35%/41% vs 22%/21%/29%/28% |
| R1e | < 5 | 61123 | 13.6% / 14.0% | 10.6% / 11.0% |  |
| R1e | >= 5 | 51319 | 13.3% / 12.7% | 13.0% / 12.7% |  |
| R1e | all | 112442 | 13.5% / 13.4% | 11.7% / 11.8% | 19%/13%/31%/37% vs 23%/21%/29%/26% |

## 11. Decision cadence and gate noise, measured live vs SIM

| source | decisions/s | decision gaps < 10 ticks | plays on a fresh crossing (prev decision p <= tau < p) | mean abs change of p per decision | share of changes >= .06 |
|---|---|---|---|---|---|
| LIVE stack2k | 1.60 | 7.0% | 97.1% | 0.036 | 21.2% |
| LIVE R1e | 1.57 | 7.6% | 93.0% | 0.038 | 21.9% |
| LIVE towerref_w2 | 1.62 | 6.4% | 96.3% | 0.033 | 19.4% |
| SIM stack2k (decide 10) | 1.61 | 0.0% | 98.2% | 0.043 | 24.9% |
| SIM R1e (decide 10) | 1.60 | 0.0% | 95.5% | 0.046 | 24.4% |
| SIM towerref_w2 + deployed options, decide 10 | 1.60 | 0.0% | 98.0% | 0.044 | 25.2% |
| SIM towerref_w2 + deployed options, decide 4 | 3.80 | 95.2% | 97.0% | 0.020 | 10.9% |

## 12. SIM cadence test: deployed live options (main 049772e) on towerref_w2, learner decides every 10 vs every 4 ticks

Isolated repo = git archive 049772e pipeline + econ_sim_patch.py (LR_DECIDE_EVERY touches the learner only). Options: class_sample .3, tau_phase .35/.45/.55, rocket_area, own_effects, log_barrel, hazard_below_tau min 9, lethal_rocket ot (--iw-press-pstar is live-only: no Hero Ice Wizard in SIM). v3 benchmark, 480 paired matches per arm.

| arm | decisions/s | elixir at push start (median) | pushes met < 4 | taps < 5 elixir /min quiet / pressured | cheap (Skeletons+Log) share | elixir at deploy 1x / 2x / OT | wins / 480 |
|---|---|---|---|---|---|---|---|
| decide 10 | 1.60 | 4.50 | 40% | 1.67 / 2.02 | 32.2% | 7.11 / 6.58 / 6.63 | 314 (+0 draws) |
| decide 4 | 3.80 | 4.00 | 50% | 2.17 / 2.32 | 32.9% | 6.91 / 6.26 / 6.12 | 303 (+0 draws) |

* decide 4 minus decide 10: elixir at push start (median) -0.50 [-0.68, -0.29]; paired outcomes better 40 / worse 49 (sign p 0.397).

