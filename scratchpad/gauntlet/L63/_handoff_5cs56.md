### §5cs.56 -- L63d (2026-09-06 02:0x-03:0x UTC): **S0 STEP 2 DONE -- the shared observation contract exists as a new deck-agnostic package `pipeline/` (obs_contract.py, vocab.py, decks/{icebow,hogeq}.yaml, 19 tests OK), and the audits behind it found that NO live recording on disk carries ground truth, so engine-vs-live fidelity cannot be measured from existing data -- it has to be built (own-click test now, tag+timestamp logging before S4).** Two stale ClashBot sessions were told to stop (owner ruling 5); clashbot-c9 confirmed idle, ClashAI-3 and clashbot-e3 silent.

**A. Audits (a), `scratchpad/gauntlet/L63/obs_audit_engine.md` (198 lines) and `obs_audit_live.md` (117 lines).**
- Engine (`native_core/env.py:187-255`): tick 20 Hz; entity `[side,x,y,name,hp,max_hp,kind]`, 1000 units/tile,
  x in [0,18000), y in [0,32000), side 0 = low y (king at 9000,3000); both players' hand/cycle/next/exact elixir
  (1e-4) visible; crown towers appear twice (card_id -1 entities + `episode.crown_towers`); no overtime flag.
  The v2 BC dataset (`L61/build_bc_v2.py`) pushes engine frames through the OLD SIM's `_update_vectors`, so
  "v2 obs" == sim obs: 96x64x12 raster (no HP channel) + 52 hand-made threat scalars + hand/next/elixir.
- Live (`replay_mine.py:488-573`, `play.py:504-566`): YOLO11s board-24-5 @960, 230 classes (165 troop / 19
  building / 46 spell / 0 UI); a detection = class, frame-fraction box, conf, team mine/enemy/unknown,
  shadow-corrected y for flyers; frame->board is `BoardWarp` (`actions.py:55-155`, tower-anchored piecewise
  linear, not a homography). Reads: elixir = bar HSV (integer), hand/next = template match, tower HP = digit CNN,
  time = wall-clock `ElixirClock` (no timer read). `play.act_period 0.6` (config value). **Deployed
  `policy_rl.pt` has no `algo` key -> play.py uses the legacy `Q(wait) >= Q(play)` gate; neither
  `sim.ppo_gate_threshold` nor `ppo_gate_rule: sample` applies live** -- the L62k ruling never reached the
  live path for that checkpoint (a; new).
- **Recordings: 3 icebow + 1 hogeq `record.py` sessions (video + clicks + labeler npz, ~750 MB), 21 overlay
  clips (2.7 GB, pixels only), 113 `reward_stats/live_*.jsonl` = 958 matches / 12 wins with per-play logs.
  None carries ground truth; nothing logs player tag or battle time -> a live match cannot be re-driven in
  the engine from what is on disk (a).** Detector numbers on record: presence recall 0.855 / precision 0.886 /
  identity 0.823 on the frozen 241-image / 820-box gate (HANDOFF:1080-1096); no box-position error measured.
- Two live-path gaps NOT previously in HANDOFF (a, by reading): play.py never installs the board warp on
  `Vision` (RGB planes are a whole-window resize while canvases are board-true); play.py ignores
  `train.rl_gate_tau` for the non-PPO deployed checkpoint. Both S4 items.

**B. The contract (`pipeline/obs_contract.py`, spec `L63/s0/obs_contract_spec.md`, decisions
`L63/s0/obs_contract_impl.md`).** Package decision: `icebow/src/clashrl` and `hogeq/src/clashrl` are diverged
copies (20 files differ), so every new component lives ONCE in top-level `pipeline/` with per-deck yaml
(`decks/icebow.yaml`, `decks/hogeq.yaml` -- hogeq's 8 cards read from `hogeq/config/cards.yaml:36-47`;
`hogeq/DECK_SWITCH.md` is a stale icebow copy). Contents: vocabulary = the detector's 230 classes + 2
engine-only (`spirit_empress_air`, `dark_elixir_bottle`) = 232, all 122 in-use catalog cards mapped; sub-spawn
`(name, max_hp)` rules measured at level 11 over all 211 batch_v2 recordings (golem <2500 -> golemite, lava
-> pups, elixir golem, royal recruits; mother_witch hog is (b) never seen, 400 guessed and flagged) plus a
spawn-spell body rule (BarbLog -> barbarians, Graveyard -> skeletons, GoblinBarrel -> goblins, RoyalDelivery
-> royal_recruit -- without it troop bodies landed on spell ids). `BoardState` = t/phase, my elixir (+exact
flag), opp elixir (None live), hand/next (vocab ids), 6 fixed tower slots, units (cls, side incl. -1 unknown,
x, y, hp_frac|None, deploying|None, age|None, conf), spells. Frame: me at bottom, my king row y = 0.90625
(engine (9000,3000) -> (0.5, 0.90625)), asserted against BoardWarp's forward map on the config tower anchors.
`from_engine` (raw observe() dict AND list-encoded frames, side-1 mirror), `from_live` (imports BoardWarp,
keeps unknown-team as side -1), `degrade` (measured recall 0.855 / precision 0.886; FP jitter 1.0 tile and
conf range UNMEASURED and labelled), `to_tokens` (F=14 per unit, S=70 scalars, 64-token cap ranked by
distance to the river). Tests: `icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_obs_contract`
-> 19 OK (implementer's run and mine). Independent sweep (`L63/s0/sweep_check.py`): 211 recordings x 80,668
frames x both sides = 161,336 conversions, 0 errors, 0 unmapped, 0 out-of-range, 4.35 units/frame, 6.9 s.

**C. New measured fact that contradicts the old builder (a).** Entity `kind 12` for buildings is NOT
"deploying": over 40 recordings, 22% of building kind-12 rows are damaged (an X-Bow at 203 hp 190 ticks after
placement). build_bc_v2's `kind in (12,14)` = deploying is (c) for buildings. The contract keeps the rule for
parity and flags it; the S1 model gets `hp_frac` and `age` directly so it does not depend on it.

**D. Not established.** `from_live` has only been exercised on synthetic detections -- the real-detector side
of the contract is untested until step 2b (own-click test on the record.py sessions). Position error of the
detector, unknown-team rate, and the conf distribution are unmeasured (degrade's defaults say so).

**E. Next (S0 step 3, engine-bound, launches in the background): corpus rebuild for BOTH decks through
`replay_batch`** -- needs a `--crawl <deck>` parameter (`replay_drive.py:39` hard-codes icebow's crawl2) and
the frame recorder on; icebow 625 x/y replays (211 done), hogeq count + acceptance rate = first hogeq numbers.
Step 2b (own-click contract test) runs on the GPU while the engine works.

**Box.** Nothing training; qemu + 2 services up; free RAM 4.8 GB; python 1 (owner's uvicorn).
