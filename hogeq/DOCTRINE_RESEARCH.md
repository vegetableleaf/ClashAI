# Hog EQ doctrine research — merged 2026-08-19 (supersedes the 2026-08-18 draft)

Synthesized from the written-guide fact sheet (157 facts, read as raw wikitext via api.php where
Fandom pages 402) plus 88 observations from 4 watched videos (yt-dlp/whisper/contact-sheet
pipeline). `src/clashrl/sim/doctrine.py` cites this file's **§2** rows ("DOCTRINE_RESEARCH.md SS2
<card>") — §2 stays the per-card placement table so those references remain valid.

**Deck:** Hog Rider 13, Evo Firecracker 13, Mighty Miner 14 (champion), Evo Tesla 14, The Log 14,
Earthquake 13, Skeletons 15, Ice Spirit 13 — avg 2.75, "2.6 Hog EQ" with Mighty Miner.

**Source keys** (every claim below carries one; full URLs here once):

| key | source |
|---|---|
| F-HogEQ | https://clashroyale.fandom.com/wiki/Deck:2.6_Hog_EQ_Cycle (the exact archetype's page, by NotHavoc) |
| F-Modern | https://clashroyale.fandom.com/wiki/Deck:Modern_Hog_Cycle |
| F-Hog | https://clashroyale.fandom.com/wiki/Hog_Rider |
| F-EQ | https://clashroyale.fandom.com/wiki/Earthquake |
| F-FC / F-FCe | https://clashroyale.fandom.com/wiki/Firecracker , https://clashroyale.fandom.com/wiki/Firecracker/Evolution |
| F-29 | https://clashroyale.fandom.com/wiki/Deck:2.9_Royal_Hog_Cycle |
| F-HQSC | https://clashroyale.fandom.com/wiki/Deck:Hog-Quake_Super_Control |
| Verc | https://clash-royale-guides.vercel.app/articles/hog-cycle-deck-guide |
| Hyp | https://hypixel.net/threads/guide-in-depth-2-6-hog-cycle-guide.2901480/ |
| Scr | https://www.scribd.com/document/787378420/Hog-2-6-guide |
| CD | https://clashdecks.com/guides/cards/hog-rider-guide |
| RT | https://royaletracker.gg/guides/hog-eq-deck-clash-royale (miscites EQ cost as 4 — treat as directional) |
| SK | https://sportskeeda.com/esports/how-play-2-6-hog-cycle-clash-royale |
| V1 | https://www.youtube.com/watch?v=15W82L_5DOw — SirTagCR classic 2.6 gameplay (Musketeer/Cannon/Fireball variant; principles transfer, cards mapped in §2) |
| V2 | https://www.youtube.com/watch?v=adEMpf3Vrjo — LeviathanCR Hog EQ **Mighty Miner** matchup guide: the EXACT archetype (his Guards = our Skeletons slot) |
| V3 | https://youtube.com/shorts/IEEJmkPXY8g — Skeletons-vs-Bandit placement short (no voiceover; every rule frame-read) |
| V4 | https://www.youtube.com/watch?v=458jkVMfU90 — SirTagCR "Master 2.6"; its 300–383 s section has Hog EQ as the OPPONENT = counter-intel |

Confidence marks: **[H]** 2+ independent sources or seen on video frames; **[M]** one good
source; **[L]** directional/needs engine verification.

**Coordinates:** placement notation "(a-b)" = (tiles from river, tiles horizontally from the
princess tower), as the Fandom pages use it. Board-normalized (sim): river y≈0.48, 1 tile ≈ 0.031
in y; bridges x≈0.25 / 0.745; our princess line y≈0.615.

---

## 1. CYCLE & PRESSURE DOCTRINE — when the Hog goes

**The bot's current behaviour — hold when nothing threatens — is exactly backwards for this
deck.** Every source states the same identity: four ≤2-elixir cards exist to reach the Hog faster
than the opponent reaches their answer; "cycle faster than they can cycle their counter — every
third Hog connects" [Verc]. A quiet enemy board is not a reason to wait, it is the window: nothing
of theirs is committed to punish us. Winning looks like "consistent chip damage — 2 hits here,
1 hit there" [CD], never one big push.

### 1.1 SEND ladder (Hog in hand; check top-down, first hit fires)

* **T1 — PUNISH (overrides every elixir floor and veto below).** Opponent just committed ≥5
  elixir to a back/economy play (Golem/Giant/Lava behind the king, Elixir Collector): Hog at the
  **opposite-lane bridge within ~2 s**. They hold ~2 elixir; the Hog gets ≥2 swings (319/swing at
  lvl 14, ~3 swings/connection ≈ 957) [Verc][Hyp][SK] **[H]**. On V2 this timing is elixir-counted:
  he tracked Pekka+Fisherman, saw Fisherman spent, deduced no elixir for Pekka, hogged, connected
  (V2 t≈119–131) **[H]**. Add EQ only under the §3 justification gate. *Matchup veto:* vs
  P.E.K.K.A-class double-lane decks in single elixir T1 is OFF — see §5.3.
* **T2 — COUNTER-PUSH.** A cheap defense just resolved and a defender survived (Tesla with HP,
  Firecracker, Mighty Miner): Hog **same lane, behind the survivor, immediately** — the leftover
  body screens the counter [F-Modern] **[H]**. Seen: V1 f_432.jpg, Hog placed directly behind the
  Ice Golem that had just eaten a Miner, pair crossing the right bridge together **[H]**.
* **T3 — OUTCYCLE GAP.** The tracked answer (building / Mini Pekka / Tornado / swarm) is out of
  their rotation AND our counter-to-their-counter is in hand: send even at 4–5 elixir
  [Hyp] **[H]**. Seen: V1 t=230 ("he's not back to Tesla. We definitely outcycled him" — Ice
  Spirit at river, Ice Golem at the left river tile, Hog behind, f_230.jpg); V2 punishes the moment
  BOTH Tombstone and Tornado were spent (t≈602–616) **[H]**.
