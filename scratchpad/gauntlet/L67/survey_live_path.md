# L67 survey: LIVE play path vs the S1 student (feature parity) -- read-only, 2026-09-07

Scope: `pipeline/` (student) vs `icebow/src/clashrl/` (live). Every claim cites file:line. (a)=measured, (b)=untested, (c)=contradicted.

## 1. The student's input (pipeline/)

Contract dataclass = `BoardState` in `pipeline/obs_contract.py:123-143`; model = `pipeline/model_v3.py:79`; tokeniser = `obs_contract.to_tokens` (:522-546).
Board frame (obs_contract.py:6-10): 18x32-tile board normalised to [0,1], x across, **y down the screen, me at the bottom** (`nx = x/18000`, `ny = 1 - y/32000`, side 1 mirrored first); "exactly the board side of `clashrl.actions.BoardWarp`".

### 1a. BoardState fields -> model input

| Field (obs_contract.py) | Type | Encoded where | Encoding |
|---|---|---|---|
| `source` :125 | 'engine'/'live'/'degraded' | not encoded | metadata only |
| `t_sec` :126 | float | sc[0] `t_300` (:537) | t/300 |
| `t_source` :127 | 'tick'/'clock'/'timer' | not encoded | metadata |
| `double_elixir` :128 | bool | sc[1] | t>=120 (:43,:150) |
| `overtime` :129 | bool | sc[2] | t>=180 |
| `my_elixir` :130 | float | sc[3] `my_elixir_10` | /10 |
| `my_elixir_exact` :131 | bool | sc[4] | 1 engine / 0 live |
| `opp_elixir` :132 | Optional | sc[5] `opp_elixir_10`, sc[6] `opp_known` | (v or 0)/10, known flag |
| `my_hand` :133 | 4 vocab ids, -1 unknown | sc[7:43] `hand_slot_onehot_4x9` (:515-519,:539) | per slot one-hot over the 8 DECK slots + col 8 "unknown/absent" |
| `my_next` :134 | vocab id / -1 | sc[43:52] `next_slot_onehot_9` | same 9-way one-hot |
| `towers` :135 | exactly 6 Tower (my K,L,R, opp K,L,R) | sc[52:58] hp_frac (0 if None), sc[58:64] hp_known, sc[64:70] alive (:542-544) | 18 scalars |
| `units` :136 | tuple[Unit] | unit tokens, F=14 cols (:488-490) | see below |
| `spells` :137 | tuple[Unit] | unit tokens with `is_spell`=1 | same row format |
| `deck` :138 | 8 vocab ids | not a feature; used to build the slot one-hots | -- |

S = 70 scalars (:495). Unit token row (`_token` :499-512): `[cls(int as float), side_mine, side_enemy, side_unknown, x, y, hp_frac, hp_known, deploying, deploying_known, age_sec/30, age_known, conf, is_spell]`. `Unit` fields :103-111: `cls` vocab id, `side` 0/1/-1 (-1 "live only; engine never emits"), `x,y` board frame, `hp_frac` "engine hp/max_hp; live None", `deploying` "engine kind in (12,14); live None", `age_sec` "engine when fed a history, else None", `conf` "engine 1.0; live detector conf". Tower :114-120: side, kind, lane, hp_frac Optional, alive.
Truncation: `to_tokens` keeps max 64 rows ranked by |y-0.5| asc then conf desc (:525-536). **No unit level, no evolution flag as a feature** -- evolution only via a separate `_evo` vocab class (vocab.py:36-43); `deploying`/`age`/`hp` are Optional with explicit `*_known` columns, so the model was built to accept their absence.

Vocab (pipeline/vocab.py:15-69): canonical ids = the detector's 230 class names (`DETECTOR_CLASSES`, "frozen copy of icebow/config/detect_classes.yaml"), + 2 engine-only names -> N_VOCAB=232. "Live is the lower-information side, so its vocabulary is the contract's" (:4-5). Engine display names reach it via `engine_key`/`engine_unit_id` (:146-211, alias table + max_hp sub-spawn split).

Extra model input NOT in BoardState: `past` [PAST_K=3, 4] = my last 3 accepted plays (slot, x, y, seconds ago; -1 none) -- dataset.py:42,62-68; consumed by model_v3.py:122-124.

