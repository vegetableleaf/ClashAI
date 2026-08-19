# Hog EQ doctrine research — 2026-08-18

Synthesized from 157 facts (6 researchers over the written guides) + 88 observations from 4
watched videos (yt-dlp/whisper/contact-sheet pipeline; SirTagCR "2.6 Hog Cycle Like a Pro",
LeviathanCR "Hog EQ Mighty Miner MATCHUP GUIDE" — the exact archetype, 29 min — a Skeletons-vs-Bandit
placement short, and SirTagCR "Master 2.6", whose Hog-EQ-as-OPPONENT section is counter-intel).
Primary written sources: the archetype's own Fandom page (`Deck:2.6_Hog_EQ_Cycle`), Modern Hog
Cycle, 2.9 Royal Hog Cycle, Hog-Quake Super Control, the Earthquake / Firecracker / Tesla-Evolution
/ Mighty Miner / Hog Rider card pages (all read as raw wikitext via api.php), RoyaleTracker,
Theria, the Hypixel in-depth 2.6 guide. Confidence marks: **[H]** stated by 2+ independent sources
or seen on video; **[M]** one good source; **[L]** directional.

This document is the research record. The living rules live in `DOCTRINE.md` and
`src/clashrl/sim/doctrine.py`; the live advisor prompt in `src/clashrl/llm_advisor.py`.

---

## 1. Cycle & pressure doctrine — when the Hog goes, and why "hold" is wrong

The deck's identity, stated identically everywhere: four sub-2-elixir cards exist so you get back
to the Hog faster than the opponent gets back to their answer. **A quiet board is not a reason to
hold; it is the window.** [H]

