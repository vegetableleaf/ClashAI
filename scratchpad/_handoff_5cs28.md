

### §5cs.28 -- OWNER REDIRECT (2026-09-04): radius-graded reward shaping replaces the prior-KL question; proposal doc `research/RADIUS_REWARD_PROPOSALS.md` written and revised with the owner's five additions; gauntlet loop PAUSED pending owner review; skill §2.6 context discipline added

**What happened.** L57 stopped with `--questions` (prior-KL vs opponent work). The owner answered with a
new direction instead: grade every placement reward by distance from the RIGHT band (attack range /
aggro radius of every board object), plus a time-dependent gradient (respond after the threat crosses so
the princess tower helps, before it hits). Draft delivered in commit 569a893; owner's additions folded
in this commit (doc §7). Nothing implemented; nothing running; box idle (Nucleo only).

**Owner rulings recorded (2026-09-04).** Late edge of the timing window = `t_hit + 1.0`. Arms G / G+E /
E all run, two at a time. Live path log-only in the first run. Q1 (keep replaced weights vs scale the
graded family) explained in doc §7.6 -- STILL OPEN, owner decides. Bridge-block plays are never
penalised for being early. Owner video reference: "When Should you Bridge Block?" (Abdod,
youtube L4WfWHLfbHw) -- could not be watched; the doc's case table §7.4 is my doctrine, needs owner
strike/add.

**(a) measured -- fact checks behind the additions.**
- Obs carries NO card identity in the image: `detect_obs.CHANNELS` = 6 role channels (+3 predictive,
  +2 HP), blob size = collision radius (`view.py:167`). The 10-dim identity block (`card_threat
  .IDENTITY_DIM`) is role bits of the DEEPEST recognised whitelisted enemy only. So the model can
  derive the role-average band, not per-card sight (wincon role spans Hog 9.5 / Giant 7.5 / Ram 5.5).
  Doc §7.1: run 1 with zero obs change; identity channel is a second experiment if the §3 gate says
  the card matters.
- Sim debugger = `run.py sim-view` (`src/clashrl/sim_view.py::render_frame`, OpenCV, mp4 via `--out`).
  Draws spell AOE / vortex / splash flashes / tower footprints / dead tower crossed out; draws NO
  attack or sight ring. Deliverable: `--radii` overlay fed from the same helper the reward uses.
- Dead princess tower: already excluded from targeting (`engine.py:2460,2546,2592,2618,2661,3121`),
  collision (`:2371`), the pixel canvas (`view.py:95`), reported as HP 0 in the tower block; the live
  "X-Bow at the spot that used to reach the taken tower" bug was real and is why the tower block exists
  (`sim/env.py:170-178` comment). New terms must use alive towers only (P6 amended; unit test owed).

**(b) plausible, untested.** Whether the trunk already reads card identity from blob size + speed
(linear probe on `c2r_best` features -> `base_card` accuracy vs role-level ~40%). Whether the pros'
Tesla tile ranks the same under per-card vs role-average radii (the §3 gate measures it). The
bridge-block case table.

**Context problem (owner raised).** Measured cause: HANDOFF.md 11,3xx lines / ~970 KB, bootstrap
~50k tokens per session. Owner approved only loop discipline (skill `.claude/commands/gauntlet.md`
§2.6: probe output to files, capped greps, never re-read, subagents for >3 files). Proposed and NOT
approved: STATE.md + `handoff/` archive + INDEX.md; roll GAUNTLET_LOG to the last 10 loops; cull §6 to
<= 20 items; one session per workstream.

**Next (after owner review of the doc).** Step 0 `sim-view --radii` overlay + `geometry_reward.py`
pure module + reward_stats ledger; §3 validation gate on the 268 replays (pros' modal Tesla tile must
outrank the corner or the term is dropped); then arms G / G+E from `c2r_best` (backups first,
PYTHONHASHSEED=0, idle-box check), E after; reads at m5k/m10k with place_probe + gate_prior_probe +
the ledger. Live stays log-only.

**Traps found.** (1) The gauntlet skill lives at `.claude/commands/gauntlet.md`, not `.claude/skills/`.
(2) YouTube pages fetch as footer-only; `youtube.com/oembed?url=...` returns title + channel, nothing
else. (3) Compound bash with several heredocs broke again (L57) -- long text goes through the Write
tool, then a one-line append.
