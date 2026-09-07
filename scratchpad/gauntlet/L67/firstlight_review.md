# FirstLight_CR review (L67b, 2026-09-07) -- what the repo actually shows, and what transfers

Source: https://github.com/Jaasssoooonnnnn/FirstLight_CR, commit 28d66cc (2026-09-06, "first commit"), shallow-cloned to
`scratchpad/gauntlet/L67/firstlight/` (480 MB, 300 files; NOT committed). Docs read in full (README, architecture,
training, training_history, policy_service, checkpoints/README = 879 lines); code grepped (model.py, imitation.py,
tensors.py, train_imitation_cache.py, cr_native_env.py, royaleapi_replay.py); one HF dataset shard downloaded and counted.
Every number below is from the repo/dataset unless marked "ours".

## 1. What it is (a)

- **Offline** Clash Royale agent stack: a modified Null's Royale 15.535.13 client (private-server APK, user-supplied) with a
  C++ probe hooked into the ARM64 engine, exposing Python `reset`/`step`, headless resident multi-match (up to 8 slots per
  engine process, 1-6 engines per emulator guest), structured observations under a "FAIR visibility contract".
  Docstring of `cr_native_env.py`: "without screenshot interpretation or ADB touch injection". **There is no live path.**
- **Data:** 252,238 RoyaleAPI replays / 17,836,160 actions (HF `VanguardX101/IL_Replay`, 1.89 GB parquet). Same source
  as our crawl (RoyaleAPI 20 Hz action timelines with `card_key`, side, coordinates). Anonymised: trophies, dates, player
  IDs stripped. Shard 0 (5,000 replays): 89.0% `pathOfLegend`/Ranked, card levels 16 = 89.8% of deck slots, level 11 =
  9.4% (challenges/friendlies). Skill tier is NOT recoverable from the data.
- **Model V4:** 12,684,339 params (ours S1Model: 1,264,680 -- 10x). Universal card encoder over 122 cards (one model for
  every deck), entity-relation transformer, spatial scatter encoder, LSTMCell core (896-wide input), heads: gate (2),
  candidate pointer (which card/ability), FiLM-conditioned location map on an **18x32 = 576-cell grid** (one cell per
  tile; ours 36x64 = 2,304 half-tile), a `delay_offset_bin` head (deploy timing), value. Decision every 5 native ticks
  (0.25 s), first decision at tick 90.
- **IL recipe:** stateful sequence training, `--time-steps 32`, lr 3e-5, wd 1e-2, bf16, 8 GPUs (`--expected-world-size 8`),
  gate ACT class weight, delay neighbour-smoothed NLL, Huber value loss on discounted returns. The IL loss has NO accuracy
  metric anywhere -- they train on loss and evaluate by playing.
- **PPO:** 1,528 concurrent matches, 40-game-second rollout segments, 8 GPUs, Slurm multinode. Rewards: terminal outcome,
  tower-health shaping, elixir-overflow penalties, (specialist 1 only) Hog deploy / first-Hog timing shaping, plus a
  demonstration-BC term (`ppo_expert_bc.py`). Opponent pools: self-play + frozen IL / Active IL / General mixtures.

## 2. The owner's claim: "a model that has not plateaued" -- (b) NOT SUPPORTED BY ANYTHING IN THE REPO

- There is **no learning curve** of any kind in the repo: no loss curve, no accuracy-vs-data, no win-rate-vs-steps. The
  only numbers are a 4-row table of argmax model-vs-model win rates (382 games/opponent general, 760 specialist):
  General vs IL 73.30%; specialist 1 vs IL/ActiveIL/General 84.74/84.08/79.74%; specialist 2 89.87/86.97/88.03%;
  specialist 2 on mixed decks 66.75/60.73/59.16%. The author's own caveat: rows "use different task distributions and
  should not be treated as one continuous win-rate curve", and original IL got a forced first action at 15 s in all of
  them.
- Their IL-only model is described as "modest overall strength"; every gain after it is PPO against frozen opponents,
  measured by win rate against those same frozen opponents. **That is the instrument our guardrails reject** -- and they
  hit the exact failure we documented in L62: their "fixed-IL detour" reached 80.10% vs IL, of which **296 of 306 wins**
  were matches where IL played <= 3 cards (our catatonic-gate / passive-opponent exploit, §5cs.49-51). They caught it by
  reading replays, same as we did.
- Specialist 2 (the "final" model) is described as **more passive** than specialist 1 while scoring higher -- again the
  pattern our four PPO arms showed (win-rate up, behaviour worse).
