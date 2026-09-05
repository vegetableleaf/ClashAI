
### §5cs.51 -- L62l (2026-09-05 21:2x-21:5x UTC, owner ruling "if the KL run has nothing left to contribute, kill it now"): **engB KILLED at m=602/609. THE VERDICT ON PPO-ON-THE-ENGINE: 500 matches moved the leashed policy NOWHERE (15.44 -> 16.33 -> 15.64 top-1, flat within noise) and destroyed the unleashed one (15.44 -> 7.47 -> 6.87, with a QUARTER of its placement logits railed).** The owner also played the KL checkpoint live and reported "not changed one bit, sloppy placements, wastes cards, worse than a scripted bot" -- the first three are (a) CONFIRMED by measurement and expected by construction; "throwing the match on purpose" is (c) contradicted (no mechanism exists). Engine-PPO as run is closed; the next direction is the owner's new gauntlet.

Instruments: `L61/read_ckpt.py` (deterministic, fixed val sets), the engB train logs, `clashrl.cli policy-stats`
under `sim.ppo_gate_rule: sample` (§5cs.50). Raw output `scratchpad/gauntlet/L62/grade_engB_m500/`,
final log lines `L62/engB_final_state.txt`. (a) unless marked.

**A. The full engB trajectory (v1 sim boards, n 1004; the ONLY instrument that ran on every point).**

| point | control (kl 0) top1/top5 | rails frac>8 / p99 | KL 0.3 top1/top5 | rails frac>8 / p99 |
| --- | --- | --- | --- | --- |
| m0 (= BC init) | 15.44 / 46.61 | -- / 6.3 | 15.44 / 46.61 | -- / 6.3 |
| m250 | 7.47 / 26.79 | 0.027 / 9.8 | 16.33 / 44.02 | 0.019 / 9.8 |
| **m500 (terminal)** | **6.87 / 22.21** | **0.262 / 18.0** | **15.64 / 45.12** | 0.017 / 9.2 |

Two clean results. (1) **The KL leash works and buys nothing.** Three points, 500 matches, and the leashed arm
is statistically indistinguishable from the file it started from (+0.89, +0.20 top-1 vs an instrument whose own band
on a moved checkpoint is 0.4-3.9pp, §5cs L39). It did not forget and it did not learn. (2) **The unleashed arm is
degenerating, and accelerating:** top-1 halved, and the railed-logit fraction went 0.027 -> 0.262 between m250 and
m500 while raw_p99 went 9.8 -> 18.0 -> (train log, m602) **31.25, max 70.6**. A quarter of its per-cell logits are
saturated; that is a policy contracting onto a few cells, not learning placement. Card-level: the control never
plays skeletons (0.0/0.9 on v2), knight 0.6, the_log 4.1. **Interpretation (b, and it is the important one):**
across engA and engB, four arms and ~1,500 engine matches, the unshaped engine reward has not produced a single
measured improvement in pro agreement. The reward, not the algorithm or the leash, is the thing with no evidence
behind it.

**B. Terminal state and the kill (owner ruling ~21:2x UTC).** Control m=602, upd 198, cum 101W/501L, pl +0.0022
vl 0.5340 kl_cell 1.5365 raw_p99 31.25, p_gate 0.0914 vs gp_target 0.1239, elapsed 112.0 min. KL m=609, upd 200,
cum 130W/479L, pl +0.0042 vl 0.4872 kl_cell 0.0617 kl_term +0.0185 raw_p99 8.33, p_gate 0.0988 vs gp_target 0.0945,
elapsed 111.9 min. `taskkill /PID 40540 /T /F` and `/PID 72932 /T /F` (the launcher shims) took their children
56708/71976 and 45856/46364. Verified: python **7 -> 3**, the three guarded survivors alive (crawler 29444 + 53824,
owner's uvicorn 63608), qemu 54304 UP (413 MB), free RAM 2.4 -> **5.0 GB**. Kept as evidence:
`engB_{ctrl,kl}_{m0,m250,m500/m502,latest}.pt` + both logs.
**TRAP (new, cost us the last 100 matches):** `_latest.pt` is written only at `save_every` crossings, NOT
continuously -- `engB_*_latest.pt` are byte-identical to m500/m502 and the weights from m500->m609 are GONE. Any
future driver should write `_latest` every update, or the kill must be timed to a crossing.

**C. The owner's live-play report, tested claim by claim.**
1. *"Has not changed one bit"* -- **(a) TRUE and expected.** See A: the KL arm is its own init. This is the leash
   working as designed, and it is the strongest evidence in the project that PPO is contributing nothing here.
2. *"Placements sloppy, little to no impact, wastes cards"* -- **(a) expected, not a malfunction.** 15.6% top-1
   means the policy does NOT pick the pro's cell on ~84% of boards. We have never had a good policy; we have one
   that agrees with a pro about one time in six. "Worse than a scripted bot" is entirely plausible: a script
   encodes hand-written correct answers, a 15%-agreement network does not.
3. *"It has to be throwing the match on purpose"* -- **(c) contradicted.** No mechanism: the reward has no term
   that pays for losing, and the policy carries no representation of the match outcome that it could sabotage.
   The appearance is produced by an undertrained policy with a value head reset at launch.
4. **Two live-path caveats, both (b) and both mine to have flagged earlier:** live play builds the observation
   from the SCREEN DETECTOR, while every number in A comes from perfect engine/sim state -- a distribution this
   checkpoint has never been graded on; and `play.py` still applies the OLD `> 0.25` gate rule (§5cs.50 changed
   viewers/graders only, deliberately). So live behaviour is not a clean read of the checkpoint. **Unresolved:
   which file the owner loaded.** If it was `engB_ctrl_*` rather than `engB_kl_*`, the observed play was the
   6.87 / 0.262-railed arm, which is far worse than the checkpoint discussed above.

**D. What is now closed, and what is not.** CLOSED: the engine-PPO pair (both arms), and with it the questions
"does the gate prior prevent the gate collapse" (yes, §5cs.49-50) and "does the KL leash prevent forgetting" (yes,
this section). NOT closed and NOT tested: whether a SHAPED or denser engine reward would move agreement; whether a
larger/better imitation corpus lifts the 15.44 ceiling; the distillation-from-rollout-search teacher the owner has
asked for twice (parked, spec in §6-PRIORITY-B); the bridge v2 dynamic verification (both engine slots are free now,
so `L62/re_verify_bridge.py deploy --bridge v2` on port 37041 can finally run); the live-socket run of the new
visualizer (`live_view.md` §6). The lead's recommendation, on the evidence in A: stop spending box time on RL
against this reward and spend it on the imitation side.

**Not established.** Everything in A is one seed and one KL coefficient -- "PPO cannot work here" is NOT what the
data says; what it says is that THIS reward, at THIS scale (500 matches), with THESE two settings, produced no
measurable gain and one degeneration. A shaped reward or a 10x longer run are untested, and the box cost of the
latter is ~4 h/1,000 matches per arm.
