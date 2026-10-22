# DIAG_12 (W18, 10-22): why the best opponent (W14 I u40, 4ff9fe93) fails 6 of 12 O4-Ranked checks

Labels: **(a) measured** (number given), **(b) plausible, untested** (measurement named), **(c) contradicted** (evidence given).
Every number: `diag12/diag12.out`, rebuilt by `diag12/diag12.py` (laptop, idle priority, ~25 s).
- Live = CLX's 233 Ranked matches (W13 `clx_ranked/rows.json` + the habits-cache frames / plays of the same logs).
- SIM = CLX vs I u40, 2,880 games (`pod_backup_weekend/w14/o4/w14F_Iu40`).
- SIM-pos = the same opponent on block 741200 with deploy positions and tower / X-Bow traces (`w14/o3/w14c_Iu40_pos`, 480 games).
- Definitions are the scorer's (`w14/o4r_table.py`); public information only, never the opponent's hand, deck order or elixir.

## 0. Bottom line

The overall CLX win passes (48.8 vs 48.1) because two errors of opposite sign cancel.
- **By phase (a):** the SIM opponent is too STRONG in regulation and too WEAK in overtime.
  - Regulation losses (share of all matches): SIM 26.5 vs Ranked 18.9, +7.6 [+1.8, +12.4].
  - Overtime losses: SIM 24.7 vs Ranked 33.0, -8.3 [-14.8, -2.4].
- **By deck (a):** it is too weak with tank / bridge-spam decks (BEAT) and too strong with the rest.
  - vs BEAT, CLX wins 41.0 vs 25.3.
  - vs the rest, 53.7 vs 60.7.

Four failing checks are one mechanism, the **chip race into overtime**.
1. The SIM opponent denies CLX's X-Bow worse than Ranked humans.
   - Bridge X-Bows lock 58.8% vs 46.4% (the live rule on both sides).
   - Damage per X-Bow vs tank decks: 0.306 vs 0.196 of a princess.
