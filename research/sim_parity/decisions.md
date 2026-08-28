# Sim-parity decisions — owner adjudications, dated

Owner rulings are FINAL AUTHORITY and outrank wiki prose (which lags reworks). Phase I implements
these as written; a wiki page that contradicts one is stale, not a conflict to re-litigate.

---

## 2026-08-25 — Scope rulings (locked at plan approval)

1. **Heroes and champions are ENEMY-SIDE ONLY.** Full engine effects, opponent AI triggers and
   threat/doctrine recognition, but NO action-space change: our decks keep their identities and
   existing checkpoints keep loading. Playable support is deferred to a future deck redesign.
2. **Stat conflicts are FLAGGED, never auto-overturned.** The sweep never overwrites a
   `verified: true` or curated balance-corrected value. Conflicts go to one batch review table
   (current value, sourced value, evidence) for the owner to adjudicate in one sitting.
   Precedent: `spark_dps_small` 60-vs-48 was deliberately left alone for exactly this reason.
3. **ALL ~24 abilities get FULL engine fidelity.** No simplified approximations anywhere,
   including Monk's projectile reflection. Meta frequency sets BUILD ORDER only, never depth.

## 2026-08-25 — Champion lifecycle (owner, in-game observation)

The wiki could not answer these; the owner verified them in the client. **These are the spec.**

4. **Champions are NOT removed from the hand while their body is alive.** You can cycle back to the
   champion card and play another one. => Do NOT implement a hand-lock. The sim's current
   no-hand-lock behaviour is CORRECT, and the mechanics audit's "champion body-blocks-replay" item
   is CANCELLED, not deferred.
5. **Two bodies of the same champion CAN coexist**, and **the ability button corresponds to the
   MOST RECENTLY PLAYED body.** => engine: `champion_ability(team)` must select the newest living
   champion body, NOT "any body with a use left" (which is what hogeq's current implementation
   does — see `hogeq/src/clashrl/sim/engine.py` `_ability_uses_left` / `champion_ability`).
   ⚠ THIS IS A LIVE BUG in the existing Mighty Miner implementation once two bodies can coexist.
6. **Single use is PER BODY, not per match.** A freshly deployed body carries a fresh use.
   => the existing per-body `ability_left` model is correct; do not convert it to a match-level
   budget. (Consistent with the 4/8/2026 single-use balance change.)
7. **The elixir refund applies to champions as well**: if the body dies before the ability goes
   off, the ability's elixir is refunded. => engine: refund `ability_cost` if the champion body
   dies between activation and effect resolution (i.e. during `ability_delay`).
8. **Skeleton King does not accrue further souls after using its ability.** => the soul bar stops
   filling for a body once that body has spent its use. (Follows naturally from single-use-per-body.)

### Source-staleness cutoff, corrected
The Champion Rework is dated **29/9/2025** (2025 Quarter 3 Update, Version History/2025 revid
436887) — NOT 2026 as first assumed when the plan was written. Champion-lifecycle text predating
**29/9/2025** is stale; the 4/8/2026 single-use change is a separate, later ruling on top of it.
Pages KNOWN to carry stale lifecycle text (do not implement from them): Goblinstein (revid 437348,
still claims the champion leaves the card cycle), Cards page trivia (revid 437053, contradicts its
own rule text on the same revision).

### Still open (nobody has answered)
* Whether an older, not-yet-used champion body keeps accruing souls while a newer body is out.
  Ruling 8 covers the post-use case only. Low impact: the button drives the newest body (ruling 5).
* Whether the per-page ability cooldowns (Archer Queen 17s, Skeleton King 20s, etc.) retain any
  meaning under single-use, or are simply dead numbers. None of these pages were updated for the
  4/8/2026 change.

## 2026-08-26 — Owner rulings (batch 2)

9. **Rarity level floors (owner; verify from wiki during R2):** commons start at level 1, rares at
   3, epics at 6, legendaries at 9, **champions at 11**. This RESOLVES conflict C1: the old
   "Explosive Escape 440 @ L13" reverse-derivation sought an integer LEVEL-1 base for a champion —
   a level that does not exist for the rarity — and landed on 366@L11. Anchored at the champion
   floor, the wiki's integer base **332 @ L11** reproduces the owner's observed 440 at L14
   (332 -> 365 -> 402 -> 440/442). => C1 RESOLVED: `ability_bomb_damage` 366 -> **332** (@L11
   reference), lands in Phase I stage I5. The KB comment "not published" is deleted with it.
   FOLLOW-ON for R2: check every value in the KB that was REVERSE-DERIVED from an in-game
   observation for the same anchor error, and check `levels.py` inversion (`base_for`) against
   full wiki ladders per rarity — champion/legendary rows may need floor-aware anchoring.
10. **Golden Knight Dashing Dash (owner; verify from wiki during R2):** he keeps dashing until
    there are NO more targets in range OR the max target count is reached, whichever comes first;
    he stops AT THE LAST TARGET'S LOCATION and then moves/attacks like a normal troop. => resolves
    agent A's load-bearing unknown: "no targets in range" ENDS the ability (no pause-and-resume),
    and there is no return-to-origin. Chain cap per the page: 10 dashes.

### Ruling 10 AMENDED by wiki verification (2026-08-26)
The dash chain has a documented THIRD terminator the ruling omitted. Golden Knight page (revid
437147), Ability section, verbatim: "He will stop dashing after dashing 10 times, if no other
valid targets are within range, **or if the last target hit is a Crown Tower**" (introduced
4/4/2022). The tower can still BE a dash target and take dash damage; the chain just always ends
there. Everything else in ruling 10 is supported (10-dash cap, no same-troop repeat, chain
continues past a dead target since 1/11/2021) or silent-but-consistent (stops at last target,
no return-to-origin). Engine spec: THREE terminators.
GK extras for I7, wiki-sourced: dash damage 335@11 vs 161 normal; backwards dashes legal since
5/5/2025; dash crosses the river; cannot force King Tower activation; dash TRAVEL SPEED is
unpublished — analog 500 (Bandit / Boss Bandit tables) as a placeholder marked untested; the
0.05s "Dashing Dash Delay" (3/11/2025) is defined nowhere — best reading is an intra-chain
wind-up, still open.

### R1 CLOSED 2026-08-26 — gate met
Lint 24/24 specs schema-complete; hero set independently re-derived and exact (16 live, 2
announced 7 Sep 2026); rarity floors confirmed verbatim from the Cards page (Common 1 / Rare 3 /
Epic 6 / Legendary 9 / Champion 11) and 440=L14 is EXACT and UNIQUE under levels.py (366
corresponds to NO level under any model); critic: no live content missing, no third variant
class (Merge Tactics out of scope), no new tower troops.
⚠ IMPORTER TRAP (critic): Elite Barbarians/Evolution is live but its stub subpage is
UNCATEGORIZED — a category-only walk undercounts evos at 41. Card Evolution#History is the
authority. Upcoming-content stubs (Werewolf + Dark Spirit 4/10/2026, Ghost Spirit 6/11/2026,
Ice Sorceress + Ice Dragon 5/12/2026, ...) are calendar intel ONLY — the channel is unmoderated;
never auto-import from stubs.

## 2026-08-26 — R2 ADJUDICATION (owner, all 14 decisions). THE APPLY SPEC.

Bulk approvals per recommendation: **#1** KBGAP 110 apply · **#2** LAG 77 apply · **#3** CROWN 15
apply + FIX crown_damage_audit.py regex ("of ITS full damage") · **#4** PARENT 7 apply · **#6**
GLOBAL chain arc: per-card `chain_tiles` from the wiki (ED family = 4.0 tiles; supersedes the 3.0
global AND cards.yaml's 3.5 comment) · **#7** ROUNDING: adopt wiki floor() for derived DPS ·
**#12** DUP: merge's pick stands (note: goblin_curse 35 = damage PER SECOND, spell lasts 6 s →
total 210). Plus the 101 sweep `update` verdicts and 66 pins stand.

**#8 ENGINE/SCHEMA — owner: do these NOW (pulled forward from Phase I)** so implementation isn't
blocked later. In the WORKTREE, never the live tree.

### #5 — verified:true rows, row rulings (each of these is the new spec)
* tesla is COMMON rarity; **tesla_evo hitpoints = base = 1182 @ L11** (evo hp same as base).
* boss_bandit's passive dash triggers on **every ground unit INCLUDING crown towers** (ground-
  targeting troops can hit crowns, so the dash can too). NB contrast Golden Knight: his CHAIN
  merely ENDS at a crown tower.
* baby_dragon_evo: wiki correct. * bats_evo heal per hit = **76** (wiki).
* firecracker_evo: **wiki correct for ALL its entries** → this RESOLVES the long-flagged
  `spark_dps_small` conflict: **60 → 48** (the owner's old verified row is overturned by the
  owner). Split spark durations apply too (big 3.0 s / small 2.5 s). §6.7 is CLOSED.
* giant_snowball_evo: roll range **4.0 tiles**, hits **air AND ground** — and VERIFY the base
  giant_snowball also hits both (KB may say ground-only).
* **earthquake damage = 81 @ L11, not 84** (overrides the 2026-08 HANDOFF card-data row).
* bomber rarity = **common**.
* decoy goblins deploy time = normal goblin-barrel goblins (1.1 s confirmed correct).
* lava_pups speed: wiki. * spirit_empress: **309** is correct.
* suspicious_bush: **1.6 tiles = the POP distance** — the bush releases its goblins 1.6 tiles from
  its target when it arrives (engine semantic, not a plain stat).
* furnace spawn speed **5 s**.

### #9 — page-self-contradictions, row rulings
* inferno_dragon_evo keeps ramp damage **7 s** (wiki). * royal_delivery: the 12% cut applies to
  the **SPAWN damage**, not the recruit's own damage. * fisherman: **NO slow anymore** (remove).
* phoenix spawn interval **3.8 s** (not 4.3). * royal_ghost: **1.8 s** to re-cloak.
* cannon_evo volley damage **281 @ L11** (nerfed); crown-tower damage: use the most up-to-date
  published number.

