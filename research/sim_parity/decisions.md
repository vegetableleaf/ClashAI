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
