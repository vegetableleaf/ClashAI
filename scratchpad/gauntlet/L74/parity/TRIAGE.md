# PARITY v2 triage — 2026-10-12

**Status: offline triage and conservative replay repair implemented; no confirmed SIM mechanic errors and no SIM rerun yet.** The eight leaders are contaminated by replay/matching artefacts. Prince/Valkyrie combat remains unresolved. No defensible first fork patch follows from these measurements. Do not label an N+1 hit-timing hypothesis a confirmed result.

Source: `C:/Users/benpe/pod_backup_weekend/podD/x_PARITY_v2/results/PARITY_v2/`. Recomputed from all 100 `sources/` and `new/` reports: **25,236 available decisions, 61,761 matched unit observations, unit position MAE 1.387123 tiles, unit HP MAE 291.330111, tower HP MAE 383.575665**. All new/fork sample arrays compare exactly equal. Fork remains the zero-patch control. There are also 7,206 unavailable decisions after SIM termination, 31,351 live-only and 43,625 SIM-only unit rows. Missing units are not assigned zero HP.

## Triage, in original associated-impact order

Impact is the old report's exposure-normalized association score, including tower error and missing bodies; it is neither damage caused by this card nor a count of independent failures. Exposures can contain SIM-only bodies. First-row counts below use **live tracks actually present during available measurements**, not all bodies in all source frames.

| Group; impact | Classification | Evidence / growth | Harness fix and remaining uncertainty |
|---|---|---|---|
| GoblinDrill; 5037.61 | **REPLAY ARTEFACT confirmed** | E1: traveling 3,720-HP body, 1,908-HP surface building and 293-HP goblins all have ID 27000013. Surface is injected again at t1215; first surface error already 16.522 tiles / 1,606 HP. 111/111 observed tracks mismatch on their first row. | 96 proxies → 20 trajectory-linked deploys; 76 exclusions. Target the unique subsequent surface point, estimate tick from the travel body's visibility interval. Remove surface/child repeats. Unpaired diggers excluded, not assigned a guessed tunnel duration. |
| GoblinHut; 4736.97 | **REPLAY ARTEFACT confirmed** | E2: 1,885-HP hut and 212-HP spearmen share ID 27000001. Child at t3631 becomes another hut; at t3641 its error is already 1,502 HP. Hut's earlier 171-HP offset also confounds levels. 4/4 first rows mismatch. | 3 proxies → 1 stationary parent, 2 child exclusions. Broad parent/child matching prevents comparing a hut against a spearman. Spawn cadence cannot yet be diagnosed. |
| Prince; 4509.14 | **REPLAY ARTEFACT / mechanics unresolved** | E3: first row missing at t165; t195–220 then agrees to 0.059 tiles / 0 HP. Another Prince has 0.346→0.621 tile error at t1070→1080 with 0 HP error. All 19 measured tracks first appear missing. This does not establish a charge threshold bug. | 23 proxies → 10 stationary-start estimates; 13 moving/charge-ambiguous starts excluded. Never reset a visibly moving Prince as a certified uncharged deployment. First-observed velocity cannot recover prior charge distance, stun/reset history or actual tap time. |
| Valkyrie; 4296.51 | **REPLAY ARTEFACT confirmed; spin mechanics unresolved** | E4: live max HP 2,302 versus an immediate 469-HP error at zero position error; a second match has max HP 2,525 and 246-HP error. Both equal the gap to 2,771, consistent with assumed level 15, not evidence of a spin hit. 30/30 first rows mismatch. | Retain/retime 31 plays; explicitly use 21 base, 3 evolved, 7 hero sightings, rather than match-wide maximum form and synthetic cycle. Uniform assumed levels and undriven abilities still prevent attribution. |
| 13000043; 4011.40 | **REPLAY ARTEFACT confirmed: unmapped observation** | E5: two 1,949-HP bodies first appear t2126 and remain unmatched; no corresponding injection exists and the frozen catalog has no entry for this ID. 2/2 first rows missing. | Record unresolved public identity, do not invent a deploy or silently coerce to a base card. ID structure suggests an AngryBarbarians evolution, **unconfirmed by this catalog**. Requires a verified public alias and re-extraction; existing sanitized plays cannot recover it. |
| GoblinGiant; 3823.33 | **REPLAY + MATCHING ARTEFACT confirmed** | E6: t1106 live tank HP 4,519 has error 4,326 (=4,519−193). At t1132 a live 193-HP rider has the same error in reverse. Spawn order paired tank with rider. Later riders were also injected as tanks. 85/88 first rows mismatch. | 67 proxies → 6 parent plays, 61 child exclusions. Match broad parent and child roles separately, and pin the visible form (5 base / 1 evolved). Some child subtypes remain indistinguishable. |
| MergeMaiden_Normal; 3606.39 | **REPLAY ARTEFACT / transformation unresolved** | E7: first matched row has 145-HP error; same live identity's max HP changes 1,484→1,629 at t1193. Form/level/identity transition is unaccounted for. 6/6 first rows missing. | Exclude all 9 normal-form proxies (also 5 mounted variants elsewhere). These are variant body observations, not certified new card plays. Do not infer opponent elixir to select a form. |
| Tombstone; 3433.32 | **REPLAY ARTEFACT confirmed** | E8: 701-HP building and 108-HP skeletons share ID 27000009; new skeleton batches repeatedly become Tombstone plays. Root has 74 HP error at age 0.5 s; skeleton has 11 HP error, both consistent with level offsets. 64/64 first rows mismatch. | 51 proxies → 11 stationary parent estimates, 40 child exclusions. Separate parent/child matching. Corrected replay is required before testing periodic/death-spawn cadence. |