### 1b. Model I/O (model_v3.py)
- Inputs (`forward` :148): `tok [B,64,14]`, `mask [B,64] bool`, `sc [B,70]`, `past [B,3,4]`, optional `card_slot [B]`, `hand_mask [B,8]`.
- Encoder :109-129: cls embedding (N_VOCAB+1) + Linear(13 feature cols + 32 Fourier(x,y)); 9x16 patch tokens with scatter-added unit embeddings; 1 global token from sc + past; 4-layer d=128 Transformer.
- Outputs (`heads` :131-137): `gate` [B] logit (play/wait), `card` [B,8] hand-masked deck-slot logits, `wait` [B,8], `value` [B,7] (crown diff -3..3); `cell_logits(enc, card_slot)` [B,2304] over **GRID_X=36 x GRID_Y=64** half-tile cells, `cell = cy*36 + cx` (:30,:38-42).
- Label conventions :45-68: `floor` (cell_index) vs `lattice` (round); checkpoint stores `args.grid` (train_s1.py:183-184,230). `cell_xy(cell, grid)` :63-68 inverts: centre (+0.5) under floor, lattice point (+0.0) under lattice. The `v5lat` checkpoints are `--grid lattice` (name tag), so **off = 0.0** in s3_bench.py:110.
- `hand_mask_from_sc` :158-161 reads sc[7:43].

### 1c. How the dataset fills each field (pipeline/dataset.py)
Source is NOT plays_ext.csv/battles.csv directly: `replay_<tag>.json` from `research/sandbox_tools/replay_batch.py --record-plays` = the ENGINE re-drive of RoyaleAPI replays (dataset.py:1-7,43). PLAY rows: `from_engine(_as_compact(play_frame), side, deck, engine_deck=...)` (:160-161); WAIT rows: compact `frames` + hand reconstructed from the next play's `hand_before` (:167-198).

| Field | Filled from |
|---|---|
| t_sec | ENGINE tick*0.05 (obs_contract.py:227-228) |
| my_elixir (exact), opp_elixir | ENGINE `elixir[2]` / players (:233-247) -- opp elixir is a training-only luxury |
| my_hand, my_next | ENGINE play_frame players.hand / log `hand_before`, `next` deck index (:238-247; dataset.py:185-192) |
| towers (hp_frac, alive; all 6 incl. kings) | ENGINE towers rows (:249-265) |
| units: cls, side, x, y, hp_frac | ENGINE entities `[side,x,y,name,hp,max_hp]` (:267-296); `deploying`=None because `_as_compact` strips col 6 (dataset.py:77-83); `age_sec`=None (no history passed) |
| spells | **none in training rows** -- `_as_compact` drops `effects` (dataset.py:81), so is_spell tokens never appear in the dataset (engine_play.py:12-15 confirms) |
| conf | 1.0 always (engine) |
| past | dataset `done` list of my accepted plays (dataset.py:62-68) |
| deck | pipeline/decks/icebow.yaml (tornado, tesla_evo, ice_wizard, x_bow, rocket, knight_evo, the_log, skeletons) |
| Replay METADATA (RoyaleAPI) | only `y_crowns` value target (:71-74) and the play's card name/x/y label (:156-165); split by tag crc32 (:86) |

So training rows have: hp_known=1, deploying_known=0, age_known=0, conf=1, side in {0,1} only, my_elixir_exact=1, opp_known=1, all 6 tower hp known, no spell tokens. The model has never seen side=-1, conf<1, hp_known=0, opp_known=0, my_elixir_exact=0, or king hp_known=0 unless `degrade()` (:432-481) was used -- that is a dataset-time option, not wired into dataset.py (grep: `degrade(` is called nowhere in pipeline/dataset.py or train_s1.py).

## 2. The live path today (icebow/src/clashrl/)

