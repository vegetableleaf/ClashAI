# Engine RL feasibility -- facts dossier (L67, 2026-09-12)

Question: win/loss-only RL on the local cr-native-sandbox engine, initialised from S1 student
`s1_icebow_v6lat_s0.pt`, "thousands of matches overnight". Read-only research; no process started.

Labels: (a) measured -- number + citation; (b) plausible but untested; (c) contradicted.

## Q1. What "the engine" is

- (a) `research/ext/cr-native-sandbox` is a headless harness around the ORIGINAL Android x86_64 `libg.so`
  of Clash Royale 15.535.29 (versionCode 150535029), not a reimplementation. README.md l.3-13: "based on the
  original Android x86_64 libg.so, headless standard 1v1 sandbox"; native 20 Hz battle stepping; all cards,
  evolutions, heroes and active abilities; replay create + in-process reset; JSON-line TCP API; Python client.
  README l.15: the repo "contains NO GUI, AI, model or learning code".
- (a) Runs inside an Android emulator (AVD `royale_worker_api31`, fixed at 4 vCPU / 4 GB RAM / 10 GB data,
  README l.162-164) as a no-Surface `app_process` service; libs pushed to `/data/local/tmp/cr-native-direct-<slot>/`
  (README l.238-246). Also ported to Linux on a cloud VM (HANDOFF §5cs.81/.84; "FIRST ENGINE SLOT RUNNING ON
  LINUX ... ready in 14.2 s" §5cs.84 header l.3519).
- (a) Driven by JSON-line TCP ops (docs/API.md §5): `reset` (in-process 4->4 BattleGameState replacement, no
  Android reboot, §5.5/§8), `step` (N ticks at 20 Hz), `observe` / `observe_compact_v1`, `act` (play: side,
  deck_index, x, y in 1000-unit cells on 18x32 grid; `dry_run` option), `ability` (entity_id), `joint_act` /
  `joint_transition` (at most one action per side per call, both sides same tick), `*_trace`, `probe_grid`.
- (a) Result codes (API.md §2): 0 accepted; 1014 ability charges exhausted; 1050 not enough elixir; other =
  native_rejected. Terminal episode sets a latch; `reset` clears it (API.md §8). Episode has terminated/
  truncated/crowns in each `step` result (§5.7).
- (a) Python gym-like wrapper exists: `NativeRoyaleEnv(port)` with `.reset(replay, warmup_steps)`, `.act`,
  `.step`, `.observe`, `.use_ability`, `.joint_transition` (README §5 l.331-383; native_core/env.py 767 lines).
- (a) Version-frozen, hash-gated: libg.so sha fixed (README §8); fails closed on any mismatch. Owner's own
  BlueStacks client was 15.535.29 at 2026-09-01 (HANDOFF l.844-847). (b) plausible but untested risk: once
  Supercell ships a balance/version update the engine stays frozen at 15.535.29 while the live game moves.
- ToS/legal note recorded: README §9 "runtime obtained legally by the user"; HANDOFF l.840 "ToS is theirs"
  (owner's call, recorded 2026-09-01 §5at).

## Q5. RL/PPO history -- ENGINE PPO WAS ALREADY RUN (the most decision-relevant fact)

- (a) FIRST PPO ON THE REAL ENGINE ran 2026-09-05 (HANDOFF §5cs.44, l.1738): owner order "start the engine
  training"; init `bc_bias_native_s0.pt` (the OLD CNN BC policy, not S1); PPO (GAE 0.994/0.95, clip 0.2,
  lr 2.5e-4, rollout 1,024 decisions, decision every 0.5 s = 10 ticks), UNSHAPED engine reward; two arms:
  control kl_coef 0 vs KL-to-frozen-init 0.3. Driver `scratchpad/gauntlet/L62/engine_ppo.py`.
- (a) engA (no gate prior): the PLAY GATE COLLAPSED in both arms -- KL arm 0.12 plays/match vs init 36.19,
  gate p max 0.2326 never crossing tau 0.25 (§5cs.46 l.1863-1875). Killed at m=422. Cause (b, lead's own
  reading): driver dropped the pro gate prior; "wait" is a local optimum under unshaped reward with a losing
  baseline (l.1900-1903).
- (a) engB (gate prior 2.0 in both arms): gate alive, but after 500 matches the verdict (§5cs.51 l.2189-2212):
  KL arm top-1 15.44 -> 16.33 -> 15.64 (flat within instrument band 0.4-3.9 pp); control 15.44 -> 7.47 -> 6.87
  with railed-logit fraction 0.027 -> 0.262 and raw_p99 9.8 -> 18.0 -> 31.25 (degenerating). Cum win record at
  kill: control 101W/501L, KL 130W/479L (l.2214-2216) -- i.e. the sampled policy won ~17-21% vs its opponent.
  "across engA and engB, four arms and ~1,500 engine matches, the unshaped engine reward has not produced a
  single measured improvement in pro agreement" (l.2209-2212, labelled (b) interpretation).
- (a) Owner played the KL checkpoint live: "not changed one bit" -- confirmed TRUE by measurement (l.2226-2228).
- NOT established per HANDOFF (l.2251-2254): "PPO cannot work here" is NOT what the data says; untested are a
  shaped reward or a 10x longer run; "box cost of the latter is ~4 h/1,000 matches per arm".
- (a) Owner ruling 2026-09-05 22:4x (HANDOFF l.509-511): engine IN as training/proxy env; "Sim, its reward,
  PPO/DQN trainers, policy net: dropped". Approved pipeline (l.484-487, §5cs.53 l.2310): S0 contract/corpus ->
  S1 imitation v3 -> S2 corpus scaling -> S3 engine search-teacher + SUPERVISED distillation ("no policy
  gradient", l.2310) -> S4 live. §5cs.53 B.2 cites Supercell's own DQN/Q-MC failing while DAgger-of-search
  beat BC 71.4+-8.8% (l.2316).
- IMPORTANT caveat for the owner's proposal: that engine PPO used the OLD model (rendered-board CNN, underfit:
  17.62 train / 15.44 val top-1, trunk cosine 0.991 = near board-blind, §5cs.52 l.2257-2275), 500-600 matches
  per arm, win/loss reward. The S1 student is a different model (token transformer, corpus v6). So "RL from S1
  on the engine" is (b) untested -- but the reward (terminal win/loss, unshaped) is the same one that failed.
- Checkpoint: (a) `icebow/data/pipeline/s1_icebow_v6lat_s0.pt` exists (also _s1, _s2).

## Q3. Throughput (measured vs extrapolated)

- (a) LOCAL BOX has exactly TWO engine slots (one AVD); ports 37031+slot (adb forward, ~20 ms/RPC) and
  38031+slot (direct, ~2 ms/RPC) are two doors to the SAME slot, not four slots (HANDOFF §5cs.66 C l.3863;
  §5cs.44 C l.1771).
- (a) Local box replay-drive (recording on): 12.52 s/match median, 288 matches/h/slot (§5cs.85 A l.3505);
  11.24 s/match (§5cs.78 E, cited l.3529). Earlier figures "engine 2.3-3.5 s per full match, ~1,850
  matches/h on the box's two slots" (§5cs.55 A l.2339) and "1.95 s greedy bench" (§5cs.42, cited l.1785) --
  those are cheaper work (no/less recording); instruments differ, do not mix (§5cs.85 B l.3510: a 1.43 s
  reading was "frames: 0").
- (a) GCP VM clashbot-s3 (Linux KVM, nested virt): 2.48 s/match on 1 slot = 1,452/h/slot; 4 slots in one
  AVD: 3.58-3.67 s/slot, 3,400 matches/h aggregate, 2.68x speed-up, 67% efficiency (§5cs.86 F l.3489-3496).
  VM start: first slot start 4 m 3 s (one-off push), later 14.2 s (§5cs.84 D l.3527). VM is POWERED OFF;
  "Restart is an owner gcloud command; disk persists" (GAUNTLET_LOG L66n l.1584). VM cost quoted: 100k driven
  matches = 69 VM-hours ~$27 (§5cs.85 C l.3512, (b) arithmetic).
- IMPORTANT: every number above is REPLAY DRIVING (both sides' recorded commands pushed open-loop). Policy-in-
  the-loop cost is much higher:
  - (a) Engine PPO on the box (old CNN, 1 policy side vs ghost): rollout 27-28 s per 1,024 decisions
    (policy 4.7 s of it) + update 12 s -> 10-17 s/match per arm, two arms sharing the box (§5cs.44 C
    l.1769-1770); 6.76 s/match uncontended first rollout (§5cs.47 D l.1972). engB: ~602-609 matches per arm in
    112 min (§5cs.51 B l.2214-2217) = ~325 matches/h per arm, ~650/h for two arms on 2 slots.
  - (a) S1 student on engine (`pipeline/engine_play.py`, CPU policy): 15.9 s wall per match (§5cs.63 B
    l.3926); 7 s per match for a CPU-only control run beside the trainer (§5cs.64 D l.3917).
  - (a) HANDOFF's own estimate for a 10x longer engine-PPO run: "~4 h/1,000 matches per arm" (l.2254).
  - (a) No snapshot op: "Each candidate is a full re-drive to the branch tick because the engine protocol has no
    snapshot op" (§5cs.87 C l.3458) -- irrelevant for plain RL rollouts, decisive for search.
- (b) extrapolation for an ~8 h night on THIS box: ~250-325 matches/h per slot with an S1 policy in the loop
  (from the engB 325/h/arm and the 11-16 s/match S1 harness readings) x 2 slots -> ~4,000-5,000 matches/night,
  minus PPO update time; BUT the box has ~3 GB free RAM while the owner plays live (task brief), and engB left
  "2.2-2.5 GB free after both trainers" with ~3 GB private per trainer (§5cs.44 C l.1771-1773) + qemu. Running it
  while the owner plays live is not viable on RAM; overnight with the box free it is. S1 model is 1,264,680
  params (§5cs.63/64 C l.3939, the v1 S1; v6lat file is 5,108,781 bytes, same size across s0/s1/s2 -- consistent
  with the same ~1.26 M param architecture, (b)). On the VM at 4 slots: (b) ~1,000-2,000/h if policy
  inference is not the bottleneck -- UNMEASURED with a policy in the loop.
- So "thousands of matches overnight": (b) plausible on count (low thousands on the box, more on the VM).
  engB already did ~1,200 matches (2 arms) in <2 h on this box.

## Q4 (part 1). Privileged-teacher gap / distillation / reranker findings

- (a) S3 engine search teacher (tower-damage rollouts in the real engine) FAILED its gate: teacher exact cell
  0.00% vs student 21.9-23.9%, mean distance 9.48 tiles vs student 3.34-3.48; the near-pro cell WAS in the
  candidate set (oracle 1.68 tiles) and was rejected by the objective (§5cs.90 A-B l.3359-3379). Five
  hypotheses (tie-break, unit-hp term, horizon, opponent model, oracle future) -> five nulls; "No tower-damage
  rollout objective tried here agrees with pros on troops/buildings; spells agree in every mode. ... Engine
  search teacher closed." (GAUNTLET_LOG L66n l.1579-1582). I.e. the ENGINE'S OWN SHORT-HORIZON OUTCOME
  SIGNAL ranked pro placements median 21/49.
- (a) Search over the student in the SIM (privileged rollouts, degraded student view) WORKS: +1.714 +- 0.420
  paired tower, t=4.08, 11/12 wins vs baseline 3/12; replicated on a disjoint slice +1.460 +- 0.336, t=4.35
  (§5cs.99 N, HANDOFF l.2570-2602). Most gain is gate+card, cell search +0.521 +- 0.341 t=1.53 n.s. (O l.2613).
- (a) DISTILLING THE SEARCH'S ACTIONS FAILS (L67i, §5cs.99 P l.2623-2637): teacher agreement up (card
  68.92 -> 86.51%), but sim tower -0.871/-1.757 -> -1.411/-2.143, plays/match ~50 -> 21-27, PRO card agreement
  63.36 -> 48.90%. "the teacher's restraint without its judgement ... privileged-teacher gap, now MEASURED".
- (a) VALUE RERANKER: offline regret 0.061-0.064 vs WAIT 0.0785; closed loop 1.5% play rate, 0/4 wins --
  COVARIATE SHIFT (§5cs.99 R l.2665-2673). Verdict: head-gated -1.257 +- 0.291 (t=-4.31); rank-only
  +0.361 +- 0.311 (t=1.16) null (S l.2677-2688). OWNER RULING 2026-09-10: reranker line CLOSED; "Do not reopen
  without a new idea that addresses the privileged-teacher gap itself -- e.g. a student that sees what the
  teacher sees" (l.2690).
- Implication for engine RL (b): on-policy RL trained on ENGINE state would itself be a policy that sees
  privileged (exact) state -- so at deploy time the live student (detector obs) has the same gap in a new form,
  unless training observations are degraded to the live view. On the plus side (b), on-policy RL avoids the
  covariate-shift failure mode of R because it trains on the states it visits.

## Q2. Closed loop? Who plays the other side?

- (a) The API is closed-loop capable: per-tick `observe` + `act` for EITHER side, and `joint_transition` applies
  one action per side on the same tick then steps (API.md §5.10-5.13). README §5 shows exactly this loop.
- (a) The sandbox itself has NO AI opponent: "contains NO GUI, AI, model or learning code" (README l.15).
- (a) `research/sandbox_tools/replay_drive.py` / `replay_batch.py` are OPEN-LOOP: they push a crawled 20 Hz
  command timeline for both sides and grade crowns/winner/state-hash (replay_drive.py docstring l.2-19).
- (a) Closed-loop IS implemented, twice:
  1. `scratchpad/gauntlet/L62/engine_env.py::EngineMatchEnv` (513 lines) -- used for engA/engB PPO. Opponent =
     "ghost": the human opponent of one mined battle replayed from their recorded 20 Hz commands, "NON-REACTIVE
     by design -- they play what they played, whether or not it still makes sense"; refused ghost plays counted
     (engine_env.py l.11-14). Reward (l.155-157): tower-HP delta term + crown delta term + terminal +1/-1/0,
     "UNSHAPED" -- note: already DENSER than pure win/loss.
  2. `pipeline/engine_play.py` (342 lines) -- plays the S1 model (`pipeline.model_v3.S1Model`) on the real
     engine vs the same ghost pool, decision every 10 ticks (0.5 s), obs via `obs_contract.from_engine` ->
     `to_tokens` (docstring l.1-8; HANDOFF §5cs.63 B l.3925). Evaluation harness, no training loop.
- (a) S1 icebow vs ghosts, 100 paired entries: 75-25 / 71-29 / 71-29 across 3 seeds (72.3 +- 2.3), no-plays
  control 0-100, rate-matched random 3-97 (§5cs.66 A-B l.3850-3861). HANDOFF itself: "still nothing against a
  reactive opponent" (l.3863, l.3887).
- (b) No self-play or scripted-bot-in-engine driver found: grep for self-play/scripted over pipeline/ and
  L62/L64/L66/L67 .py hits only the FirstLight clone (plus a false positive in live_view.py). The S0 plan item
  "scripted bot ported into the engine" (l.2321) has no implementation I could find. The API would allow
  S1-vs-S1 self-play via `joint_transition`; untested.
- (a) Why the opponent matters for win/loss RL: FirstLight_CR (external repo, libg-based engine) -- their
  "fixed-IL detour" won 80.10% vs IL with 296 of 306 wins against an opponent that played <= 3 cards; final
  specialist "more passive" while scoring higher (§5cs.95 B l.3223); §5cs.95 D l.3227: "win rate vs a frozen
  policy selects for passive-opponent exploitation". (b) Against a FINITE pool of non-reactive ghosts in a
  DETERMINISTIC engine, a win/loss-trained policy can learn entry-specific exploits that do not transfer.

## Q4 (part 2). Engine obs vs live obs

- (a) One contract, three sources: `from_engine` (obs_contract.py l.220), `from_live` (l.442), `degrade`
  (l.509); `BoardState.source` is engine / live / degraded (l.135). Token features carry `hp_known` and
  `tower_hp_known` flags (l.565-571).
- (a) What live lacks vs engine (degrade() docstring + constants, l.486-558): detector recall 0.855 / precision
  0.886 (measured); 25% of units side-unknown (measured 0.252); wrong team 15% troop/building, 40% spells;
  0.45-tile position noise (measured); NO unit hp / deploy state / age; elixir floored to integer; NO opponent
  elixir; NO king hp. Survey: "Unobservable live: unit HP/level/evo/deploying/age, king HP, opponent elixir,
  timer" (§5cs.95 A l.3210).
- (a) Cost of that shift on the student: exact cell 20.9 -> 16.8 (-4.2 pp), card 63.0 -> 50.6 (-12.4 pp),
  +1.0 tile, gate -8 pp (§5cs.95 A l.3214-3219). Live ablation: the damage is MISSING VALUES (unit HP,
  exact/opp elixir, king HP), not noise; supplying beats flagging 18.78/52.11 -> 20.15/63.25 (§5cs.98 l.3101).
- (a) Engine obs as used in training has NO spells: `_as_compact` drops `effects`, "0 spell tokens in 1,434,428
  training rows while 19.5% of live frames carry one" (l.2566); the v1 bridge's `effects` were projectiles
  listed twice; area effects (Tornado/Freeze zones) exist only in the UNVERIFIED v2 bridge (API.md §10.1;
  §5cs.45 B).
- (a) Live-only failure modes an engine policy never sees: tray reader "~31% of taps deploy nothing"
  (GAUNTLET_LOG L67v l.1670); gate collapse on impossible play histories (L67r l.1654).
- (b) Implication: engine RL optimises against exact state; at deploy the student gets the degraded view -- the
  privileged-teacher gap in a new form (owner ruling l.2690 names "a student that sees what the teacher sees"
  as the kind of new idea required). Training RL on degrade()d engine obs would address it -- untested.

## Q6. Heroes / abilities in the engine

- (a) Engine supports hero forms (`el`=2) and a generic ability command 0x5A; result 1014 = ability charges
  exhausted (API.md §2, §7; NATIVE_FULL_CARD_RUNTIME l.78-95). 8 champion ability cards, 16 hero forms.
- (a) The 16 hero forms in `native_core/data/live_card_catalog.json`: Knight, Goblins, Giant, Balloon, Valkyrie,
  Musketeer, Wizard, MiniPekka, DarkPrince, Bowler, IceGolemite, MegaMinion, EliteArcher, Berserker, Tombstone,
  BarbLog. IceWizard (card_id 26000023) has `hero_form: null`, `active_ability: null` (catalog l.729-754).
- (c) CONTRADICTED: the frozen 15.535.29 engine does NOT contain the Ice Wizard hero or Frosty Fella. RL on
  Frosty Fella timing cannot happen in this engine.
- (a) Owner unlocked hero Ice Wizard on 2026-09-12 (HANDOFF l.3097) -> (b) the live game carries content the
  engine lacks, so the live client has probably moved past 15.535.29 (version last verified 2026-09-01,
  l.844-847; not re-checked). The sandbox is hash-gated, "do not bypass the version check" (README §7
  l.427-430); bridge offsets were reverse-engineered for this exact binary (§5cs.45 B).
- (a) Other unsupported content: evo Elite Barbarians refused ("no native evolution form 26000043"): 120 of 619
  icebow and 52 of 296 hogeq replays (§5cs.59 A/B2 l.2480-2485).
- (a) The S1 action space has no ability action (N_SLOTS=8); replay_drive skips ability presses; no corpus holds
  one (l.2663).

## Q7. Other make-or-break facts

- (a) Determinism: same actions -> same state hash 211/211, 49/49 icebow, 27/27 hogeq (§5cs.59 l.2478-2485).
  Good for reproducibility; (b) bad for generalisation vs a fixed ghost pool (Q2).
- (a, derived) Speed vs real time: VM replay drive 2.48 s for a ~200 s match (S1 matches average 204 s,
  §5cs.66) = ~80x; box replay drive 12.52 s = ~16x; box with S1 policy in loop 15.9 s = ~13x. §5cs.55's
  "~60x" was (b).
- (a) Engine fidelity as a proxy: crowns match on re-driven real replays 76.9% icebow, 56.4% hogeq; all cards at
  level 11 (crawl has no levels) (§5cs.59 l.2480-2485). Engine vs old sim: 77.7% vs 26.1% (l.543).
- (a) Traps with a measured cost: DataTables pump segfaults ~1 in 10 boots (l.1261); tree-killing a trainer
  kills the in-guest worker services (l.1956-1959); worker pool redeploys artifacts by hash and restarts workers
  (l.1859); a client on 38031 while 37031 is busy hangs 120 s (l.3863); result_code 13 = not enough elixir in
  this build, docs say 1050 (l.3928); `_latest.pt` written only at save_every crossings -- 100 matches lost
  (l.2221-2223); guest services dead after idle need a ~73 s reboot (l.2335).
- (a) Per-match setup: `reset` is in-process (no Android reboot, API.md §8); ghost decks need deal-order
  inference (replay_drive.py l.14-19).
- (a) RAM: AVD configured 4 GB (README l.164); qemu RSS 413 MB observed (l.2219); each PPO trainer ~2 GB WS /
  ~3 GB private, 2.2-2.5 GB free with two trainers (l.1771-1773). (b) With ~3 GB free while the owner plays,
  engine RL cannot share the box with live play.
- (a) ToS/licence: runtime taken from the owner's own client, "ToS is theirs" (l.840); never fetch binaries from
  mirrors, never commit research/ext/ (l.854).
- (a) Standing rulings: 2026-09-05 "engine PPO ... CLOSED today, do not restart without a new reason"
  (l.476-478); "Sim, its reward, PPO/DQN trainers, policy net: dropped" (l.510-511); approved pipeline is
  supervised, "no policy gradient" at S3 (l.2310); L67ae hero plan: "RL only as a narrow, later step"
  (l.3097). The owner can overrule; the available "new reason" is that S1 is a different, stronger model (b).

## Bottom line (facts that decide feasibility)

1. Mechanically feasible: closed-loop engine play exists and engine PPO was already run (~1,200 matches in
   <2 h on the box's 2 slots). Low thousands of matches per night on the box are realistic when the box is free
   (b, from measured rates); the VM does more but is powered off and needs an owner gcloud start.
2. The same idea already failed once: 4 arms, ~1,500 engine matches, with a reward DENSER than win/loss; the
   leashed arm stayed flat (15.44 -> 15.64), the unleashed arm degenerated (-> 6.87, 26% logits railed)
   (a, §5cs.51).
3. Not identical to what failed (b): the S1 model (18-24% exact cell vs the old 15.4) was never RL'd.
4. Structural risks with measured support: non-reactive, finite ghost opponents in a deterministic engine
   (exploit selection seen in FirstLight); privileged engine obs vs degraded live obs (-4.2 pp cell / -12.4 pp
   card); no spells in the engine obs; engine frozen at 15.535.29 without hero Ice Wizard (c) or evo Elite
   Barbarians.
5. If run anyway, the minimum design implied by the ledger (b): keep gate prior + KL to S1; degrade()d obs;
   opponent diversity (S1 self-play via joint_transition, or jittered ghosts); grade against the no-plays and
   random controls AND pro agreement with play rate; one change per experiment; write `_latest` every update.

STATUS: complete
