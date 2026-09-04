
### 5cr.8 (22:2x-23:2x) FOUND (a): the live gate collapse is ONE input slot -- threat slot 31 (opp-memory slot 5) carries the opponent-elixir ESTIMATE live but OUR elixir in the sim; the policy reads it as "I have no elixir" and waits. Plus: live sessions can start with FROZEN reads (region lock)
Live observation sessions tonight, all epsilon 0 / learning off / init `policy_gatec2_20260903_best.pt` (m10k),
2 ladder matches each, obs dumped per decision (`scratchpad/gauntlet/L45/live_obs_session.py`; npz under
`data/bench/live_obs/`), and the PPO gate recomputed OFFLINE on every recorded live state with the same net + rule the
sim twin used (`analyze_live_obs.py`, `pplay_by_state.py`, `live_gate_ablate.py`; outputs `analyze_s2.txt`,
`pplay_by_state_s2.txt`, `live_gate_ablate_s2.txt`, all in `scratchpad/gauntlet/L45/`).

| session | rule | slot 31 | decisions | plays | outcome | note |
|---|---|---|---|---|---|---|
| s1 22:20 | legacy | opp est | 7 (m1) | 0 | -- | **BLIND, my error**: launched with `../.venv` (no ultralytics -> no detector). Killed 22:28. Two ladder losses for nothing. |
| s1b 22:29 | legacy 0.5 | opp est | 178 + 128 | **0** | L, L | reads FROZEN (5cr.8.3) -- not a policy measurement |
| s2 22:33 | tau 0.25 | opp est | 230 + 193 | **14** (3.3%) | L, L | plays only in the first ~20 s of each match, then idles at 10 elixir |
| s3 22:49 | tau 0.25 | **own elixir** | 0 (stuck UNKNOWN) | 0 | -- | reads FROZEN again from the first frame; killed 22:52 (5cr.8.3) |

**1. s2 is the measurement of the gap (a).** Same net, same rule (tau 0.25), recomputed offline on the recorded states
(offline rule reproduces the live decisions: 13 vs 14 plays; all 14 executed plays = the PPO's greedy card, 0
wheel/search overrides; 8/14 cells rewritten by the aim assists):

```
                       sim (gatec2_m10k greedy, 16 matches)     live s2 (425 decisions)
p(play) mean                    0.137                                 0.150
play share                      10.8%                                  3.3%
elixir at decision (mean)        3.4                                   8.75   <- live sits FULL 69% of the time
p(play)>0.25 | elixir in [7,9)  31.4%  (n=140)                          8.8%  (n=57)
p(play)>0.25 | elixir >= 9      80%    (n=5)                            1.7%  (n=295)
```
Live match time-course: p(play) 0.18 in the first 30 s (plays 3 / 5), 0.15 at 30-90 s, 0.125-0.138 after 90 s with
elixir pinned at 10.0 and ZERO plays (`threat_miss_idle` -28.8 / -42.0 per match). In sim p(play) does not fall with
time (0.177 / 0.178 / 0.188). So the owner's "plays cards as they come up, then ignores the state" is exactly this:
one burst, then the gate never opens again.

**2. Ablation (a): it is the threat vector, and inside it ONE slot.** p(play)>0.25 share on the live states at >= 9
elixir, one input group replaced at a time (offline, same net):
```
live as recorded ............................ 1.7%
obs image := sim / zero ..................... 1.7% / 2.0%      next := sim / zero  3.1% / 1.7%    hand := sim 4.7%
threat base16 (0-15) zeroed ................. 4.7%             identity 16-25 := sim 2.0%         interactions 34-45 := sim 2.4%
threat slots 16+ zeroed ..................... 93.9%            threat all zero 95.6%              threat := random sim threat 94.2%
opp-memory 26-33 := sim ..................... 89.8%            tower 46-51 zeroed 60.7% (tower := sim 5.1%: tower is not it)
slot 31 := OWN elixir/10 (sim semantics) .... 96.9%            slot 31 := sim value 89.2%         slot 30 := sim (control) 1.7%
REVERSE: sim states (elixir>=7) with live threat 33.1% -> 2.1%; with live slot 31 ONLY 33.1% -> 2.1%; with live obs 53%; live next 31%.
```
Slot 31 = `OPP_MEMORY` slot 5. Sim: `sim/env.py:643 mem[5] = eng.elixir[0]/10` = OUR elixir (5cp.4 found the code
seam, effect then (b) untested). Live `env.py` (train-rl) and `play.py:447`: the opponent-elixir ESTIMATE
(`opponent_elixir.py`), which in s2 averaged **0.035** (nonzero on 15% of decisions) -- the policy, trained on
"slot 31 = my elixir", reads ~0 and waits. Zeroing the slot does NOT fix it (4.7%): the gate needs the slot HIGH,
which is why the 5cr.7 base-block perturbation (gate agreement 0.93 under remap) missed it -- that probe never
touched 31. The obs image is NOT the gap (sim obs on live states: no change; live obs on sim states: 33 -> 53%, i.e.
the live board render if anything makes the gate MORE willing).