### #10 — split votes, row rulings
* ALL wiki load_time entries correct. * **Mighty Miner ability bomb radius 2.5 CONFIRMED**
  (conflicts.md C2 CLOSED — the sim's guess was right). * mortar AND mortar_evo hit speed
  **4.7 s**. * ghost_souldier invisibility time = royal_ghost's. * giant_skeleton collision: sweep
  recommendation accepted. * phoenix_egg → revival **3.8 s**. * ram_rider hit speed: most
  up-to-date entry.

### #11 — unpublished values, row rulings
* goblin_cage: **NO sight stat** (cannot attack while the cage stands); the "20" is LIFETIME.
* lumberjack_ghost: **untargetable and damage-immune** (no troop/building can target it, no
  damage from any source), but spells CAN still knock it back; it dies shortly after leaving its
  rage pool, or when the rage expires.
* royal_delivery: **cannot hit crown towers** — discard crown_tower_damage entirely.
* **FURNACE IS A TROOP NOW** — no lifetime stat. ⚠ ENGINE ITEM: the sim models it as a spawner
  BUILDING with lifetime decay; re-model as a troop that spawns (movement, targeting, no decay).
* Everything else in #11: keep sim values, tag `unsourced: true` per recommendation.

### #13 / #14
* little_prince: **implement Royal Rescue** (guardian ability, I7 scope); `royal_rescue_damage`
  field is real and stays. goblinstein row kept as-is.
* lumberjack_ghost lifetime **4.5 s = the rage duration**, conditional on staying inside the pool
  (leaves early → dies early). firecracker_evo `spark_dps_large` 192: wiki correct.

## 2026-08-26 late — Owner rulings (batch 3), given before going offline

11. **Electro Dragon chain cannot hit the same target twice** in one attack. VERIFIED ALREADY
    CORRECT: `_multi_hit` keeps `seen = {id(ref)}` and filters `id(e) not in seen`. The 533.6 seen
    in the arc measurement was TWO SEPARATE ATTACK CYCLES, not one chain double-hitting. Add a test
    pinning the rule so it cannot regress.
12. **Evo Electro Dragon's extra chain damage is 1/3 of the original damage** — owner gave "64 at
    level 11". ⚠ DISCREPANCY TO RESOLVE, DO NOT SILENTLY PICK EITHER NUMBER: the KB carries
    `electro_dragon_evo.damage = 267` @L11, and 267/3 = **89**, not 64. 64 implies a base of 192.
    IMPLEMENT THE RULE, NOT THE CONSTANT: add `chain_falloff_frac: 0.3333` so extra hits deal
    damage/3 whatever the card's damage turns out to be, and the first 3 targets keep FULL damage
    WITH the stun while later bounces deal the reduced damage with NO stun (the researched shape).
    Then the absolute number follows the KB automatically. Flag the 267-vs-192 question for the
    owner; if 192 is right, that is a separate damage correction.
13. **New PPO: target ~20k with an auto-stop on decline** — stop if the rolling eval average falls
    for 3 consecutive checkpoints. The stopped run peaked at 18k and then decayed for 8k more; a
    40k target mostly buys decline. Best-checkpoint gate stays on regardless.
14. **Spell A/B experiments run BEFORE the long PPO**, on the finished parity sim. They are short
    (~90 min/arm) and would otherwise contend for CPU with a long run (§2's contention trap). Their
    results feed the long run's reward settings.

**Autonomous mandate (owner, going to bed):** proceed I7 -> I8 -> I9 -> I10 -> merge -> spell
experiments -> new PPO, without waiting for approval between stages.

## 2026-08-27 — Owner rulings (batch 4)

16. **Evo Electro Dragon's chain repeats — the two halves get DIFFERENT rules.** Resolves the
    ED-3 conflict (the Evolution page's "can hit the same target more than once" against ruling 11).
    * **PRIMARY chain** (the first `chain_full_hits` = 3 full-damage-with-stun hops): ruling 11
      STANDS. It can never hit the same body twice.
    * **SECONDARY chain** (the 9 falloff bounces at damage x `chain_falloff_frac`, no stun): MAY
      return to a body it already hit, but only after bouncing to a DIFFERENT body first. No
      immediate self-repeat — it must alternate.
    Implemented in `_multi_hit`'s chain branch: the exclusion set is `seen` for a primary hop and
    `{id(cur)}` for a secondary one.

    **MEASURED re-baseline**, one swing into a line of knights 3 tiles apart (published arc 4.0),
    towers disarmed so nothing else enters the ledger:

    | bodies in arc | before (ruling 11 only) | after (ruling 16) | change |
    |---|---|---|---|
    | 1 | 192.0 | 192.0 | — |
    | 2 | 384.0 | 384.0 | — (the chain never reaches its secondary half) |
    | 3 | 576.0 | **1151.9** | **+99.98%** |
    | 4 | 640.0 | **1151.9** | **+80.0%** |
    | 6 | 768.0 | **1151.9** | **+50.0%** |
    | 13 | 1151.9 | 1151.9 | — (never ran out of fresh targets) |

    So the card now always spends its full 12-hit budget once it has three bodies to alternate
    between, instead of dying when it runs out of fresh ones. SCOPE: `electro_dragon_evo` is the
    only card in the KB with `n > chain_full_hits`, so it is the only card the ruling can reach —
    the base Electro Dragon (`full_n == n == 3`) and the Electro Spirit (`chain_full_hits` 0, so
    `full_n` falls back to n = 9) are byte-for-byte unaffected, and both are pinned by tests.

    ⚠ **ONE DELIBERATE DEVIATION FROM THE LITERAL WORDING, measured and flagged.** "Exclude only
    the immediately previous node" taken literally makes the nearest-target rule OSCILLATE: from
    the third body the two nearest are the first and the fourth, `min` breaks the tie toward the
    first, and the bolt ping-pongs between two adjacent bodies for its whole remaining budget.
    MEASURED under that literal reading on the 13-knight line: the total stayed at 1151.9 but only
    THREE bodies took anything, against twelve before the ruling — a large unmeasured NERF to the
    card's spread, and the opposite of the page line ("will chain between targets infinitely") that
    motivated the ruling. It also produces NO total-damage re-baseline in any configuration, which
    contradicts the ruling's own instruction to report one. So the implementation prefers a body
    nothing has hit yet and revisits only once it has run out — the revisit then fires exactly
    where the chain used to DIE. Both readings satisfy every test the ruling asked for.
    **OWNER: if the oscillation was intended, it is a one-line change (drop the `pool` line).**

17. **Heroes and CHAMPIONS share the slot — the Hero slot IS the Champion slot.** Owner, confirming
    the wiki, and the structural conflict I8 recorded is now closed.
    * Heroes revid 437509: *"Only two Heroes can be in a deck at a time, and only in the Hero and
      Wild slots. **Those slots are also shared with Champion card**, which means that the player
      can have 1 Hero and 1 Champion at the same time."*
    * Cards revid 437053, RULE TEXT: *"Up to 2 Champion cards can be present in a deck at any
      time."* ⚠ The SAME revision's TRIVIA says *"a deck can only have 1 Champion Card at a
      time"* — and decisions.md already records that section as the stale half ("Cards page
      trivia, contradicts its own rule text on the same revision"), so the rule text wins.
      **CAP VERIFIED: 2 champion cards, 2 ability-bearing slots.** The pool never exercises the
      difference — no deck in it holds two champions.

    THE STRUCTURAL DIFFERENCE that makes this unlike I3 and I8: an evolution and a hero are
    VARIANTS of a card the deck already holds, so the slot DRAWS one of the deck's 8. A champion IS
    one of the deck's 8. Holding it has already spent the slot — there is nothing to draw and no
    probability to put a prior over. So the model is:
    * **Champion/Hero slot** — the first champion card if the deck holds one, else the always-fills
      hero draw over `hero_candidates`.
    * **Wild slot** — the second champion card if the deck holds one, else the even split over
      {second evo, hero, nothing}, renormalised over whatever is still legal. A wild EVOLUTION does
      not consume an ability slot (an evolution is not ability-bearing), so a one-champion deck can
      still field one.
    * `sim.wild_champion_prob` is the new knob, default **1.0 rather than an even share**, and
      documented in config.yaml as UNMEASURED-BUT-FORCED for exactly the reason above. Setting it
      to 0 models a loadout the game does not permit and exists only for ablation.

    **MEASURED, 20 draws x 1000 decks = 20000 loadouts, one shared RNG stream:**

    | ability-bearing slots | BEFORE | AFTER |
    |---|---|---|
    | 0 | 1100 (5.5%) | 1100 (5.5%) |
    | 1 | 14048 (70.2%) | **15872 (79.4%)** |
    | 2 | 4591 (23.0%) | **3028 (15.1%)** |
    | 3 | **261 (1.3%)** | **0 (0.0%)** |
    | over the cap | 261/20000 = 1.30% (0.86% of match weight) | **0/20000 = 0.00%** |
    | hero slot filled | 16820 (84.1%) | **14080 (70.4%)** |
    | wild hero | 2373 (11.9%) | **3028 (15.1%)** |

    **POOL CENSUS (the count the owner asked for):** **241 of 1000 decks hold a champion card**
    (1675/5947 raw weight = **28.2%** of matches; **29.0%** after the config's ladder skew), and
    **none holds two** — histogram 0:759 1:241. By card: golden_knight 69, goblinstein 37, monk 31,
    mighty_miner 24, skeleton_king 23, little_prince 22, boss_bandit 21, archer_queen 14.

    ⚠ **THE BRIEF'S PREMISE WAS OFF, and the correction matters.** "137/1000 decks (15.3% of deck
    weight) get THREE ability-bearing slots" is not what was measured. **137 decks (948/5947 =
    15.9% of weight, not 15.3%)** hold a champion AND a hero candidate, and those fielded the
    champion's ability PLUS a GUARANTEED hero — that is TWO slots, at the cap, but with the hero
    handed over free instead of being drawn. Only the subset that ALSO won a wild hero reached
    three, and that is **1.30% of loadouts (19 of 1000 decks at seed 0, 0.86% of match weight)**.
    Both were real bugs — the free hero is the bigger one by volume, the cap violation is the
    illegal one — and ruling 17 fixes both. The visible training effect is the hero-slot fill rate
    falling **84.1% → 70.4%**.

    Wiring mirrors I3/I8 exactly: `sim/meta_decks.py` (`has_champion` / `champion_candidates`,
    validate-never-trust in the loader), `sim/opponents.py` (constructor + `make_opponent`),
    `tools/evo_audit.py` (champion census, ability-slot histogram, and it now FAILS on any deck
    over the cap). `meta_decks.yaml` gains only a header comment: unlike an evolution or a hero, a
    champion is not a hidden variant — it is visible in `cards:` — so there is nothing to declare
    and nothing that can go stale. The `champion_candidates:` key is still honoured if present.

18. **Royal Delivery is own-half only.** Owner: it *"can only be cast on the caster's half of the
    map (and whatever pocket presents itself)"*. It is a SPELL that DROPS A TROOP, so it is placed
    like a troop rather than aimed like a spell.

    **VERIFIED ON THE WIKI, and the page is more specific than the ruling.** Cards revid 437053,
    verbatim: *"Generally, spells are temporary and can be cast anywhere in the battlefield (**with
    the exception of The Log, Barbarian Barrel, and Royal Delivery**), including on top of
    buildings, while buildings ... and troops ... can only be spawned on the player's territory
    (with the exception of Miner and Goblin Drill)."* **THREE exceptions, not one.** See the
    conflicts.md entry — the other two are recorded, not flagged.

    Implemented as a KB FLAG (`flags: [own_half_only]`) rather than another literal, so the next
    one is data: `CardSpec.own_half_only` feeds the `anywhere_ids` carve-out in all three places
    that build it (`sim/env.py`, `env.py`, `play.py`), in both decks.

    **MEASURED clamp distance** (icebow's 18x24 board grid, deploy line at row 13 of 24): a Royal
    Delivery aimed at the enemy BACK row lands at row 13 — **13 grid rows / tiles moved**, and the
    LANE is never moved. Every enemy-half row clamps to the deploy line; a pocket placement is
    still legal (`deployable_mask(anywhere, pocket=...)` adds cells and every added cell is across
    the river).

    **THE REGRESSION THIS MUST NOT CAUSE.** An earlier fix (§5) had to undo the exact opposite bug:
    `anywhere_ids` was the literal `{rocket, miner}`, so EVERY other spell was forbidden from the
    enemy half — the offensive Log, the Tornado river lock and hogeq's whole Hog+Earthquake combo
    were actions the policy could not take at all. `test_every_OTHER_spell_still_goes_anywhere`
    asserts rocket / tornado / the_log / earthquake / fireball / arrows / zap all stay in the set,
    so this cannot come back through the new door.

    **SCOPE, stated plainly: this is currently INERT for both shipped decks.** Neither icebow
    (tornado, tesla_evo, ice_wizard, x_bow, rocket, knight_evo, the_log, skeletons) nor hogeq
    (hog_rider, firecracker_evo, mighty_miner, tesla_evo, the_log, earthquake, skeletons,
    ice_spirit) holds Royal Delivery, so no checkpoint's behaviour changes — pinned by
    `test_the_shipped_deck_is_UNCHANGED_by_this_ruling`. The ruling is a correctness fix to the
    RULE, and two follow-ons where it would bite are recorded in conflicts.md.

19. **Spawned-body elixir prices — three of the twenty-five.** I10 measured the hole: 25 KB keys
    carry no `elixir`, and every one falls through `build_spec`'s `or 4` to read as **4 elixir of
    enemy investment** — a Goblin Barrel decoy goblin, a Golemite and a Skeleton King's Skeleton
    each priced like a Knight. That number is read ~30 times in icebow and ~27 in hogeq, by
    `_trade_reward` (elixir_trade), `_side_value` (counterfactual), `_hog_wincon`,
    `_ability_value`, icebow's rocket / nado / bow-overcommit terms, and by `threat_value`, which
    prices a fully-ignored card at 0.120 tower per elixir — so an overpriced body also inflates
    what it costs to IGNORE it.

    Owner prices:
    * `magic_archer_decoy` → **2** — one decoy per Triple Threat, so per-body = per-activation.
    * `guardienne` → **3** — one body per Royal Rescue, likewise.
    * Skeleton King's Skeletons → **3 AT FULL CHARGE**, for the WHOLE summon.

    **THE SKELETON KING'S NUMBER IS A TOTAL.** A full charge is `ability_spawn_count` 6 plus
    `_SOUL_CAP` 10 = **16 Skeletons** (the page: *"With no souls, the Skeleton King will spawn 6
    Skeletons, but with a maximum of 10 souls, he can summon 16"*), so the per-body share is
    **3 / 16 = 0.1875** and MEASURED a full summon totals **exactly 3.0000**. An uncharged 6-body
    summon comes to **1.1250**, which is the point — an uncharged King has invested less.

    ⚠ **NOT `3 / max_souls`.** The ruling offered that formula. It gives 0.3, and 16 x 0.3 =
    **4.80** — 60% over the number the ruling set. The divisor is the SPAWN COUNT, not the soul
    bar. Pinned by a test so the wrong divisor cannot be reintroduced from the ruling text alone.

    **WHY PER-BODY rather than "price the activation, leave the bodies at 0"** (the ruling's other
    option): the reward layer has no concept of an activation's value. `ability_cost` is what the
    PLAYER PAYS — the Skeleton King's is 2, a published number the engine deducts — which is a
    different quantity from what the summoned bodies are WORTH in the opponent's ledger, and all
    ~57 call sites read `spec.elixir` on a BODY. Pricing per body reaches every one of them at
    once and cannot be forgotten by a 58th, and it degrades correctly for a partial charge.

    That required widening `CardSpec.elixir` **int → float**: `int(0.1875)` is 0. Inert for the
    ~178 cards whose cost is a published integer (4 == 4.0 everywhere it is read), and pinned by
    a test that sweeps every KB row. It also closed a latent bug in the same expression — the
    `or` chain treated a declared `elixir: 0` as MISSING and fell through to 4, so the one value
    that could not be expressed was the one I9's Clone needed (which is why the clone sets
    `elixir = 0` on the built SPEC instead). No shipped row carries 0, so nothing changed.

    All three PINNED in `config/import_pins.json` (181 → **184** pins, byte-identical pair) via
    `gen_pins.py`'s new `RULING19_PINS`, so a re-import cannot take them back to null → 4.
    ⚠ `magic_archer_decoy` keeps **`verified: false`**, deliberately: `verified` is a WHOLE-ROW
    import guard, and that row's damage / hit speed / range are explicitly open questions
    (conflicts.md I8). Flipping it would freeze an unverified guess against future correction.
    The pin is the per-FIELD mechanism, and `import_pins.json`'s own semantics say pins outrank
    `verified` — so the elixir is protected without asserting anything about the rest of the row.

    **THE OTHER 22 ARE STILL AT 4** and are listed for the owner in conflicts.md's checklist.

20. **The Log and the Barbarian Barrel: the CAST POINT is own-half, the CORRIDOR still crosses the
    river.** Owner, 2026-08-27: *"The Log's cast point is restricted to the caster's own half (plus
    pockets), but its corridor still rolls across the river."* This finishes ruling 18, which named
    the same wiki sentence and deliberately shipped only one of its three cards.

    Cards revid 437053: *"spells ... can be cast anywhere in the battlefield (WITH THE EXCEPTION OF
    The Log, Barbarian Barrel, and Royal Delivery)"*. Two independent per-card confirmations, both
    archived: `Barbarian_Barrel.wikitext` — *"It can only be deployed on the player's own side"* —
    and `Barbarian_Barrel_Hero.live.wikitext` (revid 437523), which repeats it verbatim for the
    hero form. `own_half_only` added to both KB rows; no engine change was needed, because ruling
    18 had already built the machinery (`sim/env.own_half_spell_ids` subtracts from `anywhere_ids`,
    `Actions.deploy_clamp` does the work).

    **MEASURED**, in the SIM'S BOARD SPACE (18x24 grid, river at ny 0.5, deploy line gy=13 of 24):

    | card | aimed at | clamps to | cast ny | corridor reaches | past the river |
    |---|---|---|---|---|---|
    | `the_log` (9.6 t) | gy=0 | gy=13 | 0.5625 | 0.2625 | **7.60 tiles** |
    | `barbarian_barrel` (4.5 t) | gy=0 | gy=13 | 0.5625 | 0.4219 | **2.50 tiles** |
    | `rocket` / `tornado` | gy=0 | gy=0 (unclamped) | 0.1000 | — | — |

    So the OFFENSIVE Log survives the clamp with 7.6 tiles to spare, which is the half of the
    ruling that makes it non-trivial: a test that asserted only the cast point would pass against a
    corridor of length zero. Executed as well as computed — a Log cast at the clamped deploy line
    took a Knight standing 4.0 tiles beyond the river from **3000 → 2734 hp**.

    The barrel's 2.50 tiles is independently predicted by its own page: *"If the Barbarian Barrel
    is placed at most 2 tiles from the river, the Barbarian will spawn at the opposing side of the
    Arena."*

    ⚠ **MEASUREMENT TRAP, and it cost a pass.** `ActionSpace(cfg)` is the LIVE action space: its
    `arena_box` is the screen rectangle and `cell_center` runs the perspective warp, so gy=13 comes
    back as **ny=0.4788** — already "past" a river the sim puts at 0.5, which reads as the clamp
    having FAILED. The sim re-anchors the same grid through `sim.env._board_action_space`, where
    every anchor is an identity point and gy=13 is a board-true 0.5625. This is the same shape as
    the detector-audit trap (an offline tool reading live-screen coordinates); it is now stated at
    the top of `test_log_own_half_r20.py`.

    ⚠ **SCOPE — unlike ruling 18, this is NOT inert.** Both shipped decks play The Log, so both
    policies' action spaces change: the Log's legal cells drop from all 432 to the 198 on our own
    half (plus pockets). Ruling 18's `test_the_shipped_deck_is_UNCHANGED_by_this_ruling` could not
    survive that and was replaced by
    `test_the_shipped_deck_own_half_set_is_EXACTLY_the_flagged_cards`, which asserts the honest
    thing: the set changes by exactly the flagged cards and by nothing else.

    ⚠ **THE REGRESSION THIS MUST NOT REOPEN.** §5's "every spell was forbidden from the enemy half"
    bug (`anywhere_ids` was the literal `{rocket, miner}`) deleted the offensive Log, the river
    Tornado lock and hogeq's whole Hog+Earthquake combo from the action space. Ruling 20 adds
    exactly TWO cards BY KB FLAG and narrows no rule; `NothingElseWasClampedTests` pins rocket,
    tornado, earthquake, fireball, arrows, zap and goblin_barrel as unclamped, and the flagged set
    as exactly the wiki's three.

    11 new tests, byte-identical in both decks (`test_log_own_half_r20.py`); ruling 18's file
    updated from one flagged card to three.

    **OPEN, recorded not fixed:** the engine rolls The Log **9.6 tiles** (`_LOG_ROLL_LEN`), but the
    attributes table's Range cell reads **10.1** and the 4/8/2020 balance entry says *"decreased
    The Log's rolling distance to 10.1 tiles (from 11.1 tiles)"*. The sim is one balance update
    stale. Not touched here under the one-change rule — see conflicts.md.

