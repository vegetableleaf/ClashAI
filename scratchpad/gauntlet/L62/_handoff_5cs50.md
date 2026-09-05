
### §5cs.50 -- L62k (2026-09-05 20:4x-21:1x UTC): **OWNER RULING ON THE DEPLOY RULE APPLIED -- viewers and graders now SAMPLE the gate (`sim.ppo_gate_rule: sample`, one shared `GateRule`), and under it the engB m250 arms play 17.2 (control) / 24.5 (KL) cards per match on the sim against the init's 36.6 -- the "catatonic" checkpoints of §5cs.49 were the rule, not the policy;** plus the LIVE ENGINE VISUALIZER is published: https://claude.ai/code/artifact/3aca72fa-8f09-40e9-9d59-65c0dc2e03d2 (5,268 engine frames, 527 policy decisions, radii + gate + ghost + term readout; agent's write-up `L62/live_view.md`, STATUS complete).

Owner ruling (chat, 2026-09-05 ~20:45 UTC): *"go with (1) [sample the gate], and if that doesn't work try (2) [tau ~0.10]."*
(a) unless marked.

**A. What changed in `icebow/` (instrument change; the live-play path `play.py` and the sim trainer's greedy bench are
NOT touched -- they still read `ppo_gate_threshold`).**
- New `src/clashrl/gate_rule.py` -- `GateRule(cfg, seed)`: `sample` draws play ~ Bernoulli(sigmoid(g1-g0)) from a
  seeded `torch.Generator`; `threshold` is the old `> ppo_gate_threshold`. Card and cell stay the caller's argmax.
  One implementation, because three greedy copies (sim_view, policy_stats, the cli drill helper) is how §5cs.46 was
  missed. Unit check: p 0.1192 -> sampled frequency 0.1206 over 20,000 draws; threshold path True/False at 0.269/0.231.
- `config/config.yaml` `sim.ppo_gate_rule: sample` (comment block records the why and the readers).
- `sim_view._policy_agent`, `policy_stats`, `cli._drill_policy` read it; policy-stats JSON now carries `gate_rule`
  so a number can never again be quoted without its rule. `L62/gate_probe.py` takes an optional third arg
  `sample|threshold`. `tests/test_sim_view_visibility_i9`: 15/15 OK. The threshold path REPRODUCES §5cs.49 exactly
  (engB KL m250: 63 plays / 1,089 decisions) -- the patch changed nothing on the old rule.

**B. Play rate under the ruling (sim, `--size 432`, seed 4242).**

| checkpoint | policy-stats 16 m, SAMPLE: plays/match | gate held | gate_probe 3 m SAMPLE: plays/match, p(play) mean / p50 / p90 / max, affordable | policy-stats 16 m THRESHOLD 0.25 (§5cs.49) |
| --- | --- | --- | --- | --- |
| init `engB_kl_m0` (= BC init) | **36.6** | -- | -- | 36.2 |
| engB control m250 | **17.2** | 91% | 20.0; 0.089 / 0.085 / 0.139 / 0.302; 2.87 cards | 0.1 |
| engB KL m250 | **24.5** | 83% | 31.3; 0.121 / 0.112 / 0.195 / 0.360; 2.04 cards | 1.5 |

Readings. (1) The rule was the bug: the same two checkpoints go from 0.1 / 1.5 to 17.2 / 24.5 plays per match with
NO change to the policy. (2) The sampled p(play) mean is LOWER than the threshold-run's (KL 0.121 vs 0.191) because the
policy now spends -- affordable cards fall from 3.72 to 2.04 -- i.e. the gate is elixir-conditioned, which is what the
prior fits. (3) The init's 36.6 is not a target: §5cs.49 C measured its gate at 4x the pro rate on engine boards; the
pro ghosts' 45.1/match (§5cs.41 D) is a different instrument (engine, humans) and is quoted as scale only. (4) Under
sampling, `rocket` is the only never-played card for all three (16 matches) -- the card-diversity collapse of §5cs.46
(9 of 10 cards never played) was ALSO the threshold. (5) The 16-match sampled rate is itself a random variable now
(one seed of the generator): quote it with the seed, and treat a few-plays/match difference as noise until a second
generator seed is run (b: band unmeasured).

