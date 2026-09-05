
### §5cs.43 -- L62d (2026-09-05 17:1x-18:1x UTC, owner ask): SIM_VIEW DEBUGGER NOW RENDERS REAL-ENGINE FRAMES (one renderer, two feeds; `sim_view.py` unchanged, 52/52 tests) with the L58 radii overlay, P1 band and term readout intact; **first ground-truth read of the radius table: the engine's reach is CENTRE-TO-TARGET-EDGE, so every drawn ring / reward P-term radius is 0.5-1.0 tiles INSIDE where the engine actually fires** (princess tower first shot up to 8.48 edge / 8.98 centre vs table 8.0; Musketeer 6.53 vs 6.0; Cannon 5.84 vs 5.5); (c) lingering zones are NOT in the bridge's `effects` (23,169/23,169 full frames have effects == projectiles); (a) the L61 recorder dropped every rich per-entity field the bridge exports (target, deploy timer, attack timers, ability state, level) -- a one-line recorder change + re-record recovers them, no bridge work.

Source: `scratchpad/gauntlet/L62/engine_view.md` (agent, STATUS complete); code `L62/engine_view.py`; renders + stills
`scratchpad/gauntlet/ext/engine_view/` (outside git; the owner should look at `00LYPLJLC80L_s1_full_readout_tick1591.png`
and the two mp4s). (a) unless marked.

**A. Owner ask and answer.** "Should the sim view debugger be transitioned to the engine, preserving the radii work?"
Yes: `render_frame` reads the engine through 15 attributes that the L61 adapter already supplies, so the L58 layer
(`_draw_radii`, P1 annulus, `score_placement` readout) runs on engine boards unchanged. Pushback recorded: on the engine
the debugger's job changes from catching OUR mechanics bugs to catching ADAPTER bugs, showing ghost staleness, and
checking `radii_of` against ground truth. Follow-up ask: "can the non-transferring features be re-implemented -- it
does not change mechanics". Correct that it is read-only; corrected the premise that "replay data shows interactions":
the crawl holds commands only, interactions come from the engine's observe, and the observe is bounded by which libg
struct offsets the sandbox bridge reads (`jni_bridge.cpp` ~1278-1420). The buff set (stun/slow/freeze/shield/invis/
rage/souls) needs a new offset hunt in the bridge (sandbox-side C++ + host-hash re-pin) -- a separate task.

**B. Built.** `view_engine_from_frame(frame, focus_side, spec_of)` -> `EngineView` accepted by `render_frame` as is
(30 engine attrs + 19 unit attrs all present -- no getattr default masks a missing field); `render_recording(...)` ->
mp4 (1.74 ms/frame), focus plays scored exactly as `_score_last_placement`, opponent plays as orange diamonds, `?` for
unmapped (0 unmapped over all 211 batch_v2 recordings); `view_engine_from_observe(state)` consumes the bridge's RAW
full observe (target -> attack link, `event_timer_ms` -> deploy_left (inferred), `attack_progress_ms` -> attacking
(inferred), ability_state_code 2/10/11 -> ability tag / cast ring (docs' code table), non-projectile effects -> zones);
spawner children (Graveyard/Witch skeletons, Clone) recovered from name + max_hp. Pixel checks: tower px error **0** vs
`SimMatchEnv.reset()` (1 tile = 1,000 engine units on both axes, anchors coincide); focus_side=1 view is the exact
reflection of focus_side=0; radii overlay changes 5,197 px; a Tesla placement with a real P1 band (threat goblinstein,
band 2.2-5.5, p1 -0.10 p2 +0.50 p5 +1.00) changes 42,603 px. HUD carries a fixed "ENGINE FEED: status/zones/arcs/
abilities not exported" tag. Feature table (rendered / inferred / not exported) in engine_view.md §8.4.

**C. The radius table vs the engine (§6; first shot = new projectile within 1.2 tiles of a same-side body after >= 2 s
idle; Tesla is hit-scan -> read from 220-hp drops, n=26).** Centre-to-EDGE first-shot max minus `radii_of`: princess
tower **+0.48** (8.48 edge / 8.98 centre, n=30; the wiki says 7.5), cannon +0.34 (n=3), x_bow +0.10 (13.04 at a tower =
11.5 + 1.5 tower radius, within 0.06), tesla +0.07, ice_wizard +0.13 (6.94 at a tower ~ 5.5 + 1.5), musketeer +0.53
typical and ONE 8.88-tile shot from `Musketeer@evolution` (b: evo sniper, one shot). Reading: the engine tests reach
centre-to-target-edge, the sim `_gap` convention -- the TABLE is right to 0.1-0.35 tiles for x_bow/tesla/ice_wizard/
cannon -- but the overlay draws and the reward scores the BARE `reach` (centre-to-centre), so rings sit 0.5-1.0 tiles
inside the engine's actual fire point on a Hog/Knight/Golem-sized body; the sim engine additionally adds `_REACH_SLOP`
0.6 the table does not carry. The princess tower's 8.48 is a LOWER bound on acquisition (first shot lands after the
wind-up while the target walks in; b: needs a target-lock export to pin 8.5 vs 9.0). Consequence for the radius-graded
reward and the L58 doctrine: P-term geometry was scored ~0.5-1 tile short of the real game; not changed here (owner's
call, and no arm depends on it now).

**D. What the engine does not export (c/a).** Lingering zones: over ALL 23,169 full frames on disk `effects ==
projectiles`, including frames captured inside the lifetime of 58 graveyard / 57 poison / 184 tornado / 43 freeze /
66 earthquake / 60 goblin-drill / 18 void plays -> the bridge's effect gate (4M category, side in {0,1}, in-bounds)
never passes area effects; a new registry/offset is needed. Zap/Poison/Tornado/Graveyard/Freeze/Rage/Clone/Earthquake/
Void/Mirror/GoblinCurse are never a projectile nor an effect; Log/BarbLog/Fireball/Rocket/Arrows/Snowball/Lightning/
GoblinBarrel ARE projectiles and render. Recorder drop (a): the L61 `snapshot()` kept `[side,x,y,name,hp,max_hp,kind]`
per entity and nothing else, so target/deploy timer/attack timers/ability state/level/paths are exported-but-absent on
disk; proposed one-line change (keep the raw dicts, drop `path_nodes` to stay ~10x smaller) in §8.6, NOT applied (needs
a re-record on the VM). `kind` 14 also flips on 9 old bodies within ~1.5 s of Ice Spirit / Ice Wizard / Log
interactions -> likely "cannot act" (deploying OR frozen/stunned), not only deploying (b; the L61 deploying flag in the
policy obs inherits this).

**Not established:** nothing about live-env rendering (the env agent's frames are not wired to the viewer yet -- next
loop, one call per decision on `EngineMatchEnv`); the evo-Musketeer range; the engine's acquisition radius proper.
Trap: the HUD tag overflows the 460-px canvas -- cosmetic, widen or shorten before the owner reads stills.
