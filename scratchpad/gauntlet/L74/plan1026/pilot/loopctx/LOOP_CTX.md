# LOOP-CTX: the decide-rule context in Java

Ticket: port to Java everything `decision_options.decide` reads from the match state besides the model outputs, at the
live decision config (`scratchpad/gauntlet/L70/live/LIVE_OPTIONS`). Labels: (a) measured, (b) untested, (c) contradicted.

## STATUS (keep current)
- DONE: trace (below); `obsid/CfCtx.java` (Java builder), `obsid/cf_ctx.py` (doubles -> decide kwargs), `obsid/ctx_id.py`
  + `obsid/run_ctx.sh` (identity harness). Smoke (a): 2 matches, 1,693 seat-rows, every field + decisions + RNG states
  + the stress pair identical (`/workspace/ctx/out/smoke.json`, pod 30408).
- RUNNING: acceptance runs on pod **30408** (32657 was at load 219 on 54 vCPU; nothing progressed there):
  `/workspace/ctx/out/live.json` (56 matches) and `/workspace/ctx/out/live_hero.json` (56, `--hero-abilities`).
  Restart: `ssh -p 30408 root@157.157.221.29 'nohup bash /workspace/ctx/run_all.sh &'`.
  Tree: `/workspace/ctx/rl` = s3b3d/rl data links + HEAD b84b440 pipeline + HEAD blobs of LIVE_OPTIONS, facade
  CfCore.java, body_map.json; harness at `/workspace/ctx/crforge/obsid`.
- NEXT: copy results back to `obsid/results/ctx_*.json`, fill the result section, message LOOP-INT (a9ec050f10f6a04be).

## Trace: what decide reads (decision_options.match_kwargs on an e1_eval SelfPlaySide, live cfg)
`m._cur[1]` = bs = `from_engine(sim_compact(extrapolate(m.state, prev, 26)))`: the 26-tick look-ahead board (bodies
dead-reckoned, t and my elixir moved ahead; towers / crown rows are the raw tick's). `m.state` = env.raw() at the tick.

| decide kwarg | production source | read by (live cfg) | CfCtx |
|---|---|---|---|
| t_sec | bs.t_sec = (tick + h) * 0.05 | gate_taus (tau_phase), lethal phase | HEAD[0] |
| tau_threat | tau_threat_state(m.tau_threat_state, bs): my tower hp_frac drop <= 2 s + enemy body <= 8 tiles of it | threat_taus (tau_threatened 0.2) | HEAD[1], Seat state |
| enemy_alive | bs.towers[3:6].alive | xbow_class class_sample, xbow_dead_lane | HEAD[2-4] |
| rocket_boards | (princess_dead_state alive, enemy_body_tiles(bs), rocket_kills_king(crown, side)) | rocket_dead_target block | HEAD[5-8], bodies; Seat state; Tables.dmg (my_rocket_damage per tower max HP) |
| lethal | (m.state crown_towers, side, pending, own = last 8 done_plays (card, x, y, land t, hp_after), skip = recently_hit 20 ticks) | lethal_rocket ot_behind + lethal_log + lethal_quiet 1.0 | crown rows, own rows, HEAD[26-27]; Seat HP history + play log |
| log_air_boards | log_air_board(bs, log_air_ground_child_tiles(m.state entities)) | log_air block (Log rows) | ground / air / tower rows; Tables traits + child HPs |
| barrel_goblins | barrel_goblin_tiles(bs) | barrel_lane on | goblin rows |
| rocket_value | (bs, m.pending is not None, m) | rocket_value 9 / rocket_tornado only (bs.units, my_elixir, my_hand, phase flags) | CtxBoard (HEAD[9-25] + unit rows); holder None (read only with rocket_value_lead / _threat on: refused) |
| projectiles | m._gen_row['projectiles'] | log_aim log_barrel, log_air, barrel_lane | the obs block's key (CfPubObj, already identical) |
| rngs / card_names / decision_options | per-match SeedSequence(obs_seed('decision_options:'+tag, k), decision_seed) / deck / options minus card_levels | xbow class_sample draw | cf_ctx.decision_rng / caller / cf_ctx.options_for |

Not built (cf_ctx refuses): gate_decode hazard (step_s, elixir, enemy_units, threatened), rocket_value_lead on/blend,
rocket_value_threat on, pipeline_decisions, pipeline_tau_delta. Loop-supplied inputs: `pending`, the accepted-play
log (`Seat.played(T, land, slot, cell)` at Match._land's acceptance), the RNG, the deck, the projectiles block.
Training decode 'sample' reads a subset (t_sec, grid, lethal, projectiles, barrel_goblins: SAMPLE_RULES).

## Interface (for LOOP-INT)
Call `CfCtx.build(T, names, facadeMatch, seat, seatState, doubleBuf, off)` right AFTER that FacadeMatch built this
seat's obs for the decision (it reads the obs's look-ahead snapshot `back[seat]`). -1 = a Tables key missing (no state
changed): `cf_ctx.fill_missing(T)`, build again. Then `cf_ctx.decode(view[:n].tolist())` per row and
`cf_ctx.kwargs(rows, ...)` -> `decide(..., **kw)`. Layout: CfCtx.java header comment.

## Results
(pending: the 56-match runs)
