# L62 -- LIVE ENGINE VISUALIZER (`live_view.py`): the sim debugger wired to `EngineMatchEnv` decisions

Owner ask (2026-09-05): *"can you convert the sim view into an engine visualizer, so it's on par with actual
training? like the artifact you made for the engine visualizer -- along with all the sim features + radii."*

Code: `scratchpad/gauntlet/L62/live_view.py` (new; `sim_view.py`, `engine_view.py`, `engine_env.py` all UNTOUCHED).
Renders / payloads: `scratchpad/gauntlet/ext/engine_view/` (outside git).
Label key: **(a) measured** on this box, **(b) plausible-untested**, **(c) contradicted**.

## 0. Hard constraint honoured
Both engine slots (38031/38032) are running the engB training pair (PIDs 71976 / 46364). **Nothing in this
work connected to an engine, started a worker, or touched the VM.** Everything below is built and tested
against (i) the 211 batch_v2 recordings + the every-tick `replay_00LYPLJLC80L_run1.json`, and (ii) a
REPLAY env (`ReplayEngineEnv`) that presents the same surface `EngineMatchEnv` does and is driven from a
recording. The live path is written and its wiring is exercised by the replay env; the one thing NOT
exercised is the socket. The exact command to run when a slot frees is in section 6.


## 1. What `live_view.py` is (API)