21. **A rolling spell SWEEPS its corridor over time.** Owner, 2026-08-27: *"the log doesn't damage
    everything in the corridor at once, it takes time to roll the entire 9.6 tiles, damaging a
    smaller area as it sweeps across the corridor."*

    **WHAT WAS ACTUALLY WRONG.** `_resolve_roll` was called once from the spell-resolution path and
    damaged the whole corridor in a single frame — and **`roll_speed` was DEAD DATA**: the KB
    published it for `the_log` (200) and `giant_snowball_evo` (300), and `build_spec` never read it,
    so the number that governs the entire mechanic reached nothing. A rolling spell is now a live
    `_Roll` object ticked by `advance()`, the same shape `_Vortex` and `_Zone` already use.

    **THE SPEED CONVERSION, verified rather than assumed.** CR quotes speeds as a rating in units —
    "Very Fast (120)", "Medium (60)" — and `card_import._SPEED_UNITS_PER_TILE = 60.0` is the divisor
    every troop's `speed_tiles` already goes through. The engine now carries the same constant (it
    must not import the scraper) and a test asserts the two agree, so a rolling corridor and a
    walking Barbarian can never end up on different scales.

    | card | tiles | raw | tiles/s | sweep |
    |---|---|---|---|---|
    | `the_log` | 9.6 | 200 | 3.3333 | **2.88 s** |
    | `barbarian_barrel` | 4.5 | 200 | 3.3333 | **1.35 s** |
    | `barbarian_barrel_hero` | 4.5 | 200 (inherited) | 3.3333 | **1.35 s** |
    | `giant_snowball_evo` | 4.0 | 300 | 5.0000 | **0.80 s** |

    The Evo Snowball is much the fastest — a higher speed over a shorter distance — and the barrel
    is just under half The Log.

    **MEASURED BEFORE → AFTER**, one Log, bodies pinned in place:

    ```
    whole corridor damaged at t=0    ->   swept over 2.88 s
    body 0.5 tiles ahead   t=0.00 -> 0.15 s      body 4.0 tiles ahead  t=0.00 -> 1.20 s
    body 8.0 tiles ahead   t=0.00 -> 2.40 s      body 9.5 tiles ahead  t=0.00 -> 2.85 s
    a body 8 tiles ahead that steps clear at 1.5 s:  266 damage -> 0
    a body outside the lane that steps in at 1.5 s:    0 damage -> 266
    ```

    ⚠ **THE HIT RULE TOOK THREE TRIES, and the two wrong ones are worth recording.**
    * this frame's **band** `[prev_dist, dist]` **TUNNELS**: an enemy walking toward us closes at up
      to ~5.3 tiles/s while a 0.05 s frame's band is 0.167 tiles wide, so a body can cross the whole
      band inside one tick and never be tested against it;
    * the cumulative **swept region** `[-back_slop, dist]` cannot tunnel but hits things the roll
      has already gone past. MEASURED: a Goblin Barrel's goblins landing 3 tiles **behind** a Log's
      edge took the Log's damage from a roll that had passed that tile a second earlier.
    * what ships is **"the leading edge sweeps past you"**: `_Roll.ahead` enrols a body the first
      tick it is seen at or beyond the edge (or, on the launch tick, anywhere inside the back slop),
      and only an enrolled body can be hit. `_Roll.hit` — keyed on `deploy_seq`, never `id()`,
      because CPython recycles a dead body's address — holds each to one hit per cast.

    Knockback now lands **as the edge reaches each body** rather than to the whole corridor at once,
    the `_LOG_BACK_SLOP` origin tolerance still applies, a tower is chipped once when the edge
    arrives, and Snow Bowling's carried bodies **travel** with the roll instead of teleporting (the
    old code carried an apology in its comment for exactly that).

    **THE SPELL VERDICT HAD TO MOVE WITH IT.** `_arm_spell_check` scheduled the whiff/credit
    settle at `land + 0.35 s`, i.e. **0.75 s** after a Log's cast — with the leading edge **1.17 of
    9.6 tiles** along. Every Log that killed anything past that first tile would have been billed
    `spell_waste` for damage it had not dealt yet. The settle now adds the roll's own duration
    (0.75 → **3.63 s**), the same fix §5 records for LIVE spells ("judged before they arrived",
    which is why `spell_eval_time` went to 4.0). A blast spell's timing is untouched, and pinned.

    `sim_view` draws the live roll: the swept part, the part still to come, and the leading edge
    with `dist/roll_len` — before this the debugger showed the full corridor at cast and then
    **nothing at all** for the 2.88 s the roll was working.

    **DRILL PASS RATES — the expected change, and it is a finding about the DRILLS, not the engine.**

    ```
    icebow  log_the_barrel_on_landing  scripted 100% -> 56%     log_the_ground_swarm  92/92 -> 80/80
            hold_the_spell_for_a_target 92/80 -> 88/100         ignore_the_ignorable  doctrine 20% -> 8%
            matchup_bridge_spam 20 -> 36   matchup_hog_cycle 84 -> 100   matchup_lavaloon 56 -> 68
    hogeq   log_the_barrel_on_landing  scripted 100% -> 64%     log_the_ground_swarm  88/88 -> 84/84
            hog_over_the_ignorable doctrine 40 -> 24            matchup_logbait 60 -> 40
            matchup_beatdown_golem 88 -> 100                    hold_the_cheap_answers 16 -> 20
    ```

    MEASURED MECHANISM for the big one, `log_the_barrel_on_landing`, on its own reference line:

    ```
    goblins land at t=5.40 s in both runs
    BEFORE: last goblin dies 6.00 s (alive 0.60 s), princess HP conceded  534   -- bar is < 1000
    AFTER : last goblin dies 6.60 s (alive 1.20 s), princess HP conceded 1076   -- just over it
    ```

    The reference casts the Log **3.2 tiles behind** where the goblins land; an instant roll killed
    them the moment it resolved, and the swept edge needs another ~0.6 s to arrive, which buys them
    one more volley. **The drill is still fully winnable — the reference line is simply 0.2-0.5 s
    LATE now.** MEASURED by re-timing it: cast at 3.8 / 4.0 / 4.1 s → **100% / 100% / 100%**, at
    4.3 s (today's value) → 84%, at 3.4 / 3.6 → 96%. Moving the cast point does nothing (0.84 /
    0.86 / 0.88 all score 84%), so it is the CLOCK. Re-tuning the reference is a drill-calibration
    change and is deliberately **not** bundled here under the one-change rule.

    `ignore_the_ignorable` 20% → 8% is an IMPROVEMENT — it is a restraint drill where the correct
    play is none, so a lower doctrine number is less wasted elixir.

22. **The Barbarian Barrel's roll speed is 200**, the same as The Log's (owner, 2026-08-27). The
    field is **absent upstream** — the card page publishes no roll or projectile speed in either
    attributes table and no history entry ever set one, unlike The Log, whose 20/10/2016 entry says
    *"its projectile speed to 200 (from 170)"*. So it is curated in `cards.yaml` **and PINNED** in
    `config/import_pins.json` (184 → **185** pins, byte-identical pair, via `gen_pins.py`'s new
    `RULING22_PINS`): without the pin a re-import would drop the field and silently return this one
    card to an instant corridor. At 200 the barrel's 4.5 tiles sweep in **1.35 s**.

