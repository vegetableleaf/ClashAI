# LIVETAPS (W21, 2026-10-22): the live pilot's lost and slow taps

Owner-approved ticket: fix the pilot's execution losses measured by W18 (DIAG_12 E1, 233 CLX Ranked matches: 366 taps lost
with elixir >= cost, 1.8 / 3.6 / 3.9 / 8.9% of taps in 1x / 2x / OT 2x / OT 3x; 15% of plays ~17 ticks late).
Script: `livetaps.py` (inputs = two grep extracts of the live logs, commands in its docstring); output `livetaps.out`.
Labels: (a) measured, (b) plausible but untested, (c) contradicted.

## 1. Lost taps: what they are (233 CLX Ranked matches, 9,669 taps)

My reconstruction: 414 lost taps (unconfirmed, no elixir drop within 2.5 s), **343 with elixir >= cost at the tap
(1.47 per match)**; W18 counted 366 with a slightly different pairing. Same per-phase profile: 1.6 / 3.2 / 3.8 / 8.7%.

| class (first rule that matches) | lost | share | per match | label | cause |
|---|---|---|---|---|---|
| P1 tap during the tiebreak drain (OT over) | 72 | 21% | 0.31 | (a) | the game takes no deploy after tick ~6002: 0 of 200 such taps taken (all logs since 10-07); latest taken tap 5976 |
| P2 tap after the deciding event (81-tick end sequence) | 110 | 32% | 0.47 | (a) | reader frames stay "in play" 81 ticks after the match is decided (regulation timeouts: last frame 3681 in 436 / 456); 2 of 580 such taps taken |
| A board tap under the hero ability button | 109 | 32% | 0.47 | (a) | the button (screen (818, 1224), disc ~70 px) covers the back-corner cells, e.g. (0.5, 1.5): lost 109 / 146 with my hero body on the board, 0 / 154 without; mirror corner (17.5, 1.5) 1% |
| L device load (reader frame gap >= 0.15 s or < 18 game ticks/s) | 18 | 5% | 0.08 | (a) association, (b) mechanism | lost 12.2% of such taps vs 0.5% |
| B ability tap <= 10 ticks before the card tap | 9 | 3% | 0.04 | (a) association, (b) mechanism | lost 9 / 24; within 40 ticks 16 / 52 |
| E elixir fell below cost before the release | 3 | 1% | 0.01 | (a) | |
| R remainder | 22 | 6% | 0.09 | - | no logged cause |

- **P (53%) is not an execution loss.** The match is already over (or in the drain); no play could land. (c) for
  DIAG_12 section 10's reading that "8.9% of OT-3x taps are lost": 100 of the 124 OT-3x losses are P. Without P the rate
  is **flat by phase: 1.5 / 1.8 / 2.0 / 1.9%**. P-A2's SIM handicap (`--tap-loss 1x:.018,2x:.036,ot2x:.039,ot3x:.089`)
  applied the post-end rate to plays that matter, so it OVERSTATES CLX's live handicap, most in OT 3x (8.9% vs 1.9%).
  Its "half the overtime gap was never the opponent's" (win | OT -5.2, pre-drain -8.5) needs a re-run with the corrected
  spec (c on the size; the direction stands).
