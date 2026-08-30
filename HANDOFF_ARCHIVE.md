# HANDOFF archive

Resolved dated sections moved out of `HANDOFF.md` on 2026-08-29 so the always-read
handoff stays small. **Nothing here is deleted** -- every section is verbatim, and the
main file keeps its header plus a pointer, so `grep` on a section number still finds it.

Selection rule (measured, not by date): a dated `3x`/`4x` section moved here iff it is
NOT open/pending AND is cited <=3 times elsewhere in the handoff. Sections still cited
heavily -- notably **4a** (12 references: the critic-dip figure and the
compare-at-matched-episodes rule) -- stayed behind.

---

## 3b. 2026-08-19 daytime batch (user's five tasks)

1. **Crown damage + user's EQ values — DONE `7bfe6ed`.** Curated overrides in BOTH decks
   (rocket 342, log 35, lightning 264, zap 48, poison 21; EQ 81/49/283 user-read in-game).
   Damage-sensitive suites pass unchanged (they measure relatively, per §8).
2. **Mighty Miner 14 → 15 — DONE `7bfe6ed`.** hp 2979→3269, stages [58/296/594], bomb 531.
3. **Spirit Empress — DONE `4d2ebe5`.** Was a 4-elixir 1798-HP flying hybrid: the 08-14 import
   caught the Fandom page MID-EDIT-WAR. Now two curated forms + ONE deploy choke point picking by
   caster elixir (<3 uncastable, [3,6) ground 3e melee fast ground-only, ≥6 air 6e ranged-5
   flying; exactly 6.0 = air). 10 tests per deck. Mirror rule N/A (no Mirror in sim).
4. **Sim speed — DONE `935350c`, +24%** (3.04→3.77 matches/s), byte-identical fixed-seed digest
   at every step: `__deepcopy__→self` on CardSpec/CardDB/Config (deepcopy was 34% of runtime via
   counterfactual forks), `slots=True` on 6 engine dataclasses (NOT _Zone — custom __init__),
   `card_threat.profile` memoised per-db. Top remaining costs are SEMANTIC (CF rollouts ~0.9s,
   obs building ~26%) — do not "optimise" them without a reward decision.
5. **Pathing — DONE `6c1eec8`.** Both bugs reproduced, measured, fixed from mechanism research
   (game-file Mass/CollisionRadius datamine + April-2025 rework notes + push-mechanics video):
   * STICK: a Hog vs ONE pinned defender dead-centre went from **NEVER (60 s cap) → knight +0.6 s
     / ice_golem +0.8 s / pekka +1.5 s / skeleton_king +1.4 s** over the 6.5 s baseline — mass-
     graded slide, never a latch. Mechanism: walking bodies slide along the contact TANGENT toward
     their target (k = clamp(0.45·m/o, 0.12, 0.9)); attackers hold ground (tested).
   * CRAM: 8-body push **24.7 s → 17.3 s** all-across, worst stall **6.6 → 4.5 s**. Mechanism:
     between two same-team walkers the REAR pushes the FRONT — a follower's velocity is never
     zeroed. The 2026-08-15 stopped-attacker WALL rule is untouched.
   * ⚠ TRAP for the next reader: the Evo-Recruits charge probe misread the flow fix as a
     charge-through-shield bug — two simultaneous 133 swings ≡ one 266 charge hit numerically.
     The probe now isolates the centre recruit. If a damage test breaks after a pathing change,
     check simultaneity before doctrine.
   * 4 regression tests per deck (`test_pathing_flow.py`). Research corpus incl. the datamined
     mass tiers is in the CR pathing report (session log 2026-08-19); `card_mechanics.json`
     already carries per-card mass/collision the engine uses.


## 3c. 2026-08-19 evening batch — live reward truthing (`3db2193`)