2. So CLX reaches 3:00 ahead more often: 41% vs 31% of 0-0 overtimes.
3. Then the SIM opponent converts overtime worse when CLX is behind (38.9% vs 28.8% CLX win). It splits its OT troops over both
   lanes (47% on CLX's weakest princess) where humans focus it (67%).
4. Against tank decks this shows up mostly as the **tiebreak drain**: 25.3% of BEAT matches on Ranked vs 12.2% in the SIM.

The fifth check (regulation loss) is the other half of the same imbalance. The SIM opponent is a **high-tempo** player:
- 36% more plays per minute in 2x / OT;
- answers 1.3 s sooner;
- 26% more troop elixir per minute in 2x.

That tempo wins it regulation games, keeps games open after the first princess falls (both took one), and is the whole style
failure.

**CLX's own live execution explains little.**
- (a) CLX answers tank pushes as fast live as in the SIM: 1.3 vs 1.5 s median.
- (a) X-Bow placement is exact (0.1% off by > 0.5 tile).
- (a) Two measured handicaps the SIM does not model; their effect on the cells is the first pod job:
  - LOST taps: 1.57 per match with enough elixir and no deploy. That is 8.9% of taps in OT 3x.
  - SLOW taps: the median tap-to-deploy (the game's elixir drop) is the SIM's 26 ticks, but 15.1% of plays land at 35-59 ticks
    (mean +17). Spells 23%, troops 13%.

**The engine is not the main cause.**
- (a) The BEAT gap is as large on tanks whose fight parity meets 0.95: +13.6 pp.
- (a) A tank placed before the X-Bow can lock stops the lock equally often in the SIM and live: 19.1 vs 18.5%.

## 1. Diagnosis table

Shares are of the gap, SIM minus Ranked. Fixes marked G need the owner's approval (gate definition); R are opponent-training
rounds; P are pod jobs.

| check (SIM I u40 vs Ranked) | (i) opponent policy | (ii) engine | (iii) CLX live execution | (iv) the check itself | evidence | fix |
|---|---|---|---|---|---|---|
| **win vs BEAT** 41.0 vs 25.3 [17.2, 35.6] (n 83) | **main, ~65-80%** (a/b): tank-deck humans deny X-Bows; SIM damage per X-Bow 0.306 vs 0.196, lock 60.4 vs 42.6%. After a LATE tank (> 3.5 s after our X-Bow) the lock is 64.3 vs 37.3%; with no tank in the lane 72.3 vs 52.5% | **<= ~3 pp** (b): the gap is +13.6 [+0.6, +23.6] on tanks with J1 >= 0.95 (Giant, E-Giant, Golem, PEKKA, RG, GS); the J1-suspect group (Royal Hogs 0.60, E-Golem 0.66, Battle Ram 0.89) is 33% of SIM BEAT games, +17.3 n.s. Tank-before-lock geometry: (c) as a cause (19.1 vs 18.5%) | (c) as a main cause: CLX's first play after a tank 1.3 s live vs 1.5 s SIM; 10-s defensive spend 6.4 / 7.8 vs 6.6 / 8.1 elixir (1x / 2x). Lost taps: (b), P-A2 measures | ~2.5 pp (a): SIM BEAT is 18% E-Golem (Ranked ~4%); re-weighted to the Ranked within-BEAT mix 38.5. Live n 83: the Ranked 18:00-21:59 block alone is 13.6% | The gap sits in OT: BEAT OT losses 45.8% of BEAT matches live vs 25.9% SIM; drain 25.3 vs 12.2. 0-0 OT vs BEAT: CLX behind at 3:00 56.5% live vs 37.2% SIM | R1 (chip denial), P-B tau probes, R3 (X-Bow-state starts, b) |
| **win \| OT** 57.6 vs 47.3 (n 146); **pre-drain** 66.3 vs 52.6 (n 95) | **main** (a): about half the 0-0 OT gap is the 3:00 state. SIM win rates at Ranked's state shares: 59.1 (SIM 64.7, Ranked 50.8). The other half is OT play given state. Behind: 38.9 vs 28.8 CLX win. Weak-lane focus of OT troop elixir: 46.6 vs 66.9% | (c) for the OT rules: J8 drain law within 2-3 ticks, J4 3x elixir 0.961; triple elixir present | (b) lost taps 8.9% of OT-3x taps (SIM refuses 5.3% for other reasons) + 15% slow taps (+17 ticks); bound by P-A2 | (a) 4 live rows are regulation results labelled OT (crowns unequal at 3:00, end read 1.4-3.2 s late). SIM-consistent label: win \| OT 47.9, pre-drain 53.8 (z 2.42 -> 2.25, 2.68 -> 2.39) | S1 / O1 sections | R1, R2-lane (b), G1 |
| **both took one** 13.3 vs 5.6 (n 233) | **main** (a): both comeback directions are ~2.3x. CLX answers a lost first princess 14.1 vs 5.4%, the opponent 12.6 vs 6.0%. At 0-1 (opponent leading) CLX's bridge X-Bows lock 47.7 vs 25.8% (live rule). The opponent-side excess cannot be CLX's live execution: a weaker live CLX would RAISE live comebacks | (b) P(our king falls \| our princess fell) 16.9 vs 7.6% (pocket / king activation): J3 0.947, pocket deploys equal (44.7 vs 41.0%). Not separated | (c) for the opponent-side half (sign) | ~1.6 pp (a): the SIM's first falls come earlier; SIM comeback rate at Ranked's fall-time mix 11.7 (raw 13.3) | B1 / B2 | R2 (lead_protect), tau probe |
| **regulation loss** 26.5 vs 18.9 (n 233) | **main** (a): SIM wins more regulation games. 1x 14.5 vs 11.6, 2x 9.5 vs 5.6, gave-back 2.3 vs 0.9. vs the rest of the decks +9.0 [+2.3, +13.9]. Its 2x troop elixir is 38.3 vs 30.4 per min | (b) not separated | (c): lost taps would raise live regulation losses, not lower them | **1.3 pp** (a): with the SIM-consistent OT label, Ranked 20.2 (z 2.54 -> 2.10) | P1 / P2 / I1 | P-B tau probes, R1, G1 |
| **style** 0.78 (bound 0.65) | **main** (a): tempo features. ppm_2x 11.36 vs 8.33 (d +1.22). react_s 4.72 vs 5.98 s (d -1.30). push_mean 3.90 vs 3.28 (d +1.00). react_3s +0.87. It drifted with RL: B u20 0.53 -> E 0.68 -> I 0.78 | - | (b) small: live 'mine' counts every tap incl. lost / retried (2.2 per match of 41.5) | (c) the detector's same-card 100-tick merge applied to the SIM: 0.78 unchanged | Y1 | P-B tau probes (eval-time gate threshold) |
| (W14 cell) **X-Bow lock at 1-1** 35.8 vs 12.2 | (a) melee / tank first answers at 1-1: 0 of 16 locks live vs 38.7% SIM | (c): tank-before-lock agrees (above) | (c): placement exact | **large** (a): live = 41 X-Bows in **13 matches**, 5 with a lock; the cell is conditional on reaching 1-1 (itself a failing cell). The rule difference goes the OTHER way: SIM under the live rule 39.6% (bridge 53.8) | X1 / X2 | follows R1 / R2; report with match-cluster CIs (G3) |

Passing cells today, which any fix must keep: win 48.8, vs rest 53.7 (z -1.64, close to failing), OT share 58.3, CLX lost
first 48.9, opponent takes 55.3, CLX takes 58.0 (+5.2, tolerance 8).

## 2. The measurements

**P1. Phase (a)**, share of all matches, SIM / Ranked:

| deck class | reg W | reg L | OT W | OT L |
|---|---|---|---|---|
| all | 15.2 / 18.5 | 26.5 / 18.9 | 33.6 / 29.6 | 24.7 / 33.0 |
| vs BEAT | 14.4 / 6.0 | 33.1 / 28.9 | 26.6 / 19.3 | 25.9 / 45.8 |
| vs rest | 15.7 / 25.3 | 22.3 / 13.3 | 38.0 / 35.3 | 24.0 / 26.0 |

**S1. The 3:00 state of 0-0 overtimes (a)**, CLX's weakest princess vs theirs, threshold 0.1:

| state | Ranked share | Ranked CLX win | SIM-pos share | SIM CLX win |
|---|---|---|---|---|
| behind | 50.0 | 28.8 | 39.4 | 38.9 |
| level | 18.9 | 44.0 | 19.5 | 55.3 |
| ahead | 31.1 | 90.2 | 41.1 | 93.9 |

- At 3:00 (0-0), CLX's weakest princess is 0.535 live vs 0.539 SIM.
- The opponent's weakest is 0.617 live vs 0.532 SIM.
- So the difference is CLX's OFFENCE being denied live, not CLX's defence.
- B u20's P(win | behind) is 29.9, at the Ranked value. E and I drifted above it (37.2, 38.9; SE ~5).

**X1 / X1b. X-Bow defence (a)**, bridge X-Bows, the live lock rule on both sides:

| | lock 0-0 | dmg per X-Bow | troop answer elixir |
|---|---|---|---|
| vs BEAT, Ranked / SIM | 42.6 / 60.4 | 0.196 / 0.306 | 5.84 / 8.06 |
| vs rest, Ranked / SIM | 48.1 / 58.0 | 0.217 / 0.252 | 4.82 / 8.62 |

- The SIM opponent spends MORE troop elixir at the X-Bow and locks MORE. Ranked humans deny cheaply; their answers that we cannot
  see live are bodiless spells (b: invisible to the detector).
- First troop answer at 1-1:
  - Ranked: melee / tank 53% with 0% lock.
  - SIM: 40% with 38.7% lock.

**O1. OT lane focus (a).**
- Ranked: 66.9% of the opponent's OT troop elixir goes to CLX's weakest princess, and 36 of 37 pre-drain OT falls hit it.
- SIM: 46.6%, and 38 of 45.
- So the SIM opponent finishes the weak tower when it gets there, but does not concentrate on it.

**E1. CLX execution (a).**
- 9,669 taps; 518 unconfirmed.
  - 78 of them dropped elixir: the game took them.
  - 440 did not: lost taps. 366 of those had elixir >= cost at the tap.
- Lost-tap rate per tap, by window: 1x 1.8%, 2x 3.6%, OT 2x 3.9%, OT 3x 8.9%.
- A lost card was deployed later in 182 of 440 cases, median 4.8 s later.
- Tap -> the game's elixir drop: median 26 ticks (= the SIM's action delay).
  - 15.1% of plays take 35-59 ticks, mean +17: spells 23.1%, troops / buildings 13.2%.
  - The slow mode is in the GAME's take, not in the reader's confirmation: the confirm and the drop are slow on the same plays,
    827 of 842.
  - By window, share > 34 ticks: 16.7 / 15.9 / 13.7 / 12.4%, so no OT concentration.
  - This is not spell flight time: SIM vs live first hit is 0 ticks for Rocket / Tornado and +2 for the Log.
- X-Bow rows: 19.5 (903), 21.5 (115), 22.5 (56) live vs the SIM's 19.5 / 21.5 / 22.5. Placement error 0.00 tiles.

## 3. What the opponent can and cannot fix

- **Not the opponent's job (iii) / (iv):**
  - (a) The 4 mislabelled live OT rows move reg_loss by 1.3 pp, win \| OT +0.6, pre-drain +1.2.
  - (b) CLX's lost and slow taps: size unknown until P-A2. The SIM should apply them to CLX in the gate rather than ask the
    opponent to reproduce them.
  - (a) The 1-1 lock cell rests on 13 live matches.
- **Opponent's job (i):** tempo (style, regulation losses, open games), X-Bow denial (chip race -> 3:00 state -> OT / drain ->
  BEAT), OT weak-lane focus, defending a lead.