**The decision ladder on a quiet board** (nothing committed that the tower can't handle):

1. **Elixir < 3: genuinely hold.** "Keep the bar at >= ~3 in single elixir, spending below that
   only for a large push." [H]
2. **Elixir >= 4 and the punish window is open: Hog at the bridge.** Windows, strongest first:
   opponent committed a tank in the back / placed a pump (Hog OPPOSITE lane *immediately*, they
   have ~2 elixir — "that Hog gets at least 2 swings") [H]; a successful cheap defense just ended
   (Hog SAME lane, behind the surviving Tesla/Firecracker — "repeat that transaction") [H]; the
   tracked answer (building / Mini Pekka / Tornado) is out of cycle (SirTag: "he's not back to
   Tesla. We definitely outcycled him") [H].
3. **Elixir >= 4, no read yet: escalation ladder, not blind commitment.** SirTag's opening pattern,
   three games in a row: cheap probe (Skeletons in back, purely to scout) → second probe (lone Ice
   Spirit at the river — 1 elixir that forces a response or chips) → **only after two unanswered
   probes, Hog at the bridge**. [H] The archetype's own page is more aggressive ("playing Hog at
   the first play of the game is recommended in most situations" [H]); a dissenting 2.6 guide says
   "never Hog first, wait for their card or their 10-elixir leak" [M]. Reconciliation used here:
   the Hog goes as the FIRST REAL COMMITMENT, after at most one cheap probe, and always before we
   leak at 10.
4. **Elixir >= 9 with nothing to do: cycle the cheapest card in the back** (Skeletons behind the
   king). Never leak. [H]

**Opening ranking** (Modern Hog, best→worst): Ice Spirit at the bridge (skip vs Cannoneer/Dagger
Duchess tower troops — they one-shot it) > Hog at the bridge > Log at the bridge (only if we can
cycle back fast — logbait risk) > mini-tank in back > Tesla middle. **Never open Firecracker**
(too valuable, reactive) and **never open EQ on the tower** (hard-punished by pump/X-Bow decks). [H]

**Overcommit limits:** Hog+EQ = 7 elixir; in single elixir only with a concrete reason ("DO NOT EQ
IN SINGLE" for speculative pushes) [H]. Never send the Hog into a fresh Mini Pekka / Mega Knight /
P.E.K.K.A or while their building is in rotation, without the spell answer in hand [H]. Vs decks
that stack an unstoppable counter-push (beatdown), pressure OPPOSITE lane and add nothing [H] —
EXCEPT vs P.E.K.K.A double-lane decks in single elixir, where opposite-lane pressure is explicitly
wrong for this deck: defend same-lane first, punish only when P.E.K.K.A is out of cycle
(LeviathanCR, twice) [H].

**Double elixir:** once the opponent has shown a building, Hog+EQ every push; defend-and-attack
simultaneously (Tesla down first, then Hog the other lane mid-defense: "so he can't defend and
attack at the same time") [H]. **Stalemate tech:** Mighty Miner in the back BEFORE the Hog — the
3-card cycle switches on first ("three card cycles is the name of the game") [H]. **Endgame:** when
the tower is below spell-lethal (track EQ+Log crown numbers), switch to spell-cycling — but only
once the field is clear ("there's too much elixir on the field. I have to defend first") [H].

## 2. Per-card placement table

Notation: tiles are (from river, horizontal from the princess tower) where the guides use it.
Board-normalized: river y≈0.48, 1 tile ≈ 0.031 in y; bridges x≈0.25 / 0.745.

### Hog Rider
| placement | when | src |
|---|---|---|
| **Bridge, middle or inner side** | the default pressure/counter-push play | [H] |
| **Arena edge at the river (auto pig push)** | bypasses defensive buildings planted 3-from-river center; the edge notch jump needs no helper | [H] |
| **Manual pig push**: Ice Spirit on the corner tile, Hog quick-dropped on the SAME tile (or Hog corner + Skeletons on the tile BESIDE it) | beats the standard 4-3 plant | [H] |
| Mini-tank/body IN FRONT of the Hog | anti-Tornado (they must pull the body too); Ice Spirit shoved beside also works | [H] |
| Hog as defensive kite | pulls a crossed P.E.K.K.A backward; body-blocks a Baby Dragon at the river so the tower shoots Graveyard skeletons; legitimate splash-dodge drop when everything else in hand dies to a Wizard | [M] |
| Vary bridge vs edge vs lane | repeated identical placement gets muscle-memory countered (their cannon shifts once our pre-EQ becomes a habit) | [H] |

### Earthquake (the user's rule, confirmed and sharpened)
* **Primary target: their defensive building, cast to ALSO clip the princess tower** — "place
  earthquake at the corner of the crown tower to get chip damage too" [H]. The current sim rule
  (midpoint when tower+building within 2×radius, else the building, else pure chip) matches; the
  corner-bias refinement means: when both are coverable, bias the cast toward the tower-side edge
  of feasible, not the exact midpoint.
* **Timing: cast as the Hog CROSSES THE BRIDGE, not after their building lands** — a reactively
  placed Inferno still dies before ramping [H]. Vs Tornado decks delay 1–2 s so the pull can't
  drag the Hog out from under the quake [M]. Counter-intel: the "regular-time" EQ never breaks a
  Musketeer+Cannon+IceSpirit defense — vary timing or target commitment [H].
* **Justification gate:** EQ travels with the Hog only when a building is down/known-coming AND
  EQ+Hog actually kills it and buys a tower hit. Into a no-building deck the Hog goes ALONE. [H]
* **Target table:** Tombstone = clean kill incl. the death skeletons (tick 3) [H]; hidden Tesla =
  yes, the ONE spell that reaches it, don't wait for it to pop [H]; pump = always, on sight [H];
  X-Bow/Mortar setups = yes, repeatedly [H]; Goblin Cage = partial (Brawler survives) [M]; lone
  full-HP Inferno Tower = NEVER alone (pair with Log) [H]; shielded Cannon Cart = wait for the
  shield [M]; **air = never (zero damage)** [H].
* **Pure tower chip** is a double/triple-elixir and endgame-lethal tool, weak after the 1/6/2026
  nerf (crown = 58% of troop damage); never blind-chip vs pump/X-Bow decks; gate on the opponent
  having no immediate counter-attack queued [H].
* **Defensive EQ, the rare cases** (user: "only in rare cases"): the 50% ground slow in a pinch on
  a big push; Graveyard after the SECOND skeleton wave; Goblin Barrel when the shadow is 4 tiles
  from the river; swarm answer when Log is out of cycle; keep-the-P.E.K.K.A-in-Firecracker-range
  (LeviathanCR). [H]
* **EQ+Log = the spell stack** (~536 at tournament): kills Magic Archer, Mother Witch, Zappies,
  Evo Firecracker, Evo Archers; the scripted answer to stacked Magic Archers and to GY+Freeze. [H]
* **Anti-EQ recognition:** a building river-hugged at 0-3 denies dual value BY DESIGN — when their
  building+support sits anti-EQ, hold the spell (the Hog+EQ push fails; pressure elsewhere). [H]

### Evo Firecracker
* **Never at the bridge, never the opener.** From depth, always. [H]
* **Kiting table** (defensive, vs melee chasers; her 1-tile recoil maintains the gap): 4th tile
  from bridge, staggered toward the other lane, vs Mini Pekka/Lumberjack/Prince; 5th tile + 2-3
  horizontal vs P.E.K.K.A/Giant Skeleton (kite path can activate our king FOR us); 6th + 3 vs Mega
  Knight/Battle Healer (outside jump range); 6th + 2 vs Bandit (dodges the dash); middle-of-board
  + Ice Spirit/Skeletons distraction vs Elite Barbs. [H]
* **Delay the placement so one volley hits the WHOLE stacked push**, not the front body
  (LeviathanCR, on video). Vs fast bridge threats (Wall Breakers) the opposite: place her right in
  front — at range her rocket's travel time loses the race. [H]
* **Spell-spacing:** never where one spell clips her AND the tower/Tesla; multiple FCs far apart.
  "Never let her die to anything except a spell" — screen her behind Tesla/MM. [H]
* **Offense: layered several tiles BEHIND the Hog** — splash clears the path, sparks carry to the
  tower. [H] **Suppress shots into the king corridor** (a unit 4 in front of their king, 2 from
  the crown tower: her pierce activates their king). [H]
* Cycle her often (evo charges at 2 cycles — spend the EVO copy where spark value is highest);
  protect harder in double elixir. [H]

### Evo Tesla
* **Standard: center, 3 from river** (pulls both lanes, tanks for towers). **4 from river** =
  pulls ONLY building-targeters (no support aggro — the tank-splitting spot; also the reactive
  anti-Golem/Giant spot at 4-from-tower + 4-from-river). **2-3** = the anti-pig-push spot (only
  one that pulls edge Hogs — but snipeable). **1 from river / 0-3** = the ANTI-EQ placement vs
  Hog-EQ mirrors (one spell can't zone Tesla + tower); accept ranged-snipe risk, replaceable on
  3-card cycle. [H]
* **Reactive in single elixir** (SirTag: "last possible second so its health does not decay" —
  lifetime economics), **pre-placed in double**; stack Teslas freely vs decks with no big spell. [H]
* vs LavaLoon: 3-from-river / 2-from-tower pulls the Balloon without the Hound. After a tower
  falls: beside the king, 3 (Giants) or 4 (Golem/Lava, attacks during their deploy) from the top. [M]
* Timing trick: place exactly as enemies cross the bridge → spawn pulse, re-dig, second pulse. [M]

### Mighty Miner
* **The tank-melter and the deck's second body.** Defensively: centrally, ON the tank's path;
  tile-exact body-blocking matters (Leviathan's own miss: "1 tile left, 1 tile down would have
  blocked the Ram Rider entirely"). Skeletons accompany him vs high-single-hit troops so the ramp
  is protected. **Never alone vs swarms** (no splash; stage-1 hit can't one-shot Skeletons) —
  that's what the 1-elixir ability's bomb is for. [H]
* **Ability (Explosive Escape), the trigger list:** swarmed (bomb clears it); Wall Breakers
  incoming (bomb one-shots, knockback resets Battle Ram); dodging a lethal spell/stun;
  splitting a two-lane push (he resurfaces MIRRORED across the center line); converting defense
  into opposite-lane offense. **Bridge-punish pattern:** MM alone at the bridge → they commit
  defenders → pop ability → drop Hog+EQ in the resurface lane. **Scripted counters:** Skeleton
  King (MM on him, tank the ability, pop to finish — "always fully counters"); Archer Queen (pop
  EARLY into her lane — the bomb+knockback wastes her ability). **Do not burn it reflexively** —
  13 s cooldown, good players bait it. When he tanks for a same-lane threat, place the threat
  FIRST, then pop, so the tower keeps targeting him. [H]
* vs Magic Archer decks: MM goes right AT the bridge (blocks the line-shot corridor); never in
  the back of the MA's lane. [H]
* In stalemates: MM in the back BEFORE the Hog (3-card cycle first). [H]

### The Log
* Prediction Log vs bait (pre-log the Skeleton Army onto our own Hog when it's their only answer —
  SirTag, on video); **withhold predictions vs Goblin Delivery decks** (dead card risk). [H]
* **Angle the Log so the bounce lands the unit NEXT TO our building/defender**, not straight — the
  bounce is a targeting tool (Bandit into Ice-Golem range; Executioner into Musketeer range;
  strip the Dark Prince's shield before contact "imperative"). [H]
* Timing: vs Graveyard wait 2–3 s (max skeletons accumulated); vs a walking E-Wiz, roll it to deny
  all-but-one tower hit and kill the Princess behind. Keep the Log for DEFENSE when spell-cycling
  for the finish. [H]

### Skeletons
* Opener-in-back scout; cycle at 9 elixir. [H]
* **The kite spot, tile-exact (from the video short):** vs a bridge Bandit (and dash/charge units
  generally) place them at the arena CENTERLINE ±1 tile toward her lane, on the row level with the
  princess-tower FRONT — deep, between both towers. Her dash pulls her out of the lane onto the
  trio, she's surrounded on arrival, dies to tower+skeletons with ZERO tower damage: 1 elixir vs
  3. The same spot mirrors for either lane. [H]
* Surround a tank; distract Mini Pekka/Prince/Sparky so MM's ramp and the tower go unanswered;
  drop wide to pull a Mega Minion off entirely ("we do not have to deal with it at all"). [H]
* Bridge chip only when their small spell was just spent. [M]

### Ice Spirit
* Default opener at the bridge (except vs Cannoneer/Dagger Duchess). [H]
* **The Hog's escort:** attach vs Mini Pekka decks — the freeze on the defender guarantees a
  tower hit ("you need to go in for an ice spirit with your hog so that you can freeze the mini
  pekka and guarantee a hit"). Also the anti-Tornado shove body. [H]
* At the river IN FRONT of a crossing enemy support: converts an ignorable unit into one they must
  answer (any answer is a negative trade for them). [M]
* Defensive freeze buys Tesla/MM a beat; the cheapest tempo card — cycling it toward the Hog is a
  play, not a leak. [H]

## 3. Matchup adjustments (one line each)
* **Buildings decks:** the deck's designed prey — EQ the building every Hog push; watch for
  anti-EQ plants (hold EQ, pressure anyway). [H]
* **Beatdown (Golem/Giant/Lava):** Hog opposite lane the instant the tank drops, ADD NOTHING;
  FC behind the king on the push lane; EQ every pump; never let the counter-push stack. [H]
* **P.E.K.K.A / double-lane bridge decks:** the exception — no opposite-lane pressure in single;
  defend same-lane (Tesla + freeze support), punish only when P.E.K.K.A is out of cycle. [H]
* **Bridge spam:** usually no building → Hog goes alone, EQ becomes tower chip; hold Tesla for the
  win-condition, predict their bridge Firecracker. [H]
* **Cycle mirrors:** never let one spell hit Tesla+tower; EQ their fragile building; Hog-in-the-
  back double-Hog wave is the mirror-breaker; only losable by getting outcycled. [H]
* **Graveyard/splashyard:** Tesla touching the tower eats GY skeletons; EQ the Tombstone; Guards-
  style answer here is Skeletons+tower; vs splashyard attack the OPPOSITE lane; EQ+Log answers
  GY+Freeze. [H]
* **Logbait:** punish the Rocket window (Hog in the back as it flies); prediction Log; never let
  Princess sit (we have no Fireball — FC snipes her). [M]
* **Miner/WB bait (the hard counter):** do NOT waste EQ on their Bomb Tower early — constant
  pressure outranks spell value; stack Firecrackers (they can't remove her). [H]

## 4. Counter-intel (what beats US — the bot should not be surprised)
* Standard-time EQ never breaks a spaced Musketeer+building+spirit defense; our EQ must vary
  timing or wait for commitment. [H]
* A repeated pre-cast EQ point gets dodged — they shift the building higher once we show the
  habit. [H]
* Mini Pekka in their cycle deters our lone Hogs (4-for-4, zero damage); track it. [H]
* Edge/pig-push Hogs are denied by an air troop dropped in front of the jump or an Ice Golem on
  the landing tile; vary placements. [H]
* Their 2-3 Tesla plant catches even auto-pig-pushed Hogs. [H]
* Anti-splash spacing (stagger defenders so no spell/splash doubles) is why good defenses hold —
  ours should space the same way. [H]
