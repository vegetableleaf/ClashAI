# cr-native-sandbox — what it is, what it needs, what it can do for ClashBot

Written 2026-09-01 (evening) on the owner's order: *"Take a look at https://github.com/IMAX9D/cr-native-sandbox, figure out what
it can do, and see if you can get it working. Ideally the end goal would be to use this tool to somehow convert the saved
royaleAPI replays into actual CR matches, and then obtain board snapshots (states) of the real game, all of which can be used to
train the model. And if you think there's an even better use for this tool, please let me know."*

Sources: the repo cloned at `research/ext/cr-native-sandbox` (commit `643e63b`, MIT, 5 commits 2026-08-24/25, 2 stars), its
README + `docs/API.md` read in full by me, a subagent's line-referenced deep-read of the JNI bridge, Java host, Python client and
deployment scripts (`scratchpad/gauntlet/ext/cr_sandbox_internals.md`, every claim cited to file:line), and a fresh read of our own
RoyaleAPI crawl (`icebow/data/royaleapi/crawl2/`). Labels as always: **measured** (I ran it / read it in the data), **author-reported**
(numbers from their docs; not reproduced here), **plausible-untested**, **contradicted**.

---

## 0. Verdict in six lines

1. It is the real thing: the **original Clash Royale game engine (`libg.so`, x86_64 build of client 15.535.29) running headless**
   inside a rooted Android emulator, driven tick by tick over a JSON-over-TCP API. Not a re-implementation. The engine's own card
   logic, pathing, elixir, evolutions and heroes run as the client runs them. (measured: code)
2. It does **not** render anything — the renderer is surgically disabled and there is no Surface. **No frames for the detector, ever**,
   from this tool. States yes, pixels no. (measured: code)
3. **I cannot get it working on this box today**, and not for engineering reasons: it needs (a) the game's own 5 split APKs of
   *exactly* 15.535.29 x86_64 (SHA-256-gated, fail-closed) — the repo does not ship them and I will not fetch game binaries from
   mirrors; they must come from your own installed copy; (b) ~15-20 GB of Android SDK + JDK + a 4-vCPU/4-GB emulator — installs
   you have not approved and an emulator that would fight the cuda run for cores until ~Sep 2 afternoon.
4. Your replay idea is **more feasible than I expected**, and I was wrong earlier about the data: our RoyaleAPI plays are at the
   engine's own **20 Hz tick** and in the engine's own **1000-units-per-cell coordinates** — the exact inputs the sandbox's `act`
   takes. **268 replays (23,490 plays, both sides, every non-ability play positioned) are complete command timelines** for decks the
   sandbox's catalog fully covers (measured). What is missing is the initial conditions: card levels, tower troops, and the deal
   order of the hand (all fixable or inferable — §4).
5. There is a **built-in fidelity check**: a re-simulated pro match must accept every command (no "card not in hand", no "not enough
   elixir") and must end with the crown count `battles.csv` recorded. Any drift shows up as a rejection. So we will *know* how faithful
   each reconstructed match is, per match. (measured: API semantics + our data columns)
6. **Better uses exist and I rank one above the replay dataset**: a **sim-parity oracle** — running the same command sequences in our
   Python sim and in the real engine and measuring where they diverge. That attacks the project's oldest unsolved problem (we train in a
   sim whose fidelity we have never been able to measure) and it needs nothing the replay pipeline does not already need. Details §6.

---

## 1. What it is (measured from the code)

* **Host:** an Android AVD (`system-images;android-31;default;x86_64`, the rootable AOSP image; 4 vCPU, 4096 MB, 10 GB disk),
  `-no-window -gpu swiftshader_indirect`. Inside it, `app_process` starts a hand-written Java host (`JniHost`) with **stub**
  `com.supercell.titan.GameApp/TitanApplication` classes whose JNI method descriptors match the real client's, so `libg.so`'s
  `JNI_OnLoad` registers its natives without the real app shell (no UI, no billing, no network, no integrity checks running).
  The real package IS installed on the AVD — only so the host can borrow its `AssetManager` (the asset problem Arron's
  `cr-engine-extraction` was stuck on: this repo solves it by running inside Android instead of standalone).