Entry: `play.py:100 play(cfg)`. Policy loaded = the OLD CNN `PolicyNet` (`from .model import PolicyNet`, play.py:103), NOT the S1 student:
```
ckpt_path = cfg.path(cfg.get("train", "checkpoint", default="data/policy.pt"))      # play.py:109
rl_path   = cfg.path(cfg.get("train", "rl_checkpoint", default="data/policy_rl.pt")) # :110
if rl_path.exists(): ckpt_path = rl_path                                             # :111-112
gw, gh = int(ckpt["grid"][0]), int(ckpt["grid"][1]); n_cards, n_cells = ...          # :118-119
net = PolicyNet(in_ch, n_cards, n_cells, threat_dim=threat_dim)                      # :125
gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))                 # :140
```
config.yaml:930-931 `train.checkpoint: data/policy.pt`, `train.rl_checkpoint: data/policy_rl.pt` (exists, 2026-09-05 19:51 -> this is what live loads). Live grid = `action.grid: [18, 24]` (config.yaml:499, 432 cells), `arena_box: [0.03,0.10,0.97,0.86]` (:503).

Observation built in `act_in_match(frame)` play.py:503-559 -- image + vectors, no BoardState:

| Live signal | Reader (file:line) | Form fed to PolicyNet |
|---|---|---|
| RGB frame | `vision.observe(frame)` play.py:506 (resize/remap, vision.py:108-129) | image tensor /255 (:553) |
| hand identities | `vision.recognize_hand(frame)` :507 (template match per slot, vision.py:231-269) -> `hand_ids` list of deck ids (-1 unread) | `hand_multihot` [n_cards] (:508) |
| next card | `vision.recognize_next(frame)` :511 + `CycleTracker.observe` (cycle.py) | `next_vec` [n_cards] |
| own elixir | `vision.read_elixir(frame)` :512 -> integer pips | `elixir/10` scalar (:556) |
| enemy threats (YOLO) | `PerceptionLoop.snapshot()` at `observation.perception_hz: 10` (play.py:389-395, :406-408; perception.py) / fallback `_detector.detect(frame, conf=detector_conf)` :410; `TeamTracker.tag` :415 gives `team` mine/enemy/unknown | `threat_tracker.update(frame).vector()` (:513) + identity/memory/interaction blocks `_threat_extra` :397-470 |
| tower HP | `TowerHpTracker.step(frame)` :504 (digit CNN on princess HP boxes, tower_hp.py:191-329) + `TowerTracker.step` :505 (alive flags) | `_tower_frac()` :472-489: 6 floats (my L,R princess frac, my king ALIVE proxy, opp L,R, opp king alive) -- "the KING's HP is never printed on screen" (:475) |
| semantic canvas | `detection_channels(_last_dets["all"], _db, ..., warp=actions.warp)` :523 when `_use_canvas` (checkpoint-gated :316-318) | extra image channels |
| unit HP bar | `detect_obs.read_hp_frac(frame, d)` :548 (colour-bar column ratio, detect_obs.py:266-291) -- ONLY when `observation.use_hp_canvas` (config.yaml:281 **false**; comment :275-280: "produced a FALSE 0.02 on a healthy X-Bow") | not fed today |
| opponent elixir | `OpponentElixirEstimator.update` :455 (estimate from seen plays) | mem[5] if `env.opp_mem_slot5 == opp_estimate` (:456) |
| match time | `ElixirClock` clock.py:50-143: **wall clock since IN_MATCH first detected** (`_start = time.time()`, :63,:71); badge template x2/x3 optional cross-check; no on-screen timer OCR exists (grep time_left/read_timer over clashrl: none) | only the 2x/3x multiplier / overtime flag reach the phase machine, not the policy |

Detection object = `replay_mine.Detection` (replay_mine.py:67-78): `cls` (detector class name), `cx, cy, w, h` (frame-normalised box), `conf`, `team` "mine|enemy|unknown", `ground_cy` (shadow y for flyers), `bar_vote`, `body_vote`; `.gy` property = ground y. **No level, no hp, no deploying flag** on the object.

Decision -> tap (play.py:560-766): hand-mask + elixir-affordability mask on card logits (:561-567); `cmask` = deployable cells (:583); PPO gate `wait = sigmoid(g1-g0) <= gate_tau` (:628-629, threshold rule, tau 0.25); `cell = argmax` (:634); optional live-search override (:639-); `deploy_clamp` (:694); per-card aim assists (x-bow lane/lock/depth :695-720, log corridor :721-732, tornado king :733-755, tesla pull :756-762); then `controller.play_card(*actions.decode(slot, gx, gy))` (:764).

