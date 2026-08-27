# Phase I ledger — what shipped, what proves it, where it lives

One row per stage, I0 through I10, on branch `sim-parity` (worktree `C:\Users\benpe\ClashBot-parity`).
This is the artifact to read to know the project is done. Every "proof" column is a number that was
measured, not an adjective; the argument behind each one is in `conflicts.md` under its stage.

**Read `conflicts.md` first if you are picking this up cold** — its top now carries a single
numbered checklist of the ~19 things only the owner can settle, several of which are in-game
observations that take one battle each.

---

## The table

| Stage | What shipped | Measured before → after | Commits |
|---|---|---|---|
| **E** (pulled forward) | Seven engine/KB items the owner pulled out of R2 #8 so implementation would not block later: Elite Musketeers rework, Furnace lifetime, Ram Rider snare, Rage as a friendly buff, Little Prince ramp grace, Dark Prince splash, Giant Snowball targeting | Rage: `buildings_only` → friendly-target (the spell could not buff its own army at all). Dark Prince splash 1.9 flat → **1.1**, and a stale `*_tiles` key can no longer silently shadow the real one | `50a15de`..`9f0e19d` (7) |
| **E1** | Furnace threat price re-derived by measuring how long it survives instead of assuming two waves | Owner-approved measurement replacing a guess; recorded in `conflicts.md` §E1 with the original kept | `c460939` |
| **I0** | `tools/parity_check.py` — the two-deck gate. Shared code that drifts now fails loudly; a DECK list for deliberate differences and a DRIFT list that is meant to shrink | src/clashrl 80 files: **60 identical, 20 declared, 0 UNEXPECTED**. Verified-to-fail: a deliberate divergence exits 1 | `be47ddd` |
| **I1** | hogeq → icebow backport. `engine.py` and `cards.py` **byte-identical** across decks | evolutions reporting a cycle count **6/42 → 40/42 → 42/42**. Level-scaling correction: icebow worst delta −0.93% (tesla L15 322→319), hogeq −0.76% (mighty_miner L15 3294→3269). Card head width **10 before and after** | `8ca6aa5` |
| **I2/I3** | The opponent's evolution became a measured slot instead of deck index 0, then every legal evolution, drawn per match | decks fielding a REAL evolution **0 → 1000/1000 (100.0%)**; phantoms **0**; distinct evolutions fielded **0 → 42 of 42**. ⚠ The R4 slot data was then STRIPPED: `evolutionLevel` reports card OWNERSHIP, not the fielded slot | `e08e0af`, `7febdc4`, `84e144a`, `9a57aef` |
| **I4** | Importer hardening: dry-run by default with a field-level diff, `/Hero` scrape, `import_allowlist.json`, `import_pins.json`, per-row provenance, `lifetime_s` declared, crown audit ported to hogeq | **180 pages walked**; the uncategorized-subpage probe found the 3 stubs a category walk misses (the Elite Barbarians trap). Negative controls both fired: an announced-but-unreleased page produces NO row, and a synthetic stale rocket 371 → 341 is caught. Live dry-run reconciled with **0 surprises** | `9969113`, `334c736`, `3129735`, `89e118d`, `0905104` |
| **I5** | The adjudicated ledger applied: the import-owned half through the pins, then **258 `cards.yaml` fields** by hand in house style, both decks. Per-card `chain_tiles` | `stat_sweep --all` **exit 0 both decks, MISMATCHES 0** over 174 cards cross-checked live. Crown audit **RED → GREEN** — and ⚠ P1: the tool could never have gone green before, because it was auditing the WIKI, not us | `6f6fb80`, `835a346`, `ea5e0d9`, `e33abb1` |
| **I6** | Folded into I5. R1a found zero missing evolutions beyond the KB's 42; the only work was `elite_barbarians_evo` re-sourced from its live stub page | `elite_barbarians_evo` is no longer null (recorded in `conflicts.md`, I5 section) | in `835a346` |
| **I7** | All **8 champions** firing enemy-side at full fidelity: Archer Queen, Boss Bandit, Goblinstein, Golden Knight, Little Prince, Mighty Miner, Monk, Skeleton King. `ability_kind` dispatch replacing per-card flags. Electro Dragon chain rebuilt under rulings 11/12/15 | Ruling 5's **newest-body bug** found and fixed: `champion_ability` selected "any body with a use left", which is wrong the moment two bodies coexist. Chain: `hits_per_attack: 12` was a MODEL error and is now a budget. 12 evidence conflicts, 3 wrong brief premises recorded | `1a746e6`, `3cb4fff`, `e6e317f`, `07685ee`, `9a7a660`, `8998e00` |
| **I8** | All **16 live heroes**, 12 ability shapes, the three-slot loadout (Evolution + Hero + Wild), `support:` tower troops consumed, evo_audit extended to the whole loadout | hero slot: **841/1000 decks (84.1%) REAL, 0 phantoms, 1 UNFILLED (0.1%)**; 16 distinct heroes fielded. Wild slot where both were legal: **evo 34.6 / hero 33.1 / none 32.3**. Ruling 7's refund proved against a twin run (killed inside the cast **+2.00 elixir**, after it **+0.00**). 9 measured bugs fixed, incl. three hero rows that had scraped the WRONG TABLE (musketeer_hero was the turret's 1536hp/280dps) | `e40637d`, `e36a18a`, `f96acfa`, `72d59cf` |
| **I9** | Friendly-target spells (`rage`, `clone`), drill evolution cycling, sim_view chain/ability/zone rendering, the zero-damage king-activation fix, the base Barbarian Barrel's Barbarian | Drills: evolutions were permanently **OFF** — 0 of 26 icebow drills, 0 of 24 hogeq — the opposite of the brief's premise. Chain arcs: **zero frames alive in 12 s** while the same run landed 192/960/1152/576/576, so a draw call alone would not have helped; it needed an engine RECORD. Five spells were waking the enemy king for free on a zero-damage hit | `fc48814`, `8d6180d`, `a10d32c`, `d817cb1`, `2f7150d`, `62f484e`, `dfbae6d` |
| **I10** | hogeq test debt to zero; hogeq's inert icebow reward terms stripped; this ledger; the owner checklist | hogeq **1016 tests, 3F + 39E → 0F + 0E** (55 skipped, each naming the card it needs). `sim/env.py` **2353 → 1767 lines (−586, −24.9%)** with **0 behaviour change over 9,600 decisions**. icebow held **993 OK (21 skipped)** exactly | `d993514`, `984d41a`, + this commit |

