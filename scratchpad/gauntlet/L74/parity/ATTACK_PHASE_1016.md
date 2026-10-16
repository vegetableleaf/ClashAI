# Attack phase under slow and after freeze (2026-10-16)

**Question.** The phase-3 validator found one fixed hit phase for Archer (27/27) and the princess tower (106/108), but
not for the X-Bow (236/283), Hero Ice Wizard (38/45), Knight (6/21), Tesla (12/105) or Tesla_EV1 (3/23). Lead
hypothesis: under a slow (35 progress per tick), the progress overshoots the hit point (Knight 1200: 35 x 35 = 1225).
Either the game handles that remainder differently from the SIM, or the validator ignores it. Second question: is the
low Tesla support a detection artefact or a real timing difference?

**Answer.** On every rule tested here, the SIM matches live. The validator was wrong in two places:

1. **(a) measured: the remainder is carried, in both the game and the SIM.** The attack progress is one counter that a
   hit never resets or snaps. A hit lands on the tick where the counter *crosses* a multiple of HitSpeed. Under a slow,
   the overshoot (0 to 30) carries into the next cycle. The old validator looked for an exact phase (progress mod
   HitSpeed == a fixed value), which a 35 step almost never lands on. It also missed X-Bow hits after a slow ended:
   the counter stays off the 50-grid (remainder 5) for the rest of the lock.
2. **(c) contradicted: the Tesla's timing is not different.** The low support came from detection. The validator
   counted every hp drop of the Tesla's target as a Tesla hit. In the latest capture the opponent's Tesla was shooting
   our X-Bow, which loses 5-6 hp every 2 ticks to building decay. That gave 115 drops that were not Tesla hits. Using
   the Tesla's own fire marker, 33/33 of its hits land at phase 0.

No RoyaleSim patch is proposed. `validate_p3.py` is fixed, and V3/V5 now PASS where they have data.

Scripts are in `attack_phase/`. Text outputs sit next to them. The validator before/after outputs are in
`.foreman/scratch/attack_phase/`.

## Words used here

- **progress**: the attack counter. It gains 50 per tick unbuffed, 35 under an Ice Wizard slow, and 0 while frozen.
  It counts up across hits on one target (Knight: 1200, 2400, 3600, ...).
- **crossing tick**: the tick on which progress passes a multiple of HitSpeed: `progress // HitSpeed` grows.
- **remainder**: progress mod HitSpeed on the hit tick. It is 0 unbuffed, and 0 to 30 under a 35 step.
- **load timer**: counts down 50 per tick and is set back to LoadTime on the tick the unit fires. This gives the
  **exact fire tick** for every unit with LoadTime > 0: `fire tick = sample tick - (LoadTime - load) / 50`. A target's
  hp drop only brackets the hit, and other attackers or decay can cause it. Projectile launches play the same role for
  shooters.

## 1. Live rule (`live_rule.py` -> `live_rule_1016.txt`, `freeze_resume.py` -> `freeze_resume_1016.txt`)

Three captures: `p3_20261016T133738`, `T134735`, `T135619`. Per sample pair with the same target and progress > 0,
the step comes from the body's buffs. "Linear" means progress@f1 - progress@f0 = step x dt, so nothing reset or
snapped the counter at the hit.

| state | fire marker | on the crossing tick | linear across the hit (carry, no snap) | remainder at the hit |
|---|---|---|---|---|
| unbuffed | load re-arm | **423/423** placed (1 more: the Hero IW ability tick, non-linear) | 1068/1074 (6 sample-gap / ability ticks) | 0, or 5 after an earlier slow (X-Bow 18 hits) |
| unbuffed | projectile launch | **828/834** (6: 4 non-linear sample pairs, 1 King Tower launch seen one sample late, 1 Hero IW ability) | | 0 |
| slowed (35/tick) | load re-arm | **36/36** | **72/72** | spread over 5-30 |
| slowed (35/tick) | projectile launch | **52/52** | | X-Bow: 0, 5, 10, 15, 20, 25, 30 (4/5/4/4/5/5/5) |

The Goblin Demolisher's kamikaze form is excluded: its launches never cross (17 events), which looks like a different
mechanism. It is not studied here.

**Slowed Knight, live** (`p3_20261016T135619`, g...27, IceWizardHeroSlow the whole time):
progress 1190 -> **1225** (hit t1671, remainder 25), 2380 -> **2415** (t1705, remainder 15), 3570 -> **3605**
(t1739, remainder 5). Hits are 34 ticks apart, and progress keeps climbing by 35 straight through each hit. The entry
credit under the slow is LoadTime + 35 (735 on the entry tick, 770 one tick later), not LoadTime + 50.

**After a slow ends (X-Bow, live):** 18 unbuffed X-Bow hits sit at remainder 5. The counter came out of a slow off
the 50-grid and stays there. Each hit still lands on the crossing tick.