**GateRule (gate_rule.py:11-31) is NOT used by play.py**: config.yaml:2171-2172 "play.py (live) and the sim trainer's greedy bench still read ppo_gate_threshold and are NOT changed by this key"; play.py:140 reads `sim.ppo_gate_threshold` directly and applies the threshold branch at :628-629. `sim.ppo_gate_rule: sample` (config.yaml:2173) governs sim_view / policy_stats / gate_probe only.

### Existing BoardState-from-screen code
`pipeline/obs_contract.py:325-403`: `LiveReads` dataclass (:326-334: elixir_int, hand_names 4 template keys, next_name, tower_hp 6 fracs, t_sec, t_source 'clock'|'timer', tower_alive) + `from_live(detections, reads, deck, warp=)` (:372-403): each Detection -> `vocab.unit_id(d.cls)`; ground-troop foot correction `fy = gy + TROOP_FOOT_K*h` (:382-384, K=0.25 measured); `warp.frame_to_board(cx, fy)` (:385); side from team (`unknown` -> -1 KEPT); hp/deploying/age = None, conf = detector conf; spells split by `vocab.is_spell`. `board_warp(deck)` (:355-366) imports `clashrl.actions.BoardWarp` from `deck.src_dir` and builds it from icebow/config/config.yaml.
Callers (grep -rn from_live/BoardState/LiveReads over icebow/src, icebow/tools, scratchpad/gauntlet, pipeline): **zero in icebow/src/clashrl**. Only `scratchpad/gauntlet/L63/s0/ownclick_run.py:105,131,145` (offline own-click test; `LiveReads(elixir_int=0, hand_names=(None,)*4, next_name=None, tower_hp=(None,)*6, ...)` -- dummy scalars) and `pipeline/tests/test_obs_contract.py:360-391`. **Not wired into play.py.** No live code produces a `LiveReads`; every piece it needs already exists in play.py's scope (`vision.read_elixir`, `hand_ids` -> `vision.deck_keys[i]` names, `recognize_next`, `hp_tracker.my_hp/enemy_hp/my_full/full`, `tower_tracker.mine_alive/enemy_alive`, `clock._start`) but nobody assembles them.

## 3. Parity table (BoardState field -> live availability)

Training-side distribution is MEASURED on `icebow/data/pipeline/s1_dataset_v5.npz` (246,155 rows = 66,579 play + 179,576 wait; 1,035,813 unit tokens; the file `s1_icebow_v5lat_s0.pt` names as `args.data`): distinct unit classes 107, **`_evo` classes present: 0; spell tokens (is_spell): 0; side_unknown: 0; hp_known mean 1.0; deploying_known 0.0; age_known 0.0; conf min 1.0; my_elixir_exact 1.0; opp_known 1.0; tower hp_known 1.0 on all 6 slots; hand-unknown one-hot rate 1e-6; next-unknown 0.**