* **Init:** ~60 hardcoded function addresses (RVAs) into `libg.so` 15.535.29: `CreateGameMain`, `GameMain::init` (with five
  byte-verified patches that skip renderer setup and are restored afterwards), DataTables load, the replay loader, the battle
  tick (`0xCE2CC0`), `DoSpellCommand` (play a card), the ability command, the deployment validator, elixir/hand getters.
  Every entry point checks `JNI_OnLoad - base == 0x1458BC0` and fails closed on any other build.
* **Battle creation:** `reset(replay_json)` — a Supercell-format replay object (`rndSeed`, `battle{deck0, deck1, avatar0,
  avatar1, gamemode 72000007, arena, location}`, **`cmd: []`**) goes through the client's own replay loader; the game state is
  replaced in-process (~11.5 ms author-reported; no DataTables reload).
* **Stepping:** `step(n)` runs the engine's update with a fixed 0.05 s per tick, no sleeps, up to 1,000,000 ticks per call —
  the engine runs as fast as the CPU allows (author-reported ~10,200 ticks/s in-guest ≈ 510× real time, on their box).
* **Acting:** `act(side, deck_index, x, y)` builds and executes the client's own `DoSpellCommand`; libg's verdict is authoritative
  (`result_code 0` accepted; card-not-in-hand and not-enough-elixir are rejections, no state change). `ability(side, entity_id)`
  for heroes/active abilities. `joint_transition(actions, steps)` applies one action per side (side 0 then side 1, fixed order)
  and steps — both sides on one tick, one round trip.
* **Observing:** `observe()` reads process memory (`/proc/self/mem`) and returns every entity (side, x, y in 0..18000 × 0..32000,
  card_id, level, hp/max_hp, behaviour state, target, path nodes, ability state), effects/projectiles, both players' elixir
  (exact, /10000), hand slots, cycle order, next card, the six towers' HP, tick, RNG state and a canonical `state_hash`.
* **Coverage claimed:** 122/122 standard cards, 41 evolutions, 16 heroes, ×1/×2/×3 elixir, 3+2 min, HP tiebreak. **Not claimed:**
  tower troops (Cannoneer/Duchess/Chef…), pairwise card interactions, non-1v1 modes.
* **Determinism:** certified by the author only for the no-action opening (10 cold processes → identical hash after 100 ticks).
  *Same actions ⇒ same hash* is plausible (CR replays are deterministic re-simulations by design) but **untested in the repo**.

## 2. What it is not

* **No pixels.** Renderer NOP'd at init, no Surface, no screencap path; the emulator window would show the Android launcher.
  The detector cannot be trained from this. (contradicts the "frames for the detector" hope, if anyone had it)
* **No AI, no learning code, no opponent** — you bring both sides' actions.
* **Frozen to one client build.** Every CR update (roughly monthly) changes `libg.so` and invalidates all ~60 addresses. The author
  (one person, one-week-old repo) would have to re-derive them each time. Anything we build is pinned to 15.535.29 and to replays
  from that version. For a one-off dataset or a parity oracle that is fine; for a permanent training environment it is a
  maintenance dependency we do not control.
* **Not sanctioned.** It runs the client's engine outside the client, rooted, with binary patches. It never contacts Supercell's
  servers, but it is squarely the kind of reverse-engineering Supercell's Terms of Service prohibit. That is your decision to make,
  not mine; I am stating it so it is made knowingly.

## 3. What it needs, and what is blocked on you