* **T4 — THEY ARE POOR.** Opponent just defended, just over-committed, or just cast a big spell
  (estimated bank ≤3): send [SK] **[M]**.
* **T5 — QUIET-BOARD DEFAULT** (the fix for the holding bug). Single elixir: send when **our
  elixir ≥7** — after the 4-cost Hog the bank stays ≥3, the floor every guide keeps ("elixir bar
  always at least 3 except against a large push" [F-Modern]) **[H]**. At 10, ALWAYS act — never
  leak **[H]**. Double elixir / OT: send the moment it is affordable (≥4) and cycle at maximum
  speed — "this is when you should really be trying to out cycle your opponent's defense" [Hyp]
  **[H]**. *Sim note:* `doctrine.py` currently nominates the Hog at 4 on any quiet board; keep
  that for x2/OT and for T1–T4, raise the bar to 7 for quiet x1 (§6 C8).

### 1.2 HOLD vetoes (block T5 only — never T1)

* **H1** Fresh high-DPS defender standing (Mini Pekka, P.E.K.K.A, Mega Knight) and no spell
  answer in hand [CD] **[M]**.
* **H2** Their building is in rotation and our EQ is not in hand [Hyp][CD] **[H]**.
* **H3** Their swarm counter (Skarmy/Gang) in cycle and our Log not in hand [Hyp] **[H]**.
* **H4** Their deck holds TWO hard Hog counters and it is single elixir: do not try to outcycle
  both — chip with spells, defend, wait for x2 [Hyp] **[H]**.
* **H5** The push would exceed **6 total elixir**. Cap: Hog alone / Hog+IS (5) / Hog+EQ (7 only
  with a §3 reason). Never 8+ supporting elixir [CD][F-HogEQ] **[H]**.

**While holding:** Firecracker behind the king is this deck's bank play (the 2.6 guides' "drop the
musketeer proactively at the back"; F-HogEQ: "cycle firecrackers often") [Hyp][F-HogEQ] **[H]**, or
the cheapest card to a safe corner. The bar must never touch 10 idle.

### 1.3 Opening policy (game start, merged from three sources — see §6 C1)

Escalation ladder, not blind commitment: at ~8–9 elixir **probe 1** = Skeletons behind the king,
purely to scout (V1's opener in three separate games, t=52/591/764) → **probe 2** = lone Ice
Spirit at the river (V1 f_60.jpg: it walks the left river with an empty board) → after two
unanswered probes, or on reaching 10, **Hog at the bridge** (V1 f_66.jpg: Hog+support crossing to
force a reveal) **[H]**. The archetype's own page allows Hog as literally the first play
[F-HogEQ]; V4's fixed priority is Hog > Ice Spirit > Skeletons > Log (> mini-tank) **[H]**.
Constraints from F-Modern's ranked list **[H]**: skip the Ice Spirit opener vs Cannoneer/Dagger
Duchess tower troops; Log opener only if we can cycle quickly back to the swarm answer; **never
open Firecracker** ("she can defend a variety of cards and give tons of value"); **never open EQ
on the tower** (hard-punished by pump/X-Bow decks).

### 1.4 Cycle arithmetic (the clock every decision runs on)

Cheapest 4-card route back to the Hog: **Skeletons 1 + Ice Spirit 1 + Log 2 + EQ 3 = 7 elixir**
(arithmetic on Hyp's classic-2.6 figure of 8) **[H]**. Full rotation 21 elixir; in x2 the Hog
returns every **29.1 s** (DOCTRINE.md §1). "They need to play 4 cards to get Tornado back. You can
cycle to Hog Rider in 3 cards" [Verc] **[M]**. Book their plays after every exchange and attack
into the gap — V1 t=89–101: "his minion horde is out of cycle, his Tesla should be out of cycle,
his Electro Wizard should be out of cycle" **[H]**.

---

## 2. PER-CARD PLACEMENT TABLE

V1/V4 card mapping onto this deck: their Musketeer → our Evo Firecracker (ranged back-liner),
their Cannon → our Evo Tesla (defensive building), their Ice Golem → nearest equivalents Skeletons
/ Ice Spirit / Mighty Miner as screen body. Fireball lines do not transfer (we have no medium
spell — the EQ+Log stack substitutes, §3.5).

### Hog Rider (4)
| # | named placement | geometry | trigger | src |
|---|---|---|---|---|
| H-1 | **Bridge, middle** | centre of the bridge tile, x≈0.25/0.745, shallowest own row | default for T1–T5 | Scr **[M]** |
| H-2 | **Bridge, inner side** | 1 tile toward arena centre from H-1 (x≈0.31/0.685) | vary vs Tornado users — wrong tile/order gets the Hog nadoed to the king | Scr **[M]** |
| H-3 | **Auto pig push** | the very arena-edge river tile (x≈0.06/0.94), at the front or 1 tile from the river; jumps the edge notch outside the playable water | vs a defensive building planted 3-from-river centre — defensive buildings' hitbox is smaller than passive ones', the edge path walks around it. Passive buildings (pump, spawners) at 3 CANNOT be bypassed | F-Hog, F-Modern **[H]** |
| H-4 | **Manual pig push (Ice Spirit)** | IS on the top-left/right corner tile, Hog quick-dropped on the SAME tile | beats the standard 4-3 plant (4 from river, 3 from tower) — the spawn-push shoves the Hog wide to hug the edge | Hyp **[H]** |
| H-5 | **Manual pig push (Skeletons)** | Hog on the corner tile FIRST, Skeletons instantly on the tile directly beside it (never front/behind/diagonal) | same target as H-4 when IS is out of rotation | Hyp **[H]** |
| H-6 | **Anti-nado shove** | IS on its tile, Hog immediately on the adjacent tile; spawn-push moves the Hog OUT of the king-activation Tornado radius | vs Tornado-based Hog defense (exact tiles are in F-Modern's HogIceSpiritBypassTornado.jpg — frame data still needed) | F-Modern **[H]** |
| H-7 | **Defensive kite** | 4th tile from the bridge, slightly into the opposite lane | kites Very Fast non-building-targeting troops | F-Hog **[H]** |
| H-8 | **Bridge stall** | right at the bridge | stalls ground melee (pulls on deploy, untargetable mid-jump, pulls again after landing) while still threatening the lane | F-Hog **[H]** |
| H-9 | **MK jump-dodge** | at the river as Mega Knight charges its jump — MK leaps at the mid-air Hog and whiffs | MK mid-charge | F-Hog **[H]** |
| H-10 | **Hog behind the king** | behind our king tower; cycle to the second Hog on the walk down, push both | ONLY vs Hog mirrors / cycle decks / drill cycle / after eating a blind Rocket — first Hog tanks+damages the building, EQ finishes it, second Hog connects. Named exception to "never from the back" (§6 C9) | F-Modern **[H]** |
| H-11 | **Defensive splash-dodge drop** | on defense when everything else in hand dies to incoming splash (Wizard); follow with IS to freeze | V1 t=624–649 ("very unconventional but anything else would have died") | V1 **[M]** |

Vary H-1/H-2/H-3 between pushes: "varying placements — direct bridge, bypass plants, different
lanes — keeps opponents guessing and prevents muscle-memory counters" [CD]; edge Hogs are denied
by an air troop dropped in front of the jump or an Ice Golem on the landing tile [F-Hog] **[H]**.

### Earthquake (3) — full rules in §3; placement summary
Aim so the 3.5-tile circle covers **their defensive building AND clips the princess-tower
corner** (midpoint when separation ≤7 tiles; bias toward the tower-side edge of feasible —
"place earthquake at the corner of the crown tower to get chip damage too" [F-29]) **[H]**. All
standard anti-Hog plants (4-3, 4-2, 3-2, 4-4) are dual-hittable; only a **4-6** plant escapes the
radius, and a river-hugging **0-3** is the named anti-EQ placement — on seeing one, expect no dual
value and hold the spell [F-HQSC][F-29][F-Modern] **[H]**. Their half only.

### Evo Firecracker (3)
| # | named placement | geometry | trigger | src |
|---|---|---|---|---|
| F-1 | **Kite band, light melee** | 4th tile from bridge, staggered slightly into the other lane | Mini Pekka / Lumberjack / Prince crossing; her 1-tile/shot recoil keeps the gap while both towers chip | F-FC **[H]** |
| F-2 | **Kite band, heavy** | 5th tile from bridge, 2–3 tiles horizontal from the crown tower | P.E.K.K.A / Giant Skeleton — the recoil path drags them into our king's range (activation FOR us) | F-FC, F-FCe **[H]** (2 vs 3 tile split: §6 C5) |
| F-3 | **Kite band, jumpers** | 6th tile from bridge, 3 horizontal | Mega Knight / Battle Healer — one deeper than F-2 keeps her outside jump reach for the first shot | F-FC **[H]** |
| F-4 | **Bandit dodge** | 6th tile, 2 horizontal | dodges the dash, forces a walk-up attack; she dies but the tower takes exactly 1 hit — accepted mitigation | F-FC **[H]** |
| F-5 | **Elite Barbs** | near board middle + IS/Skeletons as the aggro soak | +2 trade when the distraction lands | F-FC **[H]** |
| F-6 | **Point-blank intercept** | RIGHT in front of fast bridge threats (Wall Breakers) the moment they appear | at range her rocket's travel time is outrun and both WBs connect (2026 +25% projectile buff mitigates, doesn't remove) | F-FC **[H]** |
| F-7 | **Goblin Barrel** | deploy when the barrel shadow is 4 tiles from the river, angled to attack the bottom goblin so shrapnel lines the outer one | barrel in the air | F-FC **[H]** |
| F-8 | **Anti-push pierce** | directly in front of the tank so all 5 shrapnel pierce through into the backline | grouped pushes (Barbs, Recruits, Horde, Golem+support) — Evo spark fields excel here, whittle Night Witch/Witch | F-FC, F-FCe **[H]** |
| F-9 | **Delayed volley** | HOLD the drop until the whole stacked push is in one line | V2 t≈140 (frame: volley streaking into the Pekka+support cluster at his own bridge): "I delay it as much as possible... one hit onto his troops as well as his Pekka" | V2 **[H]** |
| F-10 | **Bank play** | behind the king | §1.2 holding state, Hog out of rotation | Hyp, F-HogEQ **[H]** |
| F-11 | **Offense layer** | several tiles BEHIND a crossing Hog, our side | splash clears his path, sparks chip; sequence Hog FIRST (§4 L7) | F-Modern, V2 **[H]** |

Hard constraints: she has exactly Archer HP — anything that one-shots an Archer one-shots her
(Arrows, Royal Delivery); a Cannoneer tower kills her before her first shot [F-FCe] **[H]**. Never
place her where one spell also clips the tower/Tesla; **never let her die to anything except a
spell** — screen behind Tesla/MM, out of bridge-unit reach (V2, stated three times) **[H]**.
Budget the 1-tile recoil per shot: repeated volleys drift her a lane over [F-FC] **[H]**. Vs
Balloon: engage AHEAD of the tower so only death damage reaches anything [F-FC] **[H]**.

### Mighty Miner (4, champion)
| # | named placement | geometry | trigger | src |
|---|---|---|---|---|
| M-1 | **On the tank's path** | tile-exact body-block, centrally on the lane | any ≥~1200 HP single body; ramp 48→246→494 | DOCTRINE.md, V2 **[H]** |
| M-2 | **Block geometry, to the tile** | V2 t≈413 frame: the Ram Rider slips PAST his MM to the tower; "1 tile to the left, 1 tile down... would have blocked the ram rider's path" | dash/charge units — a one-tile error is the difference between full block and leak | V2 **[H]** |
| M-3 | **At the bridge vs Magic Archer** | right up AT the river centre (V2 t≈1091 frame: MM drilling at the river) | denies every line-shot corridor through him to the tower; corollary stated twice — never MM in the back of the MA's lane | V2 **[H]** |
| M-4 | **Back-first in stalemates** | behind the king, BEFORE the Hog | switches the 3-card cycle on first ("three card cycles is the name of the game"); the 3-card cycle also fields 2× Guards-slot + 2× FC vs one big push | V2 **[H]** |
| M-5 | **Bridge punish** | alone at the bridge on a quiet board; ability later swaps lanes ahead of the Hog | quiet board, MM in hand, Hog next | DOCTRINE.md §4 **[M]** |
| M-6 | **Onto Skeleton King** | drop MM on him, tank his ability, grind, pop Explosive Escape to finish | "will always fully counter Skeleton King" (V2 t≈1646 frame: SK ability circle active, MM+bodies on him) | V2 **[H]** |
| M-7 | **Into Archer Queen's lane, pop EARLY** | the bomb damages + knocks her back, wasting her activated ability and forcing a re-answer | AQ ability up | V2 **[H]** |
| M-8 | **Never vs swarms without the bomb** | no splash; the stage-1 hit can't one-shot Skeletons | the sim already encodes the deliberate no-spot | DOCTRINE.md **[H]** |

Ability (Explosive Escape, 1 elixir, SINGLE USE per body since 4/8/2026): trigger only when ≥2
enemies stand in the ~2.5-tile blast (the radius is the project's one unsourced guess — §6 C10),
or per the M-6/M-7 scripts; early = wasted, late = dead **[H]**. x2 split: MM one lane + Hog the
other, simultaneously [RT] **[M]**.

### Evo Tesla (4)
| # | named placement | geometry | trigger | src |
|---|---|---|---|---|
| T-1 | **Standard pull** | centre column, 3–4.5 tiles from the river (sim band y=0.548–0.585; engine double-cover begins 3.69 tiles from the river) | any win condition committed | DOCTRINE.md, F-Modern **[H]** |
| T-2 | **Anti-pig-push** | **2-3** (2 from river, 3 from tower) — "Pink (2-3)... will pull all hog riders even when auto-pig pushed" | vs Hog decks; also the plant that catches OUR edge Hogs (counter-intel §5.9) | F-Modern **[H]** |
| T-3 | **Anti-EQ / anti-spell** | **0-3**, river-hugging — "prevents earthquake, lightning and poison from hitting both the Princess tower and the Tesla" | vs EQ/Lightning decks and the Hog-EQ mirror; accept the Queen/Cannon snipe risk — replaceable on 3-card cycle (V2 t≈1508 frame: Tesla planted centre ~3 under the river, far from either tower) | F-Modern, F-29, V2 **[H]** |
| T-4 | **Pre-placed low** | centre, deep in own half, placed while WAITING, before the push commits | vs slow-assembling mega-push decks only (Pekka, Goblin Giant Sparky) — V2 t=73 frame (Tesla dug in dead-centre, Pekka still at the enemy river) and t=900 frame; everything else: reactive, last-second (§6 C6) | V2 **[H]** |
| T-5 | **Stacking** | cycle spare Teslas from the back, keep 2 alive | opponent has NO big spell — "they don't really have a good way of killing Teslas" | V2 **[H]** |

V1's Cannon rules transfer to reactive use: place at the **last possible second** (lifetime HP
decay; V1 f_135/f_516: Cannon held in hand at 8 elixir while the Giant is still deep in enemy
territory) and spread the ranged support AWAY from the building so no single spell/splash covers
both (V1 t=136–141, plus the staggering credit at t=212: "shut down an entirety of his push...
because we staggered out our units very efficiently") **[H]**. Early-cycled buildings deliberately
bait the big spell so the replacement is spell-free when the real push comes (V4 t=151–164)
**[M]**.

### The Log (2)
| # | rule | trigger | src |
|---|---|---|---|
| L-1 | **Predict-Log the swarm spot** as the Hog approaches — rolled BEFORE the swarm lands so it clips on spawn | their Skarmy/Gang/Tombstone is the tracked answer. Seen end-to-end: V1 f_668 (Hog deploy at the right bridge) → f_672 (Log rolling through the Skarmy clumped on the Hog at their tower): "he's only got skarmy so I'm going to pre-log" | F-Hog, V1 **[H]** |
| L-2 | **Angle for the bounce** — the knockback is a targeting tool: aim slightly off-axis so the bounced unit lands NEXT TO our building/defender | Bandit bounced back into Ice-Golem-slot tanking range (V1 f_255); Executioner bounced INTO Musketeer-slot range (V1 t=267); self-identified mistake at V1 f_345: a straight Log let the Dark Prince reach the tower — angled would have landed him by the Cannon | V1 **[H]** |
| L-3 | **Shield strip** — "blowing back the Dark Prince's shield is pretty imperative" before units engage | Dark Prince approaching | V1 **[H]** |
| L-4 | **Deny-hits timing** — hold until the support (E-Wiz class) is walking up to the tower; one roll denies all but 1 tower hit AND kills the Princess behind | V1 t=701–711; spell value measured in tower hits denied, not units killed | V1 **[H]** |
| L-5 | **Suppress predictions vs Goblin Delivery decks** — a Delivery answer makes the pre-Log a dead card (V2 withheld it and was proven right, t≈1427) | opponent has shown Delivery | V2 **[H]** |
| L-6 | Bridge-Log opener only if we can cycle quickly back to it (logbait risk) | opening ladder §1.3 | F-Modern **[H]** |
| L-7 | Rolls 9.6 tiles, ground only — clears the Hog's path from our own side; NEVER the answer to air (Firecracker covers that half) | always | DOCTRINE.md **[H]** |

### Skeletons (1)
| # | named placement | geometry | trigger | src |
|---|---|---|---|---|
| S-1 | **Scout opener** | behind the king | game start, §1.3 (V1, three separate games) | V1 **[H]** |
| S-2 | **Dash-unit kite spot, tile-exact** | arena CENTERLINE ±1 tile toward the attacker's lane, on the row level with the princess-tower FRONT edge (~10 tiles behind the river; sim (0.48±0.03, 0.615)) | on SIGHT of a bridge-deployed Bandit — place while her deploy clock still shows (V3 frames: the square is down ~2 s before she crosses). Her dash pulls her OUT of the lane onto the trio, she is surrounded on arrival and dies in double tower coverage: V3 shows every tower frozen at 2534 HP across both demos — 1 elixir fully answers 3, mirrored exactly per lane (deploy square at 47% vs 53–55% arena width). Generalise to Prince/Ram-class dashers | V3 **[H]** |
| S-3 | **Wide pull** | dropped off to the side, away from the lane | drags a Mega Minion (single-target chaser) off entirely — "we do not have to deal with it at all", +2 trade framed as kite not kill (V1 t=113) | V1 **[H]** |
| S-4 | **Surround / ramp guard** | centre+ring ON the tank; or beside MM as his aggro soak | tank walking; MM's ramp must not reset | DOCTRINE.md, Hyp **[H]** |
| S-5 | **Pig-push assist** | tile directly beside the corner-tile Hog (H-5) | pig push with IS out of rotation | Hyp **[H]** |
| S-6 | **Bridge chip** | at the bridge | ONLY when their small spell was just spent — "I can go for Skeletons because he used his Log" (V1 t=300) | V1 **[M]** |

### Ice Spirit (1)
| # | named placement | geometry | trigger | src |
|---|---|---|---|---|
| I-1 | **Probe opener** | alone at the bridge/river tile | §1.3; skip vs Cannoneer/Dagger Duchess | F-Modern, V1 f_60 **[H]** |
| I-2 | **Hog escort** | onto whatever meets the Hog, as it engages | the freeze converts 1 hit into 2–3; mandatory vs Mini Pekka decks | DOCTRINE.md, Hyp **[H]** |
| I-3 | **Pig-push / anti-nado body** | corner tile before the Hog (H-4) or beside it (H-6) | see the Hog rows | Hyp, F-Modern **[H]** |
| I-4 | **Force-a-response** | at the river IN FRONT of our crossing support | converts an ignorable unit into one they must spend on — "whether it's a log, whether it's a zap... that's a negative trade" (V1 f_453: IS deploy label at the right river ahead of the Musketeer) | V1 **[M]** |
| I-5 | **Freeze-stall on tanks** | thrown onto the defending cluster fighting a Pekka-class body | V2: "you need to add... an ice spirit as well, especially the new Evo Pekka" (t≈146 frame: the freeze connecting at the river fight); our version stalls for MM/Tesla | V2 **[H]** |
| I-6 | **Budgeted bats answer** | on Miner-Bats | do NOT waste Tesla on bats (V2 t≈1670) | V2 **[H]** |

---

## 3. SPELL TIMING

### 3.1 Earthquake constants
3 elixir (RT's "4" is wrong — §6 C3), radius 3.5 tiles, 3 s duration, 3 ticks (1/s), ground only,
50% move-slow (does NOT stack with Ice-class slows). ~3.5× damage to buildings. Level 11 base:
84×3 troop / 287×3=861 building / 53×3 crown; per-level ×1.1 → lvl 13 ≈ 102×3 troop / 347×3=1041
building; crown-tower damage is now **58% of troop damage** after the 1/6/2026 nerf — recompute
every lethal table, the old "EQ+Log = 249 crown" figure is pre-nerf [F-EQ] **[H]**.

### 3.2 Cast timing
* **With the Hog: the moment he CROSSES THE BRIDGE — simultaneous, not reactive.** A building
  placed while the quake is already landing still dies before it ramps/retargets ("an Inferno
  Tower placed on a foundation after Earthquake is already landing still dies before it can ramp");
  "the 1-second window matters" [RT, corroborated by Ian77 guide summaries] — simultaneity **[H]**,
  the literal 1 s figure **[M]** (§6 C11).
* **Exception vs Tornado decks: delay 1–2 s** after the Hog so the pull can't drag him out from
  under the quake [RT] **[M]**.
* **Prediction EQ around the Hog** when their only ground answer is a swarm (no real building):
  centre it just ahead of the crossing Hog so the swarm dies as it deploys. Kill thresholds: 1
  tick kills Skeletons, 2 ticks kill Spear Goblins, all 3 kill Goblins (up to +1 level) and
  same-level Spirits [F-29, F-EQ] **[H]**.
* **EQ-predict the Evo Mortar's cycle**, and instant-EQ a Mortar placed late at the bridge —
  accept one Mortar hit on the tower as a winning trade (V2 t≈1691 frame: EQ cracks on the
  bridge Mortar; "evo mortar can ruin you") **[H]**.

### 3.3 Target geometry and the justification gate
* **Gate:** EQ travels with the Hog only when a building is down or KNOWN coming AND EQ+Hog will
  actually kill it and land a tower hit. "Using the Earthquake on healthier buildings that will
  full-counter your Hog Rider anyway is a waste of elixir" [F-HQSC] **[H]**. Against no-building
  decks the Hog goes ALONE — save the 3 elixir [F-29, RT] **[H]**. In single elixir never
  speculative ("DO NOT EQ IN SINGLE" for opposite-lane punishes) [F-Modern, F-HogEQ] **[H]**.
  Offense-gate from V2: only spend EQ when they have no immediate counter-attack queued **[H]**.
* **Dual-cover geometry:** one cast covers building+tower whenever their separation is ≤7 tiles
  (2× the 3.5 radius) — which is every standard anti-Hog plant (4-3, 4-2, 3-2, 4-4). Only **4-6**
  escapes; **0-3** is the deliberate anti-EQ plant — detect either and expect no dual value
  [F-HQSC, F-29, F-Modern] **[H]**.
* **Target table:** Tombstone = clean solo stop, neutral trade (ticks 1–2 kill the building, tick
  3 the death skeletons — cast early enough that tick 3 outlives the building) **[H]**;
  hidden/underground Tesla = YES, the one damage spell that reaches it, don't wait for the pop
  **[H]**; Elixir Collector = always, on sight ("earthquake every pump you see") **[H]**;
  X-Bow/Mortar setups = repeatedly, then Hog into the panic **[H]**; badly placed spawners =
  snipe **[H]**; Goblin Cage = partial (the Brawler SURVIVES the spell — needs Log/tower
  follow-up or an early cast so he spawns off the Hog's path) **[M]**; lone full-HP Inferno
  Tower = NEVER alone (it kills the Hog before the quake finishes — pair with Log, the cheap
  Lightning) **[H]**; shielded Cannon Cart = wait for the shield to break **[M]**. All F-EQ /
  F-29 / F-Modern.
* **Never-list:** any air unit (zero damage — Balloon/Lava/Minions/Bats); Lumberjack Ghost
  (immune since 4/2/2025 — but hover-class units like Royal Ghost DO take damage since
  2/10/2024); generic swarm defense while Log/IS are available; P.E.K.K.A is untouched as a Hog
  counter [F-EQ, RT] **[H]**.

### 3.4 Chip criteria and the spell-cycle endgame
* Pure tower chip is a **x2/OT and endgame tool only** — weak after two nerfs (4/8/2022,
  1/6/2026) — and NEVER while their deck holds a pump or X-Bow (the spell is reserved for those
  targets; blind chip is "punished hardly"). Priority: pump/siege setup > building mid-Hog-push >
  tower chip [F-Modern, F-HQSC, F-29] **[H]**.
* **The V2 endgame script:** at enemy tower ≤**773 HP** (his cited threshold), switch plan to
  MM-in-back → 3-card cycle → EQ/Log the tower repeatedly — but only once the field is clear:
  "there's too much elixir on the field. I have to defend first. ... His push is dead. I start
  spell cycling. I defended. Life's good" **[H]**. Memorize post-nerf EQ/Log crown numbers and
  finish when HP < known spell lethal [F-HQSC] **[H]**. 3–4 EQ casts finish a low tower in x2
  [RT] **[M]**. V1's version of the same discipline: "I need two more fireballs and one more Log
  to win this game" — count exact remaining spell cycles and play toward the count **[H]**.
* **EQ troops parked behind their tower** like a mini-Fireball/Rocket: the 3.5-tile radius clips
  the back-deployed support AND the tower for 3 elixir — "very safe because earthquake only costs
  3". It chips (does not kill) Dart Goblin/Princess/Archers/FC/Bomber/Rascal Girls [F-Modern]
  **[H]**.
* **Defensive EQ — the exhaustive rare-case list:** the 50% slow in a pinch on a big ground push
  about to reach the tower; Graveyard AFTER the second skeleton wave spawns; Goblin Barrel when
  the shadow is 4 tiles from the river (neutral trade); swarm answer when Log is out of cycle;
  holding a P.E.K.K.A inside Firecracker range (V2 t≈277, burned-in caption "PEKKA IN MY CRACKER
  RANGE" with the FC beaming her); splashyard's tanked Graveyard in x2 is the named
  must-EQ-on-defense matchup [F-EQ, F-HogEQ, V2] **[H]**.

### 3.5 EQ + Log stack
Combined ≈536 troop damage at tournament level (level/patch-dependent; verify current lvl-13
values in the engine — §6 C7): kills Magic Archer (V2 uses it twice — proactively at the bridge
and as the clean answer to two stacked MAs on defense), Mother Witch, Zappies, Evo Firecracker,
Evo Archers, everything Royal Delivery kills. It is a NEGATIVE elixir trade alone — only stack
when a building or the tower is also inside the circles [F-Modern, F-EQ, V2] **[H, M on raw
numbers]**.

### 3.6 The Log
Rules L-1..L-7 in §2. Timing specifics: predict-roll so it clips the swarm ON SPAWN (L-1); vs
Graveyard wait 2–3 s for max skeleton accumulation; deny-hits roll when the walking support
reaches the tower (L-4); hold the Log for DEFENSE while spell-cycling for the finish [F-HQSC];
withhold predictions entirely vs Delivery decks (L-5).

---

## 4. SYNERGY LINES (play A → play B, with the gap between them)

| # | line | timing between plays | notes | src |
|---|---|---|---|---|
| L1 | Hog → **EQ** | 0 s — cast as he crosses the bridge | §3.2; +1–2 s vs Tornado decks; only under the §3.3 gate | RT, F-HogEQ **[H]** |
| L2 | Ice Spirit → **Hog** (pig push) | quick-drop on the SAME corner tile, <0.5 s | H-4; beats the 4-3 plant | Hyp **[H]** |
| L3 | Hog → **Skeletons** (pig push) | instantly, tile directly beside | H-5; note the order reverses vs L2 | Hyp **[H]** |
| L4 | Ice Spirit → **Hog** (anti-nado) | instant, adjacent tile — the spawn-push shoves the Hog out of the king-nado radius | H-6 | F-Modern **[H]** |
| L5 | Hog → **pre-Log** | rolled as the Hog nears their tower, BEFORE the swarm lands | L-1; V1 f_668→f_672 shows the whole sequence | F-Hog, V1 **[H]** |
| L6 | surviving defender → **Hog** | within ~2 s of the defense resolving, same lane, behind the body | §1.1 T2; V1 f_432 | F-Modern, V1 **[H]** |
| L7 | Hog → **Firecracker behind** | Hog FIRST, FC a beat later, several tiles back on our side | sequencing beats Goblin Delivery — one Delivery can't answer both (V2 t≈1488); her pierce reaches from the bridge | V2, F-Modern **[H]** |
| L8 | Tesla (defense) → **Hog opposite lane** | immediately, mid-defense | "so he can't defend and attack at the same time" — V2 t≈527 frame: Pekka at his own bridge, own Tesla mid, own Hog already on the enemy right tower | V2 **[H]** |
| L9 | cheap body → **Mighty Miner behind** | body first, MM a beat later | the distraction keeps his ramp on ONE target | DOCTRINE.md **[H]** |
| L10 | **MM in back → Hog** | MM first, Hog when it rotates back in | stalemate tech; the 3-card cycle switches on first | V2 **[H]** |
| L11 | **MM lane A + Hog lane B** | simultaneous | x2 split pressure — "this dual pressure ends games" | RT **[M]** |
| L12 | **EQ + Log** | together on the same footprint | §3.5 — only with a building/tower also inside | F-Modern, V2 **[H]** |
| L13 | Hog behind king → **second Hog + EQ** | cycle the 2nd Hog during the first's walk down; EQ once their building has taken the first Hog's damage | H-10 mirror-breaker; their bridge swarm answer = FC, high-DPS answer = cheap body in front of the Hog | F-Modern **[H]** |
| L14 | Log (ground half) + **FC (air half)** | as the mixed push splits | between them they answer both halves | DOCTRINE.md **[H]** |
| L15 | **defensive EQ → FC volleys** | EQ the tank as it enters her range | the 50% slow holds it in her DPS window (V2 caption frame) | V2 **[H]** |
| L16 | Hog on defense → **Ice Spirit** | IS right after the Hog's defensive drop | freezes both threats so the back-liner "retains more HP" (V1 t=624–649) | V1 **[M]** |

---

## 5. MATCHUP ADJUSTMENTS

**5.1 Building/cycle control decks (the designed prey).** EQ the building every justified push
(§3.3 gate); watch for 4-6 and 0-3 anti-EQ plants and hold the spell when seen — pressure anyway;
identify their building in the first ~60 s with cheap probes [RT, F-HQSC] **[H]**.

**5.2 Beatdown (Golem / Giant / Lava).** T1 on the tank-drop: Hog opposite lane at once, ADD
NOTHING behind it; EQ every pump on sight; never let the counter-push stack — "massive counter
pushes are unstoppable which is why you need to abuse opposite lane pressure" [F-HogEQ, Verc,
Hyp] **[H]**. Vs Lava specifically, gate the punish on their Tombstone being dead or out of cycle
[V4] **[H]**. Defensive building goes down as late as possible (decay economics), ranged support
spread wide of it and edge-hugging so her first target is the SUPPORT, not the tank (V4
t=171–189: Musketeer touching the arena edge beside the tower — "they'll never be able to hit
both... with any spell") **[H]**. Lone Hogs early; hoard the screen body for defense [V4] **[M]**.

**5.3 P.E.K.K.A / double-lane bridge decks — the stated exception.** Opposite-lane pressure is
explicitly WRONG in single elixir for this archetype ("you just can't defend these Evo Pekka
double lane pushes... in single you just need to focus on your defense" — V2, said twice)
**[H]**. Same-lane defense: pre-placed low Tesla (T-4), Skeletons + Ice Spirit freeze (I-5), FC
delayed volley (F-9), MM on the Pekka, defensive EQ to hold her in FC range (L15). Punish only
once the P.E.K.K.A is confirmed out of cycle.

**5.4 Bridge spam.** Usually no building → the Hog goes ALONE and the EQ elixir stays banked
[F-29] **[H]**; Tesla reserved for the win condition; FC point-blank on Wall Breakers (F-6);
Guards-slot duty (blocking WBs, Cannon Cart) falls on Skeletons+Tesla. In Mortar-bait, Tesla is
cycled FOR the Cannon Cart ("the Cannon Cart is really what kills you") and never wasted on
Miner-Bats — Ice Spirit is the bats budget (V2 t≈1608–1724) **[H]**.

**5.5 Hog mirrors / cycle / drill.** H-10/L13 double-Hog wave is the mirror-breaker; T-3 anti-EQ
Tesla plant with accepted snipe risk; spam Hogs behind the king to discourage drill placements;
track THEIR EQ cycle and re-place the Tesla accordingly [F-Modern, V2] **[H]**.

**5.6 Graveyard / splashyard.** Two scripted defenses: cheap bodies on the tower accepting small
chip, or **EQ+Log** (V2 t≈692 frame: the Guards-slot defending the poisoned tower under
Graveyard) **[H]**; defensive EQ only after the SECOND skeleton wave [F-EQ] **[H]**; EQ their
Tombstones, outcycle their Tornado [F-EQ] **[H]**; commit pressure the moment BOTH Hog counters
(Tombstone + nado) are spent — they are left with awkward troop answers (V2 t≈602) **[H]**; vs
splashyard attack the OPPOSITE lane — they want to build in ours (V2 t≈622) — and abuse that
nothing of theirs kills a screened Firecracker **[H]**.

**5.7 Logbait.** Princess on the board = assume bait until disproven (V1 t=598) **[M]**; we have
no Fireball, so the FC snipes her and EQ+Log answers stacks; suppress prediction Logs until their
bait pattern is read; punish a blind Rocket with Hog-in-back (H-10) [F-Modern] **[H]**.

**5.8 Miner / Wall-Breakers bait (declared hard counter, winnable).** Do NOT spend EQ on their
Bomb Tower early — "you waste elixir onto spell damage too early, then you just give them the
momentum"; constant pressure outranks spell value here, the one matchup where that inversion
holds [V2 t≈1225] **[H]**. Stack Firecrackers — "they have no good way of dealing with your
firecracker" [V2 t≈1068] **[H]**. Keep the FC alive from Miners the way V1 guards the Musketeer:
outcycle their spell; if she survives, "you're definitely going to win the game" (V1 t=561)
**[M]**. When ahead, hold our spells and cycle Logs defensively (V1 t=570) **[M]**.

**5.9 Counter-intel — what beats US** (V4's Hog-EQ-as-opponent section, 300–383 s, + F-Hog): a
spaced Musketeer+building+spirit defense holds our standard-time EQ push — vary EQ timing or wait
for commitment **[H]**; a repeated pre-cast EQ point gets dodged — they shift the building once
the habit shows **[H]**; their 2-3 Tesla/Cannon plant catches even auto-pig-pushed Hogs **[H]**;
edge Hogs die to an air troop dropped in front of the jump (Bats/Horde on-deploy, Minions
staggered one tile) or an Ice Golem on the landing tile **[H]**; a Mini Pekka held in cycle
zeroes lone Hogs (4-for-4, no damage) **[H]**; anti-splash staggering is why good defenses hold —
ours must space the same way (V1 t=212) **[H]**. Also: a Hog at the bridge is the standard punish
for a pump in front of THEIR king (positive trade even if the Hog dies), but never send the Hog
just to kill a normal defensive building [F-Hog] **[H]**.

---

## 6. CONTRADICTIONS & CONFIDENCE

* **C1 — Open with the Hog vs never-Hog-first.** F-HogEQ (the exact archetype): "Playing Hog at
  the first play of the game is recommended in most situations"; V4 ranks Hog the #1 opener for
  any matchup; F-Modern ranks Ice Spirit above it; Verc dissents outright: "Never Hog first.
  Always wait for their card or their leak at 10 elixir" [M]; V1 opens Skeletons-in-back three
  games running. **Chosen:** the §1.3 escalation ladder — probes first, Hog as the first REAL
  commitment, always before we leak at 10. It satisfies every source except the strongest reading
  of F-HogEQ, and V1's demonstrated play is the tiebreaker. Merged rule: **H**.
* **C2 — Opposite-lane pressure always vs never-vs-Pekka.** F-HogEQ/Hyp: abuse opposite lane vs
  heavy decks [H]; V2 (exact archetype, on camera, twice) carves out Pekka double-lane decks in
  single elixir [H]. **Chosen:** V2's exception as a matchup gate (§5.3). **H**.
* **C3 — EQ cost.** RT says 4 elixir; F-EQ vardefines say 3. **Chosen:** 3. RT demoted to
  directional on all numeric claims. **H**.
* **C4 — EQ chip viability.** Older pages call spell-cycling "reliable"; post-4/8/2022 and
  post-1/6/2026 (crown = 58% of troop damage) it is a finisher only. **Chosen:** §3.4 — x2/
  endgame tool; recompute every lethal (the 249 EQ+Log crown figure is pre-nerf). **H** on the
  doctrine, **L** on any specific lethal number until the engine recomputes them.
* **C5 — FC kite horizontal offset vs P.E.K.K.A.** F-FC says 3rd tile horizontal, F-FCe says
  2nd. **Chosen:** treat 2–3 as a valid band (F-2). **H** for the band; unresolvable finer.
* **C6 — Defensive building placed late vs pre-placed.** V1: Cannon at the "last possible second
  so its health does not decay" (twice, frames f_135/f_516) [H]; V2 pre-places the Tesla vs Pekka
  and GG Sparky (frames t=73/t=900) [H]. **Chosen:** reactive-late is the default (lifetime-decay
  economics); pre-place ONLY vs slow-assembling mega-push decks and in x2 (T-4). Both behaviours
  are correct inside their own trigger. **H**.
* **C7 — EQ+Log damage figures.** F-Modern's 246+290=536 is level/patch-dependent; Input A notes
  current lvl-13 EQ troop total ≈306. **Chosen:** keep the KILL LIST (Magic Archer etc., twice
  video-confirmed) as **H**; mark all raw damage numbers **M** until `tools/` recomputes them
  from the engine card DB.
* **C8 — Sim's quiet-board Hog-at-4 vs the guides' ≥3 floor.** `doctrine.py` nominates the Hog
  at 4 elixir on any quiet board; the guides keep a ≥3 bank in single elixir. **Chosen:** the
  phase split of §1.1 T5 — quiet x1 → send at ≥7; x2/OT and any T1–T4 window → send at 4. This is
  the one doctrinal CHANGE this document asks of the sim. **M** (the exact 7 is arithmetic, not a
  quote — the ≥3 floor and the never-leak rule are the sourced endpoints).
* **C9 — "Never from the back" vs Hog-in-the-back tech.** DOCTRINE.md §5.1 says never from the
  back; F-Modern's mirror/cycle/drill/post-Rocket double-Hog wave is a named, sourced exception
  (H-10/L13). **Chosen:** amend the standing prior with the four named triggers. **H**.
* **C10 — MM blast radius 2.5 tiles** remains the project's one unsourced guess (DOCTRINE.md
  §4); nothing in either research input sourced it. **L** — measure from a clip.
* **C11 — RT's "1-second window"** for the bridge-cross EQ: the simultaneity is corroborated
  (Ian77 summaries, V2's play pattern) = **H**; the literal 1 s figure = **M**.

Everything not listed above carries the confidence mark shown inline at its row; **[H]** requires
two independent sources or direct frame evidence, **[M]** one good source, **[L]** directional.