| Field | (a) live today -- source | (b) live only with new work | (c) not observable / what training used |
|---|---|---|---|
| `t_sec` | wall clock since IN_MATCH first read (clock.py:63,71; "lags 1-2 s" :10-11) -> `t_source='clock'` | on-screen timer OCR (none exists) | training = engine tick*0.05 exact |
| `double_elixir`, `overtime` | derived from t_sec (obs_contract.py:150); `ElixirClock.overtime` clock.py:130; x2/x3 badge cross-check :85-98 | -- | -- |
| `my_elixir` | `vision.read_elixir` integer (play.py:512) -> `my_elixir_exact=False` (obs_contract.py:400-401) | sub-pip bar fraction | training: exact float, `my_elixir_exact=1` on 100% of rows |
| `opp_elixir` | `OpponentElixirEstimator` estimate exists (play.py:455) but `from_live` hard-codes `opp_elixir=None` (:401) -> `opp_known=0` | feed the estimate | (c) true value invisible; training: exact, `opp_known=1` on 100% |
| `my_hand` | `vision.recognize_hand` -> deck ids -> `vision.deck_keys[i]` -> `deck.card_id_of` (obs_contract.py:396); unread slot -> -1 -> one-hot col 8 | -- (2/52 unread after the 2026-09-04 recalibration, config.yaml:17) | training: 4 known slots on ~100% |
| `my_next` | `vision.recognize_next` + `CycleTracker` (play.py:511) | -- | training: engine `next` index |
| `towers` princess hp_frac | `TowerHpTracker.my_hp/enemy_hp` over `my_full`/`full` (play.py:480-486; digit CNN tower_hp.py:146-176) | -- | engine hp/max_hp |
| `towers` king hp_frac | **None** ("never printed on screen" play.py:475; obs_contract.py:334) -> `hp_known=0` | (b) the king's number IS printed once it is activated/damaged; no reader | training: known on 100% of rows |
| `towers` alive | `TowerTracker.mine_alive/enemy_alive` (play.py:478-479) | -- | engine |
| `units.cls` | YOLO class name -> `vocab.unit_id` (vocab ids ARE the detector ids, vocab.py:15-16) | -- | engine name via `engine_unit_id` alias + max_hp rules (vocab.py:201-211) |
| `units.side` | `TeamTracker` / perception tag mine/enemy/unknown (play.py:406-415) | -- | training: 0/1 only (measured 0 unknown); offline live unknown rate 0.252, wrong-team 0.15 troop / 0.40 spell (obs_contract.py:420-422) |
| `units.x,y` | `warp.frame_to_board(cx, gy)` + foot fix K=0.25 (obs_contract.py:382-385); TP position noise 0.45 tiles measured (:416) | -- | engine exact |
| `units.hp_frac` | **None** (`hp_known=0`). `detect_obs.read_hp_frac` exists (detect_obs.py:266-291) but is off (`use_hp_canvas: false`, config.yaml:281) and documented as inventing damage (:277-278) | hp-bar classes in YOLO (config.yaml:278-280) | training: hp_known=1 on 100% of tokens |
| `units.deploying` | None | detect the deploy circle | training: None too (dataset.py:77-83 `_as_compact`) -> PARITY OK |
| `units.age_sec` | None | per-track first-seen from `PerceptionLoop`/`TeamTracker` tracks (play.py:596) | training: None -> PARITY OK |
| `units.conf` | detector conf (obs_contract.py:386) | -- | training: 1.0 on 100% |
| unit level | (c) **not detected**: `Detection` has no level field (replay_mine.py:67-78); levels.py is stat scaling, not a reader | -- | training: no level feature either (obs_contract.py:103-111) -> PARITY OK |
| evolution flag | only as a separate `_evo` YOLO class (vocab.py:36-43) | -- | training: 0 `_evo` unit tokens (engine names fold to base via `engine_key`, vocab.py:146-154) -> a live `knight_evo` token id is unseen by the student |
| `spells` | detector spell/`_aoe` classes -> tokens with `is_spell=1` (obs_contract.py:387) | -- | training: 0 spell tokens (dataset.py:81 drops `effects`; HANDOFF:464 parked note) -> unseen token type |
| `past` (model input, not in BoardState) | not assembled live; my plays are already recorded with frame (cx, cy, t) by `_ploop.record_play` / `_team_tracker.record_play` (play.py:770-773) and `_cycle_tracker.record_play(card_id)` :765 | build (deck slot, board x, y, seconds ago) x3 from those records | training: exact engine accepted plays (dataset.py:62-68) |
| `deck` | (a) MEASURED: `pipeline/decks/icebow.yaml` = 8 slots `[tornado, tesla_evo, ice_wizard, x_bow, rocket, knight_evo, the_log, skeletons]`; live `vision.deck_keys = CardDB(cfg).deck_identities()` (vision.py:53; cards.py:499-505 "an evolved slot adds a second, separate `<key>_evo` identity") = **10** keys `[tornado, tesla, tesla_evo, ice_wizard, x_bow, rocket, knight, knight_evo, the_log, skeletons]`. Hand side is safe: `deck.card_id_of(name)` matches on BASE key (obs_contract.py:67-80), so `tesla` and `tesla_evo` both land on slot 1 | action side must pick whichever of the two identities is in `hand_ids` (see 4.2) | -- |

Net: every scalar/flag the model uses to signal "unknown" (`side_unknown`, `hp_known=0`, `conf<1`, `my_elixir_exact=0`, `opp_known=0`, king `hp_known=0`, `is_spell=1`, `_evo` ids) is at a constant in training and would flip live. `degrade()` (obs_contract.py:432-481) encodes exactly this shift with measured rates but is called by nothing in pipeline/ (grep: definition + tests only).

## 4. Action side: student (card, cell) -> screen tap

