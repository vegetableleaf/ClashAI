# L74 drill suite: catalog and Phase 1 baseline (2026-10-09)

Status: **Phase 1 done** (selectors, harvest, decision-only baseline). Phase 2 (fork scoring) and Phase 3 (training) are gated on the lead.

## What a drill is here

A drill is **not** a hand-built board with a hand-priced score. It has four parts:

1. A **selector**: code that finds real game moments matching a situation, using public information only (my elixir, hand, bodies, enemy bodies on the board, tower HP).
2. A **DO** action family and a **HOLD-BACK** action family.
3. The **answer** comes from the game: Phase 2 forks the SIM at each moment into "do", "hold back" and "the model's own choice", then compares the outcomes.
4. The forked outcomes become the **training labels** in Phase 3.

The doctrine only decides which moments get drilled. It never decides the score.

Phase 1 only answers one question: **at these moments, how often does the agent take the DO action, and how often does it hold back?**

Scores (higher is better for both):
- **DO %** = share of do-moments where the agent took the DO action inside the window.
- **HOLD %** = share of hold-moments where the agent did **not** take the held-back action.

A pass rate says nothing about whether the doctrine is right. Phase 2 measures that.

## Sources and n (all measured)

| source | what | matches | minutes |
|---|---|---|---|
| live_current | live logs, current checkpoint (`rseries_r3c_..._towerref_w2.pt`) with gate decode (family `towerref_bundle`), 10-08 15:08 to 10-09 17:43; decision states every 10 ticks | 256 | 889 |
| live_deployed | the subset of live_current that carries `tau_threatened` (closest to today's LIVE_OPTIONS). None of the logs had `--log-air block`, because it went on after them. | 100 | 360 |
| pros | corpus_v6/icebow_public_v1: 2,244 pro icebow sides, engine re-drives, frames every 10 ticks, **all** bodies (not only y <= 20) | 2,244 | 9,310 |
| SIM | scout: 96 benchmark matches (seeds 0:96) | 96 | 369 |

SIM scout details:
- It is `sim_val.sh`'s base arm plus `--log-air block`: live checkpoint, gen_v1_s0 opponent at T .3, evo census, the deployed decision flags.
- It runs through `sim_dump.py`, on the pod (`/workspace/wt_drills`, 4 workers at nice 10, no cpu.lock, 846 s wall).
- SIM plays are the model's **decisions**. A few may have been refused when they landed.

How to rerun (all single-process and light on the laptop):
1. `build_live.py` (a copy of L74/mistakes/build.py), then `build_pros.py`, produce `data/*.pkl.gz` (gitignored).
2. `drills.py run` writes `out/baseline.json` and `out/moments_*.jsonl.gz`.
3. `table.py` writes `out/table.md`.
4. `drills.py selftest` runs one synthetic board per selector.

SIM moments come with seed and tick. They are in `out/moments_sim.jsonl.gz`, where `file` is the match tag `s0:gen:<seed>` and `t` is the tick.

## How this avoids the old system's failures (HANDOFF ~6431-6435, ~5313)

| old failure (measured in August) | here |
|---|---|
| A drill's end was scored as a terminal state, which poisoned the critic | There are no drill episodes. Moments are taken from whole matches. Phase 2 forks run every branch to the real match end and also record +10 s and +20 s, so nothing is cut short. |
| `drill_frac` counted episodes, so drills got ~8% of the gradient | The Phase 3 spec counts the drills' share in **training steps** (rows that carry a drill label). |
| 9 of 28 drills never produced a positive example | Measured per drill below: how many DO actions the agent itself produced. The fork **forces** the DO branch, so a label exists even when the policy never chooses DO (D6 needs this: 0 live positives). |
| Hand-priced rewards (defence priced ~40x below offence) | No prices. The label is the outcome difference between forked branches of the same moment, using common random numbers (the same random draws in every branch). |
| Hand-built "foundational" boards that were really cell-precision tests | Only real moments: live, pro and SIM. |

## Per-drill table: current score vs pros (decision-only, before any training)

All numbers are **measured** unless marked. 95% Wilson intervals are in brackets. "SIM per 960" is the scout's count scaled to 960 matches, so it is an estimate from 96 matches.

| drill | score | live_current n | live_current % | live_deployed n | live_deployed % | pros n | pros % | SIM n (96) | SIM % | SIM per 960 |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 under fire | DO | 529 | 23.6 [20, 27] | 167 | 26.3 [20, 34] | 8,295 | 28.7 [28, 30] | 230 | 28.7 [23, 35] | 2,300 |
| D1 | HOLD | 103 | 80.6 [72, 87] | 31 | 83.9 [67, 93] | 1,568 | 81.9 [80, 84] | 57 | 78.9 [67, 88] | 570 |
| D2 threatened lane | DO | 1,666 | 72.3 [70, 74] | 676 | 73.7 [70, 77] | 19,175 | 81.3 [81, 82] | 665 | 72.6 [69, 76] | 6,650 |
| D2 | HOLD | 1,666 | 87.0 [85, 89] | 676 | 88.2 [86, 90] | 19,175 | 89.0 [89, 90] | 665 | 87.1 [84, 89] | 6,650 |
| D3 pool elixir | DO | 2,718 | 78.3 [77, 80] | 1,092 | 79.2 [77, 82] | 22,697 | 88.3 [88, 89] | 890 | 88.0 [86, 90] | 8,900 |
| D3 | HOLD | 2,718 | 85.2 [84, 86] | 1,092 | 86.4 [84, 88] | 22,697 | 94.0 [94, 94] | 890 | 88.0 [86, 90] | 8,900 |
| D4 air answer | DO | 266 | 26.7 [22, 32] | 122 | 29.5 [22, 38] | 4,878 | 24.6 [23, 26] | 181 | 26.5 [21, 33] | 1,810 |
| D4 | HOLD | 444 | 75.0 [71, 79] | 215 | 74.0 [68, 79] | 6,597 | 76.6 [76, 78] | 283 | 74.6 [69, 79] | 2,830 |
| D5 Log targets | DO | 283 | 28.3 [23, 34] | 95 | 37.9 [29, 48] | 3,643 | 15.3 [14, 16] | 106 | 26.4 [19, 36] | 1,060 |
| D5 | HOLD | 229 | 94.3 [90, 97] | 101 | 93.1 [86, 97] | 3,409 | 93.0 [92, 94] | 149 | 90.6 [85, 94] | 1,490 |
| D6 Rocket the clump | DO | 35 | **0.0** [0, 10] | 14 | 0.0 [0, 22] | 1,296 | 3.5 [3, 5] | 19 | 5.3 [1, 25] | 190 |
| D6 | DO, kill >= 6 | 35 | 0.0 [0, 10] | 14 | 0.0 [0, 22] | 1,269 | 3.3 [2, 4] | 19 | 5.3 [1, 25] | 190 |
| D6b Tornado + Rocket | DO | 5 | 0.0 | 1 | 0.0 | 174 | 4.6 [2, 9] | 0 | - | 0 (< ~30) |
| D6 | HOLD | 563 | 100.0 [99, 100] | 242 | 100.0 [98, 100] | 10,267 | 98.8 [98, 99] | 405 | 99.8 [99, 100] | 4,050 |
| D7 late tower Rocket | DO | 971 | 12.7 [11, 15] | 413 | 12.1 [9, 16] | 14,330 | 10.3 [10, 11] | 547 | 12.8 [10, 16] | 5,470 |
| D7 | HOLD | 207 | 93.2 [89, 96] | 75 | 96.0 [89, 99] | 5,206 | 91.5 [91, 92] | 128 | 95.3 [90, 98] | 1,280 |
| D8 sneaky lock | DO | 213 | 3.8 [2, 7] | 70 | 2.9 [1, 10] | 1,965 | 5.8 [5, 7] | 121 | 2.5 [1, 7] | 1,210 |
| D8 | HOLD | 1,275 | 97.0 [96, 98] | 530 | 97.0 [95, 98] | 13,682 | 94.5 [94, 95] | 702 | 96.4 [95, 98] | 7,020 |
| D9 second card | DO | 1,513 | 93.3 [92, 94] | 726 | 93.5 [92, 95] | 16,928 | 92.1 [92, 92] | 1,136 | 91.8 [90, 93] | 11,360 |
| D9 | HOLD | 1,513 | 96.4 [95, 97] | 726 | 96.1 [94, 97] | 16,928 | 96.3 [96, 97] | 1,136 | 95.9 [94, 97] | 11,360 |

What the table says (measured, decision-level only):
- **The largest live-vs-pro gaps are D3, D2 DO and D1 DO.**
  - D3 (pooling elixir): live is 10 pp below pros on DO (78 vs 88) and 9 pp below on HOLD (85 vs 94). This agrees with the mistake catalogue's N1.
  - D2 DO (defend the pushed lane): 72 vs 81.
  - D1 DO (play under fire): 24 vs 29. This agrees with M4.
- **D3 in SIM looks like pros (88 / 88), not like live (78 / 85).** This is (b), plausible but untested: the same checkpoint pools better in SIM than live. The likely suspects are live latency and how the elixir bar is read.
  - Consequence for Phase 2: forking D3 in SIM may never visit live's failure states.
  - What to check first: the D3 rate on live states replayed through the SIM decision path, which is decision-only.
- **The rest are at or above pro rates by this measure:**
  - D4: 27 vs 25 DO and 75 vs 77 HOLD. A ground-only response comes in 25% of live air-only moments vs 23% for pros; Skeletons or Knight specifically is 17% live vs 15% pros.
  - D5: live Logs swarms *more* often than pros (28 vs 15).
  - D7: 12.7 vs 10.3 per 5 s window.
  - D9: details in its section.
  - So the owner's "Knight vs a lone Balloon" (D4) is real in single cases: in 444 live air-only moments, the ground-only responses were Skeletons 40, Knight 36, Log 21 and X-Bow 14. But the rate is not above pros'. Whether those plays are bad is Phase 2's question.
- **D6: the live model has never Rocketed a >= 10-elixir clump on my half within 3 s** (0 of 35). Pros do it 3.5% of the time. So pros almost never follow the D6 doctrine either. This is consistent with the combo worker's SIM: lone Rocket and combo arms show no win gain.

## The drills

The common rules are in `drills.py`'s docstring. Briefly:
- Own frame: my king is at (9, 3) and forward is **increasing** y. This is the review/mistakes tile frame, not the model's board frame.
- No own play may be pending (except D9).
- A moment is counted once, then not again for 5 s per (drill, kind, key) unless stated otherwise.
- Live plays use the tap tick. Pro plays use the deploy tick minus 26.

### D1 Defend under fire (M4)
- **Selector:**
  - A tower of mine lost HP in the last 1 s, and an enemy body is within 8 tiles of it.
  - A 3+ elixir card other than X-Bow or Rocket is affordable (Knight, Tornado, Ice Wizard or Tesla).
  - DO-moment: enemy value within 8 tiles >= 2.0 elixir.
  - HOLD-moment: <= 1.0 elixir, and every body is <= 0.7 (trivial: the tower kills it alone).
- **DO:** a play landing within 9 tiles of that tower within 2 s (M4's failure is >= 2 s idle).
- **HOLD:** no such play.
- **Evidence:** fixes.txt F1 @6455053 says extra fall +6.8% [2.8, 10.6] and M4 3.5 runs/10 min vs pros 2.3. The "~4.3 wins/100" figure is in commit 6455053's message.
- **Phase 3:** reuse arm E2's counterfactual gate labels (branch a8bdb155). Do not build a second trainer.

### D2 Defend the threatened lane (M3)
- **Selector:**
  - Enemy value >= 5 in one lane (any y), with its closest body still at y > 12.
  - The other lane holds <= 2 elixir, and my elixir is >= 3.
  - Only one moment per lane per 15 s.
- **DO:** a play landing in the push lane or centre on my half by the crossing + 2 s, **or** >= 5 elixir held at the crossing. The crossing is when the push's closest body reaches y <= 16; the window is capped at 10 s.
- **HOLD:** < 4 elixir tapped off-side (other lane, or y > 18) from onset to the crossing + 1 s.
- **Evidence:** F2, about 2.4 wins/100. Pros spend off-side as often as live does. The cost is in the outcome, which Phase 2 measures.

### D3 Pool elixir, don't dribble (N1 / F3)
- **Selector:** a lane threat of 3-10 elixir whose closest body is > 9 tiles from that lane's target tower, while my elixir is in [1, 4).
- **DO:** the first answer within 10 s (a play landing on my half in that lane or the centre) is tapped with the threat within 9 tiles or at >= 4 elixir. Not answering at all also counts as DO.
- **HOLD:** no chain, meaning not two or more cheap cards (cost <= 3) tapped at < 4 elixir into that lane.
- **Evidence:** card-wait HANDOFF line ~5186: 26% of plays are at < 4 elixir vs pros 11-13%, and 97% of them are the model's own top card.
- **Coordination:** the mechanic_fork "patience" mechanic (wait for a better card) covers part of D3's fork.

### D4 Answer air with air (owner: Knight vs a lone Balloon)
- **Air capability comes from RoyaleSim `cards.json`, not from memory:**
  - Damages air: **Tesla, Ice Wizard, Rocket** (`attacks_air` or `aoe_to_air`).
  - **Tornado** only reaches air (its area effect has `hits_air` and a 60 dps buff) and does no damage of its own. It counts as neither a pass nor a failure.
  - Ground-only: **Knight, Skeletons, X-Bow, Log**.
- **Selector:**
  - Enemy flyers on my half (y <= 18) worth >= 2 elixir, with less than 0.5 elixir of enemy ground bodies there.
  - Skeleton Barrel does not count as air (the same exemption as the live block).
  - DO-moment: an air-damaging card is also affordable.
- **A response** is a play within 4 s landing within 7 tiles of the flyer nearest my towers, or within 7 tiles of the tower nearest that flyer.
- **DO:** the first response damages air.
- **HOLD:** no ground-only response.

### D5 Log targets
- **Selector:** Log affordable.
  - DO-moment: a swarm, meaning >= 3 small ground bodies (<= 1 elixir each) within 2.5 tiles of each other at y <= 18. This includes Goblin Barrel goblins and Skeleton Barrel skeletons once they drop.
  - HOLD-moment: every enemy body on my half is a flyer, and there is no ground enemy at y <= 20.
- **DO:** within 3 s, a Log whose corridor covers the swarm: |dx| <= 2.7 and 0 <= swarm y - Log y <= 10.6 (the Log rolls toward increasing y).
- **HOLD:** no Log landing at y <= 18.
- **Note:** live blocks the air-only case by rule today (`--log-air block`), but no log in this baseline had that rule on. So the HOLD % here is the **model's own** behaviour: 13 Logs in 229 moments.

### D6 Rocket the clump (owner: Lava Hound push with 15+ elixir)
- **Selector:**
  - Rocket affordable, and enemy bodies on my half (y <= 16).
  - Blast value = enemy value within 2.5 tiles of a body's centre (Rocket radius 2.0 plus body radius 0.5).
  - Multi-entity cards count once: Ram Rider is two bodies with the same first tick.
  - **DO-moment:** blast value >= 10 at decision time.
  - **D6b:** Tornado also in hand, elixir >= 9, pull value (5.5 tiles) >= 10 while the blast value is < 10.
  - **HOLD-moment:** threat on my half >= 3, best blast < 5, and elixir < 9 (a Rocket would leave < 3 to defend with).
  - `kill` = value the Rocket would destroy: each body's value x min(1, Rocket damage / its current HP), from cards.json table HP at the same level as the Rocket damage. The table splits DO at kill >= 6; almost every DO-moment passes that.
- **DO:** a Rocket within 3 s landing within 3.5 tiles of the clump.
- **D6b DO:** a Tornado and a Rocket within 4 s, both within 5.5 tiles of the pull centre.
- **HOLD:** no Rocket landing on my half.
- **Evidence:** HANDOFF ~5224: blast value 10.6 at decision, 2.9 destroyed at impact, 44% of value walked out during flight.
- **Not done here:** impact-time aim. The fork must aim where the clump will be at impact, as rocket_value2 does.
- **Coordination:** D6b's opportunity belongs to the combo worker (a67f26ce, `rocket_tornado`). Reuse that worker's runs; do not re-run them.

### D7 Late-game tower Rocket (the owner's example)
- **Selector:** 2x or overtime, Rocket affordable, and an enemy princess alive.
- **Threatened** = the deployed `tau_threat_state` (a tower of mine lost HP within 2.0 s **and** an enemy is within 8 tiles of it, `decision_options.py:348`) **or** >= 7 elixir of enemy bodies on my half (review.py THREAT_V).
  - DO-moment: not threatened. HOLD-moment: threatened.
  - Window 5 s; one moment per 10 s.
- **DO:** a Rocket landing within 3.5 tiles of an alive princess. A Rocket at the king tower counts as a fail (tower doctrine); it happened 16 times in pros' DO-moments and 0 times live.
- **HOLD:** no Rocket on the enemy half.
- **Coordination:** the fork is already in mechanic_fork as mechanic 3 (`rocket_tower`). Phase 2 imports it; do not duplicate.

### D8 Sneaky lock (owner spec)
- **The selector IS the sneaky-lock worker's rule.** `sneaky_rule.py` is a copy of `pipeline/sneaky_lock.py` @ af50e7f, so D8 fires exactly where the fork harness's `MECH=sneaky` trigger fires.
  - My X-Bow reaches an alive enemy princess (13.04 tiles).
  - Blockers are enemy ground bodies within 12.1 + radius of the X-Bow and nearer than that tower.
  - A plan exists when there is **exactly one** blocker, it is a troop, and some Tornado cell's simulated pull keeps it >= 0.3 tiles beyond the X-Bow's drop distance for 3 ticks without dragging another body into reach.
  - Tornado must be affordable.
  - DO-moment: a plan exists.
  - HOLD-moment: blockers exist but there is no plan. That covers two or more blockers (owner: "not ... if there are other blockers inside the xbow's range"), a building, or a body that cannot be pulled out.
  - Window 3 s.
- **DO:** a Tornado within 6 tiles of the blocker.
- **HOLD:** no Tornado within 6 tiles of any blocker.
- **Result:** pros DO it 5.8% of the time, live 3.8%. The owner's "> 80% success" is about the outcome, which the fork's lock metric measures.
- **Coordination:** owned by mechanic_fork. Do not duplicate.

### D9 The right second card (pd diag)
- **Selector:** a first card is tapped while enemy bodies on my half are worth >= 2, and the second card is tapped within 3 s.
- **DO:** the second card lands on my half and is not a no-pull Tornado. A Tornado has pull value when the enemy bodies within 5.5 tiles of where it lands are worth >= 3 elixir and number >= 2.
- **HOLD:** the second card is not a no-pull Tornado.
- **Measured Tornado share of second cards:**

| source | second cards that are Tornado | after a Log | second cards within 24 ticks (1.2 s) |
|---|---|---|---|
| live | 8.7% (n 1,513) | 7.9% (n 331) | 5 |
| pros | 10.4% (n 16,928) | 11.0% (n 2,825) | 2,683 (13.5% Tornado) |
| SIM base | 11.4% (n 1,136) | 13.1% (n 214) | 0 |

- **This contradicts the over-pick for the deployed configuration (c).** pd diag's 27-30% came from the pipeline-decisions arms, which let the model decide while a play is pending. Live and base SIM almost never pair within 1.2 s.
- **D9 is a drill only if pending-play decisions ship.** As a live drill it is saturated: 93-96% pass, equal to pros.

## Drills too rare to train on (plainly)

The bar is about 100 SIM moments per 960 matches, or about 30 live moments.

| drill | problem | measured numbers |
|---|---|---|
| **D6b** (Tornado then Rocket) | too rare everywhere | SIM: 0 in 96 matches (< ~30 per 960); live 5 (live_deployed 1). Leave it to the combo worker. |
| **D6 DO** | rare in live, no positives | live_deployed 14 (< 30); live_current 35, but 0 positives. SIM 190 per 960 clears the bar only narrowly (19 moments seen, in 14 of 96 matches). A per-match cap of 1 gives ~140 forks per 960. Trainable only with forced-DO forks; the policy itself never produces it. |
| **D1 HOLD** | borderline in live | live_deployed 31; SIM 570 per 960 is fine. |
| **D8 DO** | moments are common, positives are rare | the policy almost never takes the DO action: 8 live, 3 SIM (live_current 213 moments, SIM 1,210 per 960). This is the old "never positive" risk, unless the fork forces the Tornado (it does). |

Every other drill-kind has >= 400 SIM moments per 960 and >= 100 live moments.

## Phase 2 (gated): fork scoring, cost

- **What:** one fork run over 960 benchmark seeds. At each drill moment, fork "DO forced" and "HOLD forced"; branch A is the original match, which is the model's own choice.
  - Common random numbers; run to the match end, also recording +10 s and +20 s.
  - Import the mechanic_fork harness once its faithfulness check passes (A == replayed fork). Its folder has no report yet: **ask the lead**.
  - Selectors run inside the fork run through the `sim_dump.py` hook (the same code as the scout).
- **Scope:** 11 drill-kinds: D1 do and hold, D2, D3, D4 do and hold, D5 do and hold, D6 do and hold, D9.
  - D7 and D8 are left out because mechanic_fork already has them.
  - D6b is left out because the combo worker has it.
  - Cap: 1 fork per kind per match and 300 per kind. That is 10 x 300 + ~140 (D6 do) = **~3,140 moments, ~6,280 branches**.
- **Cost:**
  - Measured: the base match costs **35 CPU-s** (scout: 846 s x 4 workers / 96 matches, at pod load ~100).
  - Untested: a branch to the match end costs ~0.5 of a match.
  - Base 960 x 35 s is about **560 CPU-min**. Branches are 6,280 x 17.6 s, about **1,840 CPU-min**. **Total about 2,400 CPU-min (~40 CPU-hours), ~1.5 h wall at 28 processes** on an otherwise idle pod.
  - With +20 s branches only (no outcome, tower HP and elixir deltas only): about 930 CPU-min.
  - Needs `cpu.lock`.
- **Before Phase 2, settle the D3 SIM-vs-live gap above.** Otherwise D3's forks score states the live model handles worse.

## Phase 3 (gated), per the ticket

- One training run on the drill mix, reusing arm E's counterfactual-label trainer (branch a8bdb155).
- KL anchor to the live policy everywhere else.
- The drills' share is counted in TRAINING STEPS.
- Evaluate with the forked test per drill plus the 960 benchmark (search_s0 paired; ship bar: lower 95% bound > -3 pp).
- **No imitation toward pro labels:** that has lost 5-7 pp three times (HANDOFF ~5290).

## Caveats (each one is something not measured)

- Pass rates are decision-level association. **Whether DO or HOLD is the better move is untested** until Phase 2.
- Live rates mix option sets. live_deployed (100 matches) is the closest to today's LIVE_OPTIONS, and no log had `--log-air block`.
- Pro taps are deploy - 26 ticks. Pro towers are level 11 and live towers are level ~15; selectors use HP drops and alive flags only, never absolute HP.
- D6 `kill` uses cards.json table HP. About 5% of classes (archers, guards, royal_recruit, ...) are not in the table and fall back to 600 HP.
- The SIM scout (96 matches) is a firing-rate estimate. "SIM per 960" is that count x 10, not a 960 run.

## Files

- `drills.py`: selectors D1-D9, harvest, baseline, selftest.
- `build_live.py`: a copy of mistakes/build.py.
- `build_pros.py`: the pro extractor with all bodies.
- `sim_dump.py`: the search_s0 per-decision state dump hook.
- `sneaky_rule.py`: a copy of the sneaky-lock rule.
- `table.py`, `show.py`: print the tables.
- `out/baseline.json`: all rates and action breakdowns per group.
- `out/table.md`: the table above.
- `out/moments_live.jsonl.gz`, `out/moments_sim.jsonl.gz`: every moment with file or seed tag, tick, info and pass flags. The pros' file is regenerable and gitignored.
- `out/sim_dump/run/`: the scout's matches.jsonl and run.json. The 15 MB of raw dumps are gitignored.