23. **The barrel's Barbarian appears at the corridor END, when the sweep COMPLETES** (owner,
    2026-08-27). ⚠ **THE BRIEF'S PREMISE WAS WRONG ABOUT THE POSITION.** It said "before: Barbarian
    appears at the CAST POINT at t=0". It did not: `_resolve_roll` already spawned at
    `ey = s.y + fdir * roll_len`, and not at t=0 either. MEASURED, a team-1 barrel cast at
    (0.500, 0.450):

    ```
    BEFORE:  body at (0.528, 0.594) = 4.60 tiles forward, at t=0.45 s   (the spell's cast delay)
    AFTER:   body at (0.528, 0.594) = 4.60 tiles forward, at t=1.80 s   (0.45 + the 1.35 s sweep)
    ```

    So **only the timing moved, by exactly the sweep.** The wiki states the destination three
    times: *"Once the spell reaches its DESTINATION, it spawns a single Barbarian"*; *"AFTER IT
    FINISHES ROLLING, the Barbarian will help take out and tank some of the Skeletons"*; and the
    checkable one, *"If the Barbarian Barrel is placed at most 2 tiles from the river, the Barbarian
    will spawn at the OPPOSING SIDE of the Arena"*. The spawn point is `_clamp_xy`ed, so a barrel
    cast at the board edge still leaves its body, at the last legal point.

    **23a — the HERO barrel inherits all of it.** `barbarian_barrel_hero` is a minimal overlay
    (`{damage, spawns_troop, ability_*}`) and picks up `rolls`, `roll_len`, `own_half_only` and now
    `roll_speed` from the base row: measured, its sweep is the same 1.35 s and its body appears at
    the same t=1.80 s — but it is `barrel_barbarian`, its own row, not the base's. There is **no
    evo Barbarian Barrel** in the 42-evo set; the four rolling cards are the complete list.

24 / 26 / 27 / 28. **Rowdy Reroll is a LITERAL second roll of the same barrel.**

    Owner (24): *"the barbarian barrel hero's ability is to roll again, so all the roll mechanics
    carry over."* It goes through the same `_Roll` path — same tiles/s, same corridor test, same
    per-body-once damage — so everything ruling 21 fixed applies to it by construction. The
    Barbarian is a TROOP whose own `rolls` is False, so `build_spec`'s spell→body ability transfer
    now carries the barrel's `roll_speed` onto him as well; without that the reroll would fall into
    the no-speed branch and resolve instantly, i.e. ruling 21 undone on the one card that rolls
    twice.

    **THE CORRIDOR IS SHORTER, and it would have been easy to miss.** History, 4/5/2026:
    *"decreased the reroll range to 3 tiles (from 4 tiles)"*, against the barrel's own Range of 4.5.
    The engine already used `ability_range_tiles` (3.0) rather than `roll_len`, and a test now pins
    that it must. MEASURED: **3.0 tiles at 3.3333 tiles/s = 0.90 s.**

    **THE DAMAGE IS NOT REDUCED.** The reroll deals the same **232 area / 116 crown** as the first
    roll. ⚠ `rerolldmg_11 = 116` is **not** a second-roll damage despite the variable name — it is
    the barrel's CROWN TOWER damage column (116/232 is exactly the ordinary 50% crown reduction).
    Same trap class as `spell_radius` meaning corridor HALF-width for a rolling spell.

    **ORIGIN (26): the LIVING Barbarian's current position, read at activation.** Not where the
    first roll stopped — he lands at the first corridor's end and then WALKS, and a stored
    coordinate falls further behind the longer the player waits. MEASURED: after 3 s of marching he
    is **2.38 tiles** past the first roll's end, and the second roll starts at him. Which body, if
    there were several, is ruling 5's `max(deploy_seq)` in `champion_ability`, reused rather than
    reinvented. The second roll is **not** a cast, so the own-half clamp does not apply to it —
    pinned with an enemy-half origin, which is where this button is usually pressed.

    **ABSORB AND REDEPLOY (28): there is NO second Barbarian.** Owner: *"The ability does not spawn
    a second barbarian. The first barbarian disappears into the second roll when the ability casts,
    and redeploys at the endpoint of the second roll."* The wiki agrees — it heals *"the barbarian"*,
    singular. So `spawn_count = 0` on the reroll, the existing body goes through a new `_despawn`
    (removed from `units` WITHOUT dying, so no death damage, no death spawn, no trade-ledger kill
    credit — and every `target` reference to it cleared, because the engine validates targets by
    `hp > 0` and not by list membership, so a live body outside the list is a phantom that locked
    attackers keep swinging at), and `_finish_roll` puts **the same Unit object** back at the
    corridor's end. `deploy_seq`, level, ability counters and accumulated damage all survive by
    construction. MEASURED: absorbed at ny=0.5938, redeployed at ny=0.6875 — **3.00 tiles up** —
    with **zero** Barbarians on the board during the roll and **exactly one** afterwards.

    **THE HEAL (27) is 50% of the damage he has TAKEN**, i.e. half his missing hitpoints, capped at
    full. MEASURED: a Barbarian at **179 / 716 hp comes back at 448**. The prose is loose
    (*"healling the barbarian for 50% of the damage"*), so the competing lifesteal reading — 50% of
    what the reroll deals — was considered and rejected: it pays **nothing when the corridor is
    empty**, which is precisely when a player presses this to save a dying Barbarian, and it does
    not match the Strategy line *"while healing some hp"*. Recorded in conflicts.md as an owner
    in-game check. This **replaced** the previous lifesteal implementation, whose test is rewritten.

    **REFUND (26 q1 / 27): if he dies first, the elixir comes back**, and it needs no new path.
    Two halves, both existing machinery: with no living body `champion_ability` refuses and never
    charges (MEASURED: elixir unchanged at 5.000); a body killed **during** the 1.0 s activation
    delay hits ruling 7's refund in `_tick_ability_pending` (MEASURED: 1 elixir returned, and no
    roll launched).

    37 new tests (`test_rolling_spells_swept_r21.py`, byte-identical in both decks). Four existing
    tests changed, each because the behaviour genuinely changed: the i9 corridor test now advances
    instead of asserting at t=0, two i8 hero tests wait 2.6 s instead of 1.5 for a body that now
    arrives 1.35 s later, and `test_a_log_thrown_too_early_misses_the_goblins` moved its early bound
    0.3 → 0.2 s (MEASURED, delay → goblins alive: 0.0/0.1/0.2 → 3, and 0 for every delay from 0.3
    to 4.0 s — at 0.2 s the edge is 2.00 tiles along when they spawn 1.92 tiles ahead, already past
    them; at 0.3 s it is 1.67 and still arriving).