---

## Suite growth across the project

| Stage | icebow | hogeq |
|---|---|---|
| start | 773 OK (21 skipped) | 692 tests, 42 known failures |
| I4 | 790 OK | — |
| I7 | 890 OK | — |
| I8 | 935 OK (21 skipped) | — |
| I9 | 993 OK (21 skipped) | 1016 tests, 3F + 39E |
| **I10** | **993 OK (21 skipped)** | **1016 OK (55 skipped)** |

hogeq's suite was never green before I10. Its "42 baseline" was quoted for weeks as a known
quantity; it was in fact 42 tests asking hogeq's deck for cards it does not hold, and not one of
them described a hogeq behaviour. See the I10 commit body for the per-file breakdown.

---

## The gates, and what each one is for

Run from inside a deck directory with `PYTHONPATH=src`.

| Gate | Command | I10 result |
|---|---|---|
| icebow suite | `python -m unittest discover -s tests -t .` | **993 OK (21 skipped)** |
| hogeq suite | same | **1016 OK (55 skipped), 0F 0E** |
| two-deck parity | `python tools/parity_check.py --strict` | **PARITY OK, 0 unexpected** (62 src files identical, 18 declared) |
| card stats vs live wiki | `python tools/stat_sweep.py --all` | **exit 0 both decks, MISMATCHES 0**, 174 cards, 31 UNMAPPED (reported, never guessed) |
| crown-tower damage | `python tools/crown_damage_audit.py` | **exit 0 both decks** |
| evolution + hero slots | `python tools/evo_audit.py` | **exit 0 both decks, identical output**; evo 1000/1000 REAL, phantoms 0; hero 841/1000 REAL, phantoms 0 |
| head shapes | see below | icebow **10**, hogeq **11**; real checkpoints load with **nothing dropped** |
| strip neutrality | `python ../research/sim_parity/scripts/i10_reward_probe.py --before <old env.py>` | **0 / 24 matches diverge** over 9,600 decisions |