Live convention (actions.py): flat cell = `gy*gw + gx` on the CONFIG grid (`action.grid: [18, 24]`, config.yaml:499); `cell_center(gx, gy)` = `warp.board_to_frame((gx+0.5)/gw, (gy+0.5)/gh)`, then clamps x to [0.02,0.98], y to [a_top, a_bot], chat-box nudge (actions.py:201-211); `decode(slot, gx, gy)` -> `(slot_nx, slot_ny, target_nx, target_ny)` with `slots = hand.slots` (:248-252; config.yaml:17: four tray centres); `controller.play_card` taps slot then target via `capture.to_screen` (controller.py:100-108). `BoardWarp.board_to_frame(nx, ny)` (actions.py:139-144) is piecewise-linear on tower + `board_edges` anchors (config.yaml:1065-1080); its board frame = "my princess row 0.797, my king 0.906" (:56-58) = the contract's frame (obs_contract.py:6-10 states the equality).

Student convention: cell = `cy*36 + cx` (model_v3.py:30, :42); inverse `cell_xy(cell, grid)` -> board (x, y) in [0,1], +0.5 offset under `floor`, +0.0 under `lattice` (:63-68); s3_bench.py:110, :131-132 applies that `off` to `px/py` (`_hits` :147-163 divides by GRID_X/GRID_Y). `s1_icebow_v5lat_s0.pt` stores `args.grid = 'lattice'` (read from the checkpoint) -> off = 0.0. engine_play.py:56-70 already does cell -> board -> engine for the sandbox.

Convertible with existing code, no new geometry: `x, y = cell_xy(cell, 'lattice')` -> `nx, ny = actions.warp.board_to_frame(x, y)` -> `controller.play_card(slot_nx, slot_ny, nx, ny)`. Two things a wrapper must still handle:
1. Safety/legality: `cell_center`'s clamps (:205-210) and `deploy_clamp` (:254-285: king platform, river ledge, princess footprint) act on 18x24 grid indices. Bypassing them means the student's own-half rule is unenforced; routing through `actions.cell_at(nx, ny)` (:238-241) re-quantises to 0.5x1.33-tile cells (L62i: 432-grid row pitch 0.499 tiles, x-bow reach preserved, HANDOFF 5cs.48), losing the 36x64 x-resolution only in y.
2. Slot mapping: the student's `card` head is a DECK slot 0..7 (model_v3.py:95; deck order = icebow.yaml); the tap needs the TRAY slot: play.py:691 `slot = next(s for s, c in enumerate(hand_ids) if c == card_id)` where `hand_ids` index the 10-key `vision.deck_keys` (measured, see 3). So deck slot -> base key (`vocab.base_key(deck.cards[slot])`) -> the `hand_ids` entry whose `vision.deck_keys[id]` has that base key (`knight` or `knight_evo`, whichever the tray shows) -> tray position. A 1:1 index map does NOT exist (8 vs 10).

## 5. Inference (pipeline/s3_bench.py predict, :88-141)

`torch.load(ckpt)` -> `args = st["args"]`, `grid = args.get("grid","floor")` (:107-109); `S1Model(d=args.d, layers=args.layers)` :111, `load_state_dict(st["model"])`, `.eval()`; rows batched by `train_s1.Rows` (:114); forward `model(tok, mask, sc, past, card_slot=PRO slot, hand_mask=hand_mask_from_sc(sc))` (:125-126) -- **teacher-forced on the pro's card** for benchmark comparability (:122-124); `slot = card.argmax`, `cell = cell.argmax` (:127-128); `px/py` with the offset (:131-132). Device default `cpu` (:94). No preprocessing beyond `to_tokens` (done at dataset build time).
The closed-loop variant is `engine_play.py:160-219`: `load_model` (:160-178, reads `args.grid`), `decide` (:181-219): `encode` -> `heads` -> `p_gate = sigmoid(gate)`; play if `p_gate > tau` (default 0.5, :348) or Bernoulli sample (`--gate sample`); `slot = argmax(hand-masked card)`; `cell = argmax(cell_logits(enc, slot))`. This is the function a live wrapper should call.
Interpreter: the live loop runs `icebow/run.py play` (README:380) which inserts `icebow/src` on sys.path (run.py:5) -- the SAME `icebow/.venv` the tests and trainer use (pipeline/tests/test_obs_contract.py:2). Measured in that venv: torch 2.11.0+cu128, CUDA available, Python 3.13.14, ultralytics 8.4.107, cv2 5.0.0; the v5lat checkpoint loads; batch-1 decide (encode+heads+cell_logits) **17.7 ms median / 23.1 p90 on CPU, 13.6 / 17.8 on CUDA** (this box, not idle). Nothing version-wise blocks calling it from play.py; the only import-order point is `pipeline/__init__.py:3-4` (pipeline never imports clashrl at load; `from_live` imports BoardWarp lazily from `deck.src_dir`), and `pipeline` must be importable from the live process (repo root on sys.path; run.py only adds `icebow/src`).