**Freeze (live):** while a -100 buff (ZapFreeze, Hero IW freeze) is on a body, its attack component is usually absent.
When it comes back, the progress and the load timer are as they were, apart from the 1-2 ticks around the edges:

| body | before | after | next hit |
|---|---|---|---|
| Tesla g25 (10-tick freeze) | t666 p1850 | t678 p1950 | t683 at 2200 (crossing) |
| Tesla g25 | t702 p3150 | t714 p3250 | t715 at 3300 (crossing) |
| Tesla g56 | t2041 p4200 | t2053 p4300 | t2055 at 4400 (crossing) |
| Hero IW g99 | t3191 p2800 L100 | t3203 p2900 L0 | t3213 at 3400 (crossing) |
| Hero IW g57 (load held) | t2191 p3650 **L950** | t2203 p3750 **L850** | (target lost) |

That is 4/4 resumes with the next hit on the crossing tick. Some freezes also clear the target (a princess tower and a
Knight read `tgtNone` right after a ZapFreeze). That is the stun-reset retarget, which V5L covers, not the phase.

**Tesla:** while hidden it reads progress 0 (with a target sometimes held, for example our princess tower out of
reach). The capture has no separate hide/rise field, so the rise itself is **not measurable here**. A troop entry
behaves like any fresh entry: credit LoadTime + 50 = 750, first fire 7 ticks later at 1100, then every 22 ticks at
multiples of 1100. With the load re-arm as the marker, 33/33 Tesla / Tesla_EV1 fires land on the crossing tick, and V10
gives 11/11 first hits as the SIM predicts. **No slowed Tesla appears live** (all 33 are unbuffed).

Why the hp-drop events failed (`tesla_events.py` -> `tesla_events_1016.txt`): in `T135619`, 127 hp drops of the
Tesla's target came in intervals where the Tesla did not fire. 115 were on our X-Bow (drop sizes 5 x76 and 6 x39,
which is the building's lifetime decay), 8 were on a Knight hit by others, and 4 were on an Ice Cube. In `T134735` there
were 8 non-fire drops (a Pekka hit by 109 / 81, the princess tower's and others' hits). In `T133738` there were 12 (a
decaying Goblin Demolisher form).

## 2. SIM rule (royalesim 0.1.35, `4fd4d54 clean`, `sim_probe.py` -> `sim_probe35.txt`)

Code (`combat.rs attack_step_progress`, at 4fd4d54): `cycle_before = progress / hs; progress += tick; fired = progress / hs
> cycle_before`, where `tick` is the HitSpeedMultiplier composition of 50 (35 slowed, 0 frozen). On a fire it sets
`load = LoadTime`. The fire never touches progress, so the overshoot carries. When frozen, `tick <= 0` returns with
progress held. The load timer is also held under the shipped `LOAD_TIMER_TARGET_LOSS` arm (`stands`).

Probes (level 11, table client160402017_20261006, a blue Hero IW at (9, 9.2) as the slower):

| scenario | per-tick steps | hits | on crossing, load re-armed | remainders |
|---|---|---|---|---|
| Knight, no shooter | 50 x329 | 14 | 14/14 | 0 x14 |
| Knight, Hero IW slow | 50 x36, 35 x193, nothing else (no snap) | 2 unbuffed + 5 slowed | 7/7 | slowed 0, 25, 15, 5, 30 |
| Knight, Hero IW ability pressed | 0 x101 (held at **3880, load 300**), then 35 | 2 + 2 | 4/4 | after the freeze 4790 -> **4825** (25) |
| X-Bow, no shooter | 50 x419 | 52 | 52/52 | 0 |
| X-Bow, Hero IW slow | 35 x187, then 50 x232 | 16 slowed + 29 after the slow | 45/45 | slowed 0-30, **after the slow 45 x29** (off-grid carry) |
| Tesla, no shooter | 50 x115 | 5 | 5/5 | 0 |
| Tesla, Hero IW slow | 35 x96 | 3 | 3/3 | 0, 20, 5 |

SIM slowed Knight: 4790 -> **4825** (25), 5980 -> **6015** (15), 7170 -> **7205** (5), 34 ticks apart. That is the
same remainder sequence as the live Knight above (25, 15, 5, 34-tick spacing).

## 3. Verdict per rule