**3. Live reads can be FROZEN for a whole session (a; cause narrowed, see below).** s1b, 306 decisions: `hand_vec`
all-zero on 303/306, `next_vec` all-zero on 306, elixir read = 9.19 (frac) / 8 (conservative) on 299/306, while the
perception thread's detector ran (passes 1100; replay `match_20260903_222947.mp4` shows the game) and the nav state
machine still saw MATCH_END / Play Again. s3: "stuck on UNKNOWN -> dismiss" every 25 s from its first frame, zero
decisions. Same `Vision.recognize_hand` on s1b's replay frames: 3-4/4 slots on 94% of frames; on a fresh
`WindowCapture` grab during s2's match: hand [0,3,-1,5], next 9, elixir 10, IN_MATCH. So the code reads fine; the
RUNNING env's main-loop frame was not the game. Mechanism (`capture.py`): the main loop and the perception thread each
own a `WindowCapture`; each locks its region ONCE by a content scan (`_render_area`, aspect 0.50-0.68) and never
refreshes after a successful lock. Both frozen sessions (s1b, s3) started on a MATCH_END screen that had sat there
for minutes; the one that read normally (s2) started 20 s after the previous session's Play Again, mid-transition.
`region_probe.py` (fresh capture every 4 s across a match end) is the reproduction -- result in 5cr.8.5. Also
measured: a FULL bar reads 9.19 (frac) in s1b -> `play.offense_leak_guard` 9.5 cannot fire from that read.

**4. Fix shipped, config-driven, default = legacy:** `env.opp_mem_slot5: opp_estimate | own_elixir`
(`config/config.yaml`, default `opp_estimate`; `env.py` __init__ validates + prints `[env] opp-memory slot 5 source`;
the estimate is still computed for the trade potential either way). `own_elixir` writes `elixir_vec[0]` into the slot
(= what the sim wrote during training). `play.py:447` has the same seam and is NOT changed (live-play path; one
change per experiment). Session config `data/bench/live_obs_tau_slot.yaml` = tau yaml + `opp_mem_slot5: own_elixir`.
The proper long-term fix is the SIM side (`mem[5] = eng.elixir[1]/10`, 5cp.4) so the policy is trained on the
opponent's elixir -- that needs a retrain and is parked behind c2r (sim untouched while it runs).

**5. Region-lock reproduction + s3 rerun:**
**5. Region-lock reproduced (a), TWO more live defects found and fixed, and the s3 rerun (s3c) PLAYS.**
`region_probe.py` (fresh `WindowCapture` every 4 s, 22:52-22:59 and 23:02-23:04): in-match lock (734,18,657x**1198**)
or (694,0,657x**1216**) reads hand/next/elixir correctly; the moment the MATCH_END screen shows the fresh lock shrinks
1198 -> 1172 -> 1163 -> 1161 -> **1160** (`_render_area` step 3 trims the end screen's dark bottom band as a
"black bar") and stays 1160 for as long as the screen sits there. Offline on the same in-match frame
(`lock_height_test.py`): lock 1198 -> hand [0,4,8,6] next 3 elixir 10/10.0; lock 1216 -> identical; **lock 1160 ->
hand [-1,1,-1,-1] next -1 elixir 9 / 9.22** = the s1b signature exactly (hand empty, next empty, elixir 9.19). The
lock never refreshes after success, so a session launched on a stale MATCH_END screen is blind for its whole life.
s3b (23:00, first fix attempt) still froze: locked 1178 (= 1216 - 38) and the relock hook never fired because
`reset()` is called ONCE per match and loops internally until IN_MATCH -- a hook BEFORE reset only ever sees the end
screen. Fix that works (launcher only, `live_obs_session.py`): wrap `capture.grab` for the duration of `reset()`; the
first frame that reads IN_MATCH re-scans BOTH captures (main + the perception thread's, reached through its
`cap_factory` test hook) and re-grabs from the new region. s3c 23:05: `relock at match start: 1160 -> 1198` on both
captures, first decision hand [0,8,3,1] elixir 7; match 2 relock 1198 -> 1198 (no-op).
Second defect (a): the game window was MAXIMIZED at (654,0) at 22:57 and un-maximized at (614,0) after the 23:00
launch. `ShowWindow(hwnd, SW_RESTORE)` -- `controller.py:41`, comment "no-op if not minimised" -- is (c)
contradicted: Win32 restores a MAXIMIZED window to its pre-maximize size/position. That is the owner's "your clicks
moved the window off centre". Fixed in `controller.py` (IsIconic guard, restore only when minimised) and in the
launcher; window re-maximized via SW_MAXIMIZE (= the title-bar button, owner rule) before s3c; it stayed at
(654,0) maximized through s3c.
Third (a, not fixed): after `--matches N` is reached the nav has ALREADY clicked Play Again, so a ladder match runs
with nobody at the wheel (23:03:22, hand [4,1,3,8] elixir ramping, no session). Cost: one thrown ladder match per
session end. Fix belongs in train_rl's stop path (stop BEFORE re-queueing).