25 / 27. **One Barbarian, 716 hitpoints — and the barrel's missing crown damage.**

    Owner, IN-GAME 2026-08-27: *"a Barbarian has 716 hp at level 11"*, and *"the barbarian spawned
    by the barrel should have the same stats as normal barbarians."*

    ⚠ **THE BRIEF'S FRAMING WAS WRONG, and the correction matters for how much weight the in-game
    check has to carry.** It said this was *"the same shape as the Electro Dragon 267-vs-192
    correction: the wiki agrees with the stale number, so `stat_sweep` reported these rows as
    MATCHING and could never have flagged them."* It did flag them. `stat_sweep` has been printing

    ```
    barbarians_evo  hp  ours 691.0  wiki 716.0  -- I5 apply (LAG): WIKI IS SELF-INCONSISTENT.
        The 4/8/2026 rule is 'Evo HP = base HP', yet the Evo page says 716 and the base page
        says 691; both cannot be right
    ```

    since I5. The number was surfaced and pinned; what was missing was the **tie-break**. Three
    published facts all point at 716:

    | page | revid | `hp_11` | its own history |
    |---|---|---|---|
    | Barbarians | 437362 | **691** | *"On 4/8/2026 … increased the Barbarians' hitpoints by 4%"* — never applied to the vardefine |
    | Barbarians/Evolution | 437363 | **716** | *"On 4/8/2026 … REMOVED the Evolved Barbarians' Extra Hitpoints"* → Evo HP == base HP |
    | Barbarian Barrel/Hero | 437523 | **716** | (the body it drops) |

    **716 for both is the only assignment that satisfies the 4/8/2026 rule**, and once applied the
    evo row stops being a deviation at all — `stat_sweep --all` now reports **MISMATCHES: 0** with
    `barbarians_evo` gone from the known-deviation list entirely and `barbarians hp ours 716 / wiki
    691` in its place, sourced to the ruling.

    **MEASURED BEFORE → AFTER** (level 11):

    ```
    key                      hp          damage       hit_speed   built hit_dmg
    barbarians               691 -> 716   191 (kept)   1.4 (kept)   190.4
    barbarians_evo           691 -> 716   191 (kept)   1.4 (kept)   191.0
    base_barrel_barbarian    670 -> 716   191 (kept)   1.3 -> 1.4   191.1 -> 190.4
    barrel_barbarian (hero)  716 (kept)   192 -> 191   1.3 -> 1.4   192.4 -> 190.4
    barbarian_hut's spawned body:  691 -> 716 each, x3   (INHERITED -- no direct edit, and pinned
                                                          by a test, because "it inherits" is a
                                                          claim about resolution order)
    ```

    The 1.3 → 1.4 is the 2/3/2026 entry on the Barbarians page (*"increased their attack speed to
    1.4 seconds (from 1.3 seconds)"*) that **neither barrel page ever applied**. The base barrel
    row's old comment read *"the vardefine `atk_speed` on this page says 1.3 too, so unlike the hero
    row there is nothing to reconcile here"* — true, and stale together. The hero row's old comment
    picked 1.3 under rule (b) because the page's Barbarian Attributes **table** says 1.3 against its
    own `atk_speed` vardefine's 1.4, and read the base barrel's agreement as corroboration; that was
    two stale tables agreeing. **damage stays 191**, the `barbarians` card's own value, so the
    barrel drops a *normal* Barbarian and not a 0.5%-stronger one — the 192 on the Evo and Hero
    pages is level-ladder rounding between independently maintained vardefines, and I5 already
    pinned `barbarians_evo.damage` to 191 for that exact reason.

    ⚠ **`spawn_unit_stats.hit_speed` is a SECOND copy of the same number, and the hero has its own.**
    Curating the base row did not reach the hero, whose block comes from `cards_stats.json`
    (hit_speed 1.3); a stale copy left there would silently override the fix. Both are 1.4 now, and
    a test checks them separately from the body rows.

    **THE TWO BARREL-BODY ROWS ARE NOT MERGED**, though they are now numerically identical. They are
    sourced from two different wiki pages with their own revids, `_src` provenance and `verified`
    flags; the import layer reconciles them per page; and the hero page **has diverged before and
    was the right one when it did** (it carried 716 while the base carried 670). One row would make
    the next divergence invisible instead of loud. I9's
    `test_the_hero_barrel_keeps_its_own_heavier_barbarian` is renamed and rewritten to say so.

    **RULING 27 (same rows, same commit): the barrel's crown damage is 116.** The base
    `barbarian_barrel` row published **no crown value at all**, so `build_spec`'s `dmg if _td is
    None` fallback handed it its FULL damage against a Crown Tower — MEASURED **230.0**, and the
    hero inherited the same fallback at 230.0 against its own 232 roll. The published figure is
    `rerolldmg_11` **116**: ⚠ that vardefine is the **Crown Tower Damage** column, not a second-roll
    penalty (116/232 is the ordinary 50% crown reduction; the name is misleading, the same trap
    class as `spell_radius` meaning corridor HALF-width for a rolling spell). MEASURED after: a
    barrel rolled over a Crown Tower takes **116.0**, both forms.

    **PINS: 185 → 195**, byte-identical pair, via `gen_pins.py`'s new `RULING25_PINS`. One of them
    **supersedes an I5 pin** (`barbarians_evo.hitpoints` 691 → 716), which the generator's I5 loop
    would otherwise refuse with `assert got == value`. That assertion is the right default —
    silent disagreement between two pin sources is how a curated value gets quietly reverted — so
    the override is declared **explicitly** in `RULING25_OVERRIDES` rather than by weakening the
    assertion for everyone. `barbarian_hut.spawn_unit_stats` moves from the stat_diffs pin
    `'670/192/1.3'` to `'716/191/1.4'` for the same reason.

    **DRILLS: small and mixed, every move ≤ 12 pp**, which is what a 3.6% tougher / 6.7% faster
    Barbarian should do to matchup drills where the opponent holds Barbarians, Barbarian Hut or
    Battle Ram.

    ```
    icebow  log_the_ground_swarm 80/80 -> 76/76   ignore_the_ignorable doctrine 8 -> 16
            bow_punish_the_commitment 92/84 -> 88/88   nado_the_sneaky_lock doctrine 100 -> 96
            hold_the_tesla_for_their_wincon 48 -> 44   split_lane scripted 80 -> 84
    hogeq   log_the_ground_swarm 84/84 -> 92/92   log_the_barrel_on_landing 64 -> 60
            firecracker_answers_the_air 80 -> 88  hold_the_cheap_answers 20 -> 32
            mm_blocks_the_tank 40/52 -> 52/48     matchup_lavaloon 60 -> 48
    ```

    11 new tests (`test_barbarian_stats_r25.py`, byte-identical in both decks); four existing
    assertions moved to the new numbers, each with its before/after in the line.

## 2026-08-27 — RULING 29 (owner): elixir prices for ALL remaining spawned bodies

Closes the 4-elixir-default problem entirely (I10 measured 30/27 reads of `spec.elixir` across the
reward + threat layers). Owner overrides in bold; the rest are the assistant's suggestions,
owner-approved. Hero-summon bodies are priced at their ABILITY cost by owner instruction.

| body | elixir | note |
|---|---|---|
| **goblin_brawler** | **3** | owner override (suggested 2) |
| **rhino** | **3** | owner override (suggested 2) |
| **tomb_queen** | **5** | owner: the ability cost |
| **trusty_turret** | **3** | owner: the ability cost |
| barrel_barbarian, base_barrel_barbarian | 1 | one-fifth of Barbarians-for-5 |
| royal_recruit | 1.5 | |
| golemite | 2 | half the Golemites pair |
| elixir_golemite | 1.5 | refunds on death |
| elixir_blob | 0.5 | refunds on death |
| lava_pups | 0.5 | each |
| mother_witch_hog | 1 | |
| phoenix_egg | 0.5 | |
| bush_goblin | 1 | each |
| decoy_goblin, ghost_souldier, skarmy_general | 0.5 | |
| lumberjack_ghost | 3 | untargetable body |
| skeletrooper | 1 | |
| brigade_goblin | 0.5 | |

⚠ APPLICATION DEFERRED until the rollout-search experiment completes: its scoring function reads
`spec.elixir` (via `bodies_ignore_frac` and the elixir term), so changing prices mid-experiment
would make the arms inconsistent. Apply in BOTH decks with pins immediately after; also re-run
`tools/evo_audit.py` and spot-check `ignore_cost_frac` orderings, since 20 threat prices move.

## 2026-08-27 — RULING 30 (owner): the spell veto is on VALUE, not on a BODY COUNT — and the enumerated exemption class

`spell_experiments.md` §7.5 recommended a **card veto at K=3 bodies**: refuse a spell when no legal
cell catches >=3 enemy bodies under the engine's own hit test. Measured, n=300 paired, GREEDY:
monotone in K, +0.383 tower fractions at K=7 (5.82σ), +9.0pp winrate, and at K=3 it beats a
volume-matched random spell ban by +0.207 (2.98σ).

**THE OWNER REJECTED THE BODY-COUNT FORM, and he is right.** A single-body cast is routinely the
highest-value play this deck owns, and the drills say so in their own reference lines:

| drill | board | reference line | bodies |
|---|---|---|---|
| `nado_king_activation` | ONE Hog Rider | `("tornado", 0.472, 0.771, 3.6)` | 1 |
| `nado_the_sneaky_lock` | ONE enemy Knight on our X-Bow | `("tornado", 0.26, 0.40, 1.2)` | 1 |
| `rocket_the_two_for_one` | ONE Witch beside their princess | `("rocket", 0.194, 0.229, 0.6)` | 1 |
| `rocket_the_pump_on_sight` | ONE Elixir Collector | `("rocket", 0.30, 0.16, 1.2)` | 1 |
| `eq_the_pump_on_sight` (hogeq) | ONE Elixir Collector | `("earthquake", 0.30, 0.16, 0.6)` | 1 |
| `eq_clears_the_hogs_building` (hogeq) | ONE Cannon | `("earthquake", 0.20, 0.28, 0.0)` | 1 |
| `log_resets_the_charge` (hogeq) | ONE Battle Ram | `("the_log", ...)`, scored in TOWER HITS | 1 |

A K=3 threshold refuses every one of them. **So the criterion is a VALUE threshold in TOWER
FRACTIONS** — `threat_value.catch_value_frac`, the project's own measured triage model, the same
currency the rollout-search scorer used — **plus the exemption set enumerated below.** The
`nado_king_activation` board is the argument in one line: a count says `1`, the value model says
**0.340**, and three whole Skeletons together say **0.0038**.

### 30.0 A new function was needed, and the measurement says why
`bodies_ignore_frac` routes everything through `_bodies`, which returns `None` for any card the
crown tower cannot model as a clearing queue — a kamikaze body, every Spirit, a siege building —
and `group_ignore_frac` turns one `None` into `inf` for the WHOLE group. MEASURED on the sim's own
ladder pool:

```
                        bodies_ignore_frac    ignore_cost_frac
wall_breakers                 inf                 0.1415
fire_spirit                   inf                 0.0468
ice_spirit                    inf                 0.0249
```

A veto reading `inf` as "enormously valuable" would wave through every cast on a board holding one
Ice Spirit — worth half the ignore threshold. `threat_value.catch_value_frac` pools what the clearing
model covers and SUMS the per-card burst/economy price for what it cannot (right for those: a Wall
Breaker's cost is burst damage that does not queue). `inf` still propagates for a genuinely
unresolvable card (a Mortar, an X-Bow), because the tower cannot answer those at all.

### 30.1 THE ENUMERATED EXEMPTION CLASS — every play whose value is NOT the bodies caught

Read out of `icebow/DOCTRINE.md`, `DOCTRINE_RESEARCH.md`, `sim/drills_icebow.py`,
`sim/drills_hogeq.py`, `sim/doctrine.py`, `config/counters.yaml` and `reward.py`, in both decks.
**STATUS** is one of: **SHIPPED** (a named branch of `SimMatchEnv.spell_veto_exempt`),
**VALUE** (no exemption needed — the value term already clears it), **NOT SHIPPED** (with the reason).

| # | play | source | engine precondition | deck / card | status |
|---|---|---|---|---|---|
| 1 | **King activation** — the pull wakes our King for the match; the body is incidental | drill `nado_king_activation`; DOCTRINE.md rows 3/16/51 ("the classic activation — highest-value single play the deck owns"); `doctrine.py:646-667` | `doctrine._king_spots(env,u)` non-empty (which itself requires `_path_enters_pull`) AND `not eng.towers[0][2].active` AND `not _pull_resistant(u)` | icebow / tornado | **SHIPPED** `king_activation` |
| 2 | **Sneaky lock** — drag the lone defender off our X-Bow so it re-locks the tower | drill `nado_the_sneaky_lock` (ONE Knight); `doctrine.py:685-700` quotes the guide verbatim; counters.yaml:233 | enemy `locked` with `target` = one of OUR BUILDING units | icebow / tornado (log via the same branch) | **SHIPPED** `lock_break` |
| 3 | **Retarget a tower-locked wincon** onto the Tesla | `env._nado_catch`: *"most wincons pulled this way are worth less than one"* rocket; `nado_retarget_min_worth` 2.0, deliberately below `rocket_min_worth` 4.0 | `u.spec.building_only` AND `u.locked` on one of OUR TOWERS AND per-body worth >= `nado_retarget_min_worth` | icebow / tornado | **SHIPPED** `lock_break` |
| 4 | **Charge / ramp reset** — a logged Prince, Ram, Dark Prince, Bandit, Little Prince | drill `log_resets_the_charge`, scored in TOWER HITS TAKEN and explicitly not in bodies (*"a Battle Ram ALWAYS dies, it is kamikaze"*); DOCTRINE.md rows 4/28/67; `engine._knock` sets `charge_dist = 0`, `ramp_shots = 0` | spell `knockback > 0` AND (`u.spec.charge_range > 0` OR `u.ramp_shots > 0`) AND `threat_value.trade_sane` | both / the_log | **SHIPPED** `charge_reset` |
| 5 | **Tower lethal** — the cast finishes a Crown Tower; ZERO bodies by definition | DOCTRINE_RESEARCH R8 "ROCKET RANGE"; `_rocket_value`'s `on_tower` branch | a legal cell within `spell_aim_radius` of a live princess AND `t.hp <= spec.spell_tower_dmg` | icebow / rocket; hogeq / earthquake | **SHIPPED** `tower_lethal` |
| 6 | **Endgame tower finish** — 3-4 casts end a low tower | DOCTRINE_RESEARCH §3.4 (*"3-4 EQ casts finish a low tower in x2"*; the deck page's switch point is an enemy tower at <=773 HP) | `t.hp <= 3 * spec.spell_tower_dmg` | both / rocket, earthquake | **SHIPPED** `tower_finish` |
| 7 | **Tiebreak chip in overtime** | DOCTRINE.md rows 56/57 (rocket-cycle the weaker princess); hogeq doctrine's "PURE CHIP"; `rocket_chip_behind` 1.2 vs `rocket_chip_early` 0.25 | `eng.t >= _double_time` AND `_tiebreak_gap() <= 0` AND a legal cell on a live princess | both | **SHIPPED** `tower_chip` |
| 8 | **The 2-for-1** — tower chip plus a one-shottable support in one blast | drill `rocket_the_two_for_one` (ONE Witch); `env._rocket_combo`; DOCTRINE.md row 35 | a live princess in aim radius AND a 4-6 elixir troop with `hp <= spec.spell_dmg * rocket_combo_hp_frac` within `rocket_combo_radius` of it | icebow / rocket | **SHIPPED** `two_for_one` |
| 9 | **Pump punish** — a fresh Elixir Collector is one body and six elixir | drills `rocket_the_pump_on_sight`, `eq_the_pump_on_sight`; DOCTRINE.md row 50; `env._pump_rocket`; counters.yaml:744 | an enemy BUILDING in the footprint | both / rocket, earthquake | **SHIPPED** `building` |
| 10 | **The building holding the Hog** — success is the HOG CONNECTING, not the building dying | drill `eq_clears_the_hogs_building` (`success = enemy_tower_hp_lost(...)`); `hogeq/env._hog_synergy`; hogeq counters.yaml x11 | same as 9 | hogeq / earthquake | **SHIPPED** `building` |
| 11 | **The Tombstone rule** — *"always Log a Tombstone at half hp"*, two cards from a 2-elixir spell | `doctrine.py:708-714` (verbatim guide quote); counters.yaml:749 | same as 9 | both / the_log | **SHIPPED** `building` |
| 12 | **Their seated siege** — kill the bow/mortar before it fires | DOCTRINE.md rows 48/49; counters.yaml:218; hogeq counters.yaml:440/642 | same as 9 (siege is a building) — and `catch_value_frac` reads `inf` for a Mortar/X-Bow anyway | icebow / rocket; hogeq / earthquake | **SHIPPED** `building` (also **VALUE**) |
| 13 | **The retracted Tesla** — Earthquake is the one damage spell that reaches it | hogeq DOCTRINE.md:48/51; `engine._hurt`'s `if u.hidden and not hits_hidden: return` | `spec.hits_hidden` | hogeq / earthquake | **SHIPPED** — as a hit-test CORRECTION, not an exemption: `_spell_footprint` now DROPS a hidden building for a spell without `hits_hidden`. Without it a Rocket "caught" a Tesla it deals zero damage to and the veto waved that cast through |
| 14 | **Pre-log the barrel / the drill pop / a Skeleton-Barrel's skeletons** — the bodies do not exist at cast time | drill `log_the_barrel_on_landing` (barrel spawns at t=4.0); DOCTRINE.md rows 19/21 (*"pre-log beats post-log"*); `env._resnap_spell_check` exists for exactly this on the reward side | an enemy spell with `spawn_spec` in `eng.spells` whose landing point a legal cell can reach | both / the_log | **SHIPPED** `incoming_spawn` |
| 15 | **Lead / intercept casts** — aim where they WILL be | `reward.spell_intercept_cell` / `lead_point`; `train_sim_ppo`'s own note: *"a 'whiff' at empty ground that a Hog is about to walk into is a real technique"* | count bodies at `cast + spell_delay`, not at cast | both / all | **NOT SHIPPED.** It is a change to the HIT TEST, not an exemption, and it would move every arm's criterion at once. §4q: one change at a time. See 30.4 |
| 16 | **Tornado-back an air flock** | drill `nado_pull_the_flock_back` | >=2 flying bodies past y 0.55 | icebow / tornado | **VALUE** — measured 0.372 on the drill's own board, above every threshold at or below 0.45 |
| 17 | **Clump for the Ice Wizard** — *"scored in TOWER HP, not in bodies; counting corpses measured nothing"* | drill `nado_clump_for_the_wizard` | `env._nado_catch`'s clump gate (>=2 bodies worth `nado_clump_medium_worth`) | icebow / tornado | **VALUE** — 0.372 on the drill board. ⚠ vetoed at 0.65 and above; that is one of the two costs of going past 0.45 |
| 18 | **Rocket-then-Tornado** — the blast lands into a clump that does not exist at cast | drill `rocket_then_tornado`; `env._rocket_value`'s `eta` branch; `doctrine._live_nado` | — | icebow / rocket+tornado | **VALUE** — 0.924 on the drill board, clears every threshold |
| 19 | **Mitigation, not removal** (R1/R3): the rocket is the cheapest SUFFICIENT answer when Knight and Tesla are out of cycle | DOCTRINE_RESEARCH:479-484 — *"R1 and R3 are damage-MITIGATION rules, not removal rules, which is why they deliberately carry no lethality check"*; `doctrine.py:1167-1183`; `_rocket_value`'s `rocket_emergency` | `_holdable("knight")` and `_holdable("tesla")` both None, or `cheapest_stack >= 7.0` | icebow / rocket | **NOT SHIPPED.** The bodies it answers are heavy by construction (`u.spec.elixir >= 4`, past the river), so `catch_value_frac` already clears any threshold tested: a Prince is 0.551, a Balloon 0.543, a Mini P.E.K.K.A. 0.644. Adding it would be an exemption with no measured work to do |
| 20 | **Rocket a target it cannot kill** (Royal Giant, Prince, Bowler) | DOCTRINE_RESEARCH:170-171 — *"the Rocket does not kill him... do not file it as removal"* | — | icebow / rocket | **VALUE** — `catch_value_frac` prices the THREAT, not the kill, so a target too big to kill scores HIGH (royal_giant, prince, bowler all >= 0.249). The value form gets this right by construction where a lethality test would not |
| 21 | **Rocket the Balloon mid-flight, last resort** | DOCTRINE.md row 15 | — | icebow / rocket | **VALUE** — balloon 0.543 |
| 22 | **Log as chip + pushback that is explicitly NOT a kill** (Royal Hogs, Recruits, E-Barbs, Zappies...) | counters.yaml:136 *"not a kill: chip plus pushback buys the tower time"*, :387, :408, :416, :430; hogeq counters.yaml:26/151/650 | — | both / the_log | **VALUE** — every named target is >= 0.14 (royal_hogs 0.535, e-barbs 1.139, barbarians 1.523); plus `charge_reset` where a run-up is armed |
| 23 | **Earthquake's 50% slow as the value** | hogeq DOCTRINE_RESEARCH:308-310; `zone_move_slow: 0.5` | `spec.zone_move_slow > 0` | hogeq / earthquake | **NOT SHIPPED.** It applies to a big ground push, which scores high on value anyway; an unconditional slow exemption would exempt the Earthquake on every board that has any ground body |
| 24 | **Prediction EQ around the crossing Hog** — the swarm dies as it deploys | hogeq DOCTRINE_RESEARCH:258-261 | our `hog_rider` past the bridge | hogeq / earthquake | **NOT SHIPPED** — same family as 15 (judge over `spec.zone_s`, not at the cast instant). Untested |
| 25 | **The rocket-mirror bait** — cast at their tower on an EMPTY board to buy their rocket | DOCTRINE_RESEARCH:195-197, flagged **[H] NEW** in the research itself | none exists | icebow / rocket | **NOT SHIPPED.** No engine-checkable precondition, and the research marks it as an unverified hypothesis |

**⚠ ONE OWNER-NAMED EXEMPTION IS NOT MECHANICALLY REAL IN THIS ENGINE.** The brief asked for
"charge/dash reset (log, **tornado**)". `engine._tick_vortex` breaks a target LOCK when the pull
takes a body out of reach, but it never touches `charge_dist` — only `_knock` (knockback) and
`_apply_status` (stun/freeze) do. So the tornado gets `lock_break` and NOT `charge_reset`, and the
exemption is written against the mechanic rather than against the card.

**⚠ AND ONE EXEMPTION HAD TO BE GUARDED BY `trade_sane`.** The Rocket also carries 1.0 tiles of
knockback and `_knock` disarms a charge for it too, so an unguarded reset exemption made a
SIX-elixir cast unrefusable on any charging body — the exact trade `trade_sane` was written for
after the owner's *"rocketing wall breakers (a horrible elixir trade)"* report. Doctrine names the
LOG for charge resets, never the Rocket.

### 30.2 TWO EXEMPTIONS WERE MEASURED WRONG BEFORE THEY WERE MEASURED RIGHT

Both were found by the numbers, not by reading.

* **`tower_chip` fired on 300 of 300 sampled steps.** An anywhere-spell can always reach a live
  princess, so "a legal cell touches a live tower" is not a criterion — it exempted the Rocket
  permanently. The gate is now `_rocket_value`'s own: LETHAL, or FINISHABLE, or overtime-and-behind.
  ⚠ `_defensive` cannot carry it either: MEASURED `_defensive == True` at **t = 0.0** whenever the
  opponent holds a split-lane counter, and `env.py`'s own note above `_punish_window` records that
  locking it on put **93.5%** of steps in the defensive phase. Nor can `_tiebreak_gap() <= 0` alone:
  MEASURED **-0.098 at t=0** on a level disadvantage (our 4424-HP towers against their 4858).
* **`lock_break` fired on 21% of every veto evaluation** — an enemy is nearly always chewing on
  *something* — and on its own it took the value form from a working veto to a null (casts/match
  7.83 -> 6.15 against the count form's 4.25). Two gates were missing and the project already
  states both: `env._nado_catch`'s `targeters` are `building_only` bodies on our TOWERS gated at
  `nado_retarget_min_worth`, and the sneaky lock is a defender on one of our BUILDINGS. An enemy
  merely fighting one of our TROOPS is an ordinary scrap and buys nothing worth a card.

### 30.3 THE FIRST MEASUREMENT — ⚠ SUPERSEDED BY 30.6. KEPT AS THE RECORD OF WHAT WAS RUN.

> ⚠ **THESE ARMS RAN UNDER THE WRONG INTERPRETER, AND IT IS WORTH MORE THAN MOST EFFECTS THIS
> PROJECT MEASURES.** The wave scripts launch `scratchpad/spell_arms_valueform.py` as bare
> `python`, which on this box is the ROOT `.venv` — **torch 2.13.0+cpu**. HANDOFF §2's standing
> rule is "always use the venv python of the folder you are in", and the trainer, the drill
> report, the eval benchmark and live play all run the deck venv's **torch 2.11.0+cu128**.
> ISOLATED, 2026-08-27, n=300 paired, same seeds, same checkpoint, **same tree**: root venv
> **43.0% / -0.8303**, icebow's own venv **37.0% / -0.9348** — **-6.0pp winrate (2.62σ) and
> -0.105 tower fractions (1.86σ) from the interpreter alone.** Within-block comparisons below
> stay internally valid (every arm in a block shared the interpreter); the ARM-VS-CONTROL claim
> in statement 2 does not survive re-measurement, and statement 1 is contradicted. See 30.6.

All arms n=300, seeds 5_000_000..5_000_299, paired, GREEDY, `_rs_policy.pt`
(md5 `9dd42804fdf6709d5387ec61f188cb83`), on **tree 1143af2 + this change**. The baseline was
RE-MEASURED here and reproduces `sx_bx.json` on **300 of 300 matches** — i.e. today's tree is the
old `base2` plus the action-space fix `51f34fb`, exactly as expected. `rs_base.json` and the
pre-51f34fb arms are not comparable and are not quoted.

```
arm                       win%   towerd   casts/m  dump%  |  vs BASE (paired)     sigma
base (= bx)               43.0   -0.835     7.83    36.5  |      --                --
k3   count veto, K=3      48.7   -0.583     4.25    18.4  |    +0.252            +3.80  SIG
value 0.45, NO exemptions 48.7   -0.596     4.33    21.4  |    +0.239            +3.91  SIG
value 0.65, NO exemptions 46.7   -0.618     3.35    21.5  |    +0.217            +3.30  SIG
value 0.45, exemptions    45.3   -0.799     5.83    25.9  |    +0.036            +0.65  NO MEAS.
value 0.65, exemptions    45.7   -0.764     5.51    26.6  |    +0.071            +1.26  NO MEAS.
value 0.20, exemptions    38.7   -0.864     6.83    30.6  |    -0.029            -0.58  NO MEAS.
```

```
ARM AGAINST ARM, paired on the same 300 seeds. ctl(r) = random spell bans, independent
per-playable-spell probability r, the ledger's own control design.
k3         -> value0.45 no-exempt   4.25 -> 4.33 casts/m   -0.013   0.22σ   NO MEASUREMENT
ctl(0.83)  -> value0.45 no-exempt   4.36 -> 4.33 casts/m   +0.149   2.14σ   SIG
ctl(0.83)  -> k3                    4.36 -> 4.25 casts/m   +0.162   2.31σ   SIG
value0.45 exempt -> no-exempt       5.83 -> 4.33 casts/m   +0.203   3.82σ   SIG
value0.65 exempt -> no-exempt       5.51 -> 3.35 casts/m   +0.147   2.44σ   SIG
-- and the EXEMPTED arms against THEIR volume-matched controls --
ctl(0.30)  -> value0.45 exempt      7.03 -> 5.83 casts/m   +0.068   1.16σ   NO MEASUREMENT
ctl(0.40)  -> value0.65 exempt      6.45 -> 5.51 casts/m   +0.080   1.27σ   NO MEASUREMENT
ctl(0.50)  -> value0.65 exempt      6.49 -> 5.51 casts/m   +0.002   0.03σ   NO MEASUREMENT
```
(The 0.30-0.50-rate controls land ABOVE the exempted arms' volume — a bias in the ARM's favour,
since the control is forced to keep more bad casts — and the exempted form still does not clear
2σ against any of them.)

Three statements, and the third is the one that matters:

1. **The VALUE criterion is exactly as good as the COUNT criterion.** k3 -> value0.45 is
   **-0.013 at 0.22σ** with winrate identical, at matched volume (4.25 vs 4.33 casts/match). The
   owner's re-formulation costs nothing in aggregate outcome.
2. **It clears the pre-committed bar against its VOLUME-MATCHED control**: +0.149 at **2.14σ**,
   against the count form's +0.162 at 2.31σ. The criterion, not the volume cut, is doing that part.
3. **⚠ BUT ONLY WITH THE EXEMPTIONS OFF.** Turning the enumerated exemption set on costs
   **+0.203 (3.82σ)** at 0.45 and **+0.147 (2.44σ)** at 0.65, and the exempted arm does NOT beat
   its volume-matched control. The exemptions authorise ~20.6% of veto evaluations and put ~1.5-2.2
   casts per match back on the board.

**This is a real trade-off and it is not resolvable by tuning the threshold.** A value bar low
enough to admit the deck's single-target reference lines unaided is **<= 0.070** (the pump), and at
0.10/0.20 the arm is a null (-0.018 / -0.041). A bar high enough to move the metric is **>= 0.45**,
and at 0.45 the unaided rule refuses `nado_king_activation` (0.340), `nado_the_sneaky_lock` (0.302),
`rocket_the_two_for_one` (the Witch alone, 0.090) and `rocket_the_pump_on_sight` (0.070) — the
owner's objection to K=3, at a different bar. **The exemption set is the bridge, and its price is
measured above.**

Per-drill, the exemptions do the job they were written for. Evaluating each drill's OWN reference
line against the shipped rule (`scratchpad/ref_line_probe.py`, deterministic, one rep, judged over
the first 1.8 s from the reference cast because every drill's spawns land ~1.2 s after t=0):

```
icebow                          value    exemption        0.05  0.20  0.45  0.65  0.90
nado_king_activation           0.3400  king_activation     ok    ok    ok    ok    ok
nado_the_sneaky_lock           0.3022  lock_break          ok    ok    ok    ok    ok
rocket_the_two_for_one         0.5578  two_for_one         ok    ok    ok    ok    ok
rocket_the_pump_on_sight       0.0704  building            ok    ok    ok    ok    ok
log_the_barrel_on_landing         inf  incoming_spawn      ok    ok    ok    ok    ok
never_rocket_their_king        0.4391  two_for_one         ok    ok    ok    ok    ok
rocket_then_tornado            0.9235  -                   ok    ok    ok    ok    ok
nado_clump_for_the_wizard      0.3720  -                   ok    ok    ok  VETO  VETO
nado_pull_the_flock_back       0.3720  -                   ok    ok    ok    ok    ok
log_the_ground_swarm           0.5823  -                   ok    ok    ok  VETO  VETO
hold_the_spell_for_a_target    0.3817  -                   ok    ok  VETO  VETO  VETO
log_rolls_forward_not_backward 0.1702  -                   ok  VETO  VETO  VETO  VETO
hogeq
eq_clears_the_hogs_building    0.1441  building            ok    ok    ok    ok    ok
eq_kills_the_spawner           0.0367  building            ok    ok    ok    ok    ok
eq_the_pump_on_sight           0.0704  building            ok    ok    ok    ok    ok
log_resets_the_charge          0.3384  charge_reset        ok    ok    ok    ok    ok
hog_then_eq_in_order           0.1441  building            ok    ok    ok    ok    ok
log_the_ground_swarm           0.5823  -                   ok    ok    ok  VETO  VETO
```

**Every single-target reference line the owner named survives at every threshold**, and it is an
exemption that saves each one. What 0.45 costs instead is two LOG drills whose reference lines are
low-value boards: `hold_the_spell_for_a_target` (0.382) and `log_rolls_forward_not_backward`
(0.170). At 0.65 a third (`log_the_ground_swarm`, 0.582) and `nado_clump_for_the_wizard` go too.

### 30.6 RE-MEASURED AT HEAD, UNDER THE DECK'S OWN VENV, ON TWO SEED BLOCKS

`icebow/.venv/Scripts/python.exe` (torch 2.11.0+cu128), `_rs_policy.pt`
(md5 `9dd42804fdf6709d5387ec61f188cb83`), **tree = commit `cb05236` + ruling 31c + the veto
change** — the tree these commits create. n=300 paired per arm, GREEDY.

**BLOCK 1, seeds 5_000_000..299:**
```
arm                          win%   towerd   casts/m  |  vs BASE (paired)   sigma
base                         37.0  -0.9348    7.80    |      --               --
count veto K=3               46.7  -0.5857    4.20    |    +0.349           +5.15  SIG
value 0.45, NO exemptions    45.7  -0.6916    4.18    |    +0.243           +3.72  SIG
value 0.45, exemptions       43.0  -0.7814    5.74    |    +0.153           +2.65  SIG
ctl(0.83) RANDOM spell ban   46.3  -0.6342    4.34    |    +0.301           +4.54  SIG
ctl(0.30) RANDOM spell ban   40.7  -0.8014    7.26    |    +0.133           +3.06  SIG

ctl(0.83) -> count K=3              4.34 -> 4.20 casts/m   +0.048   0.69σ   NO MEASUREMENT
ctl(0.83) -> value 0.45 no-exempt   4.34 -> 4.18 casts/m   -0.057  -0.82σ   NO MEASUREMENT
ctl(0.30) -> value 0.45 exempt      7.26 -> 5.74 casts/m   +0.020   0.32σ   NO MEASUREMENT
count K=3 -> value 0.45 no-exempt   4.20 -> 4.18 casts/m   -0.106  -1.72σ   NO MEASUREMENT
```

**BLOCK 2, seeds 6_000_000..299** — run because a sign flip on one block is not a result:
```
base 34.0% -1.0828 7.75 | K=3 46.0% -0.7327 3.87 | value0.45 41.3% -0.8802 4.22
ctl(0.83) 34.7% -1.0318 4.24

base      -> count K=3              +0.350   5.43σ   SIG
base      -> value 0.45 no-exempt   +0.203   3.12σ   SIG
base      -> ctl(0.83)              +0.051   0.76σ   NO MEASUREMENT   <-- THE CONTROL MOVED
ctl(0.83) -> value 0.45 no-exempt   +0.152   2.32σ   SIG              <-- opposite sign to block 1
ctl(0.83) -> count K=3              +0.299   4.63σ   SIG
```

⚠ **THE TWO BLOCKS DISAGREE, AND THE REASON IS THE CONTROL, NOT THE ARM.** `ctl(0.83)` against
the same baseline is **+0.301 (4.54σ)** on block 1 and **+0.051 (0.76σ)** on block 2. A
random-ban control is ONE DRAW of a ban pattern: n=300 measures that draw precisely and says
nothing about the spread over draws, so a single block's arm-vs-control σ is not the test it
looks like. **This is why 30.3's +0.149 (2.14σ) should never have carried the ruling on its own,
and why block 1's -0.057 must not either.** The honest number is the pooled one.

**POOLED, 600 paired matches (both blocks), `scratchpad/sx_pool.py`:**
```
comparison                          n   towerd    sem   sigma  win pp  verdict
ctl(0.83)          vs base        600   +0.176  0.047   +3.71    +5.0  SIG
value 0.45 no-exmpt vs base       600   +0.223  0.046   +4.84    +8.0  SIG
count K=3          vs base        600   +0.350  0.047   +7.48   +10.8  SIG
value 0.45 no-exmpt vs ctl(0.83)  600   +0.047  0.048   +0.98    +3.0  NO MEASUREMENT
count K=3          vs ctl(0.83)   600   +0.174  0.048   +3.64    +5.8  SIG
value 0.45 no-exmpt vs count K=3  600   -0.127  0.042   -2.99    -2.8  SIG
```

**FOUR STATEMENTS, AND TWO OF THEM RETRACT 30.3.**

1. **Every veto form beats the baseline, and so does banning spells at random.** ctl(0.83) — an
   independent per-playable-spell coin flip, no state, no criterion — is **+0.176 (3.71σ)**.
   Most of what a veto buys this policy is simply casting fewer spells.
2. **⚠ RETRACTS 30.3 STATEMENT 2. The VALUE form does not beat its volume-matched control:
   +0.047 at 0.98σ over 600 paired matches.** The +0.149 (2.14σ) that justified "the criterion,
   not the volume cut, is doing the work" was one block under the wrong interpreter.
3. **⚠ RETRACTS 30.3 STATEMENT 1. The value form is not "exactly as good as" the count form —
   it is measurably WORSE: -0.127 at 2.99σ at matched volume**, and the count form is the only
   arm here that beats its own volume-matched control (**+0.174, 3.64σ**). 30.3 read this as
   -0.013 at 0.22σ on 300 matches under the root venv.
4. **The exempted form is unchanged in status**: +0.153 (2.65σ) over base, and a null against its
   volume-matched control (+0.020, 0.32σ). 30.3 already said this and it reproduces.

**SO THE TWO FORMS FAIL IN OPPOSITE WAYS, AND THAT IS THE RESULT.** The COUNT form has a real,
measured criterion effect and is doctrinally unacceptable — it refuses `nado_king_activation`,
`nado_the_sneaky_lock`, `rocket_the_two_for_one` and `rocket_the_pump_on_sight`, which is exactly
why the owner rejected it and that objection is untouched by any of this. The VALUE form protects
every one of those plays and has no measured criterion effect beyond the volume cut. Neither is
ready to be a training run's one attributable change.

### 30.7 WHAT STILL STANDS, AND IT IS NOT NOTHING

* **The owner's objection to the count form is confirmed and quantified.** One Hog Rider is
  **0.340** tower fractions, one Mini P.E.K.K.A. **0.644**, a whole Skeletons card **0.0038**.
  A count cannot express that; `catch_value_frac` can.
* **The exemption set does exactly what it was written for.** Re-run at HEAD in BOTH decks
  (`scratchpad/ref_line_probe.py`): **every owner-named single-target reference line survives at
  every threshold tested** — `nado_king_activation` 0.3400 (`king_activation`),
  `nado_the_sneaky_lock` 0.3022 (`lock_break`), `rocket_the_two_for_one` 0.5578 (`two_for_one`),
  `never_rocket_their_king` 0.4391 (`two_for_one`), `rocket_the_pump_on_sight` 0.0704
  (`building`), `log_the_barrel_on_landing` inf (`incoming_spawn`), and hogeq's
  `log_resets_the_charge` 0.3384 (`charge_reset`) plus its three Earthquake building drills. At
  0.45 exactly two reference lines are refused, both LOW-VALUE LOG boards:
  `hold_the_spell_for_a_target` (0.382) and `log_rolls_forward_not_backward` (0.170); 0.65 adds
  `log_the_ground_swarm` (0.582).
  ⚠ **TWO ROWS OF 30.3's TABLE ARE WRONG**: `nado_clump_for_the_wizard` and
  `nado_pull_the_flock_back` are carried by `king_activation` (both drills start with our King
  asleep), not by value, so neither is vetoed at 0.65/0.90 as 30.3 claimed.
* **The eval/train asymmetry is fixed either way**: `choose_greedy` applied no spell restriction
  of any kind before this change, so the benchmark graded behaviour training never produced.
* **Rulings 31a/31b/31c cost nothing at eval**, measured rather than assumed: root venv, same
  seeds, same checkpoint, pre-31 tree **43.0% / -0.8349** vs post-31 tree **43.0% / -0.8303**.

### 30.4 THE RULING

1. **The criterion is `catch_value_frac` in TOWER FRACTIONS**, not a body count. Config knob
   `sim.ppo_spell_min_value`.
2. **It is applied in the SAMPLING path, in `train_sim_ppo.choose_greedy`, and in the drill
   report's own greedy adapter.** ⚠ Before this change `choose_greedy` applied NO spell
   restriction of any kind, so eval and live cast spells unmasked while sampling ran masked — a
   defect `spell_experiments.md` §7.5 flagged and this ruling fixes. The annealed CELL mask stays
   sampling-only ON PURPOSE: its own docstring calls it a training wheel that decays to
   `ppo_spell_mask_end`, and putting a wheel into the benchmark would grade the scaffold.
3. **⚠ SHIPPED AT `0.0` = OFF, DELIBERATELY.** An 8k training run was live in this tree when the
   veto landed, and its workers call `Config.load()` in their own processes — a non-zero default
   would propagate into a RESPAWNED worker and contaminate that arm (HANDOFF §3n's seam, in the
   other direction). Verified INERT by behaviour, not by banner: 41 casts a 0.20 bar refused were
   all still castable at the shipped default. The next run turns it on explicitly so the veto is
   that run's one attributable change.
4. **⚠ AMENDED 2026-08-27 (close-out). DO NOT SPEND THE NEXT RUN'S ONE ATTRIBUTABLE CHANGE ON
   THIS.** 30.6 re-measured every arm at HEAD under the deck's own venv over two seed blocks
   (600 paired matches): the value form **does not beat its volume-matched random control**
   (+0.047, 0.98σ) and is **worse than the count form at matched volume** (-0.127, 2.99σ). The
   +0.149 (2.14σ) that justified the criterion in 30.3 was one block under torch 2.13.0+cpu and
   does not reproduce under the 2.11.0+cu128 everything else runs. `0.45` remains the right NUMBER
   if the knob is ever switched on — it is still the highest threshold no owner-named
   single-target reference line trips — but switching it on is now an OPEN QUESTION, not a
   measured recommendation.
5. **DO NOT enable the exemption-free form, and DO NOT go back to the count form either**, however
   they measure. Both refuse the four plays this ruling exists to protect, and §4.1 already showed
   that most of what a high threshold buys is the VOLUME cut, which `knever` gets for free by
   deleting the cards. 30.6 turns that caution into the finding: the only arm with a criterion
   effect beyond the volume cut is the one the owner ruled out on doctrine.
6. **⚠ THE VETO MUST BE EVALUATED IN THE WORKER, NOT IN THE PARENT.** The first implementation
   guarded the sampling path with `and not remote`, and `remote = workers > 1` — so under this
   project's own `--workers 12` command the veto would have been ON at eval and in the drill report
   and OFF in training: this ruling's asymmetry inverted, and invisible, because the banner still
   prints. `remote_pool.spell_veto_ids` now decides it worker-side and ships it in the per-step
   payload, and the threshold is passed DOWN as a resolved float rather than re-read from disk —
   the same rule `--drill-frac` had to learn. Measured end-to-end through a real `RemotePool`
   (`scratchpad/remote_veto_smoke.py`): at a 5.0 bar the worker returns the refused card ids; at
   the shipped 0.0 it returns none and never touches the env. conflicts.md 2026-08-27.

### 30.5 UNTESTED, worth one arm each, DO NOT BUNDLE
* **Judge the footprint at IMPACT, not at cast** (entry 15/24). Every predictive cast the doctrine
  names — pre-log a swarm, EQ around a crossing Hog, lead a marching push — is empty at the cast
  instant, and `env._resnap_spell_check` already does this on the REWARD side. It would change the
  criterion for every arm at once, so it is its own experiment.
* **AVERAGE THE RANDOM CONTROL OVER SEVERAL DRAWS.** 30.6's whole difficulty is that `ctl(r)`
  is one ban pattern, and its own effect against the baseline swung +0.176 ± a lot between blocks.
  `spell_arms_valueform.py` hardcodes `random.Random(770011)`; a `--veto-control-seed` and 5-10
  draws would turn arm-vs-control from a coin flip into a test. **This is the prerequisite for
  ever re-opening the question, not an optional refinement.**
* **Scale the threshold by the SPELL'S OWN COST.** A 2-elixir Log should not need the same tower
  fraction as a 6-elixir Rocket, and both drills 0.45 breaks are Log drills. `min_value *
  spec.elixir / 4.0` is the obvious form. NOT TESTED — stated so it is not mistaken for a result.
* **Exempt-with-a-floor** rather than exempt-outright: an exempted cast could still be required to
  clear a much lower bar. Nothing here measures whether that recovers the +0.15 the exemptions cost.

## 2026-08-27 -- RULING 31 (owner): three sim corrections before the long run

### 31a -- Electro Giant: the Zap Pack answers EVERY attacker, including buildings and crown towers

Owner report: "electro giant's reflection stun/damage applies to anything inside the reflection
radius. this includes buildings and crown towers." Clarified 2026-08-27 (superseding an
intermediate all-of-zone reading relayed mid-task): the reflection is **PER-ATTACKER, ON DAMAGE**
-- each hit from inside `reflect_r` zaps ITS OWN attacker; a bystander in the zone who is not
hitting him takes nothing; there is no zone blast. Matches the page prose exactly (revid 436724:
"Enemy units who damage the Electro Giant while being within a 3-tile radius of him will be
damaged and stunned for 0.5 seconds with each hit").

**MEASURED BEFORE (1143af2)**: the per-attacker melee shape already existed -- three Knights
hitting him each took 192 + 0.5 s stun, bystander 0, out-of-zone 0. The gaps were every
projectile path discarding the firer: a Musketeer firing from 2.0 tiles took **0.0** back, a
Cannon (building) firing from 2.0 tiles took **0.0**, a Princess Tower shooting him point-blank
took **0.0** and was never stunned. His NORMAL swing was also crown-reduced to **97.0** per hit
(vs hit_dmg 163.8 @ L11): I5 parked the page's "Reflected Tower Damage" figure (crown_11 = 97) on
the generic `crown_tower_damage`, which `build_spec` routes into `tower_hit_dmg` -- but the
page's Trivia reduces only his REFLECTING damage, so the parked figure was silently nerfing his
swing.

**CHANGE**: `Projectile.shooter` carries the firer (units AND towers) through every shot --
launch, tower arrows, shotgun pellets, spark shards, bounce/boomerang continuations -- and a new
`SimEngine._zap_pack(victim, attacker)` fires on every damage path with a known attacker body:
melee/instant (unchanged), tracking impact, area blast, pierce sweep, splash-secondary. Towers
take the published reduced `reflect_crown_damage: 97` (new KB field) through `_damage_tower` --
so a zap can activate a King, the page's own 2v2 trick -- plus the 0.5 s stun with a lock reset.
Zone membership is centre-to-EDGE: History 16/12/2024 requires the King to be zappable, and his
4x4 body keeps his centre ~3.2 tiles out. A zapped unit keeps lock + charge (the page's Sparky
note). `electro_giant.crown_tower_damage: 97` DELETED; the advisory pin re-plumbed to
`reflect_crown_damage` in both decks.

**MEASURED AFTER** (same boards): swing on towers 97.0 -> **163.8**; melee attackers unchanged
(192 + 0.5 s each, bystander 0.0, out-of-zone 0.0); Musketeer at 2.0 tiles 0.0 -> **192.0 +
0.5 s stun**; Cannon 0.0 -> **192.0 + 0.5 s stun**; Princess Tower 0.0 -> **291.0 over 3 s (3
shots x 97) + stunned 0.5 s per landed shot** -- and the Electro Giant consequently took 630.4 ->
472.8 from that tower over the same window, the real card's tower-crippling effect. NOT
implemented (recorded): direct-damage spells counting as King-Tower attacks for the reflection
(the page's 2v2 spell-origin trick) -- no spell carries an attacker body; noted in conflicts.md.

Test: tests/test_zap_pack_r31a.py (8 tests, byte-identical both decks).

### 31b -- Evo Firecracker: the impact spark zone is 2.5 tiles / 3 s, the shrapnel zones 1.2 / 2.5

Owner report: the PRIMARY spark at the main projectile's impact has a LARGER radius than the
secondary sparks. The wiki agrees and publishes BOTH geometries -- Firecracker/Evolution revid
437259 (re-fetched live 2026-08-27, identical to cache), Evolution Attributes table: Big Spark
Duration 3 sec / **Big Spark Radius 2.5** / Small Spark Duration 2.5 sec / **Small Spark
Radius 1.2** / Small Spark Count x5 / Spark Hit Speed 0.25 sec.

**MEASURED BEFORE** (engine at the 31a commit; one real attack at a target 6.0 tiles out): six
zones -- the carrier's impact zone and all five shrapnel-end zones -- every one radius
**0.75** and lifetime **2.5 s**. `spark_radius_tiles: 0.75` was an old curated value from the
zones-along-the-path model, never adjudicated (R2 #5 covered dps / durations / hit_speed
only), and `spark_duration_large_s: 3.0` sat in the KB CONSUMED BY NOTHING -- the I5 apply
wrote it and no engine field ever read it. So the impact zone was 1/11th of its published
area (0.75^2 vs 2.5^2) and died 0.5 s early. The damage split was already correct: impact
zone ticking 48/0.25 s (192 dps), shrapnel 12 (48 dps).

**CHANGE**: `spark_r_big` / `spark_dur_big` on CardSpec (KB: `spark_radius_large_tiles: 2.5`
ADDED, `spark_duration_large_s: 3.0` finally plumbed, `spark_radius_tiles` SUPERSEDED 0.75 ->
1.2 = the published SMALL radius); each shot carries its own zone geometry
(`Projectile.spark_end_r/_dur`, seeded big at `_launch` for the carrier, small at
`_spark_burst` for the bolts) and `_drop_spark_zone` consumes it.

**MEASURED AFTER** (same attack): six zones -- ONE at the impact point with radius **2.5** /
life **3.0 s** / tick 48, FIVE at the bolt ends with radius **1.2** / life **2.5 s** / tick
12. Edge-gating probed with bodies: at zone-edge minus 0.2 tiles a body takes ticks, at plus
0.3 it takes 0.0 -- so a body 1.2+r..2.5+r tiles from the landing point is hit by the impact
spark and missed by the shrapnel sparks, exactly the owner's reported asymmetry.

Test: tests/test_spark_radius_r31b.py (3 tests, byte-identical both decks).

### 31c -- Hero Wizard: tornado radius 3 (not 4), centred on the fireball's LANDING point

Owner report: "Wizard hero's ability pull seems to have an unusually large radius, check to
see if it's correct. also, the pull center should be at his projectile's landing position,
not starting position."

**RADIUS -- what each source says** (Wizard/Hero revid 437515, re-fetched live 2026-08-27,
identical to cache): the prose says "his fireballs also create 3 TILE RADIUS tornadoes"; the
page's Tornado Ability Attributes table says Radius 4; the Heroes master table (revid on
file) carries no radius at all. I8-8 took 4 under rule (b) (table beats prose). The owner's
in-game look now sides with the prose, and an owner check outranks a lone table column --
the same table family holds the Evo Valkyrie's tornado radius at 5.5 against her own
History's 1/12/2025 nerf to 5, so these ability tables demonstrably go stale.
`attack_nado_radius_tiles` 4.0 -> **3.0**, I8-8 marked superseded in conflicts.md, the 4
recorded there.

**CENTRE, MEASURED BEFORE** (engine at the 31b commit): Hero Wizard, ability up, target 5.0
tiles downrange -- the vortex appeared at the SWING, centred **dy=0.00 tiles from the
Wizard** (his own position), and the fireball's flight changed nothing. His page ties the
tornado to the FIREBALL ("his fireballs also create ... tornadoes"), so the pull belongs at
its landing point.

**CHANGE**: a projectile-delivered attack_nado rides the shot (`Projectile.nado_spec`,
spawned by `_drop_nado` where the flight ends -- the same two sites that drop the Evo
Firecracker's spark zones); an instant/melee attack_nado keeps the old swing-time,
own-position spawn. The two are told apart by `spec.proj_speed > 0` -- the attack's own
delivery shape, the same field that routes a swing through `_launch` -- never by card name.
Only two cards carry attack_nado today: wizard_hero (proj_speed 10 -> landing point) and
valkyrie_evo (proj_speed 0 -> unchanged).

**MEASURED AFTER**: same board -- no vortex at the swing; after the flight, ONE vortex at
**dy=5.0 tiles** (the landing point, within a body radius), pull_radius **3.0**, duration
2.0 unchanged. Evo Valkyrie regression: her swing still spawns the vortex immediately at
**dy=0.00 from her own centre**, radius **5.5** untouched. The two owner complaints were one
mechanism: a 4-tile pull centred up to 5.5 tiles behind the fireball reads as an enormous
radius from the receiving side.

Test: tests/test_wizard_nado_landing_r31c.py (4 tests, byte-identical both decks).

### 31d -- Hero Valkyrie: the "Dash Distance 5.5" is a TARGET-DETECTION BUBBLE, on ONE clock

**Shipped 2026-08-27.** `icebow/tests/test_valkyrie_seek_r31d.py` (17 tests, byte-identical in both
decks). Engine: `CardSpec.ability_seek_tiles`, `_seeking()`, one gate on the area-tick dispatch.
KB: `ability_seek_tiles: 5.5` on `valkyrie_hero`.

#### The evidence, and the three readings it retired
`Valkyrie/Hero` revid 437412 publishes the number and nothing else about it -- the Wild Whirlwind
attribute table's last column is "Dash Distance" (icon `{{Icon|I=Dash Range}}`) reading **5.5**,
and NO prose on any Fandom page mentions it. The brief for this work asserted the wiki documented
no dash at all and that the owner's screenshot was the only evidence it exists; **that premise was
wrong** -- the archived wikitext carries it, and its value agrees with the screenshot.

Four readings were put forward across the session. Three are retired:
1. a cumulative 5.5-tile TRAVEL cap with the spin running throughout (first brief);
2. a 5.5-tile DASH PRE-PHASE, spin on arrival (correction);
3. a Bandit-style leap (the stat-name convention -- Bandit min 3 / max 6, "immune to damage during
   her dash", already modelled as `leap_min_tiles` / `leap_max_tiles` / `leap_speed_tiles`).

**Taken:** an owner-supplied secondary source (a web result -- NOT Fandom, NOT an in-game
observation): *"Target Detection: If an enemy troop or building is anywhere within a 5.5 tile
radius, she will instantly lock onto them and enter her Ultra-Fast 'Whirlwind Stage'. If no targets
are within 5.5 tiles, she will run forward normally until an enemy enters that 5.5 tile bubble."*

#### Why a secondary source beat the wiki's own column name -- the load-bearing measurement
**5.5 IS NOT A NEW NUMBER.** MEASURED: `valkyrie`, `valkyrie_evo` and `valkyrie_hero` all already
carry **sight 5.5**, imported from the wiki into `card_mechanics.json` long before this ruling. The
"5.5 tile bubble" is therefore exactly the aggro radius the engine has always given her. A
fabricated description does not land on a constant the KB already holds. It also explains why no
Fandom prose describes a "dash": there isn't one.

#### The clock -- OWNER RULING, verbatim
*"if she walks for 2 seconds before something enters the bubble, she only enters whirlwind state
for 1.5 seconds. the timer counts down the moment the ability activates."* ONE clock, started at
activation; the walk phase burns it. Modelling it from whirlwind entry would make a mistimed
activation free, and it is not.

MEASURED, bare engine, both decks:
```
enemy inside 5.5 at activation        -> 14 spin turns (3.5 s / 0.25 s), damage from the first tick
empty bubble, enemy enters at +2.0 s  ->  6 spin turns  (~1.5 s of window left) <- the owner's case
empty bubble for the whole window     ->  0 turns, 0 damage, the ability is fully WASTED
enemy arrives after the window closed ->  0 turns
target dies after 2 turns, bubble now empty -> still 14 turns (the stage LATCHES)
building inside the bubble            -> arms it (the source says "troop OR BUILDING")
enemy crown tower inside the bubble   -> arms it (a tower is a building by every reading)
AIR body inside the bubble            -> does NOT arm it (her Target is Ground; the spin skips flyers)
```
The window opens showing **3.4 s**, not 3.5: `ability_delay_s` 1.0 resolves on the following tick
and the tick that opens the window also spends one dt of it. Pinned in the test rather than
smoothed over.

#### The opponent AI needs no new precondition, and that is provable rather than sampled
Her `ability_ai` is family `defensive` with `crowd_n` 2 / `crowd_tiles` 2.5, so `_ability_wants`
only arms with >= 2 enemy bodies within **2.5** tiles -- strictly inside the 5.5 bubble. The bot
**cannot** fire her on an empty board, so a target-in-bubble precondition would be dead code. Two
tests state the property directly. The one residual is the arm->resolve window (the bot's rolled
`reaction_s` plus `ability_delay_s` 1.0), in which those bodies can die or walk out; that is the
same window every other hero's board read already pays. A 150-match probe was run and is reported
as INCONCLUSIVE, not as support: an idle agent gives the opponent's Valkyrie nothing to crowd
against, so it produced **0** Hero Valkyrie activations in 150 matches.

#### Deliberately NOT implemented
* **The speed boost.** The Heroes blurb says "increasing her movement speed" and the secondary
  source calls the stage "Ultra-Fast", but the ability table prints **Speed Medium (60)** --
  IDENTICAL to her body -- and "Ultra-Fast" is not one of the game's tiers (Slow 45 / Medium 60 /
  Fast 90 / Very Fast 120). No source publishes a number, so any multiplier would be invented.
* **The 15% damage reduction** -- see the bug below. It has never been wired, and this ruling did
  not cause that.

#### ⚠ A LIVE BUG FOUND WHILE MEASURING THIS (found, NOT fixed)
Her KB row writes **`ability_dmg_reduction: 15.0`** -- the CardSpec FIELD name. `build_spec` reads
**`ability_damage_reduction`**, which is the key the Monk's row uses and the reason his 65% works.
Hers silently resolves to **0.0**, so the Hero Valkyrie has taken FULL damage through Wild
Whirlwind since I8. MEASURED: 1000 damage mid-ability costs her 1000.0 hitpoints; the published 15%
would cost 850.0. Control: `build_spec(monk).ability_dmg_reduction == 0.65`.

NOT FIXED HERE, deliberately: an 8k PPO run is live and she is a hero candidate in **143** opponent
meta decks, so the one-word fix is a behaviour change to sequence after it, not to bundle into a
ruling. Pinned by `test_the_published_15pct_damage_reduction_is_NOT_wired_KB_KEY_TYPO`, which flips
when it is fixed.