| need | status on this box (measured) | who unblocks |
|---|---|---|
| **The 5 split APKs of CR 15.535.29 x86_64** — `base.apk`, `split_config.en.apk`, `split_config.hdpi.apk`, `split_config.x86_64.apk`, `split_install_time_asset_pack.apk` (~1.01 GB); `freeze_runtime.ps1` hard-gates the size **and SHA-256 of all five**, then of the 14 `.so` it extracts, then `libg.so` again | absent; repo gives no source ("legally obtained by the user themselves") | **you** — from your own install. BlueStacks 5 and Google Play Games are both x86_64 Android, so an installed CR there carries exactly the x86_64 split. Route: enable ADB in BlueStacks settings → `adb connect 127.0.0.1:5555` → `adb shell dumpsys package com.supercell.clashroyale \| findstr versionName` → if it says **15.535.29**, `adb shell pm path com.supercell.clashroyale` and `adb pull` each listed path. If it says anything else, this tool cannot run against that copy (fail-closed), full stop. The en/hdpi splits must also match byte-for-byte; a device that received a different density/language split would trip the gate — a local relaxation of the gate to libg+DataTables only is possible but is a deviation from the tool's design, so I would ask first. **Do it soon if at all:** Play auto-updates the installed copy at the next client release and the window closes. |
| JDK 17, Android cmdline-tools at `C:\Android\Sdk\cmdline-tools\latest`, then `bootstrap.ps1` (platform-tools, emulator 37.1.11, platform 35, build-tools 35, NDK r27d, API-31 x86_64 image, AVD `royale_worker_api31`) | none installed; 471 GB free; `doctor.ps1` wants > 30 GB under `%LOCALAPPDATA%\cr-native-sandbox\data` | **you** — ~15-20 GB of installs outside the repo. Reversible, but not mine to do unasked. |
| VT-x + WHPX/Hyper-V | hypervisor present (Win 11 Home is fine — nothing edition-specific in the repo) | — |
| CPU/RAM for the emulator: 4 vCPU + 4 GB per AVD (author's ceiling: 4 AVDs × 4 workers = 16 battles = 16 vCPU / 16 GB) | 16 cores, **33.7 GB total RAM, 3.2 GB available right now** (cuda run ~8 GB + your desktop ~11 GB) | timing — one AVD fits only when the real run is not using 12 workers; two or more do not fit beside the desktop at all |
| No port/adb/hypervisor fights with BlueStacks / Google Play Games | both installed (yours); the sandbox hardcodes `emulator-5554` and ports 37031+/38031+, uses its own adb server, needs the hypervisor | run them closed while the sandbox emulator is up; the repo never mentions either |

## 4. Your idea: RoyaleAPI replays → real matches → real states. Feasibility, measured against our data

### 4.1 What the crawl actually holds (measured tonight; corrects my own earlier "1-second, tile-rounded" assumption — contradicted)
`icebow/data/royaleapi/crawl2/plays_ext.csv`: 45,335 plays, 519 battles, 24 pro players, 2026-08-23 → 08-31, pathOfLegend.
* `tick` is the engine tick at **20 Hz** (`seconds = tick/20`; max 5979 = 298.95 s = 3 min + 2 min OT). Same clock as the sandbox.
* `x_units`/`y_units` are **native units, 1000 per cell, cell-centred** (499/500, 1500, …, 17500 × 500, …, 31500; `x_units /
  tile_x = 1000` exactly). Same frame as the sandbox (`x ∈ [0,18000)`, `y ∈ [0,32000)`).
* Both sides are present (blue 12,229 / red 11,261 in the usable set). Abilities (1,092 rows, card `_invalid`) carry no position —
  correct, since the sandbox's ability command targets an entity, not a point.
* Positions exist for **270 of 519 battles** (the marker element is absent from the other payload variant — §5af). In **268** of
  them every non-ability play is positioned, i.e. the command timeline is complete. Deck slugs: all 174 map to the sandbox's
  15.535.29 catalog (alias table needed: `the-log→Log`, `barbarian-barrel→BarbLog`, `sparky→ZapMachine`, `spirit-empress→MergeMaiden`…).
  **Usable: 268 replays, 23,490 plays, 565 abilities.** Written to `scratchpad/gauntlet/ext/usable_replays.json`.
* One snag: **57 of the 268 contain `elite-barbarians-ev1`**, an evolution the sandbox's catalog does not list (41 evolutions; Elite
  Barbarians has none). Either the live client on Aug 23 was already newer than 15.535.29 (then your installed copy is probably
  newer too, see §3) or the catalog generator skipped it. Unresolvable without the runtime; **211 replays** avoid it.

