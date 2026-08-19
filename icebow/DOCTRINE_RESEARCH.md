# Icebow doctrine research — 2026-08-19

**Deck:** X-Bow 6, Evo Tesla 4, Ice Wizard 3, Evo Knight 3, Skeletons 1, The Log 2, Rocket 6,
Tornado 3.

Mined 2026-08-18/19 for the two things the user named: **Rocket** ("a recurring issue for the
icebow model is its misuse of rocket, or lack of use at all") and **defensive play**. 270 facts
from 7 researchers + **246 observations from 8 watched videos** (yt-dlp/whisper/contact-sheet
pipeline), then **adversarially verified**: 20 verdicts, of which **2 REJECT, 12 MISREAD-RISK,
4 CONTESTED, 2 STALE**. Recency window Nov 2025+; **Hunter CR** (pro X-Bow specialist) is the
preferred authority and supplied 7 of the 8 videos.

**Every verifier correction below has been applied.** Where a claim did not survive, it is in §6
with both readings and is *not* compiled. This file is the research record; the living doctrine is
`DOCTRINE.md`, the compiled rules are `src/clashrl/sim/doctrine.py`.

| key | source |
|---|---|
| H-Bowing | Hunter CR, "It's IceBowing Time" — https://www.youtube.com/watch?v=lCnBG9dTLv8 (2026-08-01) |
| H-World | Hunter CR, "I'm #1 In the WORLD With My Main Deck" |
| H-Rage | Hunter CR, "I Made Everyone Rage Quit (IceBow)" |
| H-Coach | Hunter CR coaching video (he corrects a student's cast order) |
| H-Match | Hunter CR, "The Full IceBow Matchup Guide (2026)" |
| Sweep | "#1 Icebow Guide in Clash Royale ft Hunter CR" (Sweep - Clash Royale) |
| F-Rocket / F-King | https://clashroyale.fandom.com/wiki/Rocket , .../King%27s_Tower |
| F-Deck | Fandom X-Bow/Icebow deck pages |
| SC-84 | Supercell Season 84 balance (2026-06-01) |

Confidence: **[H]** 2+ independent sources or seen on video · **[M]** one good source · **[L]**
directional, needs engine verification. Tags: **NEW** / **CONFIRMS** / **CORRECTS** relative to
the existing `DOCTRINE.md` + `doctrine.py`.

---

## 0. The measured problem this is meant to fix

`policy-stats`, 40 greedy matches on `policy_sim_ppo_best.pt`, 2026-08-19:

| | |
|---|---|
| **Rocket** | **2 plays of 1288 (0.2%)** — vs The Log 18.9%, Ice Wizard 18.6% |
| `xbow_into_push` | **−276.0 over 69 fires, never once positive** (largest term by 4×) |
| `spell_waste` | −23.7 over 79 fires, never positive |
| placement spread | **25 of 432 cells**, top cell 37.6% |
| win rate | 32.5% |

**The key structural fact:** `sim/doctrine.py` is ROLLOUT-ONLY — greedy eval never reads it. The
existing rocket card-prior has been nominating Rocket in rollouts for 14,300+ matches and the
policy still did not learn to value it. So **placement priors alone cannot fix rocket**; the
payoff is too rare and too precise for the value function to find. The research below is therefore
aimed at the *decision gates* (when a rocket is correct at all), which is what the reward and the
advisor can act on — not just at where the blast lands.

Hunter's own framing makes the stakes concrete: **"I'm either getting my damage with this deck
with the rocket or the X-Bow. There's two things."** [H-Bowing 05:51] **[H]** A deck with two
damage sources that never fires one of them is playing with one.

And the single most on-point observation in the whole corpus — Hunter calling his **own** worst
play of a match a rocket he *didn't* cast:

> *"I have a horrible cycle for this prince, like literally nothing. I probably should have just
> straight up rocketed that, because now I'm going to have to overspend… I had to drop nine elixir
> on that prince. If I would have just rocketed…"* [H-Bowing 01:23] **[H]**

That is the bot's failure mode, named as an error by a pro: **chaining 9 elixir of cards when 6
elixir of Rocket was the cheaper answer.**

---

## 1. ROCKET DECISION PROCEDURE

Ordered; first match fires. All damage numbers are **post-Season-84 (2026-06-01)**.

### 1.0 Numbers (verifier-corrected)
* Crown-tower damage **342** for budgeting, **341** for lethal tests — Supercell publishes the
  absolute, Fandom the percentage, and crown damage is applied at base level then scaled, so
  `1484 × 0.23 = 341.3` legitimately rounds to 342 at some levels. Never claim a kill on 342. **[H]**
* Troop damage **1484**. Rocket+Log **377**, two Rockets **684**, two Rockets+Log **719**. **[H]**
* Chip efficiency **342/6 = 57 per elixir** vs Fireball **172/4 = 43** — the Rocket-cycle
  advantage over a Fireball-cycle deck widened from ~1.19 to ~1.33 after Season 84. **CORRECTS**
  the pool's claim that Rocket took the smallest big-spell cut (false — Lightning −7% was smaller;
  Rocket −8% tied Earthquake/Vines). The ratio survives; the superlative does not. **[H]**
* **Log crown chip: use 35 (Supercell's figure). Do NOT derive it from 13% × 266.** The percentage
  and the absolute disagree at *both* endpoints (pre-nerf 15% × 266 = 39.9 vs a quoted 41), so the
  percentage is applied at base level and scaled. **Measure in-game before encoding.** **[M]**
* ⚠ **Currency caveat:** the pool's "nothing changed after June" rests on a *count* ("11 cards:
  6 nerfs, 4 buffs") that names no cards, and the August page 403'd. Treat 342/35 as
  *no-evidence-of-change*, **not** verified-current; re-check each season rollover.

### 1.1 CAST triggers

* **R1 — CYCLE STATE, not elixir math.** *"Rocket it when your normal answers (Knight, Tesla) are
  not in hand."* The trigger for rocketing a support troop is that the cheap answer is out of
  rotation. **[H]** **NEW** — and this is the single most important rule for the bot, because it
  is a *hand* condition the policy can observe, not a value judgement it has failed to learn.
* **R2 — FORCED (no alternative exists).** A Healer landing behind a push; enemy ranged **air**
  support that would delete the Tesla. **Ordering rule: rocket the air units FIRST, then place the
  Tesla** — placing the Tesla first feeds it to them; Hunter accepts a deliberate elixir leak to
  preserve that order. **[H]** **NEW**
* **R3 — THE OVERSPEND TEST (the §0 quote, generalised).** If the cheapest sufficient defense in
  the current hand costs **≥ 7–8 elixir of chained cards**, Rocket (6) is the cheaper answer. Fire
  it immediately rather than chaining. **[H]** **NEW**
* **R4 — BAD-PLACEMENT PUNISH.** A 5+ elixir unit committed at the *back*. **Lethality check
  required: HP < 1484, no shield, not being healed.** Trade is **−1 for a 5-cost, 0 (neutral) for
  a 6-cost**, before counting ~342 of tower clip. **CORRECTS** the pool, which claimed −1 for
  Sparky too (Sparky costs 6). **[H]**
  * **Royal Giant is an explicit exception:** the Rocket does **not** kill him. The payoff is
    tower clip plus crippling a one-win-condition deck's tempo. Do not file it as removal. **[H]**
* **R5 — ELIXIR COLLECTOR.** A standing target in **regulation** — Hunter rocketed a pump three
  times in one game and never let one tick out. **Two gates:** (a) **stop rocketing pumps once
  overtime starts** (the tower is worth more than the tempo); (b) **skip it if the board threat
  means you cannot survive the follow-up** — he declined a pump rocket at 7 elixir for exactly
  this reason. **[H]** **CONFIRMS+CORRECTS** the existing `#50` fresh-pump rule, which has no
  overtime or board-threat gate.
* **R6 — ROCKET + TORNADO.** **Cast the ROCKET FIRST, then Tornado onto the blast point.**
  **CONTESTED → RESOLVED by mechanics and by Hunter correcting a student verbatim** (*"I meant for
  you to play the rocket first and then tornado everything"*): Tornado lasts ~1.05 s while Rocket
  has a long cast + travel, so a Tornado cast first releases the clump before the blast lands.
  **[H]** **CORRECTS** — `doctrine.py`'s existing nado→rocket rule aims at the *live* vortex
  centre, i.e. it fires *after* the pull; the cast order must be inverted.
  * **Clump estimate, corrected:** count only units already within **~2–3 tiles** of the intended
    blast centre as guaranteed catches; outer-radius units are bonus. **Exclude Giant, Golem and a
    charging Prince from the pull estimate entirely** — a 1.05 s pull cannot drag them. The pool's
    "worth it at ≥9 elixir of clump" silently assumed Tornado's 5.5-tile radius all lands inside
    Rocket's 2-tile blast; it does not. **[H]**
* **R7 — TOWER CHIP**, on a **Princess tower** (never the King — see §6.1). Licensed by any of:
  * **defense is pre-paid** — a full-health defensive X-Bow is already down; *exception:* not if
    the opponent holds a heavy push card (Evo Battle Ram), because that elixir is spoken for. **[H]**
  * **their building-removal spell has been forced out** onto the X-Bow (vs Hog EQ: the moment
    Earthquake is spent, the tower rocket is on). **[H]** **NEW**
  * **the clock makes a counter-push irrelevant** — ~last 20–40 s, and overtime. **[H]**
  * **rocket-mirror bait:** casting at their tower with an empty board is deliberate — it buys
    *their* rocket onto your tower, after which your X-Bow goes unanswered. Cast near max elixir
    so the follow-up X-Bow is still affordable. **[H]** **NEW**
  * **Aim: the nearest corner / shortest travel** of the target tower. **[H]** (This is the only
    part of the stale spell-cycle table that survives — every number in it was wrong; see §6.)
* **R8 — CLOSING / "ROCKET RANGE".** Track the tower-HP threshold at which *n* rockets finish it
  and count rockets against the clock rather than casting on availability. Time to land two
  rockets is **a function, not a constant**: `(elixir_needed − banked) × sec_per_elixir(rate) +
  travel`. **CORRECTS** the pool's hard-coded "19–19.5 s", which is wrong in both directions
  depending on elixir phase. **[H]**

### 1.2 HOLD / NEVER

* **N1** A cheaper unit already has a lethal connection → withhold, even at the cost of a slower
  finish. **[H]**
* **N2** The board threat means you cannot defend at post-rocket elixir. **[H]**
* **N3** **vs Giant Skeleton: the building is the answer, not the spell.** Hunter's measured error
  of one video — Rocket+Log instead of Tesla, lost the tower, named Tesla-on-zero-elixir as the
  correct play. **[H]** **NEW**
* **N4** **Never the enemy King Tower.** **REJECTED** from the pool: it awards no crown, and it
  *activates* their King, which then defends against everything you do afterwards. **[H]**
* **N5** **Lone tower rockets are not gated on the elixir clock** — gate on *can I cycle back to a
  Rocket before their punish lands* **AND** *can I defend at post-rocket elixir*. Double elixir
  merely makes both easier. **CORRECTS** the pool's "solo rockets belong in double elixir". **[H]**
* **N6** **Sparky: not "on sight."** The quote is *"rocket the sparkies anytime he puts value
  **with** them"* — i.e. gated on the opponent adding accompanying investment. A **lone** Sparky
  has a cheaper answer: **Tornado it into the Knight** so the tower helps. **[H]** **CORRECTS**
* **N7** Prediction rockets: **only the low-variance class** — static, repeated commitments (pump
  re-placement, a defensive spot the opponent has used 2+ times, a building spot). **Drop
  ability/dash landing zones** unless the target's HP is under 1484 or a tower clip pays for the
  miss. **[M]** **CORRECTS**

---

## 2. DEFENSIVE PLAYS

### 2.1 The X-Bow is the asset being defended
* **Knight goes in FRONT of the X-Bow (river side), not beside it** — he self-corrects mid-sentence
  to make the bow the reason. **[H]** **CONFIRMS** the existing `_bow_defence_cells` knight rule.
* **Kill a Bowler EARLY** (Knight + Log, timed so it dies before its knockback lands) — the success
  criterion is *the bow keeps its connection*. **[H]** **NEW**
* **Once the X-Bow is spent defensively, counter-pushing is off for that rotation.** The
  counter-push window is explicitly *"they drop a Giant Skeleton in the back"* **AND** *"X-Bow
  still in hand"*. **[H]** **NEW**
* **Holding X-Bow at exactly 6 vs Mega Knight + Prince is a trap** — that elixir is defence. **[H]**
* **A defensive X-Bow in the MIDDLE is the anchor vs dual-lane pressure** and the standing answer
  vs Graveyard (he corrects himself to stress it is repeated, not a one-off). **[H]**

### 2.2 Evo Tesla
* **One tile HIGHER (away from the King) when a King activation is live** — his own Tesla sniped
  the unit that would have activated his King Tower and he called it the mistake. **[H]** **NEW**
* **Tesla placed LOW is a deliberate Fireball bait**, not a compromise — dropping it reliably pulls
  the Fireball, which keeps the Ice Wizard alive. **[H]** **NEW**
* **Pre-place and keep one on the map** vs 2.6-style cycle decks (standing posture, not reactive).
  **[H]** — note this is in tension with the lifetime-decay logic; it is matchup-scoped.
* **Stack Teslas vs Lavaloon** (a line up the map, replacing each as it dies) — the cost is
  Lightning value, so do not clump them. **[H]** **NEW**
* A **misplaced** building still earns its cost — leave it, it catches whatever crosses next,
  rather than spending more elixir to correct. **[H]**
* **Do not reflexively drop buildings at the river.** **[M]**

### 2.3 Tornado
* **Tornado-BACK is the standard air-swarm answer** — pull minions backward so your own tower
  re-targets them. **[H]** **NEW**
* **Vs Giant + Graveyard: tornado the GIANT back** so the tower stops eating the tank and switches
  to the graveyard skeletons. **[H]** **NEW**
* **Tornado→King for Hog Riders, but THROTTLED** — *do not* pull every hog into the King; repeated
  king-pulls are how you get three-crowned. **[H]** **NEW — an explicit anti-rule the sim's
  king-activation logic does not have.**
* Tornado a Wizard purely to break its tower connection, accepting that the pull concedes splash
  onto your own tower. **[M]**
* Tornado is the cheap answer that **saves the Rocket** on a lone Sparky (drag it into the Knight).
  **[H]**

### 2.4 Layering and order
* **Order matters and is stated explicitly:** ground tank down **first**, *then* Ice Wizard on top
  of the barrel/swarm — not simultaneously. **[M]**
* **vs Evo Musketeer: Log FIRST, then Skeletons**, sized to eat the opening burst. **[H]**
* **vs Giant + Mega Minion: low Tesla → late Log → Knight**, where the Knight exists to keep the
  Mega Minion **off the Tesla** (protecting the building, not the tower). **[H]**
* **Zero-damage Graveyard defense, in order:** **pre-fire Skeletons before the Graveyard lands** →
  well-timed Log to clip the skeleton spawning inside → defensive X-Bow + tower clean the rest.
  **[H]** **NEW**
* **Skeletons kite air support** (e.g. Mega Minion) into the **opposite lane** while the Knight
  handles the ground tank. **[H]**
* **Double Log for Zappies**, and it becomes *mandatory* once a Mother Witch joins the push. **[H]**
* **Do not pre-emptively Log** a tower/troop when a Battle Ram may be in their cycle — Log is the
  Battle Ram answer. **[H]** **NEW**
* **Spend the renewable card on the repeatable threat:** self-graded error — he Logged the Wall
  Breakers when Ice Wizard was correct, leaving no Log for the next one. **[M]**
* **Deliberately concede chip** when the opponent over-committed early: he declined a Log at 8
  elixir on a Skeleton-Barrel package and let the Ice Wizard grind it. **[M]** **CONFIRMS** the
  existing fundamentals tier (triage / minimise-don't-prevent).
* **Stall-to-timeout stack when behind on cards:** Evo Tesla to stun/hold → Tornado → Skeletons +
  Log together, sequenced around when the Log returns to cycle. **[M]**
* **Balloon should never connect** — the deck stacks four independent answers (Ice Wizard,
  Tornado, Tesla, Rocket). Rocket a Balloon in **any** push (the "inside Lavaloon" framing was not
  supported by the quote — see §6). **[H]**

---

## 3. X-BOW / MATCHUP NOTES

* **THE CENTRAL LESSON, and it is a Rocket rule as much as a bow rule: never place a mid-map or
  defensive X-Bow against a deck holding Rocket.** The chain is: they rocket the bow (you lose 6
  for nothing) → they rocket your tower → you rocket back → the resulting deficit means you never
  get a bow lock all game. **[H]** **NEW — and this is the doctrine counterpart to the measured
  `xbow_into_push` = −276 term.**
* **vs 2.6 Hog Cycle:** default to **rocket-cycling for the majority of the game**; go offensive
  X-Bow when it forces their Fireball onto defence. **CORRECTS** — the pool's extra gates ("with a
  lead + elixir advantage", "desperate ~1000 down") appear nowhere in the quote; the ~1000 figure
  was fabricated. Use the deficit ceiling below instead. **[H]**
* **Deficit ceiling (X-Bow mirror / pressure decks only):** never fall more than **~650–690**
  behind — i.e. **about two rockets plus a spare**. **CORRECTS** the spoken "700–800", which was
  said 2026-01-30 pre-nerf and is denominated in rocket-cycles that now claw back ~8% less. **[M]**
* **King Tower activation is the opening objective** in Royal-Hogs-type matchups — a permanent,
  game-long defensive asset, not a one-off. **[H]**
* An opponent **stacking Zappies into one lane is a gift** — it converts a split threat into one
  full-value Log. **[M]**

---

## 4. HUNTER CR — where he diverges from generic guides

1. **Rocket is a defensive/tempo tool, not just a value spell.** He rockets Royal Hogs in his own
   half when the alternative (a forward Tesla) would be shredded by their Cannon. The gate he
   states is not *"is rocket worth 4 hogs"* but **"what does the cheaper answer cost me in
   building value"**. **[H]**
2. **The trigger is cycle state.** Generic guides gate rocket on elixir value; Hunter gates it on
   whether Knight/Tesla are in hand (§1.1 R1).
3. **Rockets are a closing resource** — the last ~20 s and overtime are when you start throwing
   them, and he counts them against the clock.
4. **Bait rockets are real** in the mirror (§1.1 R7).
5. **He names his own rocket errors both ways** — not casting (the Prince), and casting when a
   building was correct (Giant Skeleton). Both directions are doctrine.
6. **Patience on the cast:** a double-dip rocket (pump + Boss Bandit) missed because it was thrown
   *a beat early*; the fix he names is waiting a fraction of a second for the target to settle —
   and the redemption cast was timed **to the opponent's ability animation**, not to the board. **[M]**

---

## 5. WHAT TO COMPILE FIRST (ranked by expected effect on the measured failures)

1. **R1 cycle-state trigger** + **R3 overspend test** — these convert "rocket is valuable" into
   *hand conditions the policy can observe*, which is what the 0.2% number says is missing.
2. **N3/N4/N6/N7 + R4 lethality check** — stop the *misuse* half of the complaint.
3. **R6 cast order inversion** (rocket **then** tornado) — the existing sim rule has it backwards.
4. **The mid-map-bow-vs-Rocket-deck prohibition** (§3) — directly addresses `xbow_into_push` = −276.
5. **R5 overtime/board-threat gates** on the existing pump rule.
6. **§2 defensive placements** — Knight-in-front-of-bow already exists; Tesla king-activation
   clearance, tornado-back, and the graveyard pre-fire order are new.

---

## 6. AMBIGUOUS, CONTESTED & REJECTED — not compiled without the noted resolution

1. **REJECTED — rocketing the enemy King Tower.** Read as *"the most important part is chipping
   the king"*. Mechanically bad: no crown, ~4,824 HP, and it **activates** their King for the rest
   of the match. Only defensible when the blast's primary target is a cluster hugging the king.
   **Do not encode.**
2. **REJECTED — "Rocket took the smallest big-spell cut."** False as written (Lightning −7% <
   Rocket −8%). The downstream chip-per-elixir ratio (57 vs 43) stands on its own arithmetic.
3. **CONTESTED → RESOLVED — Tornado/Rocket order.** Two pool facts said Tornado-first, two said
   Rocket-first (including Hunter correcting a student). **Mechanics decide: Rocket first.**
4. **CONTESTED → RESOLVED — Sparky trade value.** The pool shipped both "−1" and "6-for-6
   neutral" for the same play. Sparky costs 6, Rocket costs 6 → **neutral**, before tower clip.
5. **CONTESTED → RESOLVED — lone tower rockets.** "Double elixir only" vs "some matchups allow
   lone rockets any time". Resolved to the two real conditions in N5.
6. **CONTESTED — corroboration inflation.** Two pool entries carry the *identical* quote from the
   *identical* video with different dates (2026-08-01 vs 2026-07-31); same for a Prince quote.
   The doctrine is fine but **one utterance was counted as two sources** — confidence weights
   built on those pairs are overstated. De-duplicated here.
7. **MISREAD-RISK — "stop preventing damage" in the last seconds.** One situational call, not a
   rule; in overtime a tower loss ends the match. **Gate:** stop paying elixir only to prevent
   damage that *cannot destroy a tower before the buzzer*.
8. **MISREAD-RISK — Log crown damage 41→35.** Use **35**; do not derive from percentages (they
   disagree with the absolutes at both endpoints). **Measure in-game before encoding.**
9. **MISREAD-RISK — "no balance changes after June 2026."** Rests on a change *count* naming no
   cards, and the August source 403'd. Downgraded to *no evidence found*.
10. **MISREAD-RISK — the 19–19.5 s two-rocket window.** Caption unresolved ("19 1.5 secondsish")
    and the quantity is not a constant. Encode as a function of elixir rate (R8).
11. **MISREAD-RISK — Golden Knight / mini-tank rockets.** 1484 very likely does not kill a
    tournament-level Golden Knight, and the quote's *"you don't want to be rocketing that"* has an
    unresolved antecedent. Needs a lethality-or-tower-clip precondition; **verify his HP first.**
12. **MISREAD-RISK — "Balloon inside Lavaloon pushes."** The quote establishes a Balloon and an
    Inferno Dragon; nothing establishes Lavaloon. Generalised to *rocket a Balloon in any push*.
13. **STALE — the spell-cycle combo table (371 / 429).** Pre-nerf *and* internally inconsistent
    (it lists rocket+log = 429 and rocket+tornado = 429, but 371+41 = 412). **Only the aiming
    principle survives**; all numbers recomputed in §1.0.
14. **AMBIGUOUS, unresolved — "log rocket on this."** Cannot tell from transcript alone whether
    Log and Rocket both went onto the Dark Prince, or the Rocket was tower-chip with the Log
    clearing separate support. **Not compiled.**
15. **AMBIGUOUS, unresolved — the "surprise rocket" target on 2.6.** Most likely the Musketeer,
    but the transcript says only *"on top of this"*. **Not compiled as a card-specific rule.**
