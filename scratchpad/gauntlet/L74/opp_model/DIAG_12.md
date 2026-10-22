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