### 4.2 The two ways to replay a match
* **(A) Native playback via `cmd`.** The replay object the sandbox loads is Supercell's own replay format, and libg knows the `cmd`
  key and tracks `applied_replay_tick` — the client's replay viewer is exactly this: seed + command list, re-simulated. If we write
  our plays into `cmd` in the engine's command schema, **the engine applies them itself at the right ticks** and the result is the
  original match. *Plausible-untested*: nothing in the repo ever fills `cmd`, the per-command keys are undocumented, and I cannot
  read them out of `libg.so` without the runtime. First experiment once it runs: one command in `cmd`, step past its tick, look
  for the entity.
* **(B) Drive it ourselves via `joint_transition`.** Feed each play at its tick from the CSV (side, deck slot, x, y), abilities via
  the side's live ability entity. This works with the API as documented today. It needs the initial conditions to match:
  1. **Hand deal order.** The engine deals from `rndSeed`. We do not have the seed, but the observation exposes `deck_to_hand`,
     `hand_deck_indices`, `cycle_deck_indices` after reset, and the play sequence itself pins the original deal (438 of 536
     usable player-sides played all 8 cards; the order cards must have been in hand is a small constraint problem). If the shuffle
     depends only on the seed, one reset reveals the permutation and reordering `deck.sp` produces any target deal —
     *plausible-untested*, ~10 minutes to test.
  2. **Card levels.** The example bootstrap uses level 11 (`l:10`, King 4824 HP — the tournament level). Path of Legend levels per
     battle are on RoyaleAPI's battle page and in the official API's battlelog; our crawler did not keep them. A wrong level changes
     HP and damage → divergence. Extend the crawler (cheap) or assume tournament standard (a guess; the fidelity check will tell).
  3. **Tower troops.** Not in our crawl and *not claimed supported by the sandbox*. Princess Tower vs Cannoneer/Duchess/Chef changes
     tower behaviour. Matches where the pro used a non-default tower troop will diverge; we can identify them from the page and drop
     them, or measure how many survive the fidelity check anyway.
  4. **Off-by-one on the tick** (apply before or after the update of tick *t*) — settled by the fidelity check in one afternoon.

### 4.3 The fidelity check (this is what makes the idea honest)
Every command in a real replay was legal when it was issued. If our reconstruction has drifted — wrong level, wrong hand, wrong
tower — sooner or later a command is rejected (`card_not_in_hand`, `1050` not enough elixir), and the final crown count will not
match the one `battles.csv` recorded (`team_crowns`, `opponent_crowns`). So each reconstructed match gets a grade: **accepted
commands / total, and final crowns match yes/no**. States are taken from matches that pass, or up to the first rejection. Nothing
is assumed.

### 4.4 What the states buy (and what they do not)
268 matches ≈ 1.6 M ticks of ground-truth states with pro actions. Sized honestly: **23k labelled decisions from one week of one
deck's meta, on one client version.** That is thin for behaviour cloning of a whole policy — your own ruling (§5af: "NOT BC
pretraining") was made when the states were unreconstructable; the premise changes, the sample size does not. What it is *rich*
for: the placement prior **P(tile | card, phase, board)** you asked for (§6 HANDOFF) with the board actually observed instead of
guessed; real time-to-next-play targets for the hazard head; a corpus of real defensive situations for the regret oracle; and the
parity oracle below. It is also the first data on which our observation adapter (engine state → our 96×64×12 board) can be built
and checked against the detector's reconstruction of the same kind of situation.

