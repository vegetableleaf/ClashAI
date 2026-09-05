
### §5cs.41 -- L62b (2026-09-05 17:0x-17:3x UTC): GHOST POOL BUILT (447 human-opponent timelines, 337 W / 110 L, 314 distinct opponent decks, 437 distinct humans) -- and the owner's Q2 numbers measured against it: **10,000 distinct decks is NOT reachable from replay mining** (whole 1,148-battle corpus holds 715; marginal rate 0.56 new decks/battle and falling -> ~20-30k crawled battles, extrapolated); **zero trophy-range coverage** (434/447 are Path of Legend, no trophy number exists; no opponent rating column anywhere; 81% of icebow ratings in one 500-pt band); cheapest 2x = the crawler's x/y backfill (473 battles convert today, +273 decks). Ghost reactivity measured: 59.4% of ghost plays within 3 s of an icebow play vs 51.5% under a circular-shift null -> ~1 in 12 is a time-locked reaction that replay destroys. Plus: sim_view debugger engine feed dispatched (owner ask), and a pool-path COLLISION between the two agents resolved.

Source: `scratchpad/gauntlet/L62/ghost_pool.md` (agent, STATUS complete; snapshot of the LIVE crawl at 17:03 UTC
copied to `L62/snap/`, all numbers from the snapshot). Code `L62/build_pool.py`, `ghost_pool.py` (`load_pool`,
`sample`, `filter_pool`, `ghost_deck_key`), `analyze_pool.py`, `ceiling.py`; outputs `analysis.json`, `ceiling.json`,
`refused.json`, `engine_verify.json`. Pool `icebow/data/ghost_pool/pool.jsonl` (447 rows, 6.5 MB, outside git; schema
ghost_pool.md §0 + `mirror`, `engine_verified`). (a) throughout unless marked.