## 6. Other blockers / knobs

- Timing budget (a, HANDOFF:694-701, §5bl): served decision loop p50 **0.760 s** vs `play.act_period: 0.6` (config.yaml:1285); pipeline 0.646 s = env reads 0.343 s + trainer residual 0.315 s (not the net: forward 1.6 ms); `detect_state` 56-86 ms per decision; tower-HP OCR p90 348 ms; threat colour 60 ms; detector 29.5 ms median / 35 p90 in the 10 Hz thread (`observation.perception_hz: 10`, config.yaml:345); event wake `react_min_gap_s: 0.15` (:1295). The student adds ~18 ms; the reads it needs (elixir, hand, next, tower HP, detections) are already paid today. Numbers are contended upper bounds; `tools/latency_stage_timer.py` (idle-box run still owed, HANDOFF:702).
- Gate rule: play.py:140 + :628-629 apply `sigmoid > sim.ppo_gate_threshold` (0.25, config.yaml:2164) to the PPO 2-logit head; `sim.ppo_gate_rule: sample` (:2173) is NOT read by play.py (:2171-2172 says so). HANDOFF:2074-2077: "greedy tau 0.25 gives the control 0 plays ... tau 0.25 sits at the gate's" cliff. The student's gate is a single BCE logit (model_v3.py:94) trained on play:wait = 66,579:179,576, val gate_bal_acc 0.7475 (checkpoint `val`); engine_play defaults tau 0.5 / supports sample -- the live rule must be chosen and stated, not inherited from PolicyNet's 0.25.
- Live path record (a, HANDOFF:2310): "12 W / 957 (1.3%); detector obs never graded" -- no live number exists for ANY policy on detector observations.
- Config knobs a wrapper touches: `train.rl_checkpoint` precedence (play.py:110-112) means the S1 path needs its own switch; `action.grid` 18x24 vs student 36x64; `observation.detector_conf: 0.35` (config.yaml:321) vs `from_live` keeping every detection with its conf; `use_hp_canvas: false`.
- Deck identities: 8 (student) vs 10 (live, evo split) -- measured, see 3 and 4.2; base-key matching handles it on both sides but nothing enforces it at load.

## Blockers, ranked
1. **No live BoardState assembler in play.py** -- `from_live`/`LiveReads` exist (obs_contract.py:325-403) but have zero callers in clashrl; all inputs exist in `act_in_match` scope. Pure wiring + a `past` builder.
2. **Train/live feature-distribution shift the student never saw (a, measured on v5)**: side_unknown, conf<1, hp_known=0, my_elixir_exact=0, opp_known=0, king hp_known=0, spell tokens, `_evo` ids, 0.45-tile position noise, recall 0.855/precision 0.886. `degrade()` implements it but no dataset/trainer calls it; retraining with degrade (or zeroing the flags live to the training constants) is a decision to make before grading.
3. **Gate/deploy rule** -- play.py's tau 0.25 threshold is PolicyNet-specific; the student needs its own rule (engine_play.py:181-219 has threshold/sample).
4. **Action mapping** -- geometry exists (`cell_xy` -> `BoardWarp.board_to_frame` -> `play_card`), but deck-slot->tray-slot and the 18x24 legality clamps (`deploy_clamp`) need a deliberate wrapper.
5. **Latency** -- loop already 0.76 s vs 0.6 target; the student is +18 ms, not the bottleneck; the live-search/doctrine/OCR stages are.
6. `t_sec` from a wall clock that lags 1-2 s and ignores pauses (clock.py:10-11) -- low impact (t/300 scalar, phase flags).

STATUS: complete