**C. Discipline note.** m250 was graded under THRESHOLD (§5cs.49) and is now re-read under SAMPLE (this section);
m500 and later will be read under SAMPLE by default, with `gate_probe ... threshold` kept available so any
checkpoint can be put on the old instrument when a comparison to §5cs.45/46/49 is needed. Never mix the two columns.
Fallback per the ruling: if sampling misbehaves for viewing (the owner's call after watching), `ppo_gate_rule:
threshold` with `ppo_gate_threshold` lowered toward the pro mean (~0.10) is option (2), untested.

**D. The live engine visualizer (owner ask §5cs.43 A follow-up: "turn the sim view into the engine artifact, with all
the sim features + radii").** Agent stopped by accident mid-build, restarted from its on-disk state, finished.
- `L62/live_view.py` (58.7 KB): `LiveEngineView.attach(env)` hooks an `EngineMatchEnv` and renders one frame per
  decision through the UNCHANGED `render_frame`; `ProbePolicy` (rules sample / threshold / argmax); `ReplayEngineEnv`
  presents the EngineMatchEnv surface from a recording so the whole wire was exercised WITHOUT a socket (both slots
  are engB's). Self-test (a, replay-shadow): 527 decisions, cell round-trip 62/62 exact, obs (96,64,12) matches the
  sim, 3.35 ms/frame; BC init p(play) mean 0.4723, 86.7% > 0.25 on engine boards.
- Artifact "Engine decision view 00LYPLJLC80L" (3.74 MB, payload embedded): scrub/play 5,268 frames; per decision
  p(play) bar with tau marks, rule verdict, decided-on vs applied-at tick, elixir seen, p(cell), hand strip with costs/
  affordability/queue (hand INFERRED from the L61 cycle rule seeded from the engine queue, 0 mismatches on this
  recording); table ring vs engine fire ring vs sight toggles; P1 band annulus + threat link + 247 term readouts
  (`score_focus_play` on the post-step board); 93 ghost plays in table + timeline + board; phase clock 2x@2401 /
  3x@4801 (a: matches the engine regen 0.36 -> 0.72 -> 1.08/s; (c) sim_view's own HUD label "3x from 180 s" is wrong
  for 180-240 s on the engine -- display-only, not changed); `#tick=` deep link. Verified by a node harness + headless
  screenshots (`ext/engine_view/live_artifact_{check,headless}.json`).
- Parity table `live_view.md` §3. Rendered: board, bodies, towers/crowns/king-awake, elixir, clock/phase, hand, radii,
  fire ring, chosen cell/card, P1 band + terms, gate readout, ghost plays, projectiles. NOT rendered (not exported by the
  deployed v1 bridge): status timers, zones/Tornado/Rage/Log corridor, target links (in the raw observe, not the
  recorder frame), ability/arc events. The v2 bridge (§5cs.45 B) would supply buffs + zones once verified.
- (b) Not yet run live: the `engine accepted / refused` tag is only exercised as `shadow`; a live run reaches the page
  via `--rows` JSON (not yet in `build_payload`). Command (free slot only): `live_view.py live --port 3803x --matches 1
  --policy <ckpt> --rule sample --heads argmax --seed 0 --radii --out ... --rows ...` (`live_view.md` §6).

**Not established.** The across-generator-seed band of the sampled play rate; whether the owner finds sampled
viewing satisfactory (fallback (2) parked); anything live-socket for the visualizer. Trap: **a sampled instrument
must always be quoted with its rule and seed** -- policy-stats JSON now carries `gate_rule` for exactly this reason.