- **Engine (ii):** at most ~3 pp of the BEAT gap. Royal Hogs / E-Golem / Battle Ram fight parity: J1 0.60 / 0.66 / 0.89; the fin15
  Tornado law raised Royal Hogs J2 to 0.72. FIN15 queue item: the evo Royal Hogs winged fall. No engine law found for the other
  cells.

## 4. Why W14 plateaued at 6 / 12 (c on "more of the same")

- W14's levers were knobs (lr, KL anchor, gate anchor, tempo via decide interval) and training mixes (BEAT x3, OT starts,
  CLX-only).
- The cells that fail are about HOW the opponent wins, not how often. The win-only objective is near saturation (training win
  ~0.47 vs the frozen mix): a policy that wins by tempo in regulation and one that wins the chip race into OT score the same.
- Every knob kept the first kind. OT starts (I) fixed OT share and princess takes but not OT conversion: lane focus 47%.
- Two things only change WHAT is optimal:
  - a reward on the mechanism (chip denial = R1; lead defence = R2);
  - a decode / imitation term on the tempo (P-B probes, then a tempo-calibrated gate).
- Decide-interval slowing (W14 probe 60 / 80) delayed RESPONSES too. CLX gained 4-7 pp and both-took rose to 17-20: (a) the
  wrong tempo knob.
