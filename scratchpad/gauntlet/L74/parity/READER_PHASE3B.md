# Reader phase 3b: exact creation tick of every new body (10-17)

Layout-free semantic note. The memory side (where the fields live, how they were found, the build) is in the private
reader notes; nothing here is an offset, a binary hash, a device path or a command line.

## Problem

The reader samples the board every ~2 game ticks (frame gaps measured on 5,826 of 6,110 sample pairs = 2 ticks; 1 and 3
ticks occur). A body first seen at frame tick T1 was created somewhere in (T0, T1] (T0 = the previous frame), and
`fights.py` cannot tell where, so it places plays mid-gap and draws the ceiling from the whole gap.

## New per-body fields (phase-3 capture, `phase3.bodies[]`, every listed body, attack-capable or not)

| JSON key | unit | meaning (measured) |
|---|---|---|
| `deploy_remaining_raw` | ms | Deploy time left. Starts at the definition's DeployTime (card plays) or at a spawner-given value (children), -50 every game tick, 0 once deployed. `behavior_state_raw == 4` exactly while it is > 0. |
| `deploy_tick_raw` | battle tick | The tick the body's deploy started. Constant for the body's whole life; 0 = never deployed (towers, never-deploying children, a digger's tunnel object). A staggered body changes it once, 0 -> its deploy start. |
| `card_tick_raw` | battle tick | The tick a card play made this object. -1 for objects made by other objects (spawned children, the Hero IW cube / IceCube, the Goblin Drill building). |
| `active_ms_raw` | ms | Active time: 0 while deploying or tunnelling, then +50 every tick. In behaviour 11 (staggered multi-spawn) it instead counts DOWN the stagger delay left; 0 ends the stagger. |

Per definition (`phase3.defs[]`, once per definition): `DeployTime` (ms), `DeployTimerDelay` (ms; only the on-screen
deploy timer reads it, the countdown does not; 0 everywhere seen), `DeployTimeAffectedByCharacterSpeed` (0/1; when 1
the countdown step is speed-scaled by buffs; 0 everywhere seen).

All four body values are null only if that one read failed (never happened: 0 null rows in every smoke match).

## How the harness gets the creation tick

Frame tick convention (measured): a body made while the battle tick reads X is first visible in the frame labelled X+1.
So, at a body's first sighting (frame T1, previous frame T0), its creation frame tick C (the tick `fights.py` puts in
(T0, T1]; its play tick is C - 1 in the harness's own convention) is:

1. deploying at first sight (`deploy_remaining_raw > 0`) and `deploy_tick_raw > 0`: **C = deploy_tick_raw + 1**;
2. else `card_tick_raw >= 0` (a card-made object first seen without a deploy: a digger's tunnel object, a staggered
   recruit / hog first seen mid-stagger): **C = card_tick_raw + 1**;
3. else, not in behaviour 11 (a never-deploying spawned child: Witch skeletons...): **C = T1 - active_ms_raw / 50**
   (its active time is 0 on its creation frame);
4. else (in its stagger with no card tick: none seen yet): keep the frame-gap window.

`validate_p3.py` V11 implements this as `creation_tick()` and checks it; `countdown_creation()` is the countdown-only
rule for captures that predate the stamps (first - (DeployTime - remaining) / 50 + 1; right for card troops only).

## Validation (live ranked matches beside the live run, game build 160402012, 0 read errors, 0 null rows)

Final probe, 3 consecutive matches (`validate_p3.py` V11 PASS on each):

| match | new bodies timed | creation tick in (T0, T1] | via deploy / card / active | card countdown = DeployTime from C | -50/tick | zero inside gap | behaviour 4 <=> remaining > 0 | stamp changes (all a new deploy, in gap) |
|---|---|---|---|---|---|---|---|---|
| 1 | 92 | 92/92 | 66 / 26 / 0 | 56/56 | 866/866 | 92/92 | 24,299/24,299 | 27/27 |
| 2 | 203 | 200/203 | 171 / 32 / 0 | 142/145 | 1,929/1,932 | 197/197 | 36,130/36,130 | 32/32 |
| 3 | 108 | 108/108 | 61 / 15 / 32 | 45/45 (+8 longer starts) | 691/693 | 71/71 | 20,044/20,044 | 15/15 |
| **all** | **403** | **400/403 = 99.3%** | 298 / 73 / 32 | 243/246 | 3,486/3,491 | 360/360 | 80,473/80,473 | 74/74 |

The 3 misses (match 2) are three Skeletons first seen on a 1-tick frame gap whose stamp is one tick after the frame
label: that frame's state was one tick ahead of its label (the sampling artefact below), not a field error. The same
three are the countdown misses. Supplementary: two earlier matches with the same stamps but without `active_ms_raw`
(116/117, 98/98; the one miss is an Evo Mega Knight, see below), and three countdown-only matches (no stamps): the
countdown-only rule placed only 78-87% inside the gap, because of the credit-0 bodies and the spawner-given starts.

## Spawned children (reported separately)

| child | timer at first sight | stamps | value |
|---|---|---|---|
| Hero IW floating cube, Hero IW IceCube | yes (deploying) | deploy stamp yes, card tick -1 | start 1000 ms, first step one tick after creation (as its hero) |
| Barbarian (from a spawner), BarbLog hero barbarian, Goblin Brawler, Voodoo Hog | yes | deploy stamp yes, card tick -1 | spawner-given start: 1000 / 1000 / 500 / 200 ms if credit 0 (each +50 if credit 1; the stamp gives C either way) |
| Goblin Barrel goblins | yes | deploy stamp + card tick (they are card-made) | start 1100-1150 ms, longer than their own DeployTime (the barrel's) |
| Goblin Drill goblins (periodic) | yes | deploy stamp yes, card tick -1 (research pass, 6/6 stamp in the gap) | start 500 ms (first-sight 500 / 450) |
| Witch / Evo Witch skeletons (plain, interval, healing), Goblin Drill no-timer goblins | **no** (0) | none (deploy stamp 0, card tick -1) | active_ms_raw 0 or 50 at first sight -> C = T1 - active / 50: 32/32 inside the gap (the +1-tick alternative: 12/32); 4/4 Drill goblins in the research pass |
| staggered card spawns (Royal Recruits, Royal Hogs, Bats, Mini Zap Machine) | 0 while in behaviour 11 | card tick yes; deploy stamp set when their deploy starts (the only stamp changes seen) | C = card tick + 1 |
| towers (incl. tower troops) | no | deploy stamp 0, card tick -1 | present from the first frame; not new bodies |

Evo Mega Knight: its stamp puts creation ~4 ticks before the reader's body list first shows it (twice); it is not in
the list during its first ticks (its spawn jump, plausibly), so for it the stamp is better than any first sighting.

## Parity facts this surfaced

- **First countdown step.** Card-played troops and buildings take their first -50 on the creation tick (countdown at
  first sight = DeployTime - 50 x (T1 - C + 1); "credit 1"). The Hero Ice Wizard, its floating cube, its IceCube, the
  Goblin Drill building and some staggered bodies (Royal Recruits, Royal Hogs, Mini Zap Machine) take it one tick later
  ("credit 0"): their deploy ends DeployTime / 50 + 1 ticks after creation, one tick later than a Knight's. Worth checking
  against the SIM: a countdown-only reconstruction is off by one for exactly these bodies, the stamps are not.
- **Never-deploying children are not updated on their creation tick** either (active time 0 on the creation frame), the
  same pattern as the Hero IW cube: bodies made by other objects start one tick "late".
- **Spawner-given deploy times** exist (table above); a SIM that gives such children their own DeployTime will deploy
  them at the wrong time.
- **Countdown law** -50 a tick held on every unscaled interval; the apparent exceptions (5 of 3,491) are pairs of
  adjacent samples whose two steps sum exactly: one frame's state one tick ahead of its label. A sampling artefact
  (well under 1% of frames, mostly on 1-tick gaps; also seen in the 10-16 attack data). The stamps are game truth; on
  such a frame the label, not the stamp, is off.

## Cost

One extra read per listed body (the four values come from one read) plus two one-time definition reads. Same matches,
new probe vs the live run's own 10-16 probe running beside it: read time per frame median +0 to +28 us (0-6%) over 7
matches (final probe: +1, +11, +10 us), p95 -211 to +140 us (noise of two concurrent readers); 0 read errors in every
match.

## Open

- Staggered bodies first seen in behaviour 11 with `card_tick_raw = -1` (none seen): `active_ms_raw` is their stagger
  time left, which gives the deploy start, not the creation tick.
- The card-tick field's code path was not traced (empirical: it equals the deploy stamp for every card-played troop).
- Whether the SIM reproduces the one-tick-later first step of Hero IW / cube / children (a fights.py / SIM question).