- P1 still costs the RUN: 19 of the 29 `5_unconfirmed` run stops since 10-07 happened in the drain (Rockets at a dying
  princess, `lethal_rocket` firing on the drain's falling HP); 9 more were the hero-button corner.
- P2 is harmless (<= 3 taps per match, the match is decided) and not fixed: a tower-read rule would risk the reader glitch
  (68 / 600 matches show a princess "dead" for 10-30 ticks) for no gain.
- **A** is the real execution loss. Its sharp rise from 10-13 (corner lost 8-14% before, 30-45% after) dates the Hero
  Ice Wizard in the deck. The model likes that corner (1,205 taps since 10-07). Retries make it worse: after a lost tap
  the same card at the same cell follows 80 times, lost again 45 (the 10-21 spot block caps this at 2 per 20 s).
- After P and A, the remaining loss is **0.6 / 0.7 / 0.5 / 0.5%** per tap (52 taps, 0.22 per match).
- Elixir read errors: (c) as a class. Only 3 losses had the bar drop below the cost before the release; the elixir
  margin does not raise the loss rate.
- Stale hand slot / card-cycling animation: (c). Taps 0-6 ticks after a confirmation lose 0.5%, the same as later ones
  (0.6 / 0.8%); same slot vs other slot no different.
- Spot rejections other than the button: (c) beyond the button. No other cell has a sustained loss rate; the
  10-21 corner example (20261020_142524, Skeletons at (0.5, 30.5) = my back corner) is class A.

POSTFIX check (34 CLX / CLXI matches after the 10-21 spot block): 0.88 affordable lost taps per match (A 7, P 20, B 1,
R 2); with the hero up the corner still loses 7 / 11.

## 2. Slow taps (15%): (c) as a pilot execution problem

- Confirmed plays: tap -> slot rotation (= the elixir charge) median 26, p90 42; > 34 ticks 14.4% (W18: 15.1%).
- **82.6% of the slow plays were tapped before the card was affordable** (`--afford-ticks 23` lets a tap go up to 23 ticks
  early; the game holds it and takes it ~22 ticks after it can pay). Residual = latency - (max(arrival, need) + 22):
  median 0.2, p90 2.0, p99 6.2 ticks; > 8 ticks only 0.5% of plays, concentrated at tap_end_ms >= 250 (6.6%).
- So the pilot lands each play at the earliest tick the game allows; waiting until affordable would land it later.
- What IS wrong is the SIM: `Match.apply` lands every play at T + 26 whatever the elixir wait, so need-driven plays land
  16.8 ticks (mean) earlier in the SIM than live. Recommendation for the parity stream (not done here):
  land at T + max(26, need + 22), refused if need > ~23 (afford_arrival (a)). This replaces P-A2's random
  `--tap-slow 0.151:17` with the game's own rule.

## 3. Fixes (commit with this file)

| fix | where | class | condition | when the condition does not occur |
|---|---|---|---|---|
| UI guard: while my hero body is on the board, cells whose tap point lies inside the hero button's disc (`button_cells`: 0.08 x width around hero_button.BUTTON) are masked from the cell choice; the model's next-best cell is used. Opt-out `--no-ui-guard`. Logs `ui_guard` (the covered argmax) on decision / play events and `hero_up` on play events | live_play.py `button_cells`, live_gen.py `GenPilot._mask_ui` (in `guard_cells`, beside the legal guard) | A | hero body on the board AND the chosen cell is covered | mask None = byte-identical |
| Deploy window closed: no card, follow-up or ability tap once `tick + 22 >= 6002` (the tiebreak drain) | live_play.py `deploy_closed` | P1 | game tick >= 5980 | never before tick 5980; no tap there was ever taken |
| Lost-spot blocks reset per match (bug in 3495ef6: `_fails` holds this match's ticks, so drain failures blocked a card's spot for all of the next match) | live_gen.py `reset_match` | - | a multi-match run | identical within a match |

Tests: `pipeline/tests/test_livetaps_1022.py` (UI mask identity / move / flag; reset clears the blocks),
`scratchpad/gauntlet/L68/live_reader/test_livetaps_1022.py` (deploy_closed boundary 5979 / 5980; button_cells covers
(0.5, 1.5), not the mirror or the lane). `start_live.sh icebow --no-fast-plays --check`: LIVE_CHECK_PASS on Mark CLXI
(686b245a), `ui_guard: true, deploy_end: 6002`. No LIVE_OPTIONS change is needed (both fixes default on).

Not changed (small or untested): L (load; a longer press `input swipe x y x y 60-100 ms` instead of `input tap` is the
candidate, (b)), B (hold card taps until the ability press resolves, (b)), P2 (harmless), the elixir-hold slowness (game rule).

## 4. Expected effect (233-match baseline -> after the fixes)

| metric | baseline (RANKED 233) | expected |
|---|---|---|
| affordable lost taps per match (all) | 1.47 | ~0.69 (A 0.47 -> ~0, P1 0.31 -> 0; P2 0.47 and the rest 0.22 stay) |
| same, excluding post-end taps, per tap by phase 1x / 2x / OT2x / OT3x | 1.5 / 1.8 / 2.0 / 1.9% | ~0.6% in every phase |
| button-area taps with the hero up, lost | 109 / 146 | ~0 taps there (the guard moves them) |
| 5_unconfirmed run stops | 29 since 10-07 (19 drain, 9 corner) | ~0 |
| slow share (> 34 ticks) / residual > 8 | 14.4% / 0.5% | unchanged (game rule; not a pilot fault) |

Risk: the guard moves the model off a cell it liked; the moved-to cell is the model's own next choice (as the legal
guard does). The corner was being chosen while it could not be played at all.

## 5. Live verification plan (owner authorized a short run; the lead starts it)

- Run: current live model (Mark CLXI), current LIVE_OPTIONS (log_frames stays on: the scorer needs the frames), 30-50
  Ranked matches, main account (check towers / X-Bow in hand at the first match).
- Logged automatically: `play` (+ `ui_guard`, `hero_up`), `decision` (+ `ui_guard`), `confirmed` / `unconfirmed` /
  `late_landing`, `tap_timing`, `frame`, `start` (+ `ui_guard`, `deploy_end`).
- Score (inside scratchpad/gauntlet/L68/live_reader/, then from the repo root):
  ```
  grep -H -E '^\{"event": "(start|play|confirmed|unconfirmed|late_landing|tap_timing|stop|end|ability|ability_confirmed|ability_unconfirmed|cpu_starved|follow_up_scheduled|follow_up_cancelled|record_only)"' live_play_20261*.jsonl > $S/events.txt
  grep -H -o -E '^\{"event": "frame", "t_dev": [0-9.]+, "tick": [0-9]+, "my_side": [0-9], "elixir": [0-9.]+, "backlog": [0-9]+' live_play_202610[2-3]*.jsonl > $S/frames.txt
  icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/livetaps/livetaps.py $S/events.txt $S/frames.txt live_play_<first stamp of the run>
  ```
  The VERIFY block prints the same table as the baseline plus the W21 trace (taps with the hero up, guard moves, taps
  after tick 5979 = must be 0). Also count `grep -c '"why": "5_unconfirmed"'` over the run's logs.
- Pass: class A ~0 and P1 = 0; affordable lost per match well under 1.47 (expected ~0.7; at 40 matches the Poisson SE
  is ~0.13); no new failure class; win rate is NOT the readout (40 matches cannot see it).
- If the guard fires but class A persists: the button disc is wider than 0.08 x width -> raise UI_BUTTON_R.
- Optional follow-ups for a later run (not built): `input swipe` press for class L; hold after an ability press for B;
  a drag (`input swipe hand -> board`) as a way to keep the corner cell playable with the hero up (b).