- The gate threshold (tau) removes marginal plays and keeps urgent answers: (b), P-B tests it.

## 5. Pod plan (dedicated pod 157.157.221.29:33401; `w18/pod_start.sh`, `w18/w18_runner.sh`, append-only queues)

| order | job | stream | cost | decides |
|---|---|---|---|---|
| P-A1 | identity: I u40 block 741200, no flags, vs w14F_Iu40_741200 | A | ~10 min | pod / code identity (pairs everything below) |
| P-A2 | CLX `--tap-loss 1x:0.018,2x:0.036,ot2x:0.039,ot3x:0.089 --tap-slow 0.151:17` vs I u40, 2,880 (paired) | A | ~50 min | the (iii) share of every cell (both live handicaps at once; split only if it moves cells); whether G2 matters |
| P-B1..3 | I u40 `--opp-tau 0.45 / 0.35 / 0.55`, block 741200 with positions | B | ~25 min each | tempo / style and its effect on reg loss, both-took, X-Bow locks |
| R1 | opponent training: I u40 + `princess_redirect: penalty` (cfg/oppW18R1_redirect_s74.yaml), 40 updates, gated every 5 | GPU + 24 actors | ~2.5 h | chip denial -> 3:00 state, OT, BEAT drain |
| next | best tau as a full 2,880 O4 check; R2 = R1's winner + `lead_protect: on` (both-took); R3 (b, code needed) = X-Bow-placement scenario starts | | | |

## 6. Owner decisions (prepared, not applied)