Three user reports, all confirmed real:
1. **Live `spell_waste` did not exist** — the spell-impact frame sampler was RETIRED (env.py's own
   note) and spells were paid AT CAST by aim geometry. Now: a pending-impact queue verifies every
   spell against the TEAM TRACKER at impact (tracks bridge the detector's ~31% per-pass misses, so
   a blinked frame can't fake a whiff). Tower-aim exempt on LIVE towers only.
2. **`nado_bad`** (both sims + live-approx): pulled units that survive, wake no king, and end ≥1
   TRUE tile closer to our princess towers = the cast improved the enemy's position. The
   verification caught a real bug pre-ship: normalized-space distance mixes the 18×32 anisotropy
   (a 2.2-tile pull measured 0.9), distances are now per-axis tiles.
3. **The HOLD-despite-enemy-plays gate**: `_needs_answer` read only the latest detector pass →
   a threat blinking out on the decision tick made the board "quiet" (the model FORGOT enemies it
   saw). The gate now triages the tracker's remembered enemies (with_base ported to hogeq),
   deduped against live dets — and the advisor's `_situation` string appends them too, labelled
   "briefly out of sight" (follow-up commit), since the LLM was otherwise still TOLD an empty
   board. **Deliberately NOT counting unknowns** — post-553fe5c they're mostly
   our own cards; recorded so nobody "fixes" it back.
4. **Training wheels ON** (`train.training_wheels`): doctrine aim-correction for all live spells
   (log→corridor, tornado→king-cell else clump, else nearest enemy). CELL-ONLY — the card axis of
   the stored DQN action is never altered, same contract as the existing aim assists.

⚠ CORRECTED (the NOTE inside 3db2193's commit message is WRONG about this): the overnight
icebow PPO spawned its workers 19:39 on 08-19, BEFORE the 21:44 sim edits -- Python imports once,
so that run has NO `nado_bad` anywhere in it, and it has had the crown-damage values since step 0
(committed earlier that day). Nothing straddled. `nado_bad` first applies to the NEXT sim launch;
the live terms (spell_waste-at-impact, wheels, gate memory) to the next train-rl session. Caveat
only if a worker crashes and respawns after 21:44: that worker imports the NEW sim -- check worker
process creation times before comparing per-term stats.


## 3d. 2026-08-19 ~22:00 — the "collapsed" PPO was a SCRATCH run (and the log was stale)

The user saw the evening PPO's winrate "collapse". Findings, all verified from checkpoints:
- **`data/ppo_percard.log` stopped 08-17 17:28** — everything read from it about the evening run
  (including the "19k matches, ladder 9%" I sent to Discord) described the Aug-17 run. Tonight's
  run logged only to its console. **Tee future runs to a file.**
- **Tonight's 19:39 launch had NO `--resume`/`--init`** (verified from the process command line) —
  it trained FROM SCRATCH, reached 3,016 matches, banked ladder-avg 12.2% @1500, and **overwrote
  `policy_sim_ppo.pt` + `policy_sim_ppo_best.pt`**, clobbering the Aug-17→19 warm lineage's end
  state (no backup of it exists). Rollout winrate is curriculum-pinned near ~30% BY DESIGN
  (difficulty rises whenever the window beats it) — judge runs by the `EVAL @` avg-5 lines only.
- **`policy.pt` (BC, Aug 17) is `in_ch: 3`** — the sim needs `in_ch: 12`, so `--init data/policy.pt`
  silently falls back to scratch (shape gate). A BC warm start needs BC re-run on the 12-channel
  canvas first.
- **Strongest surviving compatible checkpoint: `policy_sim_ppo_best_win40_14300.pt`** (Aug 16,
  banked ladder avg-5 33.2%, in_ch 12/thr 52/gate present, heads measured healthy: card-head norm
  0.09, gate absmax 0.90 — no `--reset-gate` needed). Recommended restart:
  `run.py train-sim-ppo --matches 800000 --envs 96 --workers 12 --size 432 --init data\policy_sim_ppo_best_win40_14300.pt`
- **Fix (both decks): value warmup now engages on `--init` warm starts** (`warm_loaded`), not just
  resume — before, a RANDOM critic trained alongside a warm policy from minibatch 0, the exact
  hazard class of the 2026-08-14 head-sharpness incident.


## 3e. 2026-08-19 late — the live-reward batch crashed a real match (and why nothing caught it)

User ran `train-rl` (icebow); it died mid-match at `float(value)` in reward_stats.add.

- **icebow:** `self.w_spell_waste_live = ("spell_waste", -0.3)` — the reader call had lost its
  function name in patching, so the weight was a TUPLE. The detection worked perfectly; billing
  the FIRST TRUE WHIFF is what crashed. Live env.py's reader is `rw`, defined ~55 lines BELOW
  where I put the reads.
- **hogeq:** same lines read `r(...)` — a name that exists nowhere in live env.py. Its live env
  would have raised NameError on construction: `train-rl` was 100% broken there, undetected.
- **Both weights now live in the `rw()` block** with every other reward weight.
- **Third bug, found while auditing:** `reset()` never cleared `_pending_spells`, so a spell cast
  in a match's closing seconds came due during the NEXT match and was judged against its empty
  opening board — a guaranteed phantom whiff billed to a match that never cast it. Fixed.

**WHY THE 16 TESTS MISSED IT: no test constructs the live `MatchEnv`.** It needs a window and a
detector, so every test in both decks uses `SimMatchEnv`; the live wiring had never executed. The
new `LiveEnvInitLintTests` lints the SOURCE instead (AST): no `self.w_*` may be a container, no
function may call a bare name unbound in local+module+builtin scope, both spell weights must come
from a reader call, and `reset()` must clear the queue. **Verified non-vacuous** by re-injecting
both shipped bugs and confirming each test fails (`scratchpad/verify_lint_catches.py`).
Building the lint exposed a bug IN the lint: `ast.walk` for module scope descends into function
bodies, so a local `r` inside `_wheels_spell_aim` masked the very NameError being checked — module
scope is now collected from top-level statements only.

Suites after: icebow 427 OK, hogeq 42 (its documented baseline; none from these files).


## 3f. 2026-08-19 night — the advisor, the doctrine wheels, and a warp bug in hogeq

**The advisor (`b07b983`).** User: "the advisor keeps timing out which causes the model to play
randomly." Both halves confirmed, two independent causes:
- The single-card answer was a JSON object (`{ "card": "tornado" }` = 10 generated tokens at ~44
  ms) -> p50 **0.855 s** against a 0.90 s budget. It was losing by 20 ms. Reproduction: **0 of 15**
  calls answered. Bare card name (3 tokens) -> p50 **0.492 s**, **15 of 15**.
- The circuit breaker was PERMANENT (`disabled=True` for the session). At a ~40% timeout rate five
  in a row arrives immediately, so every later exploration step was a uniform-random card. Now a
  cooldown (30 s, doubling, 300 s cap) that any single good answer clears.
- **The prompt's last line is load-bearing** — scored on tools/llm_eval.py's 13 engine-verified
  cases: `"Answer with the card name only."` **11/13**; `"...or hold."` **3/13** (holds 11x);
  nothing appended **0/13**; the old JSON schema **7/13**. Shipped the 3/13 wording first and the
  eval caught it. A top-level string enum was fast, "valid", and answered `hold` 12/12 — latency
  alone would have shipped a bot that never plays.

**Doctrine wheels for the defenders + the buffer fix (this batch).** Already wheeled before:
x_bow lane/lock/depth, tesla centre-pull, rocket weaker-tower/pump/intercept (unconditional,
predating the flag), plus 08-19's spell wheels. Added: `_wheels_troop_aim` for **knight**
(bodyguard one row in front of the bow on the threat's side; body-block between attacker and tower
when no bow is out), **skeletons** (onto the attacker), **ice_wizard** (behind and offset, out of
one spell radius with the bow) — mirroring sim `_bow_defence_cells`, geometry derived from the real
tower anchors, king-footprint guarded, and a one-cell tolerance so a placement the model already
got right is left alone.

⚠ **THE PREREQUISITE, do not undo:** `train_rl` stored the action the POLICY chose while `env.step`
executes a doctrine-corrected CELL. That teaches backwards — the model's bad cell gets credited
with the corrected cell's reward, so it learns the mistake was right and the wheel can never come
off. `env._last_exec_action` now carries the executed action and the replay buffer stores THAT
(Q-learning is off-policy, so this is the correct form). This affected the pre-existing rocket/xbow
/tesla assists too, for as long as they have existed.

**hogeq's `coords_to_grid` never got icebow's warp fix.** Measured: round-tripping every cell
through `cell_center -> coords_to_grid` mismatched **412 of 432** cells in hogeq, **0 of 432** in
icebow. hogeq still rescaled the arena box LINEARLY while `cell_center` maps through the
perspective warp. Everything that turns a POINT into a CELL goes through it — the labeller (human
tap -> training cell) and every aim assist — so **hogeq's recorded demonstrations were stored ~2
rows toward the enemy end of where the human actually tapped, and its aim assists landed short by
the same amount**. Fixed (now 0/432). Consequence worth acting on: hogeq BC data labelled before
this is systematically shifted, so a re-label (or re-record) is the honest next step there.

Suites: icebow 450 OK, hogeq 42 (unchanged baseline — the warp fix added none).


## 3g. 2026-08-20 — reaction latency, phantom tracks, offense windows

User: reactions land 4-5 s late (hog reaches the tower first); false positives on the allied side
whiff spells into random tiles; and the model needs offensive windows, not all-game defence.

**Latency.** The healthy chain is ~1.3 s (10 Hz perception → event wake → 0.5 s advisor → act).
The 4-5 s sessions were the DEGRADED chain: the perception thread dies silently → `_detect_enemies`
falls back to 1 Hz synchronous detection with nothing in the log → motion classification needs
seconds → (pre-`b07b983`) the advisor burned another 0.9 s timing out. Fixes:
- `PerceptionLoop.ensure_alive()` — a dead loop restarts itself and SAYS SO; `_detect_enemies`
  warns (rate-limited) on a dead loop or a stale snapshot instead of silently degrading.
- The wake event now also fires on a **fresh first sighting** (track hits == 1) at gy ≤ 0.50 of a
  card we don't own — placement IS the commitment; waiting for the classifier ("enemy" needs
  motion_min = 0.05 of net march) cost 0.3-0.7 s per reaction.
- Found while testing: an unowned card deep in OUR half classifies enemy on FIRST sighting via
  the deck veto — Miner/Barrel-style materialisations already wake with zero classification delay.
- **Per-match health line**: `[perception] running/passes/wakes` + `det_age` in the cadence line.
  passes ≈ hz × seconds when healthy; det_age near act_period = blind-between-decisions again.

**Phantoms.** Confirmed the user's guess: a 1-frame false positive classified by side-prior or a
bar misread became an enemy TRACK served for forget_s = 4.5 s → gate opened → spell wheels aimed
at it → whiff into grass. Now: tracks carry `hits`; `enemy_tracks` serves only ≥ `min_hits`
(**observation.team_track_min_hits: 2**, ~0.1-0.2 s corroboration at 10 Hz), dets carry
`d.trk_hits`, and `_needs_answer`'s live-det path requires ≥ 2 (default 2 when unannotated).

**Offense.** The quiet-board pressure rule (bow at 6+) lived on EXPLORATION steps only — a greedy
model at 10 elixir just leaked. New leak-guard wheel (**train.offense_leak_guard: 9.5**): a greedy
WAIT on a quiet board at ≥ 9.5 elixir becomes the pressure play (icebow X-Bow, hogeq Hog at the
bridge) — the punish/outcycle/second-bow window. The ONE sanctioned wait→play conversion; sound
only because the buffer stores the EXECUTED action (a683d46). Defence always outranks it
(needs_answer suppresses).

16 new tests per deck. Suites: icebow 466 OK, hogeq 42 baseline.


## 3h. 2026-08-20 late — enemy spells are not threats + the last phantom-cast path

- **Enemy spells ignored everywhere** (user rule: "nothing can be placed to counter a spell"):
  `enemy_tracks` never serves a non-spawn spell (so our spell wheels can't aim at THEIR spell and
  a rocket landing near their zap no longer dodges its whiff bill), the threat gate skips spell
  dets, and `_situation` never describes them to the advisor. Exception `SPAWN_SPELLS =
  {graveyard, goblin_barrel, royal_delivery}` — those land units and demand answers.
- **The remaining hallucinated casts had a measured path**: live_20260819_230129 shows tornado
  casts at board mass 0.009 (empty screen) with raw_cell == cell — the CHOICE was the
  hallucination, and it came from `_situation`, which had NO trk_hits filter (the gate got one
  earlier, the advisor string didn't). A 1-frame phantom was described, the advisor answered
  "tornado". `_situation` now requires trk_hits ≥ 2.
- **Static-phantom demotion** (`observation.team_phantom_stale_s: 6.0`): a misdetected decoration
  re-sights every pass so min_hits never kills it, and the deck veto reads it enemy forever. A
  REAL enemy deep in our half (y > 0.55) marches or takes tower fire (bar evidence within
  seconds); a track that has done neither for 6 s stops being served. Their side is exempt
  (buildings legitimately stand still and unhurt).
- The Karpathy-skills repo (multica-ai/andrej-karpathy-skills) was inspected, NOT installed:
  third-party name-squat packaging four generic coding maxims as AI instruction files; nothing
  technical to integrate, and third-party instruction files don't get vendored into this project.

12 new tests per deck (spell serving + spawn exception, static demotion with all three escape
hatches — march/bars/their-side — situation filter). Suites: icebow 478 OK, hogeq 42 baseline.


## 3i. 2026-08-20 — counter validity + the counter table

User: "the advisor is suggesting unrealistic counters... knight on a balloon (knight can't even
see the balloon) or rocketing wall breakers (a horrible elixir trade)."

**The veto (`65fda67`), `threat_value.pick_invalid`** — both failures were ALREADY forbidden in
the advisor prompt IN WORDS and shipped anyway; same lesson as the triage tier (52a238e), so the
rule is KB code:
- `can_touch`: an ALL-flying group needs an air-attacker, tornado (repositioning air is the
  answer), or a non-ground-only spell. `the_log` rolls, `earthquake` shakes the ground — neither
  reaches a balloon. A MIXED group never vetoes a ground card.
- `trade_sane`: a SPELL costing 3+ more than the whole group it erases is a losing move (rocket 6
  on wall_breakers 2). Troops are never trade-vetoed — which is why **skeletons stay a legal wall
  breakers answer with the tower helping** (user's note, pinned by a test).
- LIVE: vetoes the advisor's pick, falls back to the doctrine/cheapest-valid answer, never random.
  `_needs_answer` split so the triaged group is computed once and shared with the veto.
- SIM: `doctrine_cards` filters nominations at BOTH exits; offensive nominations exempt.
- MEASURED on tools/llm_eval.py (+3 cases for the reported bugs): old prompt **13/16** and it
  answered the balloon case with `the_log` — the user's bug reproduced in the harness; new prompt
  **14/16** (balloon→tesla, wall_breakers→the_log). The remaining miss (three_musketeers: rocket
  vs tornado) is the known nado→rocket ordering item, not a regression.

**The table plumbing (`a363a87`), `clashrl/counters.py`** — rows are threat_cards → ordered
respond[{card, when, where, note}], looked up combo-first (an exact combo beats its parts; a
superset push still finds it), filtered to what is in hand. Consumers: advisor-vetoed → doctrine
answer; **advisor-silent → doctrine answer instead of a uniform-random card** (the measured cause
of the "plays randomly" sessions); sim `doctrine_cards` nominates the same rows at 5.0/4.0.
Data lives in `config/counters.yaml` (`train.counter_table`); first row for a key wins so a
hand-written override survives a regenerate. **No table shipped yet** → empty table → every path
keeps its previous behaviour.

**DONE (`0aad2c0`): 108 researched rows per deck** in `config/counters.yaml`. 17 agents, 178
entries from deckshop / the CR wiki API / reddit guides, covering all 131 cards + 38 meta combos.
The `where`→wheels mapping shipped in `1ea0cc6`.
- Highlights: balloon→tesla PRE-PLACED centre (never knight); wall_breakers→the_log then
  **skeletons at_tower** (the user's own note, found independently); lavaloon→ONE mitigation row;
  graveyard→ice_wizard pre-placed ON the tower; three_musketeers→**tornado then rocket** (the
  ordering the eval wanted); hog→tesla 4-3 centre. 16 icebow rows are `mitigation: true`.
- ⚠ icebow's adversarial agent DIED on a session limit → I ran that audit locally
  (`scratchpad/local_audit.py` pattern): 1 hard fail (rocket on a lone elixir_golem), 0 mechanics
  contradictions. hogeq's agent passed with 7 corrections.
- Two bugs the audit exposed, both fixed: `lookup()` broke ties by DICT ORDER (a golem+firecracker
  push could answer the firecracker) → rows now carry `danger` and the most dangerous match wins;
  and the sim's table nominations at 5.0/4.0 OVERRODE the hand-written rocket gates (two existing
  doctrine tests caught it) → now 2.5/2.0. **Hierarchy: measured doctrine > researched table >
  uniform floor.** Do not raise those weights.
- Regenerate: `python tools/counters_build.py <research.json> --deck <deck>`. First row for a
  threat key wins, so hand-written overrides go ABOVE the generated rows.

Suites: icebow 527 OK, hogeq 42 baseline.


## 3j. 2026-08-20 late — the phantom-credit bug, the defensive bow, the LLM out of the reaction path

**Why `spell_waste` stopped firing AND whiffs still paid (`5b04c17`).** ONE mechanism, and it was
my own 08-19 fix biting back: the tracker BRIDGES a track for `team_forget_s` (4.5 s) so a real
unit blinking out is not forgotten — and a FALSE POSITIVE is remembered exactly as long. A
rocket's whole flight is ~1 s, so at impact the phantom was still "inside the blast" → no whiff
billed → and the credit `_wincon_exec_live` paid at cast STOOD. **The model was being taught that
casting at ghosts pays.**
- Verdicts now run on FRESH sightings only (`env.spell_verify_fresh_s: 0.8` — still several 10 Hz
  periods, so real 1-3 frame gaps are bridged). `enemy_tracks` grew `max_age`; memory callers
  (threat gate, `_situation`) are untouched.
- A whiff HANDS BACK the at-cast credit (`spell_waste_clawback`) → a whiffed spell is strictly
  negative.
- **`[spell]` log line per impact**: aim, radius, `N fresh, M remembered`, and a `PHANTOM` marker
  when only memory saw the target. This is the line that separates "detector false positive" from
  "model casting at nothing" — read it before diagnosing further.

**Defensive bow / "a back build is not a quiet board" (user).** `_needs_answer` only triaged OUR
half, so a golem assembling behind their king read as quiet and the loop hunted for PRESSURE —
which is how the leak-guard fired an offensive bow into a push already paid for.
`threat_value.massing_in_back` (shared): real elixir at/behind their princess line (y ≤ 0.28) AND
nothing on our half (y > 0.42). On that board: the gate says answer, the wheel plays the bow into
the back-centre band, **env.step SKIPS its forward lane/lock/depth snap** (that snap is what makes
a bow offensive), the sim doctrine aims the same spot ABOVE the phase flag, and the prompt says it.

**Reaction latency, part 2** (perception healthy, det age 0.07 s). The loop is
`choose(obs) → execute → wait → observe`, so the advisor's ~0.5 s sits between seeing a threat and
tapping. Defence decisions now consult the **counter table first** (dict lookup, and measurably
more accurate) and skip the LLM on a hit — **75% of answerable meta threats covered (66/88**;
spells and triage-ignorable cards excluded, since neither should be answered). Gaps still go to the
advisor. `react_min_gap` 0.30 → 0.15 (it is slept BEFORE the event is checked = a hard floor).
⚠ Uncovered-but-answerable, worth a follow-up research pass: berserker, electro/ice/fire/heal
spirits, knight, goblins, mini_pekka, and enemy buildings (tesla, bomb_tower, furnace, goblin_cage).

**Latent bug found on the way:** hogeq's `PerceptionLoop.enemy_tracks` never got the `with_base`
port — the gate calls it with `with_base=True`, raising TypeError, swallowed by the gate's own
except. **hogeq's threat-gate memory has been inert whenever its perception loop runs.** Fixed.

Suites: icebow 543 OK, hogeq 42 baseline.


## 3k. 2026-08-20 — the king rocket was FREE, and live never paid for the tornado combo (`c7aa9c3`)

**"It learned to rocket cycle the opponent king tower."** Chip on the king was ALREADY off and was
never the payoff — `_chip_progress` slices `[:2]` in both envs and live does not even read the
king's HP (`enemy_tower_hp_boxes` has 2 boxes). **Measured: a king rocket scored exactly 0.0.**
Zero was the bug — not a reward, but not a cost, while it dodges the leak penalty, so it was a
FREE six-elixir cycle. The live `near_enemy_king → w_wincon_mis` guard exists but sits in the
MINER branch; the rocket branch fell through to `return 0.0`. Now an explicit misplace both sides
(sim 0.0 → **-1.0**, princess unchanged +0.75).
⚠ Do not "restore" chip on the king: the overtime tiebreak reads PRINCESS HP, so king chip is
worth nothing at any point in a match.

**"It still doesn't understand the placement for rocket tornado."** Root cause: the sim has priced
the combo since 2026-08-16 (`rocket_nado_mult`, `rocket_nado_window_s`) and **live had no term for
it at all** — so a sim-trained checkpoint carried the TIMING across and had no gradient toward the
TILE. Live now mirrors it: `_last_nado` remembers the cast point/time; a rocket within
`rocket_nado_window_s` (2.5 s) AND `rocket_nado_radius` (**0.11 — deliberately tight, "the same
tile" not "nearby"**) pays `w_wincon * rocket_nado_mult`; and with wheels on the rocket is SNAPPED
to the tornado's tile ahead of the intercept assist.

Suites: icebow 555 OK, hogeq 42 baseline.


## 3l. 2026-08-20 — FIVE-TRACK ARCHITECTURE AUDIT (read this before more training)

Five parallel audits: reward architecture, sim↔live parity, deck divergence, hogeq's test
baseline, RL pipeline. **The headline: live training has been learning from plays that never
happened.** Fixed items are in `0ab0dc4`; everything else below is an open, prioritised backlog.

### THE VERDICT ON THE ARCHITECTURE
BC → sim-PPO → live-DQN is **not** the blocker; the design is standard and defensible. Two other
things are:
1. **The live data contract was fiction.** Measured over 12 sessions / 3,647 plays: six-elixir
   cards show a BIMODAL drop distribution — 27% drop by 4+ (deployed), **33% drop by ≤ 0**, which
   is impossible if 6 elixir left the bar. Mechanism found: illegal cells. 122 of 188 illegal-cell
   plays sat on grid row 12 with `min_own_gy` 13 — the X-Bow snap ran AFTER `deploy_clamp`.
   *Fixed (re-clamp + deploy confirmation), but legal cells still only deploy ~42% by that metric —
   **a second failure mode remains unidentified. Next live session, watch the `[deploy]` lines.***
2. **The live sample budget is 2-3 orders short and cannot be fixed by tuning.** 72,378 live
   decisions EVER vs 479,820 params and 2,072 legal actions = **0.15 decisions/param**, ~3.6
   deployed plays per (card, cell). `policy_rl.pt` carries **743** cumulative live gradient steps.
   The replay buffer is a local `deque` **discarded every launch** (never exceeds ~1,500 of
   100,000; each transition redrawn ~64×; SB3/Rainbow use replay ratio 0.25, we use 1.0).
   The sim yields ~300× more decisions per wall-clock hour.
   **RECOMMENDATION: demote `train-rl` from trainer to VERIFIED EVALUATOR + corpus collector.**
   Run greedy at the sim's gate threshold, record win rate, append verified transitions to a
   persistent corpus, feed that back through BC. Live win rate (0.87% over 805 matches) vs sim
   benchmark (27.6%) is the project's central unexplained quantity and is currently unmeasurable.

### OPEN, RANKED (not yet fixed)
1. **Live builds identity/memory/interaction blocks in FRAME coords; the sim uses BOARD coords.**
   30 of 52 threat dims wrong. `env.py:510-511, 516, 550-555` (+ `play.py:371-392`). The warp
   already exists 80 lines below (`env.py:586-611`) — mechanical fix, no retrain. Consequences
   measured: `identity_front 0.44` lands at board 0.497 (the fix is inert); depth saturates at
   0.575 so `threat_max_depth 0.65` **can never fire live**; interaction ETAs ~42% short.
2. **Threat dims 0-15 mean different things in sim vs live** (`sim/view.py:200` vs
   `threats.py:186`): sim slots 6-15 are always 0.0; live drives all 16. Needs a layout decision +
   fresh PPO run.
3. **hogeq's Hog earns ZERO wincon reward** in sim AND live — `_wincon_exec*` branch on
   xbow/tornado/rocket/miner ids, all empty for that deck. Its largest positive term is inert.
4. **The sim's whole X-Bow/tornado ledger is absent live** (8 terms incl. `xbow_into_push` −4.0).
   Live pays a flat +3.0 for ANY forward bow including into a committed push; sim pays −4.0.
   "Sim teaches bow-and-tornado; live un-teaches both."
5. **Junk beats waiting**: with a threat on the board, waiting = −1.0 (`threat_miss_idle`) while a
   tornado at nothing ≈ 0.0. There is NO spend term live at all. Live `threat_miss_idle` also
   lacks all four guards the sim added after measuring "always play" as 8× optimal.
6. **Live `_bonus` cap wraps only 2 of ~10 terms** → once the penalty budget saturates, wrong-card
   spam becomes exactly free.
7. **Deck divergence, Tier 1**: icebow's Earthquake building bonus is dead data (10.5× under-
   modelled, EQ in 33/1000 meta decks); hogeq's Log aim assist is permanently disabled via a
   `None` fallback though it runs the Log; icebow never got Firecracker recoil; hogeq never got the
   Tesla king-clearance; `hogeq/tools/llm_eval.py` grades hogeq's prompt against ICEBOW doctrine
   (7/13 expected answers are cards hogeq cannot play).
8. **hogeq's 42-failure baseline: 0 are real bugs** — 41 are icebow tests copied into a deck
   without those cards, 1 is a Cloudflare block. But ~55-70 MORE tests **pass green while
   exercising unreachable code**. Plan: 6 rewrite, 35 skip-with-reason, 1 environment.

### THE ROOT CAUSE BEHIND #7/#8
The code forked, **so the tests forked too**. `test_aim_assists.py` exists only in icebow;
`test_earthquake.py` only in hogeq — **each deck deleted the exact test that would have caught its
own bug.** Recommended Phase 0 (~1 day, zero behaviour change, would have caught all six Tier-1
findings): add `.gitattributes` (the CRLF mismatch is why `git diff` showed 614 changed lines where
4 were real, which is why this drift went unreviewed), plus `tools/deck_parity.py` +
`tests/test_deck_parity.py` with an explicit allow-list so divergence becomes opt-in and reviewed.
Then Phases 1-5: reconcile → decouple `Config.load`'s root → one shared package, two deck dirs →
deck plugin → one test suite run twice.


## 3m. 2026-08-20 — decision period 1.0s → 0.6s (`c328bef`). RETRAIN REQUIRED (sim).

Driven by the user's cadence line: pipeline 0.37 s vs **paced wait 0.49 s** — the loop waited more
than it worked. 0.6 s keeps the wait positive (~0.23 s); **do not go below ~0.45 s** or the period
becomes shorter than the pipeline and the served cadence drifts off the trained one again.

**Everything that had to move with it** (a lone `agent_dt` edit would have been silently
destructive):
| knob | 1.0s | 0.6s | why |
|---|---|---|---|
| `sim.agent_dt` / `play.act_period` | 1.0 | **0.6** | must always match each other |
| `train.gamma` | 0.99 | **0.994** | `0.99^0.6` — holds the half-life at 69 SECONDS, not 41 |
| `train.n_step` | 3 | **5** | keeps ~3.0 s of credit reach-back |
| `leak`, `threat_miss_idle` | — | **× dt** | charged per DECISION; would otherwise bill 1.67× per second |
| `llm_advisor_timeout_s` | 0.9 | **0.55** | a 0.9 s call overran a 0.6 s decision every time |

Per-tick scaling is applied **in code** (`self._tick_scale`, both envs) rather than by editing
weights, so it stays correct through any future period change. Event-driven terms (wincon_exec,
threat_response, crown, chip, spell_waste) are per PLAY and untouched.

### RETRAINING: what is and isn't needed
- **Checkpoints still LOAD** — no observation/action shape depends on dt (verified against
  `policy_sim_ppo_best_win40_14300.pt`: in_ch 12, threat 52, cells 432 unchanged).
- **But the MDP changed**, so the value head is calibrated to the old horizon and the old per-tick
  reward rates. **Run a fresh `train-sim-ppo --init <best>` (warm start, NOT from scratch)** and
  let the critic re-converge — the value-warmup path added in `ea25251` now covers `--init`, which
  is exactly this case.
- Judge it on the `EVAL @` avg-5 ladder lines; the bar to beat is the 33.2% banked by
  `policy_sim_ppo_best_win40_14300.pt`.
- ⚠ Sim reward totals before and after are **not comparable** — leak/idle now bill 0.6× per
  decision by design. Compare per-SECOND or compare win rates, not raw episode sums.
- Two latent test bugs surfaced (not caused) by the change: `_tick(env, seconds)` stepped once per
  second regardless of dt, and a quiet-refill loop used `range(5)` for "≥3 s". Both are now
  time-based.


## 3n. 2026-08-20 — why the drill pass rate sat at the random baseline (four root causes)

Owner's call after three PPO runs stuck at 17–20% against a 16.7% random baseline: *"I'd rather the
process be slow and accurate… go with option 1"* — fix each interaction's reward individually
rather than bolt a drill-completion bonus on top. Doing that end-to-end on the first drill found
that the problem was never a single reward weight.

**`run.py drills --outcomes` is the acceptance test now.** `--reward` asks whether the correct play
beats idling, and a drill can pass that while still teaching its own opposite. `--outcomes` asks the
question the optimiser actually asks: *under the trainer's own exploration, does PASSING pay more
than every other outcome?* At the start, **14 of 28 icebow drills said no.**
`tools/drill_terms.py <drill> [reps]` is the follow-up — per-REWARD-TERM means split by outcome, so
when a drill pays for the wrong thing it names the term responsible.

### The four causes, in the order they were found

1. **The king-activation credit measured a different event than the drill.** `king_hit` required the
   king to be AWAKE plus something NEAR it. Waking is a consequence of the king taking *damage*,
   which is strictly after the retarget — and the proximity proxy is the §6.0a false positive (a
   king woken by chip collects the credit while the attacker walks past). The real event is the
   owner's own wording: *the attacker is now going for the KING* — an identity test on `u.target`,
   which the drill's success predicate already used. It was also gated behind `age >= 3.5`, and **a
   drill ENDS the instant its success predicate fires**, so the episode was over before the window
   opened. Now per-tick, on `u.target`.

2. **The tornado graded itself on a snapshot taken before the pull happened.** `_register_nado`
   recorded membership at the DECISION instant; the engine applies the pull on the following
   advance. Measured on the drill's own reference line, which passes 100%:

   | t | hog distance to vortex centre | radius 5.5 |
   |---|---|---|
   | 3.60 | 5.53 tiles — snapshot taken here | OUT |
   | 4.20 | 5.09 tiles — vortex applies here | IN |
   | 4.80 | on the centre, targeting our KING | — |

   `pulled` was **empty**, and clump/retarget/combo/king/bad-pull all iterate it, so the entire
   `nado` family was silent. Same defect already fixed for rocket and log (judge a spell when it
   LANDS); the tornado was never included, and unlike those it is not an instant — the vortex pulls
   for its duration, so membership now accrues across the window, recording each unit's position and
   tower lock AT CAPTURE. **The tornado is in the icebow hand for every matchup drill**, so this one
   silent credit was suppressing far more than the tornado drills.

3. **The gate was the one head with no exploration prior.** Five drills recorded ZERO passes in 60
   episodes and four were the same kind — the skill is WHEN, not where. Each is passed by waiting
   several seconds and then playing; the card head has a prior and the cell head has one, but the
   gate sampled from the policy alone at ~50/50 per step, so a twelve-step hold arrives with
   probability ~0.5¹². **No reward can fix that**: `hold_the_tesla` already paid correctly in the
   direction it could express (timeout +0.66 beat playing early +0.01), but the outcome it exists to
   teach was never once generated. Every drill already carries the answer — its `reference` line
   records WHEN each card is played, a field used until now only by the report's third column.

4. **`hand=("tornado",)` did not restrict the hand.** `_restrict_hand` set
   `cycle = wanted_slots + rest` and the hand is `cycle[:4]`, so a drill naming one card still dealt
   three others, all playable — against its own docstring ("a rep must fail for the RIGHT reason").
   Measured on `nado_king_activation`: `threat_response` pays **zero** for a pull spell by design
   (it is judged by `_nado_shaping`), yet it read +0.286 on passes and **+0.839 on timeouts** — the
   policy was answering the Hog with the rest of the deck and collecting +1.0 a time, so episodes
   that never performed the technique out-earned the ones that did. Not a broken reward: blocking a
   Hog with a body IS a real answer. A broken **drill** — it claimed to present one card and
   presented four, so its pass rate was never evidence about the technique. This contaminated all 25
   drills that declare a hand.

5. **The reward paid for the second card thrown at a one-card threat.** `threat_credit_budget` is a
   flat **2** — "a real defense is 1-2 cards, not 4" — which is right for a push and wrong for a lone
   Miner. `skeletons_kill_the_miner` passes only if the answer costs ≤ 1.5 elixir (one Skeletons), so
   a passing episode can collect at most one +1.0 credit while an episode that keeps throwing
   Skeletons collects both and fails on `spent > 3.0`:

   | term | pass (n=9) | fail (n=46) |
   |---|---|---|
   | `threat_response` | +0.556 | **+1.130** |
   | `elixir_trade` | +0.271 | +0.141 |
   | **episode** | +0.587 | **+1.188** |

   The cheapest sufficient answer is the tier *above* every counter rule, and this term was paying a
   premium to violate it. The budget now scales with how many enemy **cards** are committed (via the
   same `cards_from_bodies` collapse `_threat_miss_idle` triages with — bodies are not cards), still
   capped by the configured budget, so a real two-card push funds exactly what it funded before.
   ⚠ The depth window was the other suspect and is **not** at fault — measured, the Miner sits at
   depth 0.526 inside the 0.12–0.65 window and the reference line duly collects its credit.

### Drill realism: NOISE (shipped on) and COMPOUND boards (built, default off) — 2026-08-21

Owner's diagnosis of why drills did not transfer: *"the situations in drills are highly specific,
but in real matches the game state will almost always consist of multiple drill-specific
interactions along with some other cards that … exist purely as noise."* It matches the measured
failure — a single-interaction board makes WAIT correct for most of the episode, and training 30% of
steps on that took plays/step from 10.4% to 5.9% and winrate from 10% to 0%.

**NOISE (`sim.drill_noise: 0.5`, ON).** Distractor cards per episode. Tagged (`Unit.drill_noise`) and
skipped by `enemy_units()`, so the engine simulates them and the POLICY sees them while the GRADER
is blind — otherwise the 12 "no enemy alive" and 37 HP predicates all become lies. They spawn in the
lane the drill is NOT about, and `princess_hp_lost`/`hits_taken` are lane-aware. Level chosen by
measurement (the reference line must still pass, or the drill grades luck): 0 → ~98%, **0.5 → 93%**,
1.0 → 89%, 1.5 → ~83% with one drill unwinnable.

**COMPOUND (`sim.drill_compound_frac: 0.0`, OFF).** Several interactions on one board.
* **SIMULTANEOUS, not consecutive** (owner's correction — consecutive "would not be much different
  from non-compound drills"). Offsets are bimodal: ~45% land exactly together so the policy must
  triage, the rest overlap at 0.6–3.5s. Measured, **17 of 25 boards carry ≥2 simultaneous
  components**. My first cut used 3–9s × i, which against 12–22s time limits was two drills in a
  trench coat.
* **TWO-LEVEL GRADING**, as specified: each component judged by its own predicates against ONLY its
  own units (`Unit.drill_tag` + the `_drill_component` filter — without it one drill's "no enemy
  alive" is answered by another's Hog), AND the overall board (`drill_compound_hp_frac: 0.25`),
  because acing two interactions while the third takes the tower is not playing the board well.
* Calibrated: **do-nothing 5%, doctrine 55%**. Bars are `pass_frac 0.5`, `hp_frac 0.25` — the first
  cut (0.6/0.45) had the oracle at 28% and the HP bar never binding at all.

**Sequencing (owner):** noise-only run first, compounds after it has a verdict — one training change
at a time.

### ⚠⚠⚠ THE RUN IS DEGRADING, AND `best_wr` HID IT (2026-08-21, 10:50)

**`best_wr` is a HIGH-WATER MARK, not a current score.** It only ever ratchets upward, so "flat at
11.525" does not mean "not improving" — it meant the policy peaked at match 1500 and has been
getting WORSE ever since. Measured directly, 40 full-difficulty matches per arm, identical
opponents and the trainer's own greedy rule:

| checkpoint | winrate | plays / step |
|---|---|---|
| **untrained net** | **15.0%** (6W-34L) | ~50% |
| `policy_ppo_drill_best.pt` @ match 1500 | 10.0% (4W-36L) | 10.4% |
| current @ match 7900 | **0.0%** (0W-40L) | **5.9%** |

The harness reproduces the banked 11.525 for the match-1500 checkpoint, so it is sound. **A policy
trained for 7,900 matches now loses every match and is 15 points WORSE than random init.**

**The mechanism is the collapsing play rate.** P(play) fell 0.286 → 0.14 and plays/step 10.4% →
5.9%, while elixir rose 2.45 → 4.25. An untrained gate plays ~50% of steps and wins 15%; in a
three-minute match a policy that rarely answers anything simply loses. ⚠ **The banking I reported
all morning as the drills working is the failure, not the progress.**

**Prime suspect: the drill mix teaches WAITING.** A drill is mostly waiting for one right moment,
so at `drill_frac 0.3` a large share of training states have "wait" as the correct action — and the
0.85 gate prior makes the sampled action a wait even more often than that. Global passivity is
exactly what would transfer.

**THE EXPERIMENT THAT SETTLES IT** (and it is the one this whole session set out to answer): train
`--drill-frac 0.0` against `--drill-frac 0.3`, equal budget, and compare winrate AND plays/step at a
fixed match count. Use `wr_eval2.py`-style direct measurement, never `best_wr`.

⚠ **Never quote `best_wr` as current performance again.** Six thousand matches of degradation were
invisible behind it, including in my own reports this morning.

### ⚠ RESTART REQUIRED: the run started 07:44 has the dead-match-accounting bug (fixed in `9e7d15f`)

`3a3dd73` (self-imitation, ~03:50) inserted `if True:` immediately after the `if is_drill:` block,
which stole the `else:` belonging to it and made the **entire match-accounting branch dead code**:

```python
if is_drill: ...
if True:  ep_from[i] = ...
else:                                  # never runs
    wins += ...; losses += ...; win_hist.append(...)
```

* **Visible symptom:** `0W-0L-0D` on a run with real matches (owner spotted it).
* **Real damage:** `win_hist` drives the winrate EMA, and the EMA drives **curriculum difficulty**
  (`d_tgt = max(0.15, wr_ema / full_wr)`), the PFSP ledger and the checkpoint gate. With `win_hist`
  permanently empty the EMA is 0, so difficulty collapses to its **0.15 floor** — the policy trains
  against the weakest opponents in the pool while `evaluate()` (independent, still correct) scores
  it against full-strength ones.

**This fully explains the "very odd results"**: `best_wr` 3.778 at 3000 matches against the previous
run's 11.333 at 2500, banking up but execution down. That run was not testing the floor anneal; it
was training on a broken curriculum.

⚠ **The 07:44 run is compromised from its first match.** Restart it on `9e7d15f` or later. The
earlier run (01:14–07:44) loaded its code *before* `3a3dd73` and is unaffected — its 11.333 is real.

⚠ **Void:** every old-vs-new comparison made from the 07:44 run, including the claim that the floor
anneal made things worse.

### PARKED, deliberately: anneal `ppo_drill_gate_floor` too (2026-08-21)

`ppo_drill_cell_floor` now anneals 0.75 → 0.20 (`01c036b`). **`ppo_drill_gate_floor` is still a
fixed 0.85 and has the same problem** — the gate is sampled from `(1-floor)*policy + floor*prior`
and the stored log-prob is the mixture's, so the gate's importance ratio is crushed exactly like the
cell head's was, and the timing prior does the work the policy should be learning. Measured
consequence: the drills where the policy scores 0% against a passing doctrine are mostly TIMING
drills (`hold_the_spell_for_a_target`, `log_the_ground_swarm`, `nado_the_sneaky_lock`).

**Not changed on purpose.** Owner: ship one training change at a time "so we don't confound the
effects of multiple changes". The cell-floor anneal is being measured on its own first; both share a
motivation, so shipping them together would make either result unattributable.

**Revisit when** the cell-floor anneal has a verdict — if placement improves and timing drills stay
at 0%, this is the next lever.

### ⚠⚠ CORRECTION: THE CELL HEAD WAS LEARNING ALL ALONG (2026-08-21, 05:15)

**I raised a false alarm and recommended a restart on the strength of it. Retracted.** Entropy is
the wrong instrument for this head, and three of my four overnight alerts came from measuring
badly rather than from anything wrong with the run.

Separating PLACEMENT structure (spread *within* one card's own map) from a per-card bias:

| checkpoint | within-card logit sd | vs untrained |
|---|---|---|
| fresh (untrained) | 0.000267 | 1× |
| A/B, 5000 drill episodes | 0.003846 | 14× |
| **live run, 6000 matches** | **0.191689** | **719×** |

A head carrying **719× an untrained net's placement structure** still sits within 0.018 nats of
maximum entropy, because a 0.19 logit spread over 157 cells is still a near-uniform softmax. The
"cell head is indistinguishable from untrained" alert was an artefact of the metric, full stop.

**What survives:** the importance ratio `r = 0.0125` is measured independently and is real, so the
drill's advantage genuinely does arrive attenuated and learning is slower than it could be. The
floor anneal (`01c036b`) is therefore a reasonable OPTIMISATION — but it is not repairing a broken
thing, and **restarting the run is not urgent.**

**What is now measured and true:**
* `ppo_sil_coef: 0.05` is HARMFUL — A/B at 5000 drill episodes: pass rate 40% → 11%, entropy 0.24 →
  0.00, reward +0.0 → −3.7. It collapses the policy. Stays off.
* The watchdog alerts on **within-card logit spread vs an untrained net**, not entropy. Entropy is
  kept only for the COLLAPSE direction, which it does detect well.

**The lesson, three times over in one night:** measure the thing the way the trainer sees it, at a
sample size that can see it. Too small a sample (elixir), the wrong support (unmasked 432 vs
deployable 157), and the wrong statistic entirely (entropy vs structure) each produced a confident,
wrong alert.

### ☀ WHEN YOU WAKE (2026-08-21 morning) — what happened overnight, ranked

1. ~~RESTART THE icebow RUN~~ — **RETRACTED, see the correction above.** The run is healthy and IS
   learning placement (within-card structure 375-719× an untrained net at 6000-12500 matches).
   Restarting only picks up the floor anneal, which is an optimisation, not a repair. Your call,
   not an emergency.
2. **hogeq drills are clean and ready** (`c8e6059`): 27/27, 0 unwinnable, 0 not-discriminating.
   Pull and the hogeq run is good to go.
3. **One real finding**: the drill prior was throwing away its own gradient (r = 0.0125, so the
   drill advantage arrived at ~1% strength). Floor anneal shipped; `ppo_sil_coef` shipped OFF as the
   deeper fix, **unvalidated — decide against a baseline**.
4. **Two false alarms, both from my own instrument, both fixed.** The elixir alerts were a
   640-observation sample of a ~1% event; at 2400 observations the bar reaches 6 in 9.8% of steps
   and `x_bow` is played *more* often than it is affordable. The watchdog now samples 2400 and
   debounces over two consecutive cycles. ⚠ **Treat a single watchdog cycle as a hypothesis, not a
   finding** — that is the lesson, and it cost two Discord alarms to learn.
5. **Open, not urgent**: `rocket` is never SELECTED even when affordable (0.0% of plays against 1.8%
   affordability) — the exact failure the doctrine CARD prior exists to address. Re-check on a run
   that has the floor anneal.

### ⚠ THE DRILL PRIOR WAS THROWING AWAY ITS OWN GRADIENT (2026-08-21, ~02:30)

The overnight watchdog caught the cell head still untrained at 4000 matches, and the diagnosis is
the most important thing in this batch: **a high fixed exploration floor buys the rare success and
then discards it.**

    trained cell entropy   6.0652 of 6.0684      fresh (untrained)   6.0684 of 6.0684

Not the entropy bonus — that anneal completed at 3000 episodes and the head did not move. It is the
IMPORTANCE RATIO. Cells are sampled from `(1-floor)*policy + floor*prior` with floor **0.75** inside
a drill, and the stored log-prob is the mixture's (which is what keeps PPO exact). So the update
forms `r = pi/mu`, and measured on the live checkpoint, on the cell the prior recommends:

| | |
|---|---|
| `pi(cell)` — the policy | 0.0101 (uniform 0.00231) |
| `mu(cell)` — what the sampler used | **0.2827** |
| `r = pi/mu` | **median 0.0125** |

The surrogate delivers `r*A`, so **the drill's advantage arrives at ~1% of its strength** — an ~80×
attenuation on precisely the samples carrying the drill's signal. Every drill fix in this batch was
real, and almost none of it could reach the cell head.

**Fixed (small, reversible):** `ppo_drill_cell_floor` now anneals 0.75 → 0.20 over 6000 episodes,
exactly as the cell-entropy coefficient does and for the symmetric reason — high early when the
success has to be generated at all, decaying so `mu` approaches `pi` and the successes finally
teach. Trainer smoke-tested.

⚠ **This does not fully close the gap.** At floor 0.20 with `pi` at 0.01 the ratio is ~0.08 — 6×
better, still small. **The real fix is an auxiliary self-imitation term** (cross-entropy pulling the
card/cell heads toward the actions taken in episodes that PASSED a drill), which does not pass
through the ratio at all. That is a change to the update itself and wants a waking decision.

**A general lesson for any prior in this trainer:** the strength of a sampling prior and the
learnability of what it demonstrates trade off directly. A prior strong enough to make a rare
action common is, by the same arithmetic, strong enough to stop that action from teaching.

### hogeq drills retuned for ladder levels (2026-08-21 overnight)

**0 UNWINNABLE, 0 NOT DISCRIMINATING, 0 passable by doing nothing** across all 27, at the levels the
model actually plays. Same tools as icebow (`drill_calibrate.py`, `drill_ref_sweep.py`), both ported.

**The bug that was hiding six of them:** a restricted hand let ONE CARD BE REPLAYED FOREVER. The
hand is `cycle[:4]`, so a drill dealt one or two cards has every card permanently in hand and a
played card returns with no cycle cost (a real hand is 4 of 8). Doctrine columns were passing by
spamming — `ice_spirit` ×5, `the_log` ×3-4, `earthquake` ×2, icebow's `tornado` ×3 in two seconds —
while each drill's own single-cast reference scored 0%. That reads as "stale line" and was really
"the column is cheating". **The trainer explores inside drills too, so it was a line the POLICY
could learn.** A drill that declares a hand now gets ONE PLAY PER DEALT CARD.

**Two new measurement primitives, both forced by the ladder level roll:**
* `hits_taken` / `hits_at_most` — enemy levels roll 13-16 (±32% damage), so for a drill whose play
  buys one denied hit the effect is *smaller than the spread the roll itself produces* and no HP bar
  can separate it. A denied hit is the same event at 13 and at 16. This is what made
  `ice_spirit_denies_the_hit` (7.56 → 6.04 hits) and `log_resets_the_charge` measurable at all.
* `enemy_base_below_frac` — a FRACTION of a card's own bar. One Earthquake takes a level 16 pump to
  22% and a level 13 one to nearly nothing, so "the pump died" scored the LEVEL ROLL, not the play.

⚠ **`drill_ref_sweep.py` had a real defect, now fixed**: it played on the clock while
`scripted_policy` HOLDS until the first enemy appears (timings are relative to the arrival, since
`randomise` jitters spawns). The sweep therefore scored a different policy than the report's third
column — it read 35% where the report read 0%, and its "100%" candidate scored 0% once shipped.
**Always confirm a swept placement against `run.py drills` before keeping it.**

### Drill state at ladder levels (2026-08-21, ready to train)

`run.py drills` — **0 UNWINNABLE, 0 passable by doing nothing**, 24 of 28 reference lines at 100%,
none below 84%. `run.py drills --outcomes` — **28 of 28 pay most for passing.**

Reference lines are not documentation: they are the report's winnability proof AND the source of
`drill_prior_cells`, the exploration prior the trainer samples inside a drill. A stale line aims the
trainer's own prior at a cell that no longer works, which is why they were refreshed rather than
left as a cosmetic gap. `tools/drill_ref_sweep.py` sweeps one step of a line and reports each
candidate's pass rate; `tools/drill_calibrate.py` reports the do-nothing vs correct-line damage
distributions so a threshold lands in the measured gap (it falls back to the DOCTRINE arm for
matchup drills, which have no reference line by design).

**The doctrine of the retune, and it is real Clash Royale:** every drill wanted its defender
placed DEEPER, where our own tower is already shooting, instead of out front where it fights alone.
Level-11 boards hid this because a weak attacker died either way.

⚠ **TRAPS this batch added to the list**
* **A 1-2 card restricted hand lets a card be REPLAYED IMMEDIATELY.** Both cards are always in
  `cycle[:4]`, so there is no cycle cost — a real hand is 4 of 8. `nado_clump_for_the_wizard`'s
  doctrine column read 96% by casting tornado three times in two seconds. Elixir is the only brake;
  keep drill starting elixir tight, and distrust a doctrine column that spams one card.
* **"All enemies dead" is not evidence** when the tower kills them anyway (Miner), when they are
  kamikaze (Wall Breakers), or when every line kills them eventually (minions).
* **Do not interpolate a placement.** For `tesla_pulls_the_wincon`, (0.56, 0.725) passes 100% and
  (0.50, 0.725) — the obvious "same but deeper" — passes **0%**. Measure the point you ship.

⚠ **hogeq's 27 drills have NOT been retuned.** The level fix landed in both decks, so its
thresholds are still level-11 numbers facing ladder enemies — expect the same breakage icebow had.

### Retuning the curriculum for ladder levels (2026-08-21)

Levelling the drills correctly broke four of them. All four are fixed, and `tools/drill_calibrate.py`
is the tool that did it: it runs a drill's two extremes -- **do nothing** and **its own reference
line** -- with the predicates stripped, and reports each arm's damage distribution. A threshold
belongs in the GAP between them; if there is no gap, the scenario needs rethinking rather than a new
number. Every bar below is now measured, not guessed.

* **`skeletons_kill_the_miner`** -- a MITIGATION drill (owner). Ignored 401 HP, answered 217: 184 HP
  saved for ~1 elixir, 46%. Old bars demanded the Miner die (he dies either way -- the tower gets
  him) and under 350 HP, which no one-elixir answer can reach.
* **`knight_guards_the_bow`** -- its predicate required the Valkyrie DEAD while its own notes said
  *"scored on the BOW SURVIVING… killing the Valkyrie would be the wrong play"*. She is a
  Knight-counter by design: pinned by level, the reference went 75% at L11 → 65/55/35/35% at L13-16.
  Scored on the bow surviving now: **100% at every level including 16**, baseline 0%.
* **`skeletons_stop_the_wall_breakers`** -- swept the answer: `y=0.66 at t=0.0` holds damage to a
  mean of 183 against 497 for the old `(0.70, t=0.6)` (breakers are fast; the half second cost more
  than the placement). Bar at 450 because **ignored never drops below 472** -- doing nothing cannot
  pass, by measurement. "All enemies dead" dropped: Wall Breakers are kamikaze.
* **`nado_pull_the_flock_back`** -- the Tornado is the ENABLER, not the answer, the same correction
  `nado_the_sneaky_lock` already carries. Six ladder minions deal ~950 dps and kill a 4424 HP tower
  in ~5 s, so a damage-free pull bought 130 HP for 3 elixir. With the Ice Wizard dealt alongside it:
  ignored 4372 (min 4150) vs 2588 (max 3132) -- clean separation, bar at 3600.

**State: 0 UNWINNABLE, 0 passable by doing nothing.** Reference lines still below par at ladder
levels (drill winnable, hand-written line stale): `nado_clump_for_the_wizard` scripted **0%** while
doctrine passes 96%, `split_lane` 40%, `knight_blocks_the_charge` 68%, `tesla_pulls_the_wincon` 68%.

### ⚠⚠ EVERY DRILL PUT OUR REAL-LEVEL CARDS AGAINST LEVEL 11 ENEMIES (owner caught this, 2026-08-21)

> *"just need to make sure it isn't putting the model's level 14-16 cards up against level 11
> opponents, because that mismatch is a fatal mistake and large level differences will completely
> change how interactions work."*

It was. `DrillEnv` hardcoded `level=11` for every scripted spawn, while:

* **our hand** plays at the deck's real account levels — `x_bow` 16, `knight` 16, `skeletons` 15,
  `tornado`/`tesla`/`rocket`/`the_log` 14, `ice_wizard` 12 (`SimMatchEnv` builds specs from
  `db.deck_levels()`);
* **full-match training** rolls the opponent from `sim.enemy_levels` [13,14,15,16] weighted
  [3,5,2,1] — mean ≈ 14.1 — explicitly *"so the opponent's card levels vary like a real ladder
  opponent"*.

So a drill was a level 16 Knight against a level 11 Prince where training is a level 16 Knight
against a level 14 one. **Level 11 → 14 is +32% HP and +32% damage** on every card measured.

**It changes the answer, not the margin.** Each drill's own hand-written reference line — the play
the report certifies as correct — run against the enemy level it should have faced:

| drill | L11 | L14 | L16 |
|---|---|---|---|
| `skeletons_kill_the_miner` | 100% | **0%** | 0% |
| `knight_blocks_the_charge` | 100% | 90% | **0%** |
| `tesla_pulls_the_wincon` | 100% | 100% | **0%** |

`skeletons_kill_the_miner` teaches *"one elixir answers a Miner"*. Against the Miner training
actually faces, it does not. **The drill was rehearsing a play that loses**, and every pass rate in
this batch before this point was measured on the wrong board.

**The fix** mirrors `make_opponent`: enemy spawns roll their level from the same ladder
distribution, per spawn, off the env's seeded rng (a rep stays reproducible), and an explicit
`--level` still pins them for fair eval — the same override `make_opponent(level=...)` already
offers. Our own pre-placed bodies take our deck's real level for that card, since a level 11 Knight
beside the level 16 one from hand is the same bug wearing a different hat.

**FALLOUT — the curriculum was calibrated on an easier board.** At ladder levels, four drills are
now UNWINNABLE (reference, doctrine and baseline all fail) and several reference lines have
degraded:

* `skeletons_kill_the_miner` 0% · `skeletons_stop_the_wall_breakers` 0% ·
  `nado_pull_the_flock_back` 0% · `knight_guards_the_bow` 36%
* degraded: `knight_blocks_the_charge` 68%, `tesla_pulls_the_wincon` 68%, `split_lane` 40%,
  `nado_clump_for_the_wizard` scripted 0% (but doctrine 96% — the reference line, not the drill)

These need retuning against the real levels — thresholds and reference placements both. **Do not
"fix" them by pinning the level back to 11**: that is the bug, and it is the reason they looked
fine. ⚠ Any drill pass rate quoted from before this commit was measured against level 11 enemies
and is not comparable to one measured after.

### ⚠ THE BIGGEST ONE: half the cards in the game could not be answered, so every answer was fined

`card_threat.counters()` is the role table the referee grades defence with — air-defence vs flying,
splash vs swarm, DPS/building vs tank, building vs building-targeter, body vs a bare win condition.
A threat matching **none** of those falls off the end and returns False for *every card in the
deck*, and `_threat_response` then charges `w_threat_miss` (−1.0) for the defence as a misread.

Measured across the card database:

> **154 non-spell cards; 74 match NO threat class, and no card in the deck counters them.**
>
> `mini_pekka` (472 dps), `sparky` (333), `lumberjack` (320), `prince` (279), `elite_barbarians`
> (274), `musketeer` (217), `wizard` (201), `bandit` (194), `archer_queen` (188), `witch` (123) …

None is a tank, a swarm, air, siege or building-targeting, and none carries the curated
`win_condition` flag — so to the referee, a Prince charging your tower is a threat nothing can
answer, and **defending is always a mistake**. This is not a drill artefact: `card_threat` is shared
with the live side, so the same hole sat under `train_rl`'s counter validation and the advisor.

Surfaced by `knight_blocks_the_charge`, a drill whose entire content is putting a body in front of a
Prince: `threat_response` read **−0.604 on the episodes that PASSED it**. The drill's correct play,
fined every time, on the drill built to teach it.

**The fix**: the branch that should have caught them was already there and already argued the case —
a bare win condition "walks (or tunnels) straight at the tower, so the answer is simply a BODY that
engages it". Equally true of a Prince or a Musketeer. The only thing stopping them was that the
branch also demanded the `win_condition` bit, which is a **deck-role label** ("this is what the deck
wins with"), not a claim about what answers the card. Gate dropped to what the reasoning needs: a
ground threat that is not a tank and not siege is answered by a body. 74 → **0**.

Deliberately unchanged, because these are the cases where "any body will do" is false: tanks still
need real DPS, a building, or a melee swarm to surround them; air still needs air defence; siege
keeps its own rule; our own siege still cannot defend; a spell is still not a body.

**`tools/counters_check.py`** (both decks) is the permanent guard — twelve cases, each one a real bug
once, each recorded in that function's comments. This table has been widened or narrowed five times
in the project's history, so it now fails loudly instead of relying on a careful reading of the diff.

### What the hand restriction broke, and the two follow-on fixes

* **A discipline drill needs the temptation in hand.** `bank_to_six_then_bow` fails if you dump the
  bar on knight/skeletons/ice_wizard/tesla but declared `hand=("x_bow",)`. Once the hand actually
  restricted, that branch became unreachable and the drill passed **60/60** — a drill nothing can
  fail measures nothing. Its hand now deals the temptations, as `ignore_the_ignorable` already did
  ("THE TEMPTATION MUST BE A COUNTER, not the whole deck"). A source scan found this was the **only**
  such mismatch across both decks.
* **`_restrict_hand` dealt in slot order**, so with more than four wanted cards which ones reached
  the opening hand was an accident of deck layout — a drill could open without the card it is named
  for. It follows the scenario's declared order now.
* **The timing prior has to know what the line costs.** `bank_to_six` opens at 2 elixir with a 6-cost
  X-Bow written at `t=0` ("first thing" — you cannot bank before the match starts). The gate prior
  read that literally, nominated PLAY from the opening tick, and the card head — which can only pick
  among *affordable* cards — chose the cheap ones the drill fails you for. The prior holds until the
  next reference card is affordable, which also survives `randomise=("elixir",)` moving the moment
  the bank fills every episode.
* **The gate floor went 0.6 → 0.85.** At 0.6 the mixture still plays at 0.23/step while the prior
  says HOLD; `bank_to_six` needs ~19 consecutive holds, so 0.77¹⁹ ≈ 1 in 80 (measured: 0 passes in
  60, twice). At 0.85 it is ~1 in 6, and a prior that says PLAY still fires at 0.84.

### Two left open, deliberately

* **`bow_defends_from_the_centre` — the reward is RIGHT and the drill is wrong.** Its failing
  episodes out-earn its passing ones because the bow locked and chipped the enemy tower
  (`xbow_lock` +0.309, `chip_offence` +0.267, `take_enemy_tower` firing in one of four): those are
  **crown trades** — our princess ate the Giant, their tower came down — which is good Clash Royale.
  The drill fails on our princess HP alone and cannot tell a tower lost for nothing from one traded
  for theirs. A fix is written (stop failing once an enemy princess tower has fallen) but **not
  applied**: at n=4 it does not clear the evidence bar the acceptance test now enforces, and acting
  on four episodes is the exact mistake that bar exists to prevent.
* **`skeletons_kill_the_miner` residue.** The budget fix cut the over-answering premium
  (`threat_response` on fails +1.130 → +0.783) and the verdict fell to `weak`, but passing still
  trails slightly. The remaining cause is that a *single* correct answer earns credit only if it
  lands inside the narrow `intercept` lane window, while repeat plays get more chances at it — more
  shots, more likely to collect. Fixing that means changing the shape of every `threat_response`
  credit in both decks, so it is measured and recorded rather than rushed.

### Also fixed: the acceptance test was convicting drills on two-sample means

It failed a drill whenever *any* outcome out-earned PASS, regardless of evidence — `timeout +5.55
(n=2)` beating `pass +2.15 (n=13)`. Acting on that would have meant rewriting reward terms that
work. A rival now needs **n ≥ 5 AND a lead wider than two standard errors of the difference**; a
real-but-unproven lead prints as `weak` and is left alone. Separately, a **restraint** drill is
passed by doing nothing, so exploration can never record a pass and "nothing to learn from" was
backwards — when no episode passes, the do-nothing line is scored and, if it is the drill's own
correct answer, becomes the PASS column.

### Traps this batch (add to §8)

* **A drill ends on its success predicate, so any reward that resolves on a delay cannot pay it.**
  The king credit waited 3.5 s for an episode that ended at 0.6 s.
* **A cast-time snapshot is one agent step stale.** Anything measuring "what this spell caught" must
  read the board when the spell APPLIES, not when it is requested.
* **`--reward` (correct play beats idling) is not the same question as `--outcomes` (passing pays
  most).** The king drill scored +1.10 on the first while paying +0.24 to time out and −0.28 to pass.
* **A significance-free comparison of outcome means is noise.** Two episodes cannot outvote thirteen.


## 3o. 2026-08-21 afternoon — THE REAL BUG: PPO training makes the policy WORSE THAN UNTRAINED

**Read this before touching drills, curriculum, or reward shaping again.** Everything in SS3n was
addressing drill CONTENT. The fault is in the OPTIMISER, it predates the drills, and it is large.

### The measurement that matters

Same eval harness, 24 episodes/checkpoint, icebow, 700 matches of `train-sim-ppo`, drills at 0.3:

```
untrained  5 inits x 40 eps    reward -13.57 +- 0.24 (sd ACROSS INITS)   <- the baseline
mult=4.0   seeds 41,42         reward -25.46     1.9x worse than doing nothing
mult=1.0   seeds 41,42         reward -29.53 / -33.96   2.2-2.5x worse
drill_frac 0.0 (no drills)     reward -28.22     2.1x worse
per-head clipping ON           reward -35.35     2.6x worse (NO improvement)
```

> **CORRECTION (same day).** An earlier version of this section, and commit `4767a7b`, quoted the
> untrained baseline as **-6.78** and claimed 3.8x-5.0x degradation. That number came from a
> differently-configured one-off eval and is NOT reproducible. Re-measured properly -- 5 independent
> inits x 40 episodes -- untrained is **-13.57 with sd 0.24**, so the degradation is ~2x, not ~5x.
> The direction and the significance are unchanged (every trained result is dozens of standard
> deviations below baseline); only the magnitude was wrong. Baseline script:
> `<scratch>/baseline.py`. Do not quote a single-draw untrained number again -- it moved by 2x.

Training does not plateau, it does not overfit -- it moves the policy AWAY from its own reward
signal, hard, from the very first episodes. An untrained net beats every checkpoint we produced.

> ## ⚠⚠ THIS SECTION'S CENTRAL CLAIM IS WRONG — THE DRILLS **ARE** THE CAUSE (2026-08-22)
>
> Everything below that says "not the drills" came from **a single `drill_frac 0.0` run** that
> scored P(play) 0.225. Re-run at **three seeds**, HEAD does not collapse without drills at all:
>
> ```
> HEAD, drill_frac 0.0, 3 seeds:  P(play) 0.993  0.922  0.964   ALL HEALTHY (untrained 0.49)
> HEAD, drill_frac 0.3, 4 runs:   P(play) 0.151  0.107  0.151  0.107   COLLAPSED
> ```
>
> The one run that "proved" drills innocent was one of the ~2-in-6 that collapse by chance — the
> collapse is **bistable** (measured escape rate 4/6), so n=1 decides nothing. No seed overlap
> between the two groups. The owner suspected drills from the start and was right.
>
> Consequences: (1) there is **no commit regression** — the bisect below measured seed noise, and
> HEAD is as healthy as the "known-good" `74ac441` in the pure-match regime (0.96-0.99 vs 0.98);
> (2) `ppo_clip_play_mult` and `ppo_value_detach` were mitigating a **drill-induced** collapse;
> (3) NEVER call a bistable result from one run again — 3 seeds minimum.

### It is NOT the drills — ⚠ RETRACTED, see the box above (this was n=1)

```
drill_frac = 0.0  (pure matches)   P(play) 0.493 -> 0.225     winrate 24% -> 10%, reward -5.9 -> -9.3
drill_frac = 0.3  (with drills)    P(play) 0.535 -> 0.174
```

With drills entirely OFF the run still degrades monotonically in its own training log. Drills make
it modestly worse; they do not cause it. The 43% drill pass-rate plateau is DOWNSTREAM of this.

### The gate collapse ("decay from start"), and a cheap reproduction

P(play) falls from ~0.50 to ~0.06-0.25 in EVERY run. It is fully expressed in **700 matches
(~25 min on 8 envs)** -- no more overnight runs to test a hypothesis:

```bash
python run.py --config <scratch>/cfg.yaml train-sim-ppo --matches 700 --envs 8 --workers 0   --size 432 --drill-frac 0.3 --seed 41 --device cpu --out <scratch>/probe.pt
```

Corroborated at full scale: the 96-env run reached P(play) 0.177 at 3371 matches. The CELL head is
learning fine throughout (cell_struct 90.8x untrained, 60 distinct cells) -- the failure is the GATE.

### `ppo_clip_play_mult` (SHIPPED, default 1.0 = OFF)

A play's PPO ratio is a product over gate x card x cell (432-way); a wait's is the 2-way gate alone.
Measured, plays leave the trust region **12-25x** more often, and their gradient is killed 10x more
(0.078 vs 0.008). The knob widens the clip bound for PLAY actions only. At 4.0 it cuts the kill
asymmetry to 3.5x and buys ~8.5 reward and ~0.22 P(play).

**It is a MITIGATION, not a fix, and it is DEFAULT OFF.** It recovers about a quarter of the damage;
the policy is still 3.8x worse than untrained. Do not spend a night on it believing it solves this.
The value 4.0 is UNTUNED -- picked because it equalised clip rates. A variance argument says ~1.7.
A 5-value x 2-seed sweep scoring REWARD is staged and unrun.

### FOUR mechanism claims I made and had to withdraw -- do not re-derive these

1. *"Clipping is asymmetric: it zeroes positive-advantage gradients while negative ones keep
   pushing."* WRONG -- PPO's clip is deliberately two-sided (kills grad when A>0 and r>1+eps, OR
   A<0 and r<1-eps). I ignored the mirror branch.
2. *"Plays carry ~2x the downward push."* WRONG -- one noisy logging window. The next window flipped
   the sign (-0.11 then +0.70).
3. *"Clipping amplifies an already-negative gate pressure, 56/44 split."* WRONG -- the metric summed
   `play_push + wait_push`, which counts wait steps with the WRONG SIGN. The update is
   `+A*r*grad log pi(a)`, so a wait step with NEGATIVE advantage LOWERS log pi(wait), which RAISES
   P(play). A negative wait push pushes TOWARD playing.
4. *"mult=4.0 stops the decay"* (from 0.062 vs 0.419 at seed 21). OVERSTATED -- at seed 61 the fix
   arm tracked down to 0.117-0.28 as well. It reduces the damage; it does not stop it.

The correct gate projection (now in the code) is `A*r*(1-p)` on play steps and `A*r*(-p)` on wait
steps. Measured that way the PPO surrogate's net gate pressure is ~0 while P(play) is collapsing --
i.e. **something outside the PPO term is driving the gate down.** Candidates, uninstrumented:
the entropy bonus, `_clamp_heads()`, and the exploration floors' effect on the behaviour policy.
Note `ent=0.07` (drills) / `0.21` (no drills) at 600 matches -- the policy has stopped exploring.

### Diagnostics added to `train_sim_ppo.py` (icebow only; hogeq has the knob, not the prints)

Printed every `log_every` episodes:
* clip rate split PLAY vs WAIT
* gradient KILLED rate split (the two-sided-correct version)
* net surviving push/step, and the **unclipped CONTROL** -- if raw ~= surviving, the bias is in the
  ADVANTAGES, not the clip. That control is what caught claim #3.
* GATE LOGIT PRESSURE, projected with the correct sign, clipped vs unclipped

**The gate-pressure metric is UNDER-POWERED as written**: it resets each window, so sd (0.011)
exceeds the between-arm difference (0.010). Accumulate across a whole run before comparing arms.

### PER-HEAD CLIPPING: implemented, measured, DOES NOT FIX IT

`ppo_clip_per_head` (default false) gives each head its own ratio and its own trust region, so the
432-way cell head cannot delete the gate's update. Measured A/B, 700 matches, seeds 41/42:

```
per-head ON    P(play) 0.137   reward -35.35
baseline OFF   P(play) 0.186   reward -29.53
```

No improvement (worse, inside noise). The head-coupling defect is REAL -- sd(log r) gate 0.002 vs
cell 0.478, measured six times -- but it is NOT what degrades the policy. Left in, default off.

### WHERE THE COLLAPSE ACTUALLY COMES FROM (measured, narrow, unresolved)

The gate is **not** starved and **not** throttled:

```
GRAD NORM per head:  gate 0.028-0.049   card 0.010-0.031   cell 0.00003-0.0001   value 0.30-1.39
```

The gate has the LARGEST policy-head gradient. `_clamp_heads()` never touches it. The cell head's
+-61% log-prob swings come from Adam taking ~lr-sized steps on a near-zero gradient, not from
learning signal.

The engine is a small, near-noiseless, EVERY-UPDATE push on the gate at states where it PLAYED:

```
GATE drift:  PLAY steps -0.169 / -0.386 / -0.408     WAIT steps -0.044 / -0.007 / +0.012
```

Play log-prob falls 0.17-0.41 per update; wait is flat. The gate's mean movement is ~11x its own
sd -- a systematic drive, not noise -- and that compounds 0.5 -> 0.06 over hundreds of updates.

RULED OUT by measurement (not argument): drills (identical at drill_frac 0.0), joint-ratio clip
coupling (per-head fix did nothing), clip bound width (mult=4.0 mitigates ~25%, does not fix),
gate gradient starvation (largest gradient), `_clamp_heads()` (does not touch the gate), floors
clipping plays by construction (only 0-3% clipped at epoch 0).

STILL OPEN: three terms touch the gate logits -- the PPO surrogate, the entropy bonus, and the
value loss through the shared trunk `z`. A probe that takes each term's gradient w.r.t. the gate
logits and reports its signed push on (logit_play - logit_wait) is instrumented and was running
when this was written. Whichever term is large and negative is the cause.

### NEXT: find why plain-match PPO moves against its reward

Self-contained, cheap to reproduce, and it blocks everything else. Start with `drill_frac 0.0` so
the drills are out of the picture. The user does not know when this regressed -- a bisect over the
sim-PPO history against the "reward vs untrained" test is the direct answer.

---


## 3q. 2026-08-22 evening — THE POCKET (rule, always on) + the spell mask (strategy, anneals off)

### The distinction that matters when adding a mask

* **RULE masks** encode the GAME: no deploying past the river, no unaffordable cards, tile legality,
  and now THE POCKET. These are unconditional. There is no flag and there should not be one --
  turning one off does not create learning headroom, it just lets the policy waste actions on moves
  the game rejects. (I proposed a pocket flag; the owner correctly refused it.)
* **STRATEGY masks** encode HUMAN JUDGEMENT: no rocketing the king, no whiffed spells. These cap the
  model at whatever a human thought of, so they get flags AND they anneal off.

### THE POCKET (`d4d5ac2`, `20ab936`) -- unconditional

Destroying a princess grants deployment territory across the river on that side, for BOTH sides.
154 -> 254 -> 354 legal cells. Wired through the trainer with a 2-bit code stored per step so the
update rebuilds the mask sampling used. Opponents use it too (neural via mask variants chosen per
act(); heuristics via `_pocket_lane()` -- they already reached over with SPELLS but never walked a
troop into a pocket). Measured: enemy troops past the river 13 -> 23 after we lose a princess.

Still NOT pocket-aware (static masks): play.py, train_rl.py, policy_stats.py, train_bc.py.

### Spell target mask (`ff767f0`, `8393859`) -- strategy, so it anneals

`spell_waste` (-0.3) cannot fix whiffs: during exploration a whiff is a RANDOM choice, and this repo
already learned that in no_king_mask ("A reward cannot stop a random choice; only a mask can"). The
real cost is the ELIXIR -- a whiffed Rocket is 6 elixir missing for the next counter, so one bad
cast becomes a missed defence too (owner: the single biggest weakness in live play).

`sim.ppo_spell_target_mask` + `play.spell_target_mask` restrict casts to cells the env's OWN
`_spell_no_target` / `spell_whiffed` says would hit. Annealed 100% -> 0% over 25k episodes,
probabilistically, so the cell head keeps getting gradient there and the model can eventually
develop casts the criterion forbids.

### Deck exploiters (`8393859`, `659224e`) -- default OFF

AlphaStar's league exploiters, adapted: the league here is the 100-DECK META POOL, not self
snapshots. `sim.deck_pfsp_power` samples decks we LOSE to more often.

**Do NOT raise `selfplay_prob` to Dota-like levels.** I suggested it; it is wrong here and SS1414's
history already records why -- 0.5 + PFSP^2 drove the benchmark 19.3% -> 1.3% overnight. A frozen
self can only pilot OUR deck, so self-play trains the MIRROR: 1 matchup of ~100, and icebow is rare
on ladder. The OpenAI Five analogy breaks on this game's structure.

### ⚠ `--resume` RESTARTS EVERY ANNEAL

`done_n = 0` unconditionally, and `_prog["n"]` drives the drill cell floor, cell entropy, the
self-play ramp and the spell mask. Resume therefore gives trained weights + fresh early-training
scaffolding, not "continue where you left off". Prefer a fresh run when the action space changed.

### Three SILENT NO-OPS found today -- check the seams, not the pieces

1. `spell_whiffed` missing from play.py's imports, inside a bare `try/except`: the live mask would
   have disabled itself every decision while looking enabled in config.
2. The parent rebuilds worker `info` from four hand-listed keys and dropped `"deck"` -- deck PFSP
   was inert for every `--workers > 0` run. Worker sent it, parent binned it, no error.
3. `run.py drills` graded the DRILL, not the policy, so rows read "policy 0% ... ok".

Each was individually-correct pieces failing at the seam, with no exception. Every such feature now
prints ONCE when it first fires; if the line is absent, it is not running.

---


## 3r. 2026-08-23 — THE WINCON BANK FAILED TWICE, AND ITS REPLACEMENT IS 98% INERT

Three commits and one full eval at 10k matches. **Net result: the x_bow incentive did not work, and
the match benchmark is still at the untrained line.** Read this before trying a third wincon nudge.

### The bank failed in BOTH directions (`3003d50` on, `b53bb4c` off)

`sim.wincon_bank_floor` masks cards cheaper than a held win condition while the bar climbs to its
cost. It has now been tried twice and failed in opposite directions:

| | setting | what the policy did |
|---|---|---|
| 2026-08-14 | low floor | **70% forced waits** — the mask ate the whole action space |
| 2026-08-23 | 4.5 | **dumped elixir to stay UNDER the floor**: median 5.29 → 2.46, x_bow affordable 45% → 9% |

**The mechanism is the same both times and it is the reason a mask cannot work here: the policy
controls its own bar.** A floor that only binds above X elixir is avoidable by never being above X.
`wincon_bank_floor: 0` and it should stay there — this is not a tuning failure, it is structural.

### `rewards.wincon_reach: 0.5` — the replacement, and why it barely fires

A ONE-TIME credit the first time the bar reaches a held wincon's cost on a board with no answerable
threat. Chosen over a per-step hold bonus because a per-step bonus is farmable by hoarding — which
is precisely the failure to avoid (owner flagged this risk before it shipped; it was measured first:
a HOARD-always policy scores +0.50 reach/match but −17.17 `threat_miss_idle`, net −16.67).

**MEASURED AT 10k MATCHES — it is nearly inert.** Instrumented clause by clause, 6 matches:

```
steps            1589
holding           874    x_bow in hand
pre_ok            371    ... and bar >= 6.0
armed             210    ... and credit not yet taken this cycle
paid                4    <-- 2% of arms
blocked_threat    206    <-- 98%, killed by the no-answerable-threat guard
```

**The guard is the whole story: the board is essentially never quiet when the policy holds the bow
with 6+ elixir.** The term as written can only pay in a state this sim almost never produces. Any
third attempt must either relax that guard or price the EXECUTION rather than the reach.

### The 10k eval — the benchmark did not move, and x_bow went DOWN

Run: started 11:50, `--envs 192 --workers 12 --device cuda`, **`--init policy_ppo_drill_best.pt`**.

```
                    W-L-D    winrate   crowndiff        x_bow share   elixir median
UNTRAINED           1-39-0     2.5%    -1.850 +-0.148        -              -
m=6000 (best)       1-39-0     2.5%    -1.875 +-0.159       2.08%         2.29
m=10000             1-39-0     2.5%    -1.925 +-0.134       1.06%         2.14
```

All three are the same policy by the benchmark. **x_bow HALVED (2.08% → 1.06%) over the 10k matches
the incentive was live** — the opposite of the intended effect. Known-good reference is 36%.

**⚠ The elixir median (2.14) is inherited, not caused by this change.** The run was `--init`ed from
a checkpoint trained UNDER the 4.5 floor, i.e. from the weights that had learned to dump. Removing
the floor did not undo the habit in 10k matches. **A config revert does not revert the policy** —
if the dumping is to be unlearned, the run has to start from weights that never learned it.

### ⚠ CORRECTION (same day): the quiet-board guard CONTRADICTED THE DOCTRINE

Owner caught it: *"x_bow shouldn't only be played when the board is completely quiet. For offensive
x_bows, if the board is RELATIVELY quiet and the opponent is low on elixir, that's fine. And if
there's a lot of enemy activity, a defensive x_bow can be placed to set up defense."* Correct, and
it is already written down -- DOCTRINE.md:41 gives the bow **two** modes and a quiet board is
NEITHER:

* **OFFENSIVE** -- row 53 gates it on *"opponent spent >=7 elixir away from our bow lane"*, an
  ELIXIR condition. `_punish_window` is exactly that test, and `_wincon` already pays
  `xbow_punish_mult` (1.5x) on it.
* **DEFENSIVE** -- rows 56/63/79, centre band (0.48, 0.55), a second pull building. It requires a
  PUSH. `_xbow_into_push` already EXEMPTS it ("it IS a pull building").

So both modes were implemented and priced, and the new guard invented a third notion of a correct
bow that contradicted both -- suppressing the credit in exactly the state (a push) that most calls
for a defensive bow. Measured at m=10000 over 12 matches, on the 286 steps where the bow was in
hand and affordable:

```
old guard : board quiet             47   16.4%
OFFENSIVE : _punish_window         252   88.1%
DEFENSIVE : real push present      201   70.3%
either (doctrine says bow)         266   93.0%
```

**Fixed:** `_wincon_reach` now keys off those two predicates instead. Re-ran the exact diagnostic:
**10 arms / 10 paid (100%, was 4/210 = 2%)**, credit 0.33 -> **0.83 per match**. Arms fell 210 -> 10
because the one-time latch now actually latches rather than being blocked and re-arming every step.

**Lesson, and it is the general one:** when a reward needs to know "is this play correct here", reuse
the predicate the rest of the file already trusts. Two terms with different ideas of a correct bow
is a bug that no test catches, because each is internally consistent.

**Not caused by this batch:** `test_budget_caps_and_hysteresis_refills` fails in `_threat_response`
(`0.0 not greater than 0.0`). Verified pre-existing by stashing. 615/616 otherwise.

### FROM-SCRATCH WOULD BE WORSE — measured, and it corrects what I told the owner

The pre-bank checkpoint is gone (overwritten), so the question was whether to restart from zero. I
had blamed the elixir dumping on bank-trained weights carried in by `--init`. **That was wrong.**

```
                            elixir median   bow affordable
UNTRAINED (from scratch)        1.79            0.1% of steps
m=6000 (best)                   2.29            4.6%
m=10000 (current)               2.21            3.8%
```

An untrained gate dumps HARDER -- it plays ~half the time with random cards. The trained checkpoints
are strictly better on elixir and on bow-affordability, and identical to untrained on the benchmark.
So there is nothing to gain by discarding the drill progress (33.7% mean). **Keep the checkpoint.**

### OFFENSIVE BOW: it was gated on ONE condition, and the doctrine has EIGHT

Owner: *"offensive x-bow shouldn't be gated on a single condition."* Right. Researched and written up
in full in `DOCTRINE_RESEARCH.md` §3A (sources: the Fandom page for OUR exact deck, the 3.0 page, the
2.9 blog, Theria -- all via `api.php`, since page fetches 402). Eight windows; two are coded.

**The headline gap is CYCLE (W2)**, which our deck's own page makes the primary decision input and
states twice: *"know where your opponent's counter to the X-Bow is in their cycle... helps with
knowing whether to play an X-Bow on offense or not."* `_opp_can_block_now()` reads their HAND only.
The sim owns their true deck order, so cycle depth is a small extension of `_opp_block_cost`.

Also uncoded: counterpush-off-a-won-defence with surviving defenders (W3), near-full-bar-with-a-
defensive-hand (W4, and `_punish_window` tests a GAP not an absolute), pump-punish-with-the-BOW (W5),
they-hold-no-big-spell (W6), after-single-elixir (W7), their-big-spell-forced-out (W8).

**Two things that need resolving before compiling, both recorded in §3A:**
1. `_bow_split_punish` is **too broad**. Sources split by TANK, not by back-tank-ness: P.E.K.K.A in
   the back -> bow (IW-Control), but *"you don't want to offensive X-bow into a Golem"* (same page)
   and Theria/2.9 both say don't. Discriminator: a building-targeting tank WALKS INTO the bow. Same
   lane vs a Golem/Giant should be excluded; DOCTRINE row 79's OPPOSITE-lane bow survives.
2. W5 conflicts with the shipped `rocket_the_pump_on_sight` drill -- the page says answer a
   single-elixir pump with the BOW, not the Rocket. One source; not changed, not settled either.

**Pocket tie-in nobody has used yet:** the inside/centre offensive plant *"when you have lost a tower
allows it to only be hit from 2 sides, instead of 3 or 4"*. We shipped the pocket in §3q and no cell
preference reacts to a lost princess.

### Drills nearly TRIPLED while the benchmark stayed flat — the §3p decoupling, again

`run.py drills --policy` (priors off, the honest number): **mean 33.7%, 8 of 28 at zero**, against
the §3p baseline of **12% and 16 of 28 at zero**. Real, large drill improvement; **zero** benchmark
movement. This is the second clean instance of "drill learning does not predict match performance".
Do not read a rising drill mean as progress on the objective.

The drill that directly tests the behaviour this change was meant to induce:
`bank_to_six_then_bow` **16%** vs doctrine 100%. It is failing, consistent with the x_bow decline.

Still at 0%: `bow_never_into_the_push`, `hold_the_spell_for_a_target`, `ignore_the_ignorable`,
`log_rolls_forward_not_backward`, `log_the_ground_swarm`, `nado_king_activation`,
`rocket_then_tornado`, `skeletons_stop_the_wall_breakers`.

### `threat_miss_idle` is the largest negative term BY DESIGN — stop re-investigating it

Owner asked why it is still the most negative term after 10k matches. Measured: it fires on **0.8%
of decisions** (13 fires / 1610), at **median 5.29 elixir with a full affordable hand** — never once
below 2.0. It is the largest term because it is the largest PER FIRE (−1.00, versus `elixir_trade`
at −0.04/fire over 41 fires), not because it fires often. Two fires outweigh forty small ones.

So it is not a mispricing and not a mask artefact: those are genuine misses, ~2/match, on boards
where the policy had both the elixir and the counter. `bowler` was 3 of 13.

### Trap added (§8)

**An unmasked card-head sample is not a play distribution.** Sampling the card head without the
in-hand-AND-affordable mask counts plays `eng.deploy()` would reject — it read 153 plays/match
against the masked 38.5, and inflated x_bow from 1.06% to 8.61%. This is the SECOND time this
exact bug produced a wrong number in this project (the first: "tesla played 609 times while dealt
on 283 steps"). `cards.py` and `ledger.py` carry the mask; anything ad-hoc must copy it.

---


## 3s. 2026-08-23 — ALL EIGHT OFFENSIVE BOW WINDOWS SHIPPED, AND THE MEASUREMENT SAYS THEY ARE NOT THE LEVER

Owner asked for every window in DOCTRINE_RESEARCH.md §3A implemented, including W5. Done — and the
measurement that came with it matters more than the feature.

### Shipped

`env._bow_window(spend) -> (reason, is_punish) | None` ORs all eight, replacing the single
`_punish_window` test at the three sites that gate an offensive bow (`_wincon_exec`,
`_xbow_overaggression`'s exemption, `_wincon_reach`). Each window is switchable via
`env.bow_windows: [W1..W8]` so a run can attribute an effect to one of them.

* **W2 (cycle)** — the one the guides rank first — is new machinery: `_opp_cycle_depth(bases)` reads
  the opponent's true deck order (first four entries are the hand) and returns plays-until-in-hand.
  `_opp_can_block_now` only ever saw the current hand.
* **W3** `_counterpush_ready()`, **W4** `_defensive_card_in_hand()` + `bow_full_bar_elixir`,
  **W6/W8** via `bow_killer_spells` (curated, not a damage threshold — §8's "changing what a key
  MEANS is not local"), **W7** conditioned on `_opp_block_cost >= bow_slow_answer_cost` because
  unconditioned it would license the bow for the whole second half of every match.
* **PUNISH vs FAVOURABLE.** W6/W7 are standing matchup properties, not moments. They pay
  `xbow_window_mult` (1.2) rather than `xbow_punish_mult` (1.5) — otherwise they would be a global
  multiplier on the bow wearing a disguise.

### W5, and why NOTHING had to be removed

Owner's rule: *"rocketing the pump immediately applies if the opponent places a pump and x-bow is not
in cycle to punish."* `rocket_the_pump_on_sight` already has `hand=("rocket",)` — the bow is absent,
so the drill was **already** the correct branch and did not need deleting. What was missing was the
other branch: new drill **`bow_punishes_the_pump`** (`hand=("x_bow","rocket")`, rocketing scored as a
FAILURE). Discriminates: nothing 0% / scripted 100% / doctrine 88%. `_pump_rocket` now scales by
`rewards.pump_rocket_bow_frac` (0.0) when the bow is in hand and affordable.

### ⚠⚠ THE MEASUREMENT: THE WINDOWS WERE NEVER THE BOTTLENECK

269 bow-affordable states, m=10000 policy, 12 matches:

```
any window fires   268   99.6%
  W1_elixir        256   95.2%   <-- the ORIGINAL single condition, ALONE
  W4_full_bar       11    4.1%
  W3_counterpush     1    0.4%
  (none)             1    0.4%
```

**W1 alone was already open on 95% of them.** Adding seven windows moved the licence rate 95.2% ->
99.6%. So the offensive bow was never under-licensed, and the x_bow share of 1.06% is NOT explained
by the reward refusing to pay. Do not expect this change to move the bow share.

### ⚠⚠⚠ AND W1 ITSELF IS MISPRICED — clause B fires on 100% of steps

```
_opp_block_cost across 12 decks: min 2.0  median 3.0  max 5.0
opponent elixir:  median 2.07  mean 2.77
clause A  opp < block_cost      :  62.0% of steps
clause B  mine+6 - opp >= 4     : 100.0% of steps   <-- ALWAYS
veto      _opp_can_block_now    :  16.8% of steps
```

`_punish_window` adds the bow's cost BACK to our side (to undo a post-spend read), so clause B is
`elixir + 6 - opp >= 4`. With opponents sitting at a median 2.07, **merely affording the bow
satisfies it**: 0 + 6 - 2 = 4. The threshold and the bow's cost are numerically the same event.

So `xbow_punish_mult` has been the STANDARD rate for every forward bow, not a selective punish. This
also explains the history in the code comment: measured post-spend it *"fired EXACTLY ZERO times in
162 X-Bow plays"*, and adding the spend back overcorrected from 0% to 100%.

**NOT FIXED IN THIS BATCH, deliberately.** `_punish_window` has three callers and the key's meaning
is load-bearing (§8), so retuning it moves every bow measurement in the ledger at once. The doctrinal
answer is that what matters is what is LEFT after paying — the guides' *"only X-Bow at around 10
elixir and when you have a good defensive hand"* is a POST-spend test, i.e. W4's shape, not a
pre-spend gap. **This is the next single change, and it should be measured alone.**

### The opening ban outranks the windows — one named exception

`test_wincon_context_modifiers` caught the windows silently repricing the first 30 s from
`bow_first_frac` (0.25x) to 1.2x. "Never X-Bow the bridge first play" is explicit doctrine and both
outside guides agree — and Theria names the exception: *"avoid playing your X-Bow **unless the
opponent pumps up first**"*. So the ban outranks every window except **W5**. Two tests cover it.

Also updated: that test stubbed `_punish_window` to isolate the non-punish paths; the licence gate is
now `_bow_window`, so the stub had gone stale against the thing it was meant to switch off. It stubs
the gate now, and part (c) keeps it stubbed so `_bow_split_punish` is genuinely consulted.

### CORRECTION to §3A: `_bow_split_punish` is NOT too broad

§3A recorded it as needing a building-targeter exclusion. Re-read: it already returns `not same` for
ground tanks, i.e. it only ever fires for an OPPOSITE-lane bow, which is precisely the out-tempo case
row 79 licenses. The Golem-in-the-same-lane bow the guides forbid never fired. No change needed.

620 tests, 1 pre-existing failure (`test_budget_caps_and_hysteresis_refills`, `_threat_response`).

---


## 3t. 2026-08-23 — DEFENSIVE DOCTRINE AUDIT

Owner asked, after the offensive windows: *"check if there are any defensive segments in the
doctrine that have not been coded yet."* Audited DOCTRINE.md §0 (fundamentals), §1 (niches),
§2 (synergies) and §4 (standing placement priors) against `sim/doctrine.py`, `threat_value.py`
and `sim/env.py`.

### ⚠ FIRST, A CORRECTION I HAD TO MAKE MID-AUDIT

I initially reported the defensive coverage as four cards, reading it off `_bow_defence_cells`
(knight / skeletons / ice_wizard / tesla). Owner: *"every card in icebow deck can be used for
defense, not just the four you listed. Doctrine should agree with me and if not, something is
wrong."* **Correct on both counts, and the doctrine does agree** — DOCTRINE.md §1 gives all eight a
defensive role (X-Bow "second pull building", Rocket "heavy removal", Tornado "drag units off a
lock", Log "knockback/charge-reset"), and so does the code:

* **Placement rules exist for all eight** in `_doctrine_cells_rules`: `tesla`, `x_bow`, `knight`,
  `skeletons`, `ice_wizard`, `tornado`, `the_log`, `rocket`.
* **All eight are nominated defensively** in `doctrine_cards` (tesla 6.0 for their wincon, knight
  4.5 vs melee, skeletons 4.0, ice_wizard 3.5, tornado up to 5.0, log 4.5, rocket, bow 4.0).

`_bow_defence_cells` is only the *bow-bodyguard formation* — one context, not the defensive
inventory. Reading a subsystem's dispatch list as the whole picture was the error.

### CONFIRMED UNCODED (the list is short, because coverage is good)

1. **Log ahead of a locked X-Bow** (§2 synergy — the Log's one offensive-support role).
   `_bow_defence_cells` returns False for `the_log`, so it falls through to the generic ground-swarm
   rule, which targets the **deepest** ground unit in OUR half (`max(ground, key=u.y)`, clamped
   `0.46 <= y <= 0.62`). The defenders walking onto a FORWARD bow stand near the river on THEIR
   side, so that rule can never propose this cast. Worth 1–2 extra bow shots plus a charge reset.

2. **The Balloon chain-pull to the King** — Tesla 4-2, then a defensive bow 6-3 (new, §3A).
   Blocked by the SAME two-card sequencing gap as the doctrinal rocket→tornado order: the cell
   prior scores one placement at a time and cannot say "this card, then that one, in this order".
   One primitive unblocks both; building either as a special case would be building it twice.

3. **4-2 vs 4-3 plant discrimination.** `_spell_pair_risk` generically covers the anti-spell plant
   family, but not the CHOICE: 4-2 pulls **all** units coming off the bridge (better when they hold
   Goblin Barrel / Miner), while 4-3 pulls building-chasers farther from the towers **and** denies
   The Log tower value. Nothing reads their win condition to pick between them.

### PARTIAL

4. **Evo Knight walk-tank + IW slow** (§2). Kiting PEKKA/MK to centre is coded and is close in
   spirit, but *placed to WALK ACROSS the push* is not expressible today — and the evo's −60%
   damage-taken-**while-walking** is exactly what makes it near-free. Needs a path geometry, not a
   spot.

5. **X-Bow + Tesla double-building** (§2). Both spots exist independently (Tesla centre-pull at
   (0.48, 0.585); defensive bow band (0.48, 0.55)), and `_bow_defence_cells` will place a Tesla
   between a standing bow and something attacking it. Missing: the PROACTIVE two-pull formation vs
   RG/Hog — nothing places the second building *because the first is already down*, only in
   reaction to a threat already on the bow.

### ALREADY CODED — and DOCTRINE.md's own "implemented in" column is STALE about F4

* **F1/F2/F3** (triage, threats add, outrange) — `threat_value.py`, as documented.
* **F4** (*"minimise damage, don't prevent it; never spend more than the push cost"*). DOCTRINE.md
  lists this as **"advisor prompt"**. It is not — `elixir_trade` is literally *(enemy value
  eliminated − elixir spent)*, normalised and clipped: F4 priced as a reward on every play in the
  sim, 41 fires in a 12-match ledger. **The doctrine table should be corrected.**
* **F5's "keep the answer in hand"** — `_holdable` in `doctrine_cards`. The "cheapest card that
  works" half is priced implicitly by `elixir_trade` rather than by a rule.
* **§4.1 double-cover** (`_double_cover`, incl. the measured row-15 conflict); **§4.2 anti-spell
  spacing** (`_spell_pair_risk` — the GENERAL form of the guides' 4-2/3-4/4-4/4-6 table, radii read
  from the engine's own specs, so that table does not need transcribing and §8 forbids it anyway);
  **§4.4** IW depth; **§4.5** skeletons cycle corners; **§4.6** nado destinations.

### Ranking, if these get built

(1) is the cheap one — a few lines in `_bow_defence_cells`, fires in a common state, and it is the
only §2 synergy with no expression anywhere. (3) is small and reads only their known cards. (5) is
a weight, not new geometry. (4) needs path geometry. (2) waits for the sequencing primitive and
should be built with rocket→tornado, once.

---


## 3u. 2026-08-23 — W1 REPRICED: the punish window was open 95% of the time, now 39%

The single change flagged at the end of §3s. `_punish_window` had two clauses and **both** were
wrong in the same direction — they asked about the wrong instant and the wrong quantity.

### Clause A: the wrong TENSE — it ignored the bow's 3.5 s deploy

`opp < _opp_block_cost` asked whether they were broke **at the instant of casting**. But an X-Bow
takes 3.5 s to deploy — DOCTRINE.md §1 calls that window the thing "everything about protecting it
happens in" — and elixir accrues throughout it. The blocker that matters is the one they can afford
**when the bow starts firing**, not when it lands.

New `_opp_deploy_lead()` = `bow.deploy_time × eng.elixir_rate()`, both read from the engine so they
track the card data and the elixir phase. It tightens *itself* in double elixir, which is correct:
the same 3.5 s buys them twice the answer.

```
clause A, 148 bow-affordable states:   64.9%  ->  14.2%
```

### Clause B: the wrong QUANTITY — a pre-spend gap with the cost added back

`mine = elixir + spend` then `mine - opp >= punish_elixir_gap (4.0)`. With opponents at a median
2.07 elixir, that is `0 + 6 - 2 = 4` — **satisfied by merely being able to afford the bow**. The
threshold and the bow's price were numerically the same event, so it fired on **100% of steps**.

Replaced by `punish_reserve_gap` (1.0), measured **POST-spend**: what is LEFT to defend with after
paying still has to lead them. That is what the guides actually say — *"only X-Bow at around 10
elixir and when you have a good defensive hand"* is a statement about the **reserve**, not about the
bar you are about to empty. At 10 elixir the reserve is 4 against their 2; at exactly 6 it is 0,
and emptying the bar for a bow is not an elixir advantage.

`punish_elixir_gap` is RETIRED, not repurposed (§8: changing what a key MEANS is not a local
change). It still loads; nothing reads it.

### The call convention, which was also quietly wrong

`_punish_window(spend, cost)`: `spend` adds back what a post-spend caller was already debited,
`cost` takes the bow's price off. `_wincon_exec` passes `spend=cost=6` (already billed);
`_wincon_reach` now passes `spend=0, cost=6` — it runs on a board where **nothing was paid**, and
was previously passing `spend=6` there, overstating our bar by a full 6 elixir. A test pins the two
conventions to the same verdict on the same board.

### Result — and the part that matters most

```
                 before    after      (137 bow-affordable states)
W1_elixir         95.2%    39.4%
W2_cycle           0.0%    19.0%   <- the window the guides rank FIRST
W6_no_big_spell    0.0%     8.0%
W3_counterpush     0.4%     5.8%
W4_full_bar        4.1%     4.4%
W7_late            0.0%     2.9%
(none)             0.4%    20.4%
any window        99.6%    79.6%
```

**Fixing W1 is what made the other seven windows exist.** They were all implemented in §3s and all
inert, because W1 is tested first and was swallowing every state. The eight now form a real
discrimination and a fifth of affordable states get no licence at all.

### Trap (added to §8)

**A probe must use the caller's own frame.** The first re-measurement after this fix reported W1 at
89% — because the probe called `_bow_window(spend=6.0)` on a board where nothing had been paid, so
the "reserve" read as the full bar. The real caller is already debited. Same family as the
live-screen and illegal-coordinate traps: the check and the system under test were looking at
different worlds, and the check was the wrong one.

620 tests + 5 new (`PunishWindowTests`), 1 pre-existing failure
(`test_budget_caps_and_hysteresis_refills`, `_threat_response`).

**hogeq carries its own copy of the old `_punish_window`** (`hogeq/src/clashrl/sim/env.py:933`) and
was deliberately NOT changed: different deck, different win condition, different deploy time. If the
icebow repricing measures well in training, port it there as its own change.

---


## 3v. 2026-08-23 — ⚠⚠⚠ §3p's UNTRAINED BASELINE DOES NOT REPRODUCE. "Training beats untrained" was never established.

**Read this before citing any trained-vs-untrained number in this file.**

§3p is the section that ended the two-day drill-floor investigation, and its conclusion rests on
one table:

```
                              winrate   crowndiff        (untrained: 2.5%, -2.200)
floors 0.30/0.25 (SHIPPED)      6.7%     -1.600     <- "all 3 seeds beat untrained"
```

**The −2.200 does not reproduce at the commit where it was written.** Measured 2026-08-23, git
worktrees at five points spanning §3p → HEAD, 3 random inits × 24 fixed-seed matches each, card
head masked to in-hand-and-affordable:

```
commit    what landed there                          UNTRAINED crowndiff   crowns taken
63909f9   SHIP the drill floor fix  (§3p ITSELF)        -1.722 ±0.100          0.236
20ab936   opponents can use the POCKET                  -1.736 ±0.097          0.139
5cb295d   spell mask ON                                 -1.667 ±0.083          0.181
ebeca9d   RESTORE the drill floor fix                   -1.833 ±0.042          0.153
611ad32   reprice W1                          (HEAD)    -1.708 ±0.087          0.181
```

**Flat.** Every point lies in [−1.83, −1.67]. §3p's −2.200 is ~4.8 SE outside what its own commit
produces. Two consequences, and the second is the one that matters:

1. **The environment never shifted.** I had claimed (2026-08-23, earlier the same day) that the
   baseline drifted −2.200 → −1.75 and that the pocket/spell-mask changes had moved it, so
   cross-date comparisons were void. **That was wrong** — the pocket did not move it, the spell
   mask did not move it, nothing did. Comparisons across those commits are fine.
2. **The "sim rewards learning" result was an artefact of a bad baseline.** Against the untrained
   value that commit actually yields, §3p's trained −1.600 is a gap of **0.12 against noise of
   ~0.14**. It is not a result. Every later decision that assumed a working training loop and went
   looking for reward-shaping problems downstream was standing on it.

### This is the SECOND time an untrained baseline broke a conclusion here

The ledger already records `48bc8e7`: *"CORRECTION: untrained baseline is −13.57, not −6.78"* —
which had likewise made training look like it was destroying a good policy. Same shape, same
load-bearing role, four days apart.

### What is actually true, stated plainly

On a fixed opponent set, untrained and every trained checkpoint measured this session are the same
policy within noise (crowndiff −1.29 … −1.83), and **crowns TAKEN is ~0.18/match everywhere,
untrained included**. A win needs three crowns or a lead at time. The offence has never existed, so
the winrate has never been able to leave zero — and no reward-shaping change downstream of that can
show up in the benchmark.

**Do not run another reward-shaping experiment until a 3-seed A/B shows training beating untrained
on TODAY's code.** `scratchpad/ab3.sh` is that experiment, written and ready; it needs the machine
to itself (§3's RAM constraint: three trainers beside the main run means thrashing, not slowness).

### Trap (§8)

**An UNTRAINED baseline is the load-bearing number in every trained-vs-untrained claim, and it is
the easiest one to get wrong.** It has now been mis-measured twice, and both times a headline
conclusion rested on it. Measure it (a) in the SAME checkout as the trained policy, (b) over
several random inits — one untrained network is a single draw from a wide distribution, and (c)
with the card head masked. It costs no training: a random init's crowndiff is a property of the
ENVIRONMENT, which is exactly why bisecting it across commits is cheap and worth doing.

---


## 3w. 2026-08-23 — `--drill-frac 0.0` AND `--workers 0` WERE BOTH SILENTLY IGNORED

Found while running the §3v A/B. **Two falsy-zero bugs compounding**, and between them the
drills-off arm of every command-line A/B has actually been training *with drills at 0.3*.

### Bug 1 — `--workers 0` silently became 12

```python
workers = int(workers if workers else cfg.get("sim", "rollout_workers", default=0))
```

`0` is falsy, so an EXPLICIT `--workers 0` fell through to `sim.rollout_workers` (**12**) and took
the REMOTE path. The flag's own help says *"0/1 = classic in-process"*; it never did that. Fixed to
`workers is not None`, with the argparse default changed to `None` so "unspecified" and "explicitly
zero" stop being the same value.

### Bug 2 — `--drill-frac 0.0` became "no override"

Then, on the remote path it had just been forced onto:

```python
drill_frac=float(cfg.get("sim", "drill_frac", default=0.0)) or None
```

`0.0 or None` is `None` — and `None` is `RemotePool`'s sentinel for *"no override, re-read
config.yaml in the worker"*. So `--drill-frac 0.0` resolved correctly to 0.0 in the parent, became
`None` crossing the process boundary, and each worker went back to disk and got **0.3**.

The banner printed `drill mix: 0% of episodes are DRILLS` the whole time. **Exactly the class §3q
was written about: individually-correct pieces failing at the seam, with no exception.** Fixed by
always passing the resolved float — a number is never a sentinel.

### Measured, before and after

```
--drill-frac 0.0 --workers 0     BEFORE:  drills 25 (100% of eps, 100% of STEPS), 0W-0L-0D
                                 AFTER:   (see the verification line in the commit)
```

### What this invalidates, and what it does not

* **Every `--drill-frac 0.0` arm run from the COMMAND LINE is void** — it trained at 0.3.
* **Runs that set `sim.drill_frac: 0.0` in config.yaml are FINE.** Both paths read the file, so the
  bug never bit. §3p's *"3 seeds at drill_frac 0.0 gave 0.993/0.922/0.964 (healthy) -- drills ARE
  the cause"* is therefore **unverified, not disproved**: the numbers differ far too much from the
  collapsed 0.11-0.15 to be the same condition, so those runs were probably config edits. **Check
  before citing it.** The code comments at `train_sim_ppo.py:877` and `:1075` cite the same
  measurement and inherit the same doubt.
* **Non-zero overrides were always fine** (`0.02 or None` is `0.02`). Only the zero arm broke.

### It also explains the A/B's other failure

Six runs each launched with `--workers 0` became six runs with **12 workers each = 72 processes** on
16 cores. The logs filled with `bash: fork: retry: Resource temporarily unavailable` and children
dying with `0xC000012D`. That is the §3 RAM/oversubscription failure, arriving through a flag that
was supposed to prevent it.

### Trap (§8)

**`x or DEFAULT` is wrong for any numeric knob whose zero is meaningful.** Both bugs are one
idiom: `0` and `0.0` are falsy, so "explicitly off" and "unspecified" collapse into each other.
This repo has `drill_frac`, `workers`, `wincon_bank_floor`, `deck_pfsp_power` and several reward
weights where **zero is a deliberate setting**, and every one of them is a place this idiom silently
substitutes a default. Use `is None`. And the tell was visible in the log for two runs: a banner
that says one thing while the episode counter says another means the override never reached the
thing it names.

---


## 3x. 2026-08-23 — drill_frac SWEEP: 0.3 IS THE BEST OF FOUR, AND NONE OF THEM BEATS UNTRAINED

The first sweep of this knob where the knob actually worked (see §3w — `--drill-frac 0.0` had been
silently training at 0.3, so every previous drills-off arm was void). 4 arms × 3 seeds, 350 matches
each, from scratch, scored on 40 fixed-seed matches per policy with a 3-init untrained reference.

```
arm          crowndiff             crowns TAKEN      wins/40   x_bow
UNTRAINED    -1.692 +-0.030          0.158 +-0.036      0.7      0.1%
frac 0.0     -1.642 +-0.085          0.142 +-0.017      2.7      0.0%   +0.6 SE
frac 0.02    -1.742 +-0.159          0.100 +-0.029      1.3      0.5%   -0.3 SE
frac 0.03    -1.700 +-0.014          0.167 +-0.008      2.0      0.3%   -0.2 SE
frac 0.3     -1.617 +-0.068          0.233 +-0.008      3.0      0.0%   +1.0 SE
```
(+- is the spread ACROSS SEEDS; the SE column is versus untrained.)

### Conclusions

1. **The shipped 0.3 is the best of the four.** No config change. Owner asked which value to switch
   to; the answer is the one already in place.
2. **LOWERING drill_frac DOES NOT HELP.** 0.02 was the worst arm on every column — worse than
   untrained on crowndiff and on crowns taken. **This kills the hypothesis I had been carrying**
   (that 85%-drill episodes were starving match learning). It is not the lever.
3. **No arm clears untrained on crowndiff.** Best is 0.3 at **+1.0 SE**, which is nothing. At this
   training scale (350 matches) PPO does not produce a policy the benchmark can distinguish from a
   random init — consistent with §3v.
4. **The ONE signal in the table is crowns TAKEN for arm 0.3**: 0.233 ±0.008 vs untrained's
   0.158 ±0.036, about **+2.0 SE**, and 3.0 wins/40 against untrained's 0.7. Marginal, single
   experiment, small budget — but it is the first time anything in this project has moved the
   metric that actually gates the winrate, and it moved in the direction of MORE drills, not fewer.

### What this means for where the fix has to go

drill_frac is settled and it is not the problem. The remaining candidate is the one §3v pointed at:
**the offence has no reachable positive signal.** In the 8k ledger `take_enemy_tower` — the largest
carrot the reward can pay — has **zero fires**, because the policy has never taken a tower; while
the offence-related terms sum NEGATIVE (`xbow_into_push` −4.00 against `wincon_exec` +1.20 for one
fire each). If that ratio survives a proper sample, attempting offence is expected-value negative
and gradient descent is correctly learning to stop trying. **Measure that on a real sample before
changing anything** — those are 1-fire terms and this file already carries two retractions caused by
exactly that kind of extrapolation.

---


## 3y. 2026-08-23 — THE ADVISOR REASONS CORRECTLY; THE BOARD IT IS SHOWN DOES NOT

Owner: *"it still tells the model to hold when the enemy is CLEARLY attacking, and to play log on
air troops (which somehow STILL registers a hit)"* — and asked whether the advisor is worth keeping.
Three separate findings, and **the advisor's judgement is not the fault in any of them**.

### 1. The Log DID register hits on air — `air_bases` was permanently empty (FIXED)

`env.py` built it as `db.names() if hasattr(db, "names") else []`. **CardDB has no `names()`**, so
the guard yielded `[]` every run, `air_bases` was an empty frozenset, and
`log_hits(..., air=air_bases)` never skipped a flying unit. Every live Log cast on Minions / Bats /
Balloon / Baby Dragon scored as a HIT.

```
hasattr(db,'names'): False        is_flying('minions'): True      <- data was fine
air_bases as built:  0 cards      after fix: 21 cards
minions  before HIT=True -> after HIT=False      skeletons stays HIT=True
```

`log_hits`'s guard was written correctly; only the ENUMERATION was broken, and it failed the silent
way. Fixed to iterate `db.cards`, and env now PRINTS the count at startup and shouts when empty.
**The sim engine was never affected** — checked directly, the Log leaves all four air cards
untouched and kills skeletons/goblins. Live reward only, which is why it survived so long.

### 2. Given a correct board, the advisor gets BOTH reported cases right

Four cases added to `tools/llm_eval.py` (which uses the REAL `LLMAdvisor` prompt) reproducing the
reports. All four PASS on `qwen2.5:latest`:

```
minions_log_is_wrong      -> tesla       (not the_log)
bats_log_is_wrong         -> ice_wizard  (not the_log)
fresh_push_do_not_hold    -> tesla       (not HOLD)
hog_committed_do_not_hold -> tesla       (not HOLD)
```

16/20 overall, reproducible (temperature 0.0, identical misses on re-run). Its one HOLD-adjacent
miss runs the OTHER way: `lone_spear_goblins_ignore` -> *tesla* when the answer is *hold*. **It
over-spends on ignorable threats; it does not hold under real ones.**

So the fault is in what reaches it, and `train_rl` already documents where: **(a)** the detector
misses a unit in ~31% of passes (fixed via tracker memory); **(b)** a freshly played enemy card is
team "unknown" for its first seconds — *"precisely the answer window"* — and **(b) is deliberately
unfixed**. Plus a third, in the same gate: `if y < 0.42 or not b: continue`, a DEPTH filter that
ignores anything still on their side of the river, so a Giant just dropped at their bridge does not
count as a threat at all. A push in its first seconds is invisible, the board genuinely looks quiet,
and HOLD is the correct answer to the question actually asked.

### 3. ⚠ THE MODEL-CHOICE COMMENT IN config.yaml WAS BACKWARDS (corrected)

It read *"gemma3:4b scores better (8/10 vs 6/10)"*. On the 20-case set the ordering **reverses**:

```
qwen2.5:latest   16/20   p50 3.08s
gemma3:4b         8/20   p50 1.24s
```

gemma3:4b fails BOTH live-report cases and answers `the_log` in **7 of its 12 misses** — precisely
the behaviour the owner reports. Switching on the strength of the old comment would have made live
play worse. Corrected in place with the numbers and a "re-run the eval before changing this".

### ⚠ OPEN, and it may make the whole question moot

`llm_advisor_timeout_s: 0.55` while the config's own comment claims **0.590s p50** — by its own
figure more than half of calls miss the budget and fall back to a RANDOM card. (The 3.08s measured
here was with the GPU at 99% from a PPO run, so it is an upper bound, not the live number.)

**Before arguing about the advisor's judgement, read what it actually did:** `train_rl.py:1103`
prints `llm-advisor <model>: N calls, N answered (X%), N failed, mean N ms`. If answered% is low the
advisor is barely running, and "I haven't seen much change with it on" has a much duller
explanation than model quality.

### ⚠⚠ RESOLVED, AND IT MOOTS THE WHOLE DEBATE: THE ADVISOR HAS NEVER ANSWERED IN LIVE PLAY

Owner supplied the line this section asked for, from their last live session:

```
[train-rl] llm-advisor qwen2.5:latest: 10 calls, 0 answered (0%), 10 failed, mean 565 ms,
           last error TimeoutError: timed out
```

**0% answered.** 565 ms mean against `llm_advisor_timeout_s: 0.55` (550 ms) -- every call misses,
by about 15 ms, and falls back to a RANDOM card.

**Cause: a config drift from a change to a different key.** The budget was sized for a 1.0 s
act_period; `play.act_period` was lowered 1.0 -> 0.6 on 2026-08-20 with `sim.agent_dt` (S3m), and
the advisor's budget was never revisited. The comment on the timeout line still SAID "act_period is
1.0s" until today. A reaction-time change three days earlier silently switched the advisor off, and
the failure mode is a silent fallback, so nothing announced it.

**Raising the timeout does not fix it.** The bot is blind during the call, so a ~590 ms answer
inside a 600 ms period leaves nothing for perception or action. Synchronously this model does not
fit this act_period. Real options: run it ASYNCHRONOUSLY (answer applied on a later decision), a
~150 ms model (qwen2.5:0.5b -- scores badly), raise act_period back toward 1.0 (gamma / n_step /
the per-tick reward scale all move with it), or leave it OFF and rely on the counter table, which
is already the documented FAST PATH and resolves the researched cases in microseconds.

### THIS RE-EXPLAINS BOTH LIVE REPORTS -- neither was the LLM

With 0% answered the advisor produced no card at all, so:

* **"tells the model to hold when the enemy is CLEARLY attacking"** = the CODE's quiet-board rule,
  `if not needs_answer: ... return (0, 0, 0)` in train_rl. Which is fed by the `y >= 0.42` depth
  filter -- so the owner's separate instinct that the depth filter was implicated was RIGHT, by a
  route neither of us had argued.
* **"plays log on air troops"** = the RANDOM fallback (the counter table only fires when it has a
  row for the threat), and then the empty-`air_bases` bug scored it as a HIT.

The 16/20 eval score is still valid -- it just describes a component that has never been in the loop.
**Do not tune the advisor's prompt or model on live observations until answered% is non-zero.**

### Method note

An on/off A/B in live play was the wrong instrument for this question and I proposed it first: it
confounds advisor reasoning with detector noise, the unknown-team window and the veto logic, and it
costs hours of the owner's live play. The offline harness isolates the reasoning cleanly in ~90 s.
Reach for the A/B only once the board description is trusted.

---


## 4b. 2026-08-24 — THE TWO P(play) NUMBERS WERE NEVER IN CONFLICT, AND THERE IS NO SPEEDUP TO BUY

### ⚠ CORRECTION TO §4a's WORDING — "the policy plays constantly" is false as written

§4a's premise was that nothing pays for a correct wait, so *"playing is weakly dominant at every
decision"* and the policy therefore plays constantly. The trainer's own telemetry says the gate
plays on **~3% of steps**, and has in every run for days:

```
run                    play% trajectory (first four updates ... last four)
ppo_run_night1      5.1 2.2 2.9 2.4  ...  3.4 3.3 3.6 3.0
ppo_run_dose10      5.1 2.0 3.2 2.1  ...  3.3 3.4 3.2 3.3
ppo_run_lever2      5.1 1.9 2.9 2.3  ...  3.2 3.4 2.9 3.5
ppo_run_crown3x     5.2 2.0 3.1 2.2  ...  2.9 2.9 2.7 2.9
ppo_restraint       5.1 2.2 3.0             <- fix 1, indistinguishable from all of them
```

**The two figures have different denominators, and both are correct:**

* the trainer's `plays are X% of steps` is `play = (g_b == 1)` (train_sim_ppo.py:1001) — the gate
  action ACTUALLY TAKEN, over ALL steps;
* `train_sim_ppo.py:434` masks the PLAY logit to `_NEG` whenever `none_play = ~playable.any(1)`,
  so on any step where nothing is affordable the gate is **FORCED** to wait — and that forced wait
  is recorded as an ordinary `g_b == 0` and counted in `n_wait`;
* the watcher's `P(play) 0.569` is conditional on a play being LEGAL.

At the measured ~5-12% affordability, `0.57 x 0.08 ~= 3%`. The two reconcile exactly. The
defensible claim is **"when the choice is real it plays ~57% of the time"**, which drains the bar
to ~2 and makes most later steps unaffordable. The elixir evidence fits that and does not fit the
raw rate: at a genuine 3% play rate the bar would climb to the cap and `leak` would fire constantly,
and for m=26000 `leak` fires **zero** times.

**Fix 1 survives this correction, and for a specific reason worth keeping:** guard 2 requires a
counter in hand AND affordable, so `restraint_hold` can only fire on the conditional decision —
the same denominator the problem lives in. **It cannot pay for a forced wait.** Had the guard been
written on "a threat is present" alone, this correction would have retired the fix.

### ⚠ UNADDRESSED, and it is in the code as a comment nobody carried forward

`train_sim_ppo.py:1098` records a measured finding that is a bigger effect than anything §4a
proposes: **`drill_frac 0.0` holds P(play) at 0.92-0.99, and four runs at 0.3 collapse it to
0.11-0.15.** Every run under discussion uses `drill_frac: 0.3`. The comment poses the mechanism
question and the current run answers it — on MATCH steps (drills excluded by construction):

```
gate drift on PLAY -0.41582  on WAIT +0.00574   (n_play 14, n_wait 294)
gate drift on PLAY -0.08759  on WAIT +0.00598   (n_play  9, n_wait 241)
```

Push is negative on PLAY and positive on WAIT **on match steps**, which is the comment's own
"drills corrupt something SHARED (advantage normalisation over the mixed batch, or the critic),
poisoning match steps too" branch — not the "drills directly teach the gate to wait" branch.
Related telemetry, same run: `clip rate PLAY 0.536 vs WAIT 0.006`, `gradient KILLED PLAY 0.225 vs
WAIT 0.004`, and `26.7% of plays ALREADY outside the 1.20 clip before any step`. With n_play ~14
per diagnostic sample the play branch is estimated from very few samples, which is self-reinforcing:
fewer plays -> noisier play gradient -> more clipping -> gate drifts off play.

**This is a candidate cause of the run-degrades-after-a-while pattern the owner has reported across
several runs regardless of what was changed.** It is NOT a reward defect, so fixes 1-3 cannot touch
it, and it is a different mechanism from fix 4's curriculum oscillation. Queue it as its own
experiment; do not bundle.

### THROUGHPUT — there is no speedup available, and the slow run was a DUPLICATE

Owner asked for faster test runs. Three levers measured, all flat:

```
lever                       result
OMP_NUM_THREADS 1 vs 2      0.70 vs 0.70 ep/s     no effect
--device cpu vs cuda        0.50 vs 0.50 ep/s     no effect (see caveat)
more workers                CPU already 96-100%   no headroom
```

**The actual cause of the slowness was a STALE RUN still alive** — killed with Git-Bash `pkill`,
which is the §2 trap, already documented from yesterday and repeated anyway. 28 processes, CPU
pinned, free RAM **0.8 GB**. Killed via PowerShell: RAM recovered to 5.6 GB. **Before diagnosing
throughput, count the processes.**

⚠ **The device A/B is weaker than it looks.** With `--envs 192` episodes complete in WAVES, so a
cumulative `ep/s` read at 100 episodes is partly wave timing rather than throughput. Both arms read
0.50 at ep100; treat that as "no visible difference", not as a clean 1.00x.

**`--device cpu` is still preferred** — same measured throughput, and it frees the GPU entirely,
which matters because the LLM advisor cannot load qwen2.5 while a trainer holds the card.

⚠ **The CLI help's claim that CPU is 5x faster for this trainer (1.0 vs 0.2 match/s) DID NOT
REPRODUCE.** It is stale; do not plan around it.

---


## 4c. 2026-08-24 — FIX 1 PAIRED READ AT 650 MATCHES: it changes behaviour, and two of four changes are wrong

First trustworthy read, using the pinned-determinism PAIRED design (same 12 seeds, both arms,
`torch.set_num_threads(1)` + `PYTHONHASHSEED=0`). Everything measured before this is withdrawn.

```
                     m=26000      restraint@650      delta
plays              570 (13.9%)    443 (11.4%)       -2.5pp
elixir median         2.14           2.86           +0.72
restraint_hold        0.67/m         1.00/m         +0.33  (sem 0.26 / 0.28)
threat_miss_idle      2.25/m         4.00/m         +1.75  (sem 0.43 / 0.79)   <-- WRONG WAY
leak                  0.75/m        10.83/m        +10.08  (sem 0.41 / 5.28)   <-- WRONG WAY
wincon_exec           1.67/m         2.83/m         +1.16
take_enemy_tower      0.50/m         0.50/m          0.00
```

**Intended direction present:** plays down, elixir banked up. That is what fix 1 was for.

**`threat_miss_idle` DOUBLED, and that is the diagnostic one.** `restraint_hold` and
`threat_miss_idle` are mutually exclusive BY CONSTRUCTION -- same `bodies_ignore_frac` call on the
same committed group, so a board is either worth answering or worth ignoring, never both. Targeted
restraint would hold this term flat or lower it. Doubling means the policy is learning **"waiting
pays"** in general rather than "waiting on IGNORABLE threats pays" -- the over-generalisation the
three guards exist to prevent.

**`leak` rose 14x**, the same hoarding signature that got `wincon_reach: 2.0` reverted. Weaker
(sd 18.3, ~1.9 sigma) but pointing the same way.

The magnitude ratio moved **0.30 -> 0.25**: the penalty is outgrowing the credit, so the policy is
currently NET-LOSING from this behaviour (-4.00 missed threats against +1.00 restraint credit). A
converged policy would not choose that, which is evidence for the confound below.

⚠ **CONFOUNDED, and the confound is large.** 650 matches is deep in the warm-start critic dip
(`vl` still climbing 0.717 -> 1.027; §4a measured the bottom at ~1,700 episodes and most recovery
by ~7,600). §4a's own rule says compare run-vs-run at matched episodes, not a mid-run checkpoint
against its init.

### ⚠ VERDICT AT 2600 EPISODES: THE EXPERIMENT CANNOT ANSWER THE QUESTION (design flaw)

The @650 alarm WAS the critic dip and reverted in full -- that call was right, and by the
pre-committed rule fix 1 is cleared of teaching blanket inaction:

```
                  base(n=30)   @650      @2600(n=30)   paired delta   sigma
threat_miss_idle    2.87       4.00        2.60          -0.27        0.5
leak                0.43      10.83        1.20          +0.77        1.2
restraint_hold      0.63       1.00        0.50          -0.13        0.8
elixir median       2.14       2.86        2.14           0.00         -
plays_pct          13.2       11.40       13.0           -0.2          -
```

**But nothing here is attributable to fix 1**, because the run is warm-started and the comparison
is against its own init -- see the new S8 trap. A sign test over the ledger says 16 of 21 terms
moved NEGATIVE (p=0.027), which is a general decline and is exactly what the warm-start tax alone
produces at this episode count. **Not "fix 1 is neutral" -- the design has no power to say either
way.**

WITHDRAWN (both were n=12 artefacts): "restraint_hold 0.67 -> 0.33, training made the rewarded
behaviour less frequent" (0.8 sigma at n=30), and "offence down / defence up, fix 1 suppresses the
win condition" (a hand-picked five-term partition; the aggregate offence test is 1.9 sigma and
falls in 18 of 30 matches where chance is 15).

### DECISION (2026-08-24): RUN TO 4000, THEN RUN THE MATCHED CONTROL

The control -- same init, same episodes, `restraint_hold: 0` -- is worth more than the fix-1
verdict: it is the **matched-episode reference baseline this project has never had**, and every
future reward experiment needs it. ~2.5 h.

### (superseded) original plan: PROBE AT 2000 / 3000 / 4000

A single endpoint cannot separate "the dip did it" from "the reward did it"; the TRAJECTORY can, and
the run is already launched with `--matches 4000` so it costs only probe time.

```
threat_miss_idle 4.0 -> 3.0 -> 2.3   =>  dip artifact, fix 1 clean, proceed to fixes 2+3
threat_miss_idle flat or rising      =>  credit teaches blanket inaction; REPAIR before 2+3
```

Repair, if needed, in order of preference:
1. dose `restraint_hold` 1.0 -> 0.5 (keeps the term live at ~0.15 of the penalty, still above the
   0.04 that measured decorative);
2. tighten guard 1 -- require the ignorable threat to be closer/committed, so fewer boards qualify;
3. only if both fail, gate the credit on `threat_miss_idle` not having fired in the same match.


## 4f. 2026-08-25 OVERNIGHT — MATCHED-CONTROL RESULTS (the design this project never had)

Three arms from the SAME init (`policy_BEST_m26000_20260823.pt`), matched at the same episode
count, differing in exactly one thing each. The warm-start critic dip is present in ALL arms, so it
CANCELS -- which is precisely what every earlier reward experiment here was missing.

```
arm        restraint_hold   env.py       episodes
control         0.0         unpatched      2600 / 3600
fix 1           1.0         unpatched      2600 / 3600
fix 2+3         0.0         PATCHED        2600
fix 4            -          -              no run (validated synthetically)
```

### FIX 1 — FAILS its pre-committed criterion (paired, n=30)

```
                   control@2600   fix1@2600   paired delta   sigma
restraint_hold        1.30           0.60        -0.70        2.9   <-- WRONG WAY
threat_miss_idle      4.67           2.60        -2.07        2.8
plays                11.4%          13.0%
elixir median         2.64           2.14
```

Criterion was "`restraint_hold` fires MORE and `threat_miss_idle` does not rise, >=2 sigma".
**Clause 1 FAILS at 2.9 sigma in the wrong direction**: the policy trained WITH the restraint credit
performs the credited behaviour LESS THAN HALF as often as the control. Clause 2 passes -- missed
threats fell 2.07 (2.8 sigma), so it is not defensively harmful.

The picture is coherent: fix 1 made the policy MORE ACTIVE, not more restrained. It plays more
(13.0% vs 11.4%), banks less (elixir 2.14 vs 2.64), and therefore has fewer of BOTH idle-event
types. **Paying for restraint produced less restraint.**

⚠ MECHANISM NOT ESTABLISHED, only the effect. A plausible candidate worth testing before any
re-dose: a positive term available on idle steps raises the CRITIC'S BASELINE for those states, and
since the credit is small and capped (2.0/match, realised ~0.5), the realised return can fall SHORT
of the raised baseline -- making idling look WORSE in advantage terms than before the credit
existed. If that is right, a bigger dose does not fix it and may invert it further; the term would
need to be uncapped or moved off the idle step entirely.

### FIXES 2+3 — FAIL their pre-committed criterion (paired, n=30), and in the predicted way

```
                 control@2600   fix23@2600   paired delta   sigma
xbow_lock            8.93          3.20         -5.73        2.1   <-- WRONG WAY
chip_linear          9.23          3.33         -5.90        2.1   <-- WRONG WAY
xbow_defends         6.93          4.40         -2.53        1.0
xbow_no_lock         0.27          0.07         -0.20        1.8
plays               11.7%         11.0%
elixir median        2.57          2.79
```

Criterion was "`xbow_lock`/`chip_linear` UP, `xbow_no_lock` present, `xbow_defends` firing, >=2
sigma". **Both primary terms moved DOWN at 2.1 sigma** -- a 64% fall in bow uptime and in the bow's
damage lane.

**The policy is not playing BETTER bows, it is playing FEWER bows.** `xbow_no_lock` did fall
(0.27 -> 0.07) -- fewer useless bows -- but `xbow_lock` fell just as hard, so the useless bows were
removed by removing bows, not by improving them.

⚠ **THIS WAS PREDICTED IN WRITING BEFORE THE RUN**, in fix23.py's own docstring and in the note to
the owner: *"There is no existing penalty for a blocked bow (S4a corrected that belief), so 2a
already removes a credit; stacking a large penalty on top would suppress bow play further while
x_bow share is ALREADY collapsing."* The dose was deliberately kept small (-0.5) for exactly this
reason and it was still enough. **Penalising a bad OUTCOME of an action suppresses the ACTION** --
the policy cannot tell "play a better bow" from "stop playing bows", and the second is cheaper.

**REVERTED FROM THE TREE 2026-08-25.** A measurably-failing reward change left in place
contaminates every experiment after it -- fix 4, fix 5 and the entropy A/B all need a clean
baseline. The patch is preserved in `scratchpad/fix23.py` for the adjustment round. The three
tests that require the new terms were removed with it; **the corrected
`test_overcommit_credit_on_bow_death` STAYS**, because its repair is true of the unpatched reward
too -- the fixture's bow sat at y=0.60, 12.7 tiles from the enemy princess against an 11.7 range,
so it could never have locked a tower and the test was crediting a bow that was physically
incapable of threatening anything. Suite green at 625.

If this is retried, the penalty has to be removed and only the CREDIT GATE (2a) kept, so a useless
bow earns nothing rather than costing something -- or the penalty has to be conditioned on a bow
that was placed in range, so it cannot be avoided by simply not playing the card.

### FIX 4 — PASSES, and it is SHIPPED (the only fix of the three that worked)

Re-measured on the shipped code by replaying the controller's exact arithmetic against a synthetic
winrate held CONSTANT, so every difficulty move is by construction pure noise response:

```
noise-driven move rate:  current 52.5%  ->  deadband 0.06  0.2%
lag on a REAL step change (8% -> 20%):  current 236 matches  ->  0.06  199 matches
```

**Strictly better on both axes**: it removes 99.6% of the noise-driven movement AND tracks a real
change FASTER, because the rate limit is no longer being spent on coin flips. That is why it ships
as one line with no trade-off to weigh.

Widening the sensor window 50 -> 200 was measured and **REJECTED**: +0.1pp of noise immunity for
1.8x the tracking lag (199 -> 353 matches). The first draft of this fix contained it.

⚠ Validated SYNTHETICALLY, not by a training run -- deliberately. In a live run the policy and the
controller move together, so no difficulty change is attributable, and this run's difficulty spent
long stretches pinned at the 0.15 floor where the defect cannot appear at all. Replaying the
controller in isolation is the stronger evidence here, not the weaker. Harness: `scratchpad/curr_sim.py`
-- re-run it before ever changing `curriculum_deadband`.

### ⚠ MEASUREMENT BUG CAUGHT BEFORE IT PRODUCED A VERDICT

The first run of this comparison reported `restraint_hold 0.00` in BOTH arms. The probe reads the
CURRENT config, and the control arm trains at `restraint_hold: 0.0` -- so the TERM WAS DISABLED IN
THE EVALUATION ENV and could not fire whatever policy was loaded. The instrument was switched off,
not the behaviour absent (same shape as `air_bases` and `--drill-frac 0.0`).
Fixed by forcing `e.w_restraint` on the ENV INSTANCE (`PROBE_RESTRAINT_W`), never by editing
config.yaml: workers call `Config.load()` in their own processes, so a mid-run edit would have been
picked up by a respawn and contaminated the control. The cap is lifted for counting too -- at
w=1.0/cap=2.0 the count saturates at 2/match and cannot tell "restrained twice" from "nine times".


## 4g. 2026-08-25 — FIX 6 SHIPPED: the cheap answer in the OTHER lane was worth nothing

Owner's doctrine, and he is right: prioritising the greater threat must not mean IGNORING the
lesser one. Golem + support one side, a Mini Pekka the other -- the golem is the bigger threat, but
the mini pekka still needs an answer, cheaply (Skeletons usually suffice).

MEASURED on exactly that board, BEFORE the fix:

```
threat_response for the correct Skeletons in the mini-pekka lane   +0.000
threat_miss_idle fires, answered vs ignored                         5 vs 5
TOTAL dense step reward, both lanes vs golem only                  +0.05
our princess HP, both lanes vs golem only                          +2266
```

**The correct play saved ~2266 tower HP and the dense reward paid +0.05 for it.** Two causes:
* `_threat_response` requires the card to counter the PRIMARY identity in the PRIMARY lane, so a
  correct second-lane answer scores exactly zero;
* `_threat_miss_idle`'s waiver is GLOBAL -- `any(our unit counters tid)`, no lane test -- so once
  the golem is answered, ignoring the mini pekka is free.

That left only the DELAYED tower-survival outcome, which is the long-horizon credit assignment this
critic handles worst -- see the whole warm-start/critic-dip story.

### The fix, and what it deliberately does NOT do

`_secondary_lane_response` pays for a correct answer to a committed threat in a lane OTHER than the
primary, judged on that lane's OWN identity, OWN triage and OWN danger:

```
                              BEFORE     AFTER
skeletons in mini-pekka lane   0.000    +0.949     (= mini_pekka 0.667 / golem 0.703)
skeletons in the GOLEM lane      -       0.000     (primary is _threat_response's job)
empty lane                       -       0.000
TRICKLE in the second lane       -       0.000     (triage refuses it)
```

⚠ **IT ADDS A CREDIT AND DOES NOT TOUCH THE PENALTY.** Making `_threat_miss_idle` lane-aware would
make it fire MORE, and that term has been the dominant negative in this ledger TWICE (-152.00 over
152 fires in 323 steps; 1595 fires / 100 matches) -- both times teaching the policy to empty its
bar, the exact failure this project has spent a week undoing. If the credit proves insufficient,
the waiver is the NEXT lever, not this one.

The credit is the SAME for skeletons, knight and tesla, on purpose: "cheapest sufficient answer" is
enforced by the credit BUDGET (`min(threat_credit_budget, n_cards)`, added in `a925d88` precisely to
stop over-answering paying) plus elixir cost, not by varying this term.

**6 tests added; all 6 ERROR on the unpatched tree, so they detect the fix rather than merely
passing.** icebow 635 tests OK.

⚠ **THIS INVALIDATES ANY CONTROL ARM TRAINED BEFORE IT** (owner flagged this). `ARM_control2.pt` was
stopped mid-run and discarded; the adjustment round needs a fresh control on the fix 4+5+6 tree.


## 4h. 2026-08-25 — FIX 7 SHIPPED: the missed-defence penalty was a STEP FUNCTION

Owner's idea, and the measurement is stronger than the framing suggested. `_threat_miss_idle` is not
flat, it is a step: free below `IGNORE_FRAC` (0.05), a full -1.0 above it. Measured on real boards:

```
committed group            ignore_frac   BEFORE    AFTER
one skeletons                    0.004     0.000    0.000   (waived)
two trickles together            0.107    -1.000   -0.107
one knight                       0.302    -1.000   -0.302
one mini pekka                   0.667    -1.000   -0.667
two mini pekkas                  2.108    -1.000   -1.000   (capped)
golem + mega minion              2.074    -1.000   -1.000   (capped)
```

**Ignoring two trickles cost exactly what ignoring a golem push cost -- a 19x difference in real
threat priced identically.** The quantity that fixes it was already being computed ON THAT LINE:
`bodies_ignore_frac` IS "how much tower does this cost me", and it was thresholded and then thrown
away.

### The second benefit is bigger than the fidelity one

`threat_miss_idle` has been the DOMINANT NEGATIVE TERM in this ledger **twice** -- -152.00 over 152
fires in 323 steps (86% of a hold-policy's entire penalty), and 1595 fires / 100 matches at -16/match
(3x the next term). **Both times it taught the policy to empty its bar**, which is the failure this
project has spent a week undoing, and which fix 1 was itself an attempt to counteract. Real fires
land mostly at 0.3-0.7, so proportional pricing roughly HALVES the term's magnitude **while making
it more accurate**. Fidelity up and a known failure mode defused in one change.

⚠ **The `IGNORE_FRAC` early return is KEPT, and not because it is harmless.** The term is
rate-limited by `threat_miss_period` (4 s) and the limiter arms whenever it fires. A 0.004 fire for
a lone Skeletons costs nothing itself but would ARM THE LIMITER and mask a real push arriving a
second later. The threshold's real job is to keep trivial threats from consuming the rate limit, and
that job survives. What it stops doing is pricing a 0.107 board like a 2.074 one -- the cliff at the
boundary falls from (0 -> -1.00) to (0 -> -0.05).

Capped at 1.0 on purpose: this term is a PROXY that makes delayed tower damage learnable, not a
replacement for the outcome terms, so a two-tower push must not out-shout what it stands in for.

4 tests added; 2 of the 4 FAIL on the unpatched tree (the two that assert ordering and magnitude).
icebow 639 tests OK.


## 4j. 2026-08-25 — FIX 1 DROPPED (not deleted). Kept armed behind one config line.

Owner's decision, on the evidence below: **drop it, but keep it available in case later runs go
sideways.** It is already in exactly that state -- `_restraint_hold` remains in `env.py` and is INERT
because `rewards.restraint_hold: 0.0`. **Re-enabling is one config line; there is no patch to
re-apply and nothing to reconstruct.**

### Why it was dropped

```
                          m=26000   OLD control   fix1 arm   control4 (4+5+6+7)
elixir median               2.14      2.57-2.64     2.14         2.79
restraint behaviour/match   0.63        1.30        0.50         1.40
threat_miss_idle /match    -2.87       -4.67       -2.60        -3.32
```

**With NO restraint credit, the corrected reward produces 2.8x the restraint behaviour fix 1
achieved (1.40 vs 0.50) and the best banking measured in this project (2.79).**

Fix 1 was a COUNTERWEIGHT to `threat_miss_idle` being over-sized. Fix 7 corrected that term at the
source -- measured on control4, it now fires at an average **-0.573**, not a flat -1.0, and its
per-match magnitude fell -4.67 -> -3.32 despite MORE fires (5.80 vs 4.67). So the thing fix 1 was
built to offset no longer exists at the size that motivated it, and its own measured failure mode
(reward a state -> get LESS of it, -0.70 at 2.9 sigma) makes a retry likely to misfire again.

⚠ **HONEST LIMIT ON THIS EVIDENCE.** control4 carries fixes 5+6+7 TOGETHER, so this is not a clean
isolation of fix 7, and it is not a paired comparison -- different arms, different seeds. Strong
evidence, not proof. The asymmetry is what decides it: shipping an unneeded reward term makes it
uncontrolled noise in every future experiment, while dropping it costs nothing measurable.

### RE-ENABLE IT IF, AND ONLY IF, THESE APPEAR

Set `rewards.restraint_hold: 1.0` (cap 2.0) again if a later run shows BOTH:
1. **elixir median falling back toward ~2.1-2.3** (the dumping signature), AND
2. **restraint behaviour/match dropping below ~0.8** measured with the probe's instrument FORCED ON
   (`PROBE_RESTRAINT_W=1.0`, cap lifted -- otherwise the counter is off and reads 0.00 whatever the
   policy does; see the trap in 4f).

⚠ If they do appear, DO NOT simply raise the dose. The measured failure was directional, not
magnitude-limited, and the standing hypothesis is that a capped positive term on idle steps inflates
the CRITIC'S BASELINE for those states until idling looks worse in advantage terms than before the
credit existed. Change the SHAPE first: pay once when an ignored threat expires harmlessly, rather
than per idle tick.


## 4k. 2026-08-25 — FIXES 4, 5, 6, 7 PORTED TO HOGEQ (2+3 and 1 deliberately not)

### What was ported, and what was NOT

```
fix 4  curriculum deadband 0.02 -> 0.06      PORTED   trainer-level, deck-agnostic
fix 5  _threat_pos ranks by DANGER           PORTED   hogeq's copy was byte-identical to the bug
fix 6  secondary-lane response               PORTED   anchor adapted (see below)
fix 7  proportional miss penalty             PORTED   deck-agnostic
fix 2+3  x_bow credit gate                   NOT      X-BOW SPECIFIC -- hogeq has no x_bow, and the
                                                      retry is still under test in icebow
fix 1  restraint_hold                        NOT      dropped in icebow; hogeq never had it (0 refs)
```

### Generated, not retyped

The hogeq patches are DERIVED from the icebow patch files by a script, not hand-copied. This repo's
ledger already records several bugs that lived in one deck only because a "cross-deck" fix was
applied by hand to one side. Deriving them makes the logic identical by construction; only the
ANCHORS are adapted.

**One adaptation was needed:** hogeq's `_punish_window(self, spend)` has no `cost` kwarg, and fix 6
uses that line purely as an INSERTION POINT for the new method. Cosmetic, but the anchor had to
match or the patch would have failed closed (which it did, until adapted).

**Every anchor and dependency was verified in hogeq BEFORE writing any patch** -- including
`threat_value.ignore_cost_frac`, which fixes 5 and 6 both need and which hogeq's `env.py` had never
called (the function exists in its `threat_value.py` with an identical signature; an early check
that grepped the wrong file said MISSING and was wrong).

### Verified behaviourally on HOGEQ's OWN deck (hog/firecracker/mighty_miner/tesla/log/EQ)

```
FIX 5  pekka(1.907) shallow vs skeletons(0.004) DEEPER -> _threat_pos x=0.25  (the PEKKA, correct)
FIX 7  knight -0.302 | mini pekka -0.667 | golem+mega_minion -1.000   (was -1.000 for ALL)
FIX 6  skeletons in the mini-pekka lane -> +0.949                      (was +0.000)
```

### Test result, against a MEASURED pre-port baseline

⚠ **hogeq's suite is NOT green and was not green before this.** Measured by stashing the ports and
re-running: **3 failures + 39 errors = 42, identical before and after** -- which is exactly the
"hogeq at its 42 baseline" this ledger has been quoting for days. 14 tests ported
(`ThreatPositionTests`, `SecondaryLaneTests`, `MissPenaltyScaleTests`), **all 14 pass**, suite
692 -> 706 tests, **zero regressions**.

**That 42-failure baseline is itself an open problem**: a suite with 42 known failures cannot be
trusted to catch a regression in this deck, which is why the ports were ALSO verified behaviourally
above rather than on test results alone. Worth its own session -- see the icebow precedent, where
one long-red test turned out to be STALE rather than broken and was masking the defensive path.


## 4l. 2026-08-25 — CROSS-DECK DIVERGENCE AUDIT (owner asked for both folders 100% current)

Compared every shared module by hash: **58 of 78 identical**, 20 differ, and only
`sim/drills_{icebow,hogeq}.py` are deck-exclusive. Line-count divergence alone does not separate a
MISSING BUG FIX from icebow-only diagnostics, so each known ledger fix was checked by signature.

### ⚠ FOUND LIVE IN HOGEQ: the `air_bases` bug — the Log's air exclusion is INERT

```python
# hogeq, before:
self.air_bases = frozenset(b for b in (db.names() if hasattr(db, "names") else [])
                           if db.is_flying(b))
```

`CardDB` HAS NO `names()`, so the generator iterated an empty list. **MEASURED: 0 cards instead of
21 flying.** The guard was written correctly and `is_flying` was fine; only the enumeration was
broken, so every call succeeded while the rule did nothing. **This is the owner's repeatedly-reported
"the Log still registers a hit on air troops" -- and `the_log` IS in the hogeq deck**, so that deck
has been scoring Log casts on flying units as hits the entire time. Fixed, with the same loud
empty-set diagnostic icebow carries.

### ALSO PORTED: falsy-zero `--workers 0`

hogeq still had `workers if workers else ...`, so an explicit `--workers 0` was silently replaced by
`sim.rollout_workers`, took the REMOTE path, and made "in-process, no workers" unreachable from the
CLI. Same family as `--drill-frac 0.0` (S8).

### DELIBERATELY *NOT* PORTED, with reasons

```
critic split + value_d      icebow has `ppo_value_head_split: false` -- TRIED AND REJECTED.
                            Porting a disabled experiment adds dead code and invites someone to
                            switch it on without re-reading why it was turned off.
ASYNC advisor               icebow has `llm_advisor_async: false` -- reverted 2026-08-25 on the
                            owner's slow-reaction report. Porting it would spread a known regression.
drill play-out              ✅ PORTED 2026-08-25 -- and my "cannot be ported" call above was WRONG.
                            I had searched for icebow's COMMENT text, which naturally differs
                            between decks, instead of the CODE sites. The structures are nearly
                            identical (`if v is not None:` + `done = True` vs the guarded form), and
                            all four sites ported cleanly. See 4m.
fixes 2+3                   x_bow specific; hogeq has no x_bow.
fix 1                       dropped in icebow; hogeq never had it.
```

### THE REAL LESSON HERE

`air_bases` was fixed in icebow days ago and the identical bug sat untouched in hogeq the whole
time, while the owner kept reporting the symptom. **A fix is not done when one deck is green.** The
audit that found it took minutes; the bug survived weeks. Run this comparison after any shared-module
fix.


## 4m. 2026-08-25 — PLAY-OUT PORTED TO HOGEQ, AND THE VERIFICATION FOUND A LIVE BUG IN ICEBOW

### ⚠ CORRECTION: "cannot be mechanically ported" was wrong

I reported play-out as a rewrite because 3 of 4 anchors were missing. **I had searched for icebow's
COMMENT text, which differs between decks by nature, rather than the code sites.** The structure is
nearly identical:

```
icebow:  if v is not None and self.last_verdict is None:  ... done = bool(done) or not self._play_out()
hogeq:   if v is not None:                                ... done = True
```

All four sites ported: `import os` + env globals, `_play_out()`, the verdict site, and the LENGTH
SEED. **The length seed is not optional** -- `_episode_prob` solves
`target = p*Ld / (p*Ld + (1-p)*Lm)`, so with play-out ON a 20.0 seed is wrong by ~25x (measured in
icebow: drills took 81% of STEPS against a configured 30%). Porting sites 1-3 without it would have
been worse than not porting.

VERIFIED behaviourally on hogeq: `play-out off -> episode ends at step 10` (its verdict);
`play-out ON -> verdict still at step 10, episode continues to step 501`. Config key
`sim.drill_play_out: true` added to hogeq.

### ⚠⚠ THE VERIFICATION FOUND A LIVE BUG IN **ICEBOW** — `CLASHRL_DRILL_PLAY_OUT=0` TURNED IT **ON**

```python
_PLAY_OUT_ENV = bool(os.environ.get("CLASHRL_DRILL_PLAY_OUT"))    # bool("0") is TRUE
```

**Any non-empty value -- including `"0"` and `"false"` -- evaluated True, so the override could only
ever ENABLE play-out, never disable it.** That flag exists specifically for command-line A/Bs, which
means **any A/B run as `CLASHRL_DRILL_PLAY_OUT=0` vs `=1` compared the feature against ITSELF** and
would have reported "no difference" for a change that is worth 50x the episode length.

Third member of the family, after `--drill-frac 0.0` and `--workers 0`: **a falsy value the code
could not express.** Now parsed properly (`""`/`0`/`false`/`no`/`off` -> False) in BOTH decks, with
proof: `icebow =0 -> False, =1 -> True`; `hogeq =0 -> False, =1 -> True`.

**Found only because the port was checked BEHAVIOURALLY rather than by "the patch applied cleanly".**
The port was correct; the flag it depended on was not.

icebow 639 OK. hogeq 706, 42 pre-existing failures, unchanged.


## 4n. 2026-08-25 — FIX 2+3 RETRY SHIPPED (unproven), ROYAL HOGS ABREAST, and ⚠ THE LOG IS THE WRONG WIDTH IN BOTH SIM AND LIVE

### FIX 2+3 RETRY — shipped on CORRECTNESS, not on a measured win

```
fix23 paired, n=30, control4 vs fix23b, both @2600 eps
  xbow_lock     5.37 -> 7.73   +2.37   1.1 sigma
  chip_linear   5.63 -> 8.57   +2.93   1.3 sigma
  xbow_defends  8.63 -> 7.97   -0.67   0.3 sigma
  xbow_no_lock  0.00 -> 0.00    0.00         (penalty removed; correctly never fires)
VERDICT: NO MEASUREMENT
```

The DIRECTION reversed -- the original was **-5.73 at 2.1 sigma (harmful)**, the retry **+2.37 at
1.1 sigma** -- an +8.1 swing in bow uptime confirming the -0.5 penalty was what suppressed bow play.
Nothing clears 2 sigma, so this is not a demonstrated benefit.

⚠ **THE EXPERIMENT WAS UNDER-POWERED BY CONSTRUCTION, AND THAT IS MY ERROR.** `xbow_overcommit` is
worth **0.07-0.08 per match**; gating it moves ~0.04 against a total reward magnitude of ~50, i.e.
**~0.08%**. No feasible sample size resolves that. A 1.5 h training arm was spent on a question the
instrument could never answer -- **compute the detectable effect size BEFORE running the arm**, not
after reading the result. "NO MEASUREMENT" here means the wrong instrument, not the absence of an
effect.

Shipped anyway because the GATE corrects a real defect (`led["cost"]` accrued independently of
`led["lock"]`, so a bow that never threatened still collected the credit) -- demonstrated
behaviourally, same basis as fixes 5/6/7.

### ROYAL HOGS SPAWN ABREAST (owner) — both decks

`cols = ceil(sqrt(n))` made the four hogs a 2x2. They enter in a HORIZONTAL LINE and fan into
separate lanes. Fixed DATA-DRIVEN via a `line_formation` flag rather than special-casing the card,
preserving the engine's "one rule, the card declares which" design. MEASURED: 4 distinct X, 1
distinct Y, span **3.96 tiles** against a 2x2's **~1.32**. Negative control: ordinary swarms still
grid.

⚠ **A PATCH-AUTHORING TRAP, recorded because it corrupted a file**: the anchor
`"    cols = int(math.ceil(math.sqrt(n)))"` (4 spaces) matches as a SUBSTRING of the real 8-space
line and replaces only part of it. Anchor on the full line INCLUDING its newlines.

### ⚠⚠ OPEN: THE LOG'S WIDTH IS WRONG IN BOTH SIM AND LIVE, AND THEY DISAGREE BY 1.9x

Surfaced when the owner corrected a claim of mine. **The real Log is 3.90 tiles wide.**

```
owner (real game)                      3.90 tiles
SIM   _LOG_ROLL_HALFW 2.2      ->      4.40 tiles    ~13% TOO WIDE
LIVE  log_half_width 0.064     ->      2.30 tiles    ~41% TOO NARROW
```

Wrong in OPPOSITE directions, so they cannot both be reasoned about with one mental model:
* **LIVE too narrow** -- the whiff verdict and the aim assist believe the Log covers half of what it
  does, so a cast that would really connect is scored a WHIFF and the assist demands precision the
  card does not need. This is the §4.2 family: "it knows it in sim but not live".
* **SIM too wide** -- over-credits the Log, teaching the policy it clips troops it would miss.

**PROPOSED (not yet applied):** set both to 3.90 -- sim `_LOG_ROLL_HALFW = 1.95`, live
`log_half_width = 1.95/18 = 0.1083`. NOT shipped in this batch because it moves a reward-relevant
quantity in the sim and belongs in its own change, and because the published width should be sourced
from the wiki first the way the spawn intervals were.

⚠ My original claim -- "four abreast exceed the Log's width" -- was WRONG twice: it quoted the LIVE
number in a SIM context, and that number is itself wrong. At 3.96 vs a real 3.90 the outer hogs sit
right AT the edge. The formation fix stands; that justification for it did not.


## 4o. 2026-08-25 — ⚠⚠ THE GATE'S GRADIENT IS INVERTED BY CLIPPING, AND TWO LEVERS FIX DIFFERENT HALVES

### The finding (supersedes §4a's "the bow is unaffordable, not unwanted")

```
gate P(play) by elixir (control4)          %steps with PLAY masked to -inf
  elixir:   0     1     2     3   ...  10        0: 97.9%   1: 82.5%   2: 61.4%   3+: 0.0%
  P(play): .473  .416  .353  .265  ...  .085
```

The gate's apparent enthusiasm lives ENTIRELY where it cannot act. At 0-2 elixir, 62-98% of steps
have zero affordable cards, so PLAY is masked and the output is inert. **Where every decision is
real (3+ elixir) it plays 9-27% of the time, falling monotonically as elixir rises.** The x_bow
costs 6 and can only be played there -> 0.75 bows/match, and raising affordability 4.6%
(2.7% -> 12.4%) moved usage 0.70 -> 0.75. **The card head PREFERS the bow at 1.48x fair share
(0.370 vs 0.250).** It is not unwanted and no longer unaffordable -- THE GATE WILL NOT ACT.

⚠ This also retires the "gate wants to play 57%" figure quoted earlier: that average is dominated
by masked steps where the output means nothing.

### The refusal is IRRATIONAL under its own reward

```
NEVER play                  -0.2127 /step        holding is 6.7x worse than playing
play only at elixir >= 6    -0.0316 /step
play whenever affordable    -0.0278 /step
```

And every loss term pushes the gate TOWARD playing (parameter-path probe, comparable units):
`VALUE +77.25 | POLICY GRAD (unclipped) +56.35 | ENTROPY +3.48`.

⚠ **The in-trainer probe (`CLASHRL_GATE_PROBE`) CANNOT SEE THE VALUE TERM** -- it takes
`autograd.grad(term, gate_logits)`, and the critic reaches the gate through shared-trunk PARAMETERS,
not through the gate logits. It returns `value +nan` on every sample. That is a good explanation for
why the previous investigation stalled: its instrument was blind to the largest candidate. Use
`scratchpad/gate_param_probe.py`, which measures `-<d(logit gap)/dtheta, d(term)/dtheta>` instead.

### STAGE A SWEEP — the two levers fix DIFFERENT HALVES, and neither works alone

```
arm  per_head  mult   clipPLAY  clipWAIT  sign-agree  mean clipped  verdict
A0   false     1.0      0.621     0.008      1/6        -0.00106    fail   (inversion reproduced)
A1   true      1.0      0.668     0.011      5/6        +0.00338    fail
A2   false     4.0      0.169     0.011      1/5        +0.00012    fail
A3   true      2.0      0.507     0.014      5/6        +0.00395    fail
A4   true      4.0      0.170     0.014      4/5        +0.00430    PASS
```

* **`ppo_clip_per_head` fixes the SIGN** (3-head coupling: a play's joint ratio is gate x card x
  cell, a wait's is the gate alone). A1 flips sign-agreement 1/6 -> 5/6 and the mean clipped
  pressure -0.00106 -> +0.00338 -- but leaves `clipPLAY` at 0.668, so the corrected gradient is
  censored on two thirds of plays.
* **`ppo_clip_play_mult` fixes the FREQUENCY** (minority-action volatility: d(log p)/d(logit) is ~1
  for the minority action and ~p for the majority, so the same logit move swings a play's log-ratio
  ~1/p harder -- MEASURED, gate log-ratio sd 0.518 on plays vs 0.027 on waits). A2 collapses
  `clipPLAY` 0.621 -> 0.169 but leaves the sign wrong, because the joint ratio still couples heads.
* **Only A4 gets both.** Dose 2.0 (A3) fails the clip-rate bar at 0.507, so 4.0 is the smallest that
  works, not the largest that passes.

**THIS RECONCILES THE OLD VERDICT.** HANDOFF recorded per-head as "no improvement, inside noise" and
that was not wrong, it was INCOMPLETE: A1 un-inverts the sign while still clipping 67% of plays, so
the corrected gradient barely reaches the gate.

### ⚠ THE LEVERS WERE MUTUALLY EXCLUSIVE UNTIL TODAY

`_surr` used the base `clip_eps` and the per-head branch OVERWRITES `pl`, so setting both applied
only per-head and `ppo_clip_play_mult` was a SILENT NO-OP. Fourth member of the family after
`--drill-frac 0.0`, `--workers 0` and `CLASHRL_DRILL_PLAY_OUT=0`. **The combination that passes
could not have been tested before this was fixed.** `_surr(r, eps)` now takes a per-sample bound;
the gate gets `eps_b`, card/cell keep `clip_eps` (they exist only on play steps, so they carry no
play/wait asymmetry to correct).

### STATUS: Stage B running — mechanism is NOT outcome

`ARM_clipfix.pt`, 2600 episodes, A4 config, matched against `ARM_control4.pt`. Un-inverting the
gradient is necessary, not sufficient, and this can still come back null. Pre-committed: >=2 sigma
on the paired probe or it is reported as NO MEASUREMENT.


## 4v. 2026-08-26 — ⚠⚠ RETRACTION: "THE LOG'S PLACEMENT IMPROVED" WAS MY OWN MEASUREMENT BUG

Owner: "log is wider than 1.95 tiles, I thought we established this in the past." They were right,
and chasing it found an error in MY probe, not in the KB.

**The KB is correct.** `_LOG_ROLL_HALFW = 1.95` is the corridor HALF-width -> **3.90 tiles wide**
(the owner's own number from §4n), and `roll_len = 9.6` tiles FORWARD. So the Log covers a
**3.9 x 9.6 tile corridor**, not a circle.

**`scratchpad/spell_probe.py` judged EVERY spell as a circle of radius `spell_radius`.** For the
Log that is a 1.95-tile circle — it threw away ~9.6 tiles of forward sweep and scored good casts
as wasted. **This is the SAME circle-vs-corridor bug the engine's own whiff snapshot had and
fixed** (§5: "A rolling spell's whiff snapshot was a CIRCLE"). I reintroduced it in the
instrument after it had been fixed in the engine.

### What changes when the probe mirrors `_resolve_roll` instead
```
                              init     26k     delta   sigma
the_log  OLD probe (circle)    81%     66%   -15.1pp    2.84   <- REPORTED AS A REAL IMPROVEMENT
the_log  FIXED (corridor)      60%     59%    -0.7pp    0.11   <- FLAT. No improvement at all.
tornado  (circle, correct)     51%     60%    +9.3pp    1.34
ALL      FIXED                 54%     57%    +2.7pp    0.62
```
**RETRACTED: "the Log's dump rate genuinely improved 81% -> 66% (2.84 sigma)" (§4r, §4t).** With
correct geometry it is 60% -> 59%, i.e. nothing. The apparent gain was the policy drifting its
casts in a way the CIRCLE test rewarded and the corridor test already counted.

**What still stands:** spells are wasted at a high rate (57% of casts land with nothing in their
real hit area), and the cell-head entropy measurement (tornado 5.790 / the_log 5.400 vs a 6.068
uniform maximum) is untouched by this — it never used spell geometry. The two-failure split
(placement + restraint) also stands: the restraint evidence is drill-based, not geometry-based.

**What is now FALSE:** any claim that spell placement improved over the run. It did not.

### TRAP (§8): an instrument can carry a bug the code already fixed
The engine knew the Log is a corridor. The probe did not. When writing a measurement tool, mirror
the ENGINE'S OWN hit test (`_resolve_roll` here) rather than re-deriving geometry from a spec
field whose meaning you assumed — `spell_radius` means RADIUS for a blast and HALF-WIDTH for a
roll, and nothing in the name says so.

---


## 4u. 2026-08-26 — THE 40k RUN WAS STOPPED AT 26,600. Reference policy = `policy_BEST_m18000_20260826.pt`.

Owner's call, on the §4t degradation. Stopped via PowerShell process lifecycle (Git-Bash `pkill`
cannot see Windows processes and fails SILENTLY — §2): **16 processes killed, recount verified 0.**

* **`data/policy_BEST_m18000_20260826.pt`** (copy of `policy_ppo_long_best.pt`) is the REFERENCE
  POLICY from here. It is at **matches=18000**, which is exactly where the rolling eval peaked
  (ladder avg-5 33% / fair 22%) — the trainer's own best-gate and our independent eval reading
  agree, which is a useful cross-check on both.
* `data/policy_ppo_long.pt` (matches=26600) is the LAST policy, ~13pp of ladder worse. Do not use
  it as a baseline by accident — the filename does not say "worse".
* 7 "new BEST" saves happened over the run; the last was the 33% one.

**NO new PPO until sim-parity implementation is 100% complete** (owner). The merged restart, from
this reference policy, is that experiment's ONE change.

---


## 4s. 2026-08-26 — THE ROCKET IS NOT A WIN CONDITION: 19% land on a tower, and overtime is reached but never PLAYED

Owner asked whether the 86%-own-half rocket reading meant (a) overtime is never reached or (b)
overtime is reached but the rocket-cycle plan is not run. `scratchpad/rocket_probe.py`, 30 matches:

```
(a) REACHES overtime      18/30 (60%)   median match length 180.1s   max 255.3s
    BUT total overtime PLAYED = 86s across all 30 matches (~4.8s per OT match)
(b) rocket rate  OVERTIME 2.09/min   REGULATION 0.54/min   (3.9x -- the doctrine IS weakly present)
    ON an enemy crown tower: 9 of 47 casts (19%)
    median distance from the nearest enemy tower EDGE: 8.7 tiles (rocket radius is 2.0)
    enemy towers still alive at match end: mean 2.60 of 3
```
**Both hypotheses are wrong as stated.** It DOES reach the 3-minute mark (60%) and it DOES rocket
nearly 4x more often per minute once there — but the match RESOLVES AT THE BUZZER instead of
playing overtime (median end 180.1s, one tick past regulation), so the rocket-cycle window barely
exists. And the rockets that are cast are not tower-directed: **8.7 tiles from the nearest enemy
tower edge, four times the blast radius.** Same shape as §4r: the cell head is not aiming.

The number that frames all of it: **2.60 of 3 enemy towers alive at the end.** This policy almost
never takes a tower, so overtime is entered from behind or level, not as a closing plan.

⚠ METHOD CAVEAT: these probes read `data/policy_ppo_long.pt`, which the LIVE trainer overwrites
every checkpoint. Two probes minutes apart read DIFFERENT policies — the own-half rocket share
read 86% (n=28) in one probe and 57% (n=47) in this one. Copy the checkpoint before probing if a
figure needs to be stable, and never compare two probes taken at different times as if they were
the same policy.

---

