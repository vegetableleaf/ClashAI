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