- **G1 (iv)**: the live OT label = crowns level at 3:00 AND end > 3610 (the SIM's rule).
  - Moves reg_loss 18.9 -> 20.2, win \| OT 47.3 -> 47.9, pre-drain 52.6 -> 53.8, OT share 62.7 -> 60.9.
  - It does not flip a cell on I u40.
- **G2 (iii)**: run the O4 check with CLX's measured live lost and slow taps applied to CLX (`--tap-loss`, `--tap-slow`), if P-A2
  shows the cells move.
  The opponent should not be trained to reproduce CLX's handicap.
- **G3 (iv)**: report both-took-one and the 1-1 lock cell with match-cluster CIs. The 1-1 cell has an effective n of 13.

## 7. Predicted O4 after the fixes (my estimates, not measurements)

| check | now | after P-B (tau) + R1 + R2 | confidence |
|---|---|---|---|
| win, vs rest, OT share, lost-first, opp takes, CLX takes | pass | pass; vs rest is the most at risk (z -1.64 now) | medium |
| style | 0.78 | pass if tau ~0.45 brings ppm_2x to ~9 | medium (0.5) |
| reg loss | 26.5 | pass with tau + G1 (needs <= 25.4 under G1) | medium-low |
| win \| OT / pre-drain | 57.6 / 66.3 | pass if R1 moves the 3:00 ahead share from 41 toward 31 | low-medium |
| BEAT | 41.0 | still fails (needs <= 34.7); R1 maybe -3 to -6 pp | low |
| both took one | 13.3 | still fails (needs <= ~8.5) unless R2 halves comebacks | low |

Expected: 8-10 of 12 after these rounds, not 12. BEAT and both-took-one are the two I expect to need a second fix each
(R3 X-Bow-state starts; a Ranked-imitation tempo term).

## 8. HYPOTHESIS LEDGER (owner 10-22: several independent causes per cell; updated after every pass)

Shares are in pp of the cell's SIM - Ranked gap, measured on the I u40 2,880 / pos 480 rows vs the 233 Ranked rows
(`diag12.out` sections in brackets).
- Status: **C** = confirmed (measured, explains that much), **R** = rejected (measured, explains ~0 or the wrong sign), **U** =
  untested (the test named), **P** = a pod job is measuring it.
- "Remainder" = the gap no confirmed hypothesis has accounted for yet.

### 8.1 win vs BEAT: gap +15.7 (SIM 41.0 vs 25.3)

| # | hypothesis | test | share | status |
|---|---|---|---|---|
| B1 | (iv) within-BEAT win-condition mix (SIM 18% E-Golem, Ranked ~4%) | re-weight SIM per-wincon rates to Ranked's BEAT mix [W1] | 2.5 | C |
| B2 | (iv) opponent tower level / tower troops: 13% of Ranked opponents below max | live BEAT vs max-tower opponents only: 27.0 (n 74) [L4] | 1.7 | C |
| B3 | (iv) Ranked skill drift | BEAT by thirds: 29.6 / 20.0 / 26.9 [L7] | 0 (no trend) | R |
| B4 | (ii) fight parity of the tank cards | the gap on J1 >= 0.95 tanks is +13.6 [+0.6, +23.6]; the J1-suspect group (Royal Hogs, E-Golem, Battle Ram) is +17.3 n.s. [G1] | <= 2.8 (bound) | U (W19 asked for fin15 per-card numbers) |
| B5 | (ii) X-Bow first-target geometry vs a tank | lock when a same-lane tank lands <= 3.5 s after our X-Bow: SIM 19.1 vs live 18.5 [X1b] | 0 | R |
| B6 | (iii) CLX's defensive latency vs tanks | first own play after a tank: 1.3 s live vs 1.5 s SIM; 10-s spend equal [K1] | 0 | R |
| B7 | (iii) CLX lost / slow taps | vs BEAT live 1.75 lost / match, 17.4% slow (vs rest 1.47 / 14.1%) [L5] | ? | P (P-A2) |
| B8 | (i) X-Bow denial by tank decks -> chip race -> drain | dmg per bridge X-Bow 0.306 vs 0.196; drain losses 12.2 vs 25.3% of BEAT matches; 0-0 OT behind at 3:00 37.2 vs 56.5% [X1b, P3, P4] | the drain excess alone is 13.1 of the 15.7 | C (mechanism) |
| B9 | (i) tank-push lethality in regulation | BEAT regulation losses 33.1 vs 28.9 (n.s.) [P1] | ~0 | R |
| | **remainder** | 15.7 - 2.5 - 1.7 = 11.5, all inside B8's OT / drain mechanism; B4 (<= 2.8) and B7 (P-A2) still open | | |

### 8.2 win | OT: gap +10.3 (57.6 vs 47.3); OT decided before the drain: +13.7 (66.3 vs 52.6)

| # | hypothesis | test | share | status |
|---|---|---|---|---|
| O1 | (iv) 4 regulation results labelled OT live | SIM-consistent label [D1] | 0.6 / 1.2 | C (G1) |
| O2 | (iv) tower level | max-tower live win \| OT 46.7 (n 137) [L4] | -0.6 (wrong sign) | R |
| O3 | (iv) Ranked drift | win \| OT by thirds 51.1 / 52.0 / 39.2 [L7] | the target moves 12 pp; see G5 | C (target issue) |
| O4 | interaction with BEAT: tank-deck overtimes | if the SIM's BEAT OTs went at the Ranked rate: 57.6 -> 50.3 [L1] | 7.3 of 10.3 (70%) | C |
| O5 | (i) the 3:00 state (chip race in regulation) | SIM win rates at Ranked state shares 59.1 vs 64.7 [S1] | ~40-55% of the 0-0 OT gap | C |
| O6 | (i) OT play given the state: weak-lane focus | OT troop elixir on CLX's weakest princess 46.6 vs 66.9% [O1]; P(win \| behind) 38.9 vs 28.8 | the rest of S1 | C (mechanism) |
| O7 | (iii) lost / slow taps in OT 3x | P-A2; association: won OTs have MORE lost taps (2.16 vs 1.55 per match) [L5] | ? | P |
| O8 | (ii) OT rules (triple elixir, drain timing) | J4 3x 0.961, J8 drain law within 2-3 ticks (FIN15) | 0 | R |
| | **remainder** | O4 + O5 / O6 overlap (tank-deck OTs are where the state and the conversion differ); no unexplained part beyond P-A2 | | |

### 8.3 both took one: gap +7.7 (13.3 vs 5.6)

| # | hypothesis | test | share | status |
|---|---|---|---|---|
| T1 | (iv) first falls come earlier in the SIM | SIM comeback rate at Ranked's fall-time mix 11.7 [B2] | 1.6 | C |
| T2 | (iv) tower level | max-tower live 5.4 [L4] | 0.2 | R |
| T3 | (iv) Ranked drift | 5.2 / 7.7 / 3.8 [L7] | 0 | R |
| T4 | deck class | BEAT 20.4 vs 9.6, rest 8.9 vs 3.3: both elevated ~2-2.7x [L3] | (not a cause) | - |
| T5 | (i) the opponent's defence when LEADING (CLX trailing 0-1) | CLX takes one back 14.1 vs 5.4%; bridge X-Bow lock at 0-1 47.7 vs 25.8% [B1, X1] | ~half (one of two directions) | C (mechanism) |
| T6 | (i) the opponent's attack when TRAILING (CLX led 1-0) | opponent takes one back 12.6 vs 6.0% [B1]; CLX's own execution cannot produce this sign | the other half | C (mechanism, cause inside it U) |
| T7 | (ii) pocket / king behaviour after a fall | king HP per pocket deploy 0.173 vs 0.135 (+28%), same pocket card mix [pocket2] | ? | U (W19) |
| | **remainder** | 6.1 after T1, split T5 / T6 by direction; what makes the trailing SIM opponent score is untested | | |

### 8.4 regulation loss: gap +7.6 (26.5 vs 18.9)

| # | hypothesis | test | share | status |
|---|---|---|---|---|
| R1 | (iv) live OT mislabel | [D1] | 1.3 | C (G1) |
| R2 | (iv) tower level / tower troops | max-tower live 15.3 (n 203); lower-tower 43.3 (n 30) [L4] | -1.6 at the SIM's 7% tower-troop mix (wrong sign) | R |
| R3 | (iv) Ranked drift | 14.3 / 20.5 / 21.8 [L7] | recent thirds are closer (gap 4.7 on the last third) | C (target issue, G5) |
| R4 | deck class | at the Ranked mix: rest +5.4, BEAT +0.3. Hog 15.9 vs 5.6, MK 34.4 vs 24.2, Royal Hogs 28.9 vs 0 [L2] | (where, not why) | - |
| R5 | (i) 2x tempo / aggression | troop elixir per min in 2x 38.3 vs 30.4; 2x regulation losses 9.5 vs 5.6% [I1, P2] | ? | U (R3 play_cost tests it) |
| R6 | (ii)/(i) king kills after a princess | regulation losses with our king down 9.3 vs 3.4% of matches [L2] | <= 5.9 (overlaps R5) | U (W19 + T7) |
| R7 | (iii) CLX execution | would RAISE live regulation losses; lost taps in regulation 1.13 / match [L5] | 0 (sign) | R |
| | **remainder** | 6.3 after R1, split R5 / R6, neither isolated yet | | |

### 8.5 style: 0.78 (bound 0.65)

| # | hypothesis | test | distance | status |
|---|---|---|---|---|
| S1 | (iv) the live tap list holds lost / retried taps (the SIM's: landed plays only) | live 'mine' = confirmed taps at their tap tick [L6b] | 0.78 -> 0.71 (react_s d -1.30 -> -1.12) | C (G4) |
| S2 | (iv) the clock offset (game tick vs clock) | ticks - 78 [L6] | 0.78 -> 0.79 | R |
| S3 | (iv) the detector's same-card 100-tick merge | [Y1] | 0.78 -> 0.78 | R |
| S4 | (iv) the live detector misses short-lived cheap units | 2x plays of cost <= 2: SIM 1.79 vs live 1.10 per min (+63%; c3 +20%, c4 +13%, c5+ +34%) | <= the c<=2 share of ppm_2x | U (detector recall on live frames) |
| S5 | (i) the gate threshold | eval tau 0.35 / 0.45: ppm_2x 11.30 / 11.02 vs 11.32 [P-B] | ~0 | R |
| S6 | (i) tempo inside the policy (plays whenever affordable) | R3 play_cost | ? | P |
| | **remainder** | 0.71 after S1 (needs <= 0.65): react_s d -1.12, ppm_2x +1.22, push_mean +1.00 | | |

Note on L6: the 0.64 printed for "our plays = confirmed - 26" is an artefact. 24% of live taps share their tick with a
detected opponent play (the pilot reacts on that frame). Shifting our play 2 ticks earlier makes that same play count as an
instant answer, so the variant is not used.

### 8.6 Owner decisions added by this pass

- **G4 (iv)**: score style with the live pilot's CONFIRMED taps (lost / retried taps out), as the SIM side counts only landed
  plays: 0.78 -> 0.71.
- **G5 (iv)**: which Ranked target to calibrate to.
  - CLX's Ranked win falls with the rank climb, by thirds of the 233: 57.1 / 48.7 / 38.5; win \| OT 51.1 / 52.0 / 39.2.
  - The 233-match average is a moving mixture; the current rank is ~38-45%.
  - Options: the whole 233 (today's gate), or the last 100-150 matches. The latter needs more Ranked play for n.

## 9. NEW TARGET (owner 10-22): the most recent 100 Ranked CLX matches (`w18/o4r_recent.py`)

**Data (a).**
- W13's pipeline (index.py -> anatomy.py), re-run over every CLX Ranked log: 267 matches, 10-20 13:28 -> 10-21 14:32 (the switch
  to Mark CLXI). That is 34 more than the 233, which stopped at 07:08.
- Output: `diag12/recent/rows_ext.json`. W13's rows.json stays the 233-match reference.
- The window is the last 100: 10-21 02:47 -> 14:22.

**Tolerance rule (stated).**
- Each predeclared point tolerance is scaled by sqrt(n_233 / n_recent) of that cell's live n, so it stays the same multiple of
  the live standard error as W14's rule.
- |z| < 1.96 is unchanged; it widens by itself with n.
- The style bound stays 0.65 (an effect size), measured against these 100 matches' opponents.

| cell | all 233 [95%] | **recent 100 [95%]** | tolerance (pp) |
|---|---|---|---|
| * CLX win | 48.1 [41.7, 54.5] | **40.0 [30.9, 49.8]** | 5 -> 7.6 |
| * win vs BEAT | 25.3 [17.2, 35.6] (n 83) | **41.9 [26.4, 59.2] (n 31)** | 10 -> 16.4 |
| * win vs the rest | 60.7 [52.7, 68.1] (n 150) | **39.1 [28.5, 50.9] (n 69)** | z only |
| * OT share | 62.7 [56.3, 68.6] | **57.0 [47.2, 66.3]** | z only |
| * win \| OT | 47.3 [39.3, 55.3] (n 146) | **43.9 [31.8, 56.7] (n 57)** | 8 -> 12.8 |
| * win \| OT before the drain | 52.6 [42.7, 62.4] (n 95) | **45.7 [30.5, 61.8] (n 35)** | z only |
| * CLX lost the first princess | 48.1 [41.7, 54.5] | **53.0 [43.3, 62.5]** | z only |
| * opponent takes a princess | 51.1 [44.7, 57.4] | **57.0 [47.2, 66.3]** | 8 -> 12.2 |
| * CLX takes a princess | 52.8 [46.4, 59.1] | **45.0 [35.6, 54.8]** | 8 -> 12.2 |
| * both took one | 5.6 [3.3, 9.3] | **5.0 [2.2, 11.2]** | z only |
| * regulation loss | 18.9 [14.4, 24.4] | **28.0 [20.1, 37.5]** | z only |
| loss by tiebreak drain | 15.5 [11.4, 20.6] | 16.0 [10.1, 24.4] | monitored |

**Re-score against the recent 100** (`diag12/recent/o4r_recent100.out`):

| opponent | CLX win | vs BEAT | vs rest | win \| OT | pre-drain | CLX takes | both took | reg loss | style | pass |
|---|---|---|---|---|---|---|---|---|---|---|
| target (recent 100) | 40.0 | 41.9 | 39.1 | 43.9 | 45.7 | 45.0 | 5.0 | 28.0 | <= 0.65 | 12 |
| I u40 (2,880) | 48.8 F | 41.0 | 53.7 F | 57.6 F | 66.3 F | 58.0 F | 13.3 F | 26.5 | 0.79 F | **5** |
| E u40 (2,880) | 50.7 F | 43.4 | 55.1 F | 57.5 F | 63.3 F | 60.3 F | 14.8 F | 25.6 | 0.69 F | 5 |
| B u20 (1,920) | 57.0 F | 48.7 | 62.3 F | 63.0 F | 68.8 F | 64.7 F | 12.1 F | 22.9 | 0.54 | 5 (+ lost-first F) |
| A3 u35 (1,920) | 53.0 F | 45.5 | 57.8 F | 60.1 F | 67.5 F | 62.1 F | 13.8 F | 23.9 | 0.75 F | 5 |

**What changes with the target (a), and what does not.**
- At the current rank the opponent must be STRONGER overall: CLX win 40 vs I u40's 48.8.
  - The extra strength is with the NON-tank decks (vs rest 39.1 live vs 53.7).
  - BEAT and regulation loss now PASS for I u40. On the old target those two were failing.
- Failing on BOTH targets, i.e. the robust gaps:
  - CLX takes a princess: X-Bow denial, ledger B8 / T5;
  - win \| OT and OT before the drain: 3:00 state + OT focus, O5 / O6;
  - both took one: T5 / T6;
  - style: tempo, S6.
- The fix rounds already queued aim at exactly these:
  - R1 princess_redirect: chip / X-Bow denial;
  - R3 play_cost: tempo;
  - R2 lead_protect: lead defence.
- The new target adds one requirement: R1's extra defence must not cost strength. CLX win has to FALL (48.8 -> <= 47.6), not rise.

**The window is noisy (iv), so read single cells with care.** With I u40, the failing set changes with the window length:

| window | fails | which |
|---|---|---|
| 80 | 5 | win, vs rest, pre-drain, CLX takes, style |
| 100 | 7 | (as in the table above) |
| 120 | 6 | win, win \| OT, pre-drain, CLX takes, both took, ... |
| 150 | 5 | win \| OT, pre-drain, CLX takes, both took, style |

- The BEAT swing (25.3 on all 233 -> 41.9 on the last 100) rests on 31 matches.
- The vs-rest swing (60.7 -> 39.1) rests on 69.
- The cells stable across windows are CLX takes, win \| OT, pre-drain and both took one. Those are the ones to fix first.