One file, one renderer, three entry points. `LiveEngineView(out=None, *, focus_side=None, radii=True, width=560,
fps=6, grid=True, rule=..., fire_ring="nearest", fire_fixed=0.5)` is a passive wrapper: `.attach(env)` shadows
`env._render` (to capture the raw engine observe the env already receives -- NO extra observe RPC) and `env.step`
(to call `on_decision(env, action, info, gate, state, pre_state)` after every step); `.detach()` deletes the two
instance attributes so the class methods come back (a: the self-test wraps 40 steps and checks the env is restored).
Each decision produces one `render_frame` call plus my own overlays, one `_decision_row` dict (written by `--rows`),
and optionally one mp4 frame (`--out`). `ProbePolicy(env, ckpt, rule, gate_tau, heads, seed)` runs the GreedyPolicy
net and applies the gate rule explicitly (`sample` = training's Bernoulli draw, `threshold` = p > tau, `argmax` =
GreedyPolicy's p > 0.5), reporting `p_play = sigmoid(g_play - g_wait)`, the card/cell heads, the engine hand+queue
(`env.sim._queue_ids()`, L61 rule) and a `wait_reason`. `ReplayEngineEnv(rec_path, focus_side, decision_ticks=10)`
presents the `EngineMatchEnv` surface (`reset/step/_render/deck_keys/hand_vec/sim/spec_of/...`) fed from an every-tick
recording, so the wire runs with no socket; decisions are SHADOW (`accepted=None`). CLI: `live_view.py {live | replay
| export | selftest}` with `--rec --focus --port --matches --policy --rule --gate_tau --heads --seed --radii/--no-radii
--fire_ring --fire_fixed --width --fps --out --rows`. `build_payload` / `mode_export` write the artifact payload
(schema `live_view_payload_v2`); `live_build_artifact.py` (in `ext/engine_view/`) embeds it into the template.
`EngineMatchEnv` itself lives at `scratchpad/gauntlet/L62/engine_env.py` (not under `icebow/src/`); it is unmodified.

## 2. How an `EngineMatchEnv` decision becomes a `render_frame` picture

Path, per step (a: exercised 527 times per replay run, 40 times through the real wrapper in the self-test):

1. `env._render(state)` receives the RAW engine observe; the wrapper stores it as `_last_state` (pre-decision frame).
2. `env.step(action)` runs; the wrapper then calls `on_decision` with `pre_state` (what the policy saw) and `state`
   (post-step). `pre_state` gives `obs_tick` / `obs_elixir`; `state` gives the frame the placement is scored on.
3. `frame_of(state)` = `EngineMatchEnv._frame_of(state)` verbatim (the recorder-shaped dict the L61 adapter and the
   trainer read) + `projectiles` when the observe has them. Attributes carried: `tick`; `elixir[2]` (exact if present);
   per entity `side, x, y, name, hp, max_hp, kind` (7); per tower `side, type, lane, x, y, hp, max_hp` (7); per
   projectile `side, x, y, target_x, target_y, name` (6, additive -- absent from the recorder shape).
4. `view_engine_from_frame(frame, focus, spec_of, full=..., sim_eng=env.sim_eng0)` (engine_view.py, unmodified) builds
   the sim-shaped engine object: `_mirror_fns(focus)` puts the focus side at the bottom (focus 1: x' = 18000-x, y' = y),
   engine units / 1000 = tiles, `spec_of(name)` resolves the sim `UnitSpec` (with max_hp patched from the frame) so
   `radii_of` works; every attribute `render_frame/_draw_radii/board_from_engine` reads is present (a, engine_view.md
   section 3e: 30 engine attrs, 19 unit attrs, no silent getattr default).
5. `sim_view.render_frame(eng, width, note, actions, radii=True)` draws board, bodies, towers, HUD, table rings.
6. My overlays, drawn on the returned image only: `_overlay_fire_rings` (reach + target hitbox, section 5cs.43 rule;
   a: changes pixels only, 6 rings on the reset frame), `_overlay_targets`, the chosen cell + `score_focus_play(eng,
   spec, nx, ny, t)` (P1 band + term readout, computed on the POST-step board), the ghost opponent's plays
   (`_add_ghost_marks`), and a 52 px decision strip (`_strip`) with p(play), rule, verdict, result_code, hand.

Coordinates round-trip (a): `cell_to_engine`/`engine_to_cell` exact on 62/62 cells, max error 0.000333 tiles; the
normalised threat (0.25, 0.4531) inverts to engine (13500, 14499) = the IceGolemite at (13500, 14500) in frame 1090.

## 3. Feature parity vs `sim_view`

| sim_view feature | live_view (mp4 / rows) | artifact page | source / label |
|---|---|---|---|
| board, bridges, river, grid | rendered | rendered (canvas) | render_frame / template (a) |
| bodies with hp bars, name | rendered | rendered; square = building (kind 12/13), circle = troop (14/15), dashed = 12/14 | frame `entities` (a) |
| towers hp, destroyed | rendered | rendered; crowns line from towers at 0 hp; `K*` = king awake (kind 13 on `-1`) | frame `towers` (a) |
| elixir bars both sides | rendered | rendered, top/bottom labels follow the flip | frame `elixir` (a) |
| clock, 1x/2x/3x phase | rendered | rendered; 2x at 120 s, 3x at 240 s | INFERRED from the sim `elixir_rate` rule; (a) matches the engine regen on this recording (0.36 -> 0.72 /s at tick 2401, 0.72 -> 1.08 at 4801). sim_view's own HUD label says 3x from 180 s: (c) contradicted by the engine for 180-240 s (display-only, read-only file, not changed) |
| hand + next + queue | rows (`hand`, `queue`) | hand strip with costs, pick highlight, unaffordable dimmed, next/then | INFERRED: L61 cycle rule seeded from the engine queue, advanced on accepted focus plays; hand_source "engine", mismatches 0 (a) |
| table radii (attack ring, sight) | rendered | rendered, toggles | `geometry_reward.radii_of` (a) |
| engine fire ring (reach + target hitbox) | rendered (nearest / fixed / off) | rendered, mode select | section 5cs.43; gaps 0.5-0.6 tiles on the busiest frame (a) |
| flying marker | -- | second thin ring on the body | sim spec `flying` (a, rendered; b: whether the engine treats it as flying) |
| chosen cell + card | rendered | tilted cross + card label, kept for the last 5 decisions | policy output (a) |
| P1 band annulus + threat link + term readout | rendered | rendered (evenodd annulus lo..hi, buildings only) + terms panel | `score_focus_play` on the post-step board (a) |
| p(play), rule verdict, why-wait | strip | readout: p bar with tau 0.25 / 0.50 marks, rule string, wait reason | ProbePolicy (a) |
| engine accepted / refused + result_code | strip | tag `engine accepted` / `refused <name>`; `shadow` in replay | live only (b: no live run yet); RESNAME table for 0/9/22/1014/1050 |
| ghost opponent plays | rendered | cell markers + plays table + timeline ticks | recording / engine play log (a) |
| projectiles | rendered | rendered (2792 of 5268 frames carry any) | frame `projectiles` (a) |
| status timers (stun/slow/shield/invis/freeze) | blank | absent | NOT EXPORTED by the deployed v1 bridge |
| zones (Poison, Graveyard, Heal), Tornado vortex, Rage, Log corridor | blank | absent (play marker only) | NOT EXPORTED by v1; a v2 bridge exists but is unverified (HANDOFF section 5cs.45 B) (b) |
| unit target links | blank | absent | not in the recorder frame; the raw observe has target ids (engine_view.md section 8) (b) |
| ability state / events, splash/arc events | blank | absent | sim-engine-only records |
| deploy timer (exact) | -- | dashed outline = "no attack component" (kind 12/14) | (b) not specifically a deploy timer |

## 4. Self-test numbers -- (a) measured, REPLAY-shadow (no live socket)

From `ext/engine_view/live_selftest_full.json` (rec `replay_00LYPLJLC80L_run1.json`, focus 1, rule sample, heads
argmax, seed 0): obs shape (96, 64, 12) == sim; cell round-trip 62/62 exact, max err 0.000333; reset frame 0 units,
6 fire rings, overlay changed 1387 px; 527 decisions, 247 plays chosen, 280 waits; p(play) mean 0.4723, max 0.9126,
min 0.1213, p90 0.6829, frac > 0.25 = 0.8672, frac > 0.5 = 0.4687; episode tick 5275 (263.8 s), outcome side1_win,
crowns [0, 1], our_rejected 0, shadow true, hand_source engine, hand_mismatch 0; 2.57 ms per render_frame call, whole
replay 4.3 s wall; ring gaps on the busiest frame (tick 2740, 9 bodies) 0.5-0.6 tiles (Knight 1.2 -> 1.8, Cannon
5.5 -> 6.0, Tesla 5.5 -> 6.1, princess 8.0 -> 8.6). Wrapper path: 40 steps through the real `attach` and env restored.

From `live_tau025.log` (rule threshold, tau 0.25, same recording): 527 decisions, 457 plays / 70 waits, 3.35 ms per
render_frame call (mp4 written). From `live_rule_sweep.json`: sample seeds 0/1/2 -> 247/243/247 plays (56.2/55.3/56.2
per min); threshold tau 0.25 -> 457 (104.0 per min); threshold tau 0.5 -> 247; argmax -> 247. p_mean 0.4723 in all
rows (the net is deterministic; only the rule changes).

These are shadow numbers: the policy never drove the match, so the play rate is NOT a live play rate (a live accepted
play spends elixir and changes the next state). Interpreting 457 plays/match under tau 0.25 as a live rate is (b).

## 5. The artifact

Path: `C:/Users/benpe/ClashBot/scratchpad/gauntlet/L62/live_artifact_00LYPLJLC80L.html`, **3,738,142 bytes** (LF, UTF-8,
non-ASCII in the JS escaped), built by `live_build_artifact.py` from `ext/engine_view/live_payload_00LYPLJLC80L.json`
(3,697,595 B, schema `live_view_payload_v2`) + `live_artifact_template.html` (41,164 B). Check report
`ext/engine_view/live_artifact_check.json`: size <= 16 MB, payload round-trip equal, 5268 frames / 527 decisions /
93 plays, exactly 2 script tags, no undefined/NaN/Infinity, `<title>` at offset 0, no doctype/html/head/body, external
host = fonts.googleapis.com only, every `DATA.*` field the page reads is present, every `getElementById` id exists.

What it shows (a, verified in the built file by `live_artifact_headless.json` -- node vm harness with a DOM/canvas
stub -- and by two headless-Edge screenshots `live_artifact_shot_top.png`, `live_artifact_shot_band.png`):
* scrub/play through all 5268 ticks and step decision-to-decision (`stepDec` from 0 lands on tick 20; `#tick=NNNN`
  deep link); 5268 frames draw in 305 ms without error;
* the board as the policy saw it: entities, towers (line `themK* 4824 ...`), hand strip (4216 hand cells across the
  527 readouts), both elixir bars with correct side labels under the flip, clock + phase ("2:00 2x elixir" at tick
  2401, "4:00 3x elixir" at tick 4801), crowns ("us 1 - 0 them" on the last frame, = final crowns [0,1] for focus 1);
* radii toggles: table ring / fire ring / both / off, fire ring vs nearest / 0.5 / 0.9 / 1.5, show for all / side /
  towers, sight on/off, flip -- all modes executed (110,346 ellipse calls);
* per decision: p(play) readout with the 0.25 / 0.50 marks, rule string (`sample (g ~ Bernoulli p)`),
  verdict (PLAY/WAIT + why), decided-on tick vs applied-at tick, elixir seen, p(cell), chosen card + cell marker,
  hand affordability, term readout for all 247 scored plays, P1 band annulus (x_bow at obs_tick 1080: lo 1.75 / hi 7.0
  tiles round the ice_golem threat, 4 ellipses at exactly those radii, visible in the band screenshot), engine result
  tag (`shadow` here; `engine accepted` / `refused <reason>` in a live payload -- (b) untested, no live run);
* ghost opponent plays: 93 rows in the plays table, 93 timeline marks, cell markers on the board;
* the honesty note states shadow decisions, timing convention, hand rule, phase measurement, post-step scoring.

Payload schema (10 lines):
```
schema "live_view_payload_v2"; tag; focus_side; decision_ticks 10; tick_s 0.05; shadow; rule; gate_tau; heads; phase_s [120,240]
board {tiles_x 18, tiles_y 32, units_per_tile 1000, tower_range, king_range, siege_sight, princess_half, king_half}
specs {EngineName: {key, kind, r_atk, r_sight, r_body, flying, elixir, siege}}   deck [{key, elixir, kind, r_atk, r_body}] x10
policy {in_ch, n_cards, n_cells, threat_dim, grid, algo, rule, gate_tau, heads, ckpt}
frames [{t, el [e0,e1], e [[side,x,y,name,hp,max_hp,kind]...], tw [[side,type,lane,x,y,hp,max_hp]...], p? [[side,x,y,tx,ty,name]...]}] x5268
plays [{t, side, card, x, y, ok, res}] x93                    (every play the engine saw, both sides)
decisions [{tick, seconds, obs_tick, obs_elixir, hand, queue, p_cell, play, card_id, card_key, cell, p_play, rule,
            wait_reason, p_card, top_cards, n_playable, elixir, engine_xy, accepted, result_code, result, scores?}] x527
scores {p1_pull_band..p7_fragility, bridge_block_*, d_threat, d_path, threat_base, threat_x, threat_y, p1_band_lo, p1_band_hi, t_cross, t_hit, t_resp}
final {tick, terminated, outcome, winner, crowns, termination_reason, towers[], elixir}; final_decks; episode {..., hand_source, hand_mismatch}
```
Mismatch found and fixed this run: none in the v1 schema (every field the template read existed). What was missing
was features, added on both sides: decision-time `obs_tick`/`obs_elixir`, `hand`/`queue`, `p_cell`, `deck` costs,
`phase_s`; template: hand strip, band annulus on canvas, crowns, king-awake, flying ring, engine result tag,
`recentPlays` (marker + band survive the next decision), dynamic elixir labels, `#tick=` deep link.

## 6. Commands

Live mode -- ONLY on a FREE engine slot (both 38031/38032 were busy this run; not executed, (b)):
```
cd C:/Users/benpe/ClashBot/icebow && PYTHONPATH=src PYTHONHASHSEED=0 ./.venv/Scripts/python.exe \
  ../scratchpad/gauntlet/L62/live_view.py live --port 38031 --matches 1 \
  --policy data/bc_pro/models/bc_bias_native_s0.pt --rule sample --heads argmax --seed 0 --radii \
  --fire_ring nearest --out ../scratchpad/gauntlet/ext/engine_view/live_<TAG>.mp4 \
  --rows ../scratchpad/gauntlet/ext/engine_view/live_<TAG>_rows.json
```
(`--rule threshold --gate_tau 0.25` or `--rule argmax` for the other rules; `--policy` any GreedyPolicy-compatible
checkpoint; `--focus` is taken from the env's side in live mode.)

Replay (mp4, no engine) and export -> artifact regeneration (what produced the file in section 5):
```
cd C:/Users/benpe/ClashBot/icebow && PYTHONPATH=src PYTHONHASHSEED=0 ./.venv/Scripts/python.exe \
  ../scratchpad/gauntlet/L62/live_view.py replay --rec ../scratchpad/gauntlet/ext/replay_00LYPLJLC80L_run1.json \
  --focus 1 --rule sample --radii --out ../scratchpad/gauntlet/ext/engine_view/live_00LYPLJLC80L_s1_sample.mp4

cd C:/Users/benpe/ClashBot/icebow && PYTHONPATH=src PYTHONHASHSEED=0 ./.venv/Scripts/python.exe \
  ../scratchpad/gauntlet/L62/live_view.py export --rec ../scratchpad/gauntlet/ext/replay_00LYPLJLC80L_run1.json \
  --focus 1 --rule sample --heads argmax --seed 0 \
  --out ../scratchpad/gauntlet/ext/engine_view/live_payload_00LYPLJLC80L.json

cd C:/Users/benpe/ClashBot/icebow && ./.venv/Scripts/python.exe \
  ../scratchpad/gauntlet/ext/engine_view/live_build_artifact.py \
  --payload ../scratchpad/gauntlet/ext/engine_view/live_payload_00LYPLJLC80L.json \
  --template ../scratchpad/gauntlet/L62/live_artifact_template.html \
  --out ../scratchpad/gauntlet/L62/live_artifact_00LYPLJLC80L.html \
  --report ../scratchpad/gauntlet/ext/engine_view/live_artifact_check.json
```
A live-mode payload for the page needs an `export`-shaped dump from the live run; today `export` reads a recording
only, so the live path to the artifact is mp4 + `--rows` JSON (b: not wired to `build_payload` yet -- the one
remaining gap). Self-test: `... live_view.py selftest --rec <rec> --focus 1` (writes `live_selftest_*.json/png`).

STATUS: complete