Only 3/88 GoblinGiant first rows are aligned; two diverge later. Those do **not** establish mechanics errors: parent/rider ordinal ambiguity and the already divergent surrounding battle remain. A tick-zero mismatch is a diagnostic clue, not proof by itself. Here the role/coordinate/form evidence independently establishes the artefacts.

## Trace excerpts

Pointers below use **zero-based JSON `samples[index].rows[index]`** in the named `new/<match>.json`. Complete first-12-row excerpts, original commands and source identities are in [`triage/traces.json`](triage/traces.json). Live coordinates/HP come from the source frame joined with the original `Tracks` algorithm; v2 did not retain signed SIM HP or native character subtypes.

| ID | Match suffix (all `live_play_20261008_…`) | Exact excerpt numbers |
|---|---|---|
| E1 | 000844 | `[83][6]` t1130: live (9235,4164), HP 3720, SIM missing. `[84][6]` t1140: 1.190 tiles / 1821 HP. `[87][7]` t1185: 13.690 tiles / 2069 HP. `[90][8]` t1215: surface (17000,26000), HP 1899/max1908, 16.522 tiles / 1606 HP. `[94][9]` t1255: goblin max293, HP error3427. Re-plan row10: target (9235,4164)→(17000,26000), tick1130→1125, visibility interval1120–1130. |
| E2 | 053140 | `[285][8]` t3569: hut max1885, missing. `[286][8]` t3579: 0 tiles /171 HP. `[287][8]` t3589: child max212, missing. `[288][8]` t3600: child 0.119 tiles /19 HP. `[292][9]` t3641: next child 1.620 tiles /1502 HP. |
| E3 | 002006 | `[2][6]` t165: Prince max2790, missing. `[3][9]` t195: 0.059 tiles /0 HP, repeated through `[6][9]` t220. `[78][9]` t1070: 0.346/0; `[79][9]` t1080: 0.621/0. |
| E4 | 001328; 002006 | 001328 `[87][7]` t1142: max2302, missing; `[88][6]` t1152: live full HP2302, 0 tiles /469 HP. 002006 `[104][6]` t1400: full HP2525, 0 tiles /246 HP. Cannot deduce a signed damage event from these absolute errors. |
| E5 | 043718 | `[169][8]`, `[169][9]` t2126: two ID13000043 bodies at (13800,17499)/(15200,17499), max1949, both missing. Still missing at `[173][8]`, `[173][9]` t2166. |
| E6 | 012304 | `[89][7]` t1106: tank max4519, error4326 HP /0.900 tiles. `[90][8]` t1132: rider max193, error4326 HP /0.631 tiles. `[90][9]` other rider: HP error0. |
| E7 | 003019 | `[80][7]` t1173: live1165/max1484, 0 tiles /145 HP. `[82][7]` t1193: live959/max1629, 0 tiles /32 HP. `[186][7]` t2413: next full-HP1484 body, 0 tiles /145 HP. |
| E8 | 003700 | `[162][9]` t2016: building696/max701, 0 tiles /74 HP. `[163][10]` t2026: skeleton108/max108, 1.481 tiles /11 HP. Source play t2097 at (10004,11505) is a skeleton batch mislabeled as Tombstone. |

## Offline re-plan and implemented rules

`--fix-artefacts` requires `--mechanics-replay`; both are **default off**. No live scripts, SIM sources, remote machines or client code were edited or executed. Changes are uncommitted.

Measured over the exact saved 100-match cohort:

| Quantity | Count |
|---|---:|
| Original opponent injections | 2,888 |
| Retained opponent injections | 2,225 |
| Excluded injections | 663 |
| Retained tick changes | 2,224 |
| Retained coordinate changes (Drill) | 20 |
| Unique excluded or retimed/retargeted injections | **2,887** |
| Retained injections with explicit public form | 2,225 (423 non-base) |
| Matches with changes | 100 |
| Own plays preserved exactly | 3,594 |