**s3c (a): tau 0.25 + slot 31 = own elixir + working reads, 2 ladder matches, 463 decisions, 58 plays (12.5%).**
```
                                     sim     s2 (opp-est slot)    s3c (own-elixir slot)
play share                          10.8%         3.3%                 12.5%
elixir at decision (mean)            3.4          8.75                 5.18
decisions at >= 9.5 elixir           --           69%                  0%
p(play)>0.25 | elixir [4,7)         16.2%         --                   7.4%  (n=190)
p(play)>0.25 | elixir [7,9)         31.4%         8.8%                26.1%  (n=138)
p(play)>0.25 | elixir >= 9          80% (n=5)     1.7% (n=295)        52.1%  (n=71)
p(play) by time  0-30 / 30-90 / 90+  .18/.18/.19  .18/.15/.13        m1 .18/.16/.22  m2 .17/.16/.23
plays by time    (per match)         --           burst then 0        m1 5/7/9   m2 5/9/23
```
Executed cards: log 11, knight 10, ice_wizard 9, skeletons 9, tesla 7, knight_evo 4, rocket 3, tornado 2, x_bow 2,
tesla_evo 1; 56/58 = PPO greedy card, 0 overrides, 26/58 cells rewritten by the aim assists; ghost plays 1/21 and
0/37. Reward terms m1: elixir_trade +2.5 (34 fires, +20/-14), threat_response +4, threat_miss_idle -55.8 (93),
leak -3.7; m2: elixir_trade -1.0 (72 fires), wincon_exec +3, threat_miss_idle -22.2 (37). Outcomes L 0-3 (2.7 min),
L 0-1 (3.1 min, went the distance). Live search: asked 200 / ran 166 / changed 123 / UNAFFORDABLE rejected ~108
per 200 -- unchanged defect (5cr.8.6). So: the gate now opens through the whole match, p(play) rises late as in
the sim, elixir is spent (mean 5.2 vs 8.75). The policy is still bad (2 losses, the idle penalty still dominates),
but it is now the SAME bad policy as in the sim rather than a frozen one.

**Next seam (a, measured, not fixed): live hand recognition reads 2.9 of 4 slots.** s3c: all 4 slots recognized on
24% of decisions (111/463), 3 on 49%, <= 2 on 27%; s2: exactly 3 slots on 94%. x_bow in hand 5% (s3c) / 22% (s2)
vs 56% in the sim; rocket 0.89-0.99 vs 0.96, tesla 0.21-0.29 vs 0.20, knight 0.01-0.07 vs 0.11, evos ~0. The sim
always sees 4/4. The missing card is the WIN CONDITION most of the time -> the policy cannot play the X-Bow it
cannot see (2 x_bow plays in 463 decisions). Which template fails and why is next loop's first measurement (a
per-slot audit against the live frame -- the overlay replay is NOT usable for this: its 492x912 canvas does not match
the relocked 1198 region, 3-4 misses per frame on a resize).

**6. Live search (a, from train-rl's own counters, s2):** asked 400, ran 368, **changed 342**, waited 26,
**UNAFFORDABLE picks rejected 337**, 2.9 rollouts/decision, `reads` 0.14-0.16 s of a 0.63-0.68 s loop. I.e. the
search proposes a different action on 93% of decisions and 92% of THOSE are thrown away as unaffordable -- with the
agent at 8.75 elixir on average. Something in the search's affordability (its rollout elixir, or the reject check)
is wrong live; not chased this loop (one change per experiment). It produced no executed play in s2.

**7. c2r (same instrument as gatec2's own log):** EVAL@2000 (absolute m12k) ladder 19% / fair 13% vs gatec2's series
2/12/23/27/25% (ladder) -- inside the band, not a discriminator. Counter 2875 at 22:50, 0.6 ep/s, drills 46% last-300;
m5k gate ~23:50. No claim of improvement past gatec2_m10k yet.

**8. Does NOT establish:** that own-elixir-in-slot-31 makes the policy play WELL live (it opens the gate; the
card/cell heads and the aim assists decide the rest); anything about the live search beyond its own counters; the
retrain with opponent elixir in the slot (parked).

**9. Traps:** `../.venv` has no ultralytics -> the live env runs BLIND with no error beyond one "could not load
detector" line; ALWAYS launch live sessions with `icebow/.venv/Scripts/python.exe`. `pkill` does not exist in this
Git Bash -- use PowerShell `Stop-Process`; a chain script keeps going when you think you killed it (check
`rounds2.progress`). Owner's window rule (this session): if the game window drifts off-centre, press the
maximize/"full screen" button on the CR title bar (icon becomes two overlapping rectangles) -- between sessions, not
mid-match, because each `WindowCapture` locks its region once.