- "Hall of Fame on an account" is author-reported, has no code path in the repo (no capture, no ADB), and the README
  separates it from the measured evaluations. It is (b) at best.
- In our metric (pro-cell agreement) they have measured nothing, so "not plateaued" vs our +1.50 pp/doubling is
  **untested**, and the shape of their pipeline (IL "modest" -> PPO vs frozen pools) is the same shape that produced no
  agreement gain here. What they have is a strong offline result bought with ~150x our replays and ~400x our engine
  throughput, not evidence that the plateau we measured is absent.

## 3. Where their result actually comes from (a), and why we cannot copy it as-is

| lever | FirstLight | ours | ratio |
|---|---|---|---|
| replays used for IL | 252,238 (all decks, universal model) | 1,638 icebow-side (v5) | ~150x |
| engine throughput | 1,528 concurrent matches (Slurm, 8 GPU) | 4 slots on one n2-standard-8 (now off) | ~400x |
| model | 12.7 M, recurrent | 1.26 M, per-frame | 10x |
| observation | engine-native, exact | engine-native for training; live = detector (S4 gap, -4.2 pp measured L67a) | -- |
| live path | none | the whole point of the project | -- |

The single mechanism that turns 252k replays into usable data is the **universal card encoder**: every replay trains
the same weights. Our student has 8 deck-slot heads, so only replays where one side plays the exact icebow deck count.

## 4. What transfers, ranked by cost-to-test

**A. Their dataset as an icebow corpus extension -- cheap, decisive, fits our instrument.** Shard 0: 41 exact-icebow
sides / 10,000 sides (0.41%), 176 x-bow+tesla sides, 212 x-bow sides. Extrapolated to 50.4 shards: **~2,070 exact
icebow sides** (b, one shard), ~8,900 x-bow+tesla. v5 has 1,638 -> v6 would be ~3,700 = one more doubling; the S2 slope
predicts **+1.5 pp** exact cell (18.2 -> 19.8 -> 20.9 -> ~22.4). Caveats: (i) skill tier unknown (trophies stripped;
level-16 Ranked = max-level accounts, probably top ladder but not "pro" -- a lower-skill corpus could LOWER agreement
with the pro VAL, which is exactly why this must be run as an A/B on the same v3 VAL, not assumed); (ii) overlap with
our own crawl is unknown (tags anonymised; dedupe by deck + event-sequence hash); (iii) format conversion needed
(payload_json events -> our battles.csv/plays.csv). Cost: ~0.9 GB download (replays parts only), a converter, 3 seeds
of `train_s1` (~40 min each on the box). This is the S2 "mining closed" verdict re-opened by a source S2 did not have.

**B. Universal card representation -- the real lesson, a new model family.** Replace the 8-slot card head with a card
embedding shared across cards so that all ~8,900 x-bow+tesla sides (or all 500k sides) train one model. Expected
effect: the S2 slope says +1.5 pp per doubling; ~5 doublings of x-bow-family data (b: extrapolation far outside the
measured range, and cross-deck transfer is untested). Cost: model + dataset rewrite (days), then a 3-seed A/B. Do A
first: if A shows the slope holds on foreign-crawled data, B is worth building; if A is flat, B's premise is gone.

**C. Their engine (`native_runner/`, Apache-2.0).** Python `reset`/`step`, headless resident slots, snapshotless but
fast. Would replace our re-drive-per-candidate sandbox for state generation and any future PPO. Requires: a Null's
Royale 15.535.13 APK supplied by us, rooted MuMu/AVD, JDK 17 + NDK build. Owner question: this is a private-server
client, distinct from the sandbox we already run; whether that is acceptable is theirs to rule on. Not on the S4 path.

**D. Small things worth copying:** delay/deploy-timing head (they model WHEN within the decision window, we don't);
gate ACT class weight in the IL loss; LSTM over 32-step sequences (our student is per-frame with past[3,4] only);
one-tile 18x32 grid (their placement target is coarser than ours -- consistent with §5cs.48's finding that phase, not
resolution, matters).

**E. Nothing for S4.** They never faced the detector/live-observation problem; the -4.2 pp / -12.4 pp card degradation
measured in L67a has no counterpart in their work.

## 5. Recommendation

Do A next (one change: corpus += HF exact-icebow sides, graded on the unchanged v3 VAL, 3 seeds). It is the cheapest
test of the owner's hypothesis ("their gain is available to us") on our own calibrated instrument, and it either
re-opens the S2 data axis or closes it with a number. S4 (degradation-aware retrain) resumes right after; it is
independent of A and a positive A makes the S4 checkpoint better, not different.

STATUS: complete