## 5. What "getting it working" costs, in order, with the gates

| step | cost | gate |
|---|---|---|
| 0. You pull the 5 APKs from your own install and confirm `versionName 15.535.29` | 10 min of your time | version match, else stop |
| 1. Installs (JDK 17, cmdline-tools, `bootstrap.ps1`) | ~20 min wall, ~15-20 GB, low CPU (downloads) — can run beside the cuda run | your OK |
| 2. `prepare_runtime` + `freeze_runtime` (hash gates) + `doctor` | 5 min | all five APK hashes + libg hash match |
| 3. Emulator boot + `smoke.ps1` (must reproduce hash `96598dc9028e1802`) | 15 min; **4 vCPU + 4 GB — after the cuda run ends (~Sep 2 afternoon)** or with your explicit OK to slow it | smoke PASS |
| 4. First-hour experiments: `cmd` playback yes/no; deal-order trick; actions-determinism (same actions twice → same hash); per-tick observe cost | 1-2 h | decides route A vs B and the throughput picture |
| 5. Replay driver: slug→card-id map, level/tower-troop crawler extension, driver, fidelity grader, state dump | 1-2 days | fraction of the 268 (or 211) that pass the fidelity check |
| 6. Observation adapter engine-state → our board tensor | 1 day | round-trips a known situation |

## 6. Better uses, ranked (my recommendation)

1. **Sim-parity oracle (highest value, cheapest once the tool runs).** Play the *same* command sequence in our Python sim and in the
   real engine; compare tower HP over time, unit positions/HP, elixir, and outcome. For the first time we would have a *number* for
   how wrong the sim is and *where* (which cards, which interactions). The parity chain, the geometry verdicts and the doctrine
   spot constants have all been argued from videos and wiki numbers; this measures them. Needs only steps 0-4 plus a command
   translator our sim already half has (`tools/sim_parity/`). Uses the pro replays as the test set — so it and your idea share
   every piece of work up to the state dump.
2. **Real-engine evaluation of the trained policy.** Run the cuda run's checkpoints inside the real engine against fixed scripted
   opponents (the sandbox lets us script both sides) and measure the sim→engine gap directly, before the live game does. Needs
   the observation adapter (step 6). Cheap per checkpoint (author-reported ~0.6 s of engine time per 5-min match before observation
   overhead — unmeasured here).
3. **Your replay dataset** (§4) — for the placement prior, hazard targets and the regret corpus; not BC unless you revisit the
   ruling with the 23k-decision sample size in view.
4. **RL directly in the real engine.** The strategic option: it would delete the sim-parity problem class entirely and give a
   122-card opponent pool that plays correctly. Back-of-envelope from the author's numbers: ~10k ticks/s per worker in-guest, a
   decision every 10 ticks, ~600 decisions per match → roughly 1-2 s per match per worker before RPC + inference overhead, 4 workers
   per AVD → order of several thousand matches/h per AVD, i.e. **comparable to or above the cuda sim run's ~3,700/h — but every
   number in that sentence is untested on this box**, the RAM ceiling is one AVD beside your desktop, and the training loop (drills,
   doctrine, threat vectors, continuation log) is welded to the Python sim — weeks of porting, not days. The one measurement that
   decides whether to even discuss it: **matches/h with a random policy, 1 AVD × 4 workers, observe every 10 ticks** (step 4 gives it
   for ~free). If it is below the sim's rate, the option is dead; if it is 3× above, it is the most important thing this project
   could do.
5. **Detector frames — no.** Contradicted by the code (§2).

## 7. Open technical questions, settled in the first hour with the runtime
`cmd` command schema (route A); whether Elite Barbarians' evolution exists in 15.535.29's tables; whether the deal permutation is
seed-only; actions-determinism hash; per-tick `observe_compact` round-trip cost on this box; whether the five APK hashes from a
BlueStacks/GPG pull match the manifest (density/language splits).