| rule | live | SIM | verdict |
|---|---|---|---|
| unbuffed: hit when progress reaches a HitSpeed multiple | 423/423 re-arms, 828/834 launches | 100% of probe hits | **SIM == live** |
| slowed: 35/tick, hit on the crossing tick, overshoot carried (no reset, no snap) | 36/36 + 52/52 on crossing, 72/72 linear | yes (code + 26 slowed probe hits) | **SIM == live**. The hypothesis "the game resets to a fixed value" is contradicted |
| after a slow ends: the off-grid remainder persists | X-Bow remainder 5 x18 | X-Bow remainder 45 x29 | **SIM == live** (same mechanism) |
| slowed entry credit = LoadTime + step | Knight 735 / 770 | `progress = lt - load; progress += tick` | **SIM == live** |
| freeze: progress held, load held, resume with carry, next hit on the crossing | 4/4 resumes; Hero IW load 950 -> 850 over 12 ticks (10 frozen) | held 3880 / 300 for 101 ticks, then crossing | **SIM == live** (n = 4 live resumes, small) |
| Tesla: same cycle (entry 750, first fire 7 ticks, every 1100) | 33/33 on crossing, V10 11/11 | 5/5 + 3/3 | **SIM == live** (unbuffed only, live) |

**Patches proposed for RoyaleSim: none.**

## 4. Validator fixes (`reader_val/validate_p3.py`, tests in `test_validate_p3.py`)

1. `candidates()` uses the crossing model. A tick "hits" phase P when a value congruent to P (on the 50-grid) lies in
   (progress - step, progress]. At +50 on the grid this is identical to the old exact phase. Under 35 it is the
   crossing.
2. `rearm()` is a new fire marker: the load timer **rose** between samples. It gives an exact fire tick when LoadTime -
   load is a whole number of ticks. V3/V5 phase events and V10 first hits use it for non-shooters with LoadTime > 0, in
   place of the target's hp drop. Hp drops remain only for LoadTime-0 non-shooters. The rule is "rose", not "fell less
   than 50 x dt": a sample pair whose tick gap over-reports the game's advance (t2700 -> 2702, progress +50, load -50)
   falsely re-armed a Battle Healer and a Knight_EV1 under the looser test.
3. V10 credit and hit prediction use the body's step (LoadTime + 35 and a ceil-to-crossing under a slow).
4. V10 now skips a component that reappears after a freeze with its held progress ("resumed after a freeze"). It had
   been counted as a fresh entry (Tesla 1950 / 3250 / 4300, X-Bow 9495).

Tests: `test_validate_p3.py` gains a slowed-Knight battle (+35, crossing hits, load re-armed) and two `candidates`
asserts. Red to green: with the old exact-phase `candidates` patched in, the slowed battle gives
`V3 FAIL fixed_phase=25 support=5/32`. With the fix, it gives V3 PASS phase 0 n/n, and V10 Knight credit 5/5, hit 5/5.
Output: `VALIDATE_P3_SYNTHETIC_OK: 6 scenarios`.

### New per-attacker support (fixed phase, events)

| attacker | T133738 | T134735 | T135619 (was) |
|---|---|---|---|
| Knight | 6/6 (was 0 events) | 0 events | **42/42** (6/21) |
| X-Bow | 84/84 | 15/15 | **283/283** (236/283) |
| Tesla | 4/4 | 7/7 | **16/16** (12/105, phase 1000) |
| Tesla_EV1 | 1/1 | 3/3 | **2/2** (3/23, phase 450) |
| Hero IW | 14/14 | 20/21 | **45/45** (38/45) |
| princess tower | 118/118 | 101/101 | 107/108 (106/108) |
| Archer | | | 27/27 |
| others | Skeleton 37/37, Blowdart 22/22, Bomb Tower 20/20, Barrel Goblin 19/19, Battle Healer 8/8, Knight_EV1 7/7, **Goblin Demolisher kamikaze 10/17 at phase 1050** | Baby Dragon 20/20, King 15/16, Mega Minion 6/6, E-Wiz hero 6/6, Pekka 3/3 | Knight_EV1 12/12, Skeleton 8/8, Archer_EV1 5/5 |

Verdicts per capture (V1-V10):

- T133738: V3 SKIP->**PASS**, V10 FAIL->**PASS** (96/105).
- T134735: V10 FAIL->**PASS** (51/52; was 31/43).
- T135619: V3 FAIL->**PASS**, V5 FAIL->**PASS**, V10 PASS (106/109; was 79/87).

V1, V2, V4, V5L, V6, V8 and V9 lines are byte-identical before and after.

## Concerns

- **V6 still FAILs** on all three captures, and that predates this work. A frozen body has no attack component, so V6
  never gets a frozen interval to check. On top of that, slow35 is 638/640, 148/148 and 118/119 exact. The 3 misses
  were not examined.
- **V5L FAILs on T133738** (1 switch without a reset). That predates this work and is not touched here.
- The Goblin Demolisher kamikaze form (phase 1050, 10/17; its launches never cross a multiple) is unexplained.
- Freeze resume is n = 4 live. A slowed Tesla and the Tesla rise are not observed live.
- The load re-arm marker assumes a fire is the only thing that raises the load timer. Across 469 re-arms (all states), 467 land
  on the crossing tick; the 2 exceptions are hero-ability ticks (Hero IW, E-Wiz hero).