Thus one retained injection keeps its old tick/point but gains an explicit form. These are **planning counts**, not successful SIM-deploy counts or measured improvements. [`triage/plans.json`](triage/plans.json) records every source row, retained action, exclusion and inference receipt; [`triage/input_hashes.json`](triage/input_hashes.json) pins source/new/fork bytes.

Exclusion breakdown: 485 parent-ID child bodies; 43 unresolved chargers; 34 moving/unresolved building bodies; 31 Miner tunnel timings unobserved; 29 Drill surface repeats; 14 Maiden variants; 15 non-unique/unrecoverable proxy-body joins; 10 unresolved Drill destinations; 2 child/play ambiguities near a public spawner. These sum to 663. Not every excluded event is proven to be a spawn: ambiguous observations are explicitly quarantined.

Rules use same-side public bodies, exact proxy origin within 2 millitiles, track segments split after >60 ticks of absence, and the preceding visibility frame. Child-role classification requires a max-HP ratio <0.45 of the same public card family's observed maximum in that match/side; this separates the large measured parent/child gaps without claiming a level. Buildings need two stationary initial sightings within 40 ticks. Drills need fast travel (>150 millitiles/tick), a unique stationary surface within 40 ticks after travel ends, intermediate HP and a plausible endpoint distance. Evolution relocations linked to an earlier surface are excluded. Known differently-ID'd child bodies within 2.5 tiles /40 ticks of a parent are ambiguous and excluded; opposite-side parents cannot cause exclusion.

**Timing is estimated, not recovered exactly.** The midpoint of `(previous visible frame, first sighting]` replaces the old first-sighting tick. That interval bounds *visibility*, not a network tap or hidden spawn command; client visibility delay can start earlier. Initial moving positions for ordinary troops are not back-projected through unobserved combat. Stationary charger starts are the only retained charger estimates. A lone emerged Miner gives no launch time and is excluded. Never initialize an invented charge state. The Drill destination inference uses future public observations for offline reconstruction only.

The adapter derives form templates from each runtime's own reset/save API, then changes only the injected card's evolution counter/hero membership. Public base/evolved/hero sightings determine that injected play, not match-global maximum form, hidden opponent cycle, or synthetic mana. Other cards, combat state and own hand synchronization are preserved. The opt-in matcher separates broad parent/child roles (plus Drill travel/surface), avoiding the demonstrated tank/rider ordinal swap; it still cannot distinguish every child subtype or clone. The next rerun saves paired public x/y/HP/maxHP values to support better diagnostics.

## Short-horizon error growth (existing v2 baseline)

**Actual spawn timestamps were not recorded.** These are ages since the first observed **live** body, with its identity split on >60-tick gaps. They are a left-censored proxy for spawn age, not true tick-zero mechanics measurements. The 95 observations of bodies already present in the opening frame are included and flagged in the JSON. A SIM-only row has no live age; all 43,625 such rows are excluded from age bins and retained in match-time coverage. MAEs use matched observations only; live-only counts remain visible. No post-fix MAE is claimed.

| Observed unit age | Matched observations | Live-only observations | Position MAE (tiles) | Unit HP MAE |
|---|---:|---:|---:|---:|
| 0–<2 s | 11,954 | 9,432 | 1.050 | 179.5 |
| 2–<5 s | 15,782 | 6,779 | 1.369 | 246.1 |
| 5–10 s inclusive | 17,107 | 6,990 | 1.550 | 319.1 |
| >10 s | 16,918 | 8,150 | 1.478 | 384.4 |

| Match time | Matched unit observations | Position MAE | Unit HP MAE | Tower HP MAE |
|---|---:|---:|---:|---:|
| 0–<30 s | 9,459 | 1.519 | 195.1 | 53.8 |
| 30–<60 s | 13,295 | 1.375 | 274.3 | 236.1 |
| 60–<120 s | 19,129 | 1.328 | 291.1 | 421.6 |
| 120–<180 s | 18,413 | 1.374 | 350.0 | 653.0 |
| ≥180 s | 1,465 | 1.584 | 333.4 | 1132.5 |

[`triage/analysis.json`](triage/analysis.json) also gives all eight **per-group age curves**, first-row mismatch counts, unmatched denominators and the original ranking. HP error grows substantially with age and match time. Position error is not monotonic. Whole-match error is useful as a snowball-contaminated severity measure, **not a mathematical upper bound on every short-horizon mechanic error**. Survivor selection, missing units, ordinal mismatching and terminal censorship all affect these curves. The corrected replay should be compared on common available ticks and accompanied by its changed exclusion/rejection counts.

## Confirmed mechanics and Phase 5 lookup queue