**A. Corpus and conversion.** The crawl has grown past the 268 tags §5ay/L61 worked from: battles.csv **1,148**,
plays_ext.csv 101,351 rows / 1,137 tags. Converted (deck validated by the engine's own `validate_deck`): **447 / 1,148**;
refused 701 = **574 replays with NO x/y at all** (bimodal per tag: a replay has all positions or none; not correlated
with date or battle type -> a crawl-payload property) + 111 Elite Barbarians evolution (§5ay's blocker) + 15 no play
rows + 4 no consistent deal + 2 out-of-deck plays (7 tags had byte-identical duplicated play rows -- deduplicated).
Ceiling (`ceiling.py`, every acceptance test except the positional one): **473 more battles would convert if x/y
were backfilled** (-> 920/1,148 = 80.1%), +207 more with an Elite Barbs evo form in the engine build. 211 of the 447
carry L61's engine verification (99.2% plays accepted, crowns-match 164/211 = 77.7%); the other 236 are convertible on
paper and (b) UNTESTED on the engine.

**B. Opponent deck diversity vs the "10,000 decks" ambition.** 314 distinct ghost decks in 447 battles, **259 seen
exactly once**, most-repeated 9x; 437 distinct opponent humans; 170 card variants / 120 base cards (vocabulary
saturated, deck space not). Saturation curve (timestamp order): 50 -> 49, 100 -> 93, 200 -> 169, 300 -> 231, 447 -> 314;
**marginal 0.56 new decks/battle over the last 100** (0.94 over the first 50). Whole corpus, converted or not: 715
distinct decks, 598 once. (b, extrapolated) 10,000 distinct decks needs ~20,000-30,000 crawled battles at a rate that
is still falling. Reading: **(c) contradicted -- the 10,000-deck pool cannot come from ghosts**; the reachable number
from this corpus is 587 (314 + 273 from the x/y backfill). 10,000 is only reachable by synthesising decks from the
120-card vocabulary, and a synthetic deck has no human policy behind it -- it needs the learned general-deck opponent
(owner-approved, §5cs.38 pushback 2) or a scripted one. The two are different things and the choice is explicit.

**C. Rating / trophy coverage vs "10,000 trophies to top ladder".** **(c) contradicted as it stands.** battles.csv has
`rating`, `rank`, `wins_7d` for the ICEBOW player only -- **no opponent rating, trophy or card level anywhere** (30
columns + battles_raw.json checked). Two naming traps: `rating` is a Path-of-Legend rating (1,923-3,429 here, median
2,282, **363/447 in 2,000-2,499**), not trophies; `rank` is the player's rank on RoyaleAPI's leaderboard FOR THIS DECK
(150 players), not ladder. 434/447 battles are Path of Legend, which has no trophy number at all. There is no
low/mid-ladder data, and card levels are a constant fill (11). Reaching the bot's ~10,000-trophy band means crawling a
DIFFERENT population (trophy-road players of this deck), not more of this leaderboard -- the supply probe in §6 is now
mandatory before any "10k replays" plan.

**D. Command density and holes.** Ghost plays/match mean 45.1 (median 47, min 2, max 81; 20,145 total); gap between
ghost plays mean 5.39 s, median 4.10, p10 1.55, p90 11.0; 72% of ghost plays land after 120 s; **0/447 timelines
extend into overtime**. **Ability presses: 1,000/20,145 ghost commands (5.0%, in 336/447 matches) are hero/evo ability
presses the driver skips** -- kept with x/y null. Deal ambiguity: median 256 of 1,680 (hand, queue) assignments
consistent, never unique (matches L61's `deal_inference` on all 211 shared tags) -> never feed an opponent-hand
channel from this pool as ground truth.

**E. What a ghost is (measured part).** 59.4% of ghost plays within 3 s of an icebow play / 78.2% within 5 s, vs
51.5% / 70.0% under a circular-shift null (5 reps) -> **+7.9 / +8.2 points of demonstrably time-locked reaction**,
i.e. ~1 ghost play in 12 is a direct response the replay cannot reproduce -- a floor, since position/HP/elixir reads
have no tight time lock. (b) How fast the BOARD diverges once our policy plays is what the env agent's rejection-rate
run measures; not done yet. Reasoning (agent §7, endorsed): ghosts are sound as a curriculum first rung, a frozen
deterministic eval suite, and the source of real decks; NOT sound as the sole training opponent past ~30-60 s.

**F. Collision (process).** The env agent started at 17:02 before ghost_pool.md existed, wrote its OWN 202-record
builder (`L62/build_ghost_pool.py`: the 211 L61-driven tags minus 7 non-position-based deals minus 2 mirrors, schema
with `deck_index` in the engine's final permuted order) to the SAME `pool.jsonl`; the pool agent then overwrote it
with the 447-row file. Ruling sent to the env agent: its builder owns `pool_env_v0.jsonl`; `pool.jsonl` is the
447-row file. `filter_pool(engine_verified=True, mirror=False)` + position_based reproduces the 202 exactly (verified
by the pool agent). Trap for the record: two agents in one loop directory must be given DISJOINT output paths in the
prompt, not just disjoint .md files.

**G. Owner ask (17:1x UTC): move the sim_view debugger to the engine, preserving the radii work.** Answered yes with
scope: (a) `render_frame` reads the engine through 15 attributes; the L61 adapter already supplies units (real
`CardSpec`), towers (real `Tower`), elixir, t, so `_draw_radii` / the P1 annulus / the term readout (which only read
spec + towers) run on engine boards unchanged -> ONE renderer, two feeds, no rewrite, not the HTML `replay_view.py`
(no radii there). NOT exported by the engine and therefore blank-and-labelled, never faked: stun/slow/shield/invis/
dash timers, `ability_active_s`, souls, chain arcs, ability flashes, zones. Pushback given: on the engine the
debugger's job changes from catching OUR mechanics bugs to catching ADAPTER bugs (mirror, anchors, name map,
deploying flag), showing ghost rejections, and -- new -- CHECKING `radii_of` against ground truth (does a unit open
fire at the drawn ring?). Third agent dispatched (`L62/engine_view.md` / `engine_view.py`), recordings-only, no VM,
forbidden from editing sim_view.py; deliverables incl. pixel checks and a first-shot-range read for 3 defenders.

**What this does NOT establish.** Nothing about training outcomes (no policy has played a ghost yet); nothing about
the 236 un-driven battles; the 10,000-deck estimate is an extrapolation of a falling rate, not a measurement.