**Negative controls — every gate was re-confirmed to still FAIL on a deliberate regression:**

| Gate | Injected regression | Result |
|---|---|---|
| `parity_check --strict` | one comment line appended to hogeq's `sim/engine.py` | **exit 1**, `UNEXPECTED: 1`, names the file. exit 0 again once reverted |
| `crown_damage_audit.py` | rocket `crown_tower_damage` 341 → 371 (the pre-1/6/2026 value) in a temp KB via `--kb` | **exit 1**, `** OUR VALUE IS STALE ** [crown]`. exit 0 against the real KB |
| `i10_reward_probe.py` | none needed — its own `--control` and `--no-pin` modes are the controls | control 0/24; unpinned 3/24 **with and without** the strip, i.e. pure noise |

**Head-shape check.** The card head must stay 10 for icebow and 11 for hogeq or every existing
checkpoint refuses to warm-start. Verified against REAL checkpoints in the live tree, read-only:

```
icebow  policy_BEST_m18000_20260826.pt   ck n_cards=10   card_head.weight (10, 328)   deck identities 10
hogeq   policy_sim_ppo_best.pt           ck n_cards=11   card_head.weight (11, 328)   deck identities 11
both    PolicyNet.load_compat dropped:   NOTHING
```

`load_compat` is the production loader; "dropped NOTHING" is the real assertion, because a
`strict=False` load would silently leave a mismatched head at its random init and still print
"warm-started".

---

## Two traps for whoever runs the merge

1. **`core.autocrlf=true` in this worktree, and 9 shared source files live as LF in the working
   tree** (`engine.py`, `cli.py`, `card_import.py`, `perception.py`, `replay_mine.py`,
   `sim_view.py`, `train_rl.py`, `sim/scenarios.py`, `sim/drill_env.py` — each in BOTH decks, so
   each pair matches). A `git checkout` of ONE deck's copy rewrites it as CRLF and
   `parity_check` immediately fails on a file whose `git diff` is empty. Hit once during I10 and
   fixed by rewriting the bytes, not by another checkout. If parity fails on a file git says is
   unmodified, this is why.
2. **The sim is not reproducible across processes.** See `scripts/i10_reward_probe.py` and the
   `conflicts.md` I10 entry: `_settle_spell_casts` keys spell attribution on `id(Unit)` and
   CPython reuses addresses. Any A/B on this sim has a noise floor of ~2-3 matches in 12 unless
   Unit objects are pinned. This is unfixed and needs an owner ruling.

---

## What Phase I deliberately did NOT do

Recorded so a later pass does not read a gap as an oversight. Full lists live in `conflicts.md`
under each stage's "NOT IMPLEMENTED, DELIBERATELY" heading.

* **Our decks stay unchanged.** Heroes and champions are enemy-side only (ruling 1): no
  action-space change, and every existing checkpoint keeps loading.
* **Detector retraining** for the 16 hero classes and 16 hero abilities. `detect_classes.yaml`
  already lists all 32, so the taxonomy is complete and nothing is missing; training a detector
  that can SEE them is out of Phase I scope.
* **Monk's SPELL reflection** — projectile reflection is complete; the page never enumerates
  which spells count as "projectile spells", and guessing redirects real damage onto a tower.
* **Mirror**, the Clone's forward shove, Goblinstein's clone-anchor rule, Skeleton King's
  sub-troop soul exclusions, the Golden Knight's facing arc, the graded Royal Rescue pushback.
* **Waypoint pathing**, hero drills, `import_mechanics.py` modernization beyond the E2 fix.