**Confirmed real mechanic errors: none. Ranked confirmed fork-patch candidates: empty.** A valid candidate requires a correct public injection, known role/form/level, initially matching local state, and a reproducible later discrepancy. The saved v2 report does not meet that condition for any of the top eight. Sampling is usually 10–30 ticks (0.5–1.5 s), so it cannot identify an N versus N+1 tick hit difference.

The following are **conditional investigations in associated-impact order**, not findings from decrypted code. Phase 5/redump was not opened for this ticket. Look for the named behavior/data references, not fabricated symbols or addresses.

| Priority | Group | What to look up in the redump Ghidra project; falsifiable mechanic hypothesis after input repair |
|---:|---|---|
| 1 | GoblinDrill | GoblinDrillDig → stationary building transition; destination storage; travel speed/start delay; spawned-character provenance; evolved re-burrow/re-emerge lifecycle. Test tunnel arrival and first-spawn timers separately from deploy tick. |
| 2 | GoblinHut | GoblinHut_Rework spawn timer, spawn offsets, first spawn, death cleanup; child character vs owning card ID. Test a cadence offset only with level-matched hut/children. |
| 3 | Prince | Charge accumulation threshold and distance/speed integration; deploy freeze; resets on attack, stun, displacement and target changes. Hypothesis: a charge transition/reset differs, **not yet supported by a clean trajectory**. |
| 4 | Valkyrie | Attack wind-up/progress, radial target enumeration and hit application phase; evolved pull and hero behavior; level scaling. Hypothesis: spin damage lands one tick later/earlier. Need tick-resolution public controlled evidence; these sampled traces cannot settle it. |
| 5 | 13000043 | Public class-13 form → base card/character mapping and evolution cycle/formation. Verify proposed AngryBarbarians alias before adding it. This is an identity repair prerequisite, not a combat patch. |
| 6 | GoblinGiant | Rider creation/attachment, independent targeting, release on parent death, evolved additional spawns, child ownership IDs. Hypothesis: rider release/target cadence differs only after parent/rider matching is proven. |
| 7 | MergeMaiden_Normal | Variant choice, normal/mounted transition, HP rescaling/preservation, deploy versus transformation events. Public animation/appearance evidence is required; do not consume hidden opponent elixir. |
| 8 | Tombstone | Building lifetime decay; periodic spawn interval/offset; death-spawn event ordering and batching. Hypothesis: first/death spawn is shifted relative to expiry; evaluate with equal level and a correctly timed parent only. |

Unresolved coverage requirements: public alias for 13000043; exact deploy/charge history for excluded observations; per-character identity for mixed children/transforms; actual levels instead of assumed15; omitted enemy spells and own abilities; controlled local initial state. Excluding an uncertain opponent play avoids a false injected card but also omits real pressure, so the resulting full-match replay remains exploratory. The first rerun is an artefact-removal measurement, not proof of mechanics fidelity.

## Files, verification and rerun

Implementation: `inference.py`, `planning.py`, `mechanics.py`, `core.py`, `driver.py`, `run_parity.sh`. Analysis/tests: `triage_analysis.py`, `tests/test_triage.py`, `verify_triage.py`. Evidence: `triage/{analysis,plans,traces,input_hashes,verification}.json`, `triage/GATES.md`.

Offline checks use the existing local Python environment; no installs or network. Run:

```powershell
research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/parity/verify_triage.py
python scratchpad/gauntlet/L74/parity/triage_analysis.py --verify
```

Measured verification: **50 tests passed** (synthetic artefact rules plus all existing harness tests); offline analysis reproduced the published v2 aggregates and checked new/fork trace equality, injection accounting, chronological actions and unchanged own plays. The actual `driver.py plan --mechanics-replay --fix-artefacts` CLI also completed **100/100** at `output/triage_replan_20261012/`: 32,442 planned decisions, 5,819 actions (3,594 own +2,225 opponent), 663 play exclusions. No engine import occurred in offline analysis. Real-runtime form-template and replay behavior remain pod-validation work.

The pod command below is **provided, not launched**. Run from the repository root after the changed harness is already on pod D. It reuses the exact saved cohort, keeps level15 assumptions, uses the existing CPU lock, and requires a fresh output directory. No build or SIM-source patch is needed. Old's Hero Ice Wizard unsupported result is still expected; compare new/fork on their shared measurements.

```bash
MECHANICS_REPLAY=1 FIX_ARTEFACTS=1 \
COHORT=/workspace/results/PARITY_v2/sources \
OUT=/workspace/results/PARITY_v2_fixed_injection \
WORKERS=24 bash scratchpad/gauntlet/L74/parity/run_parity.sh
```

If the archive is mounted elsewhere, change only `COHORT` to its `sources` directory. Leave `ASSUME_LEVEL` unset when using `COHORT`. A previous output directory is deliberately refused. `DONE` alone does not mean fidelity passed: inspect `SUMMARY.txt`, unavailable ticks, exclusions, command rejections and first-appearance traces.
