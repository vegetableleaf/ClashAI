# L58 brief: validation gate for the radius-graded reward (doc §3, §7.1, §7.8)

Repo C:\Users\benpe\ClashBot; python `icebow/.venv/Scripts/python.exe` from cwd `icebow`, `C:/...`
paths, PYTHONHASHSEED=0. No installs, no git commits, no edits to `src/` (the module under test is
`src/clashrl/geometry_reward.py`, built in step 0 -- read `scratchpad/gauntlet/L58/impl_geometry.md`
for its API and deviations). Never touch `data/` in git. Progress file, written INCREMENTALLY:
`C:\Users\benpe\ClashBot\scratchpad\gauntlet\L58\gate.md`, ending `STATUS: complete`. Numbers only from
what you ran.

## Goal
Before any training: does each graded term rank the PROS' placements above the policy's locked
placements, on real board states? And what is the current policy's mean band score (for `w_geom =
1/mean`, cap 2.0, doc §7.8)?

## Part 1 -- pro replays through the engine (the 268 complete command timelines)
Driver: `scratchpad/gauntlet/L51/sim_replay_drive.py` (`drive()` at line 136 deploys each pro play via
`eng.deploy(side, spec, x, y)` at ~line 171). Copy it to `scratchpad/gauntlet/L58/gate_replay.py` (do
not edit L51's file) and add, IMMEDIATELY BEFORE each accepted deploy:
  board = geometry_reward.board_from_engine(eng, side)
  s_pro = geometry_reward.score_placement(board, placement_for(spec, x, y))
  for each candidate tile c in CANDIDATES: s_c = score_placement(board, placement_for(spec, cx, cy))
where CANDIDATES = the policy's sim landing tiles {corner (1.5,18.5), lane (4.5,20.5), centre (8.5,23.5),
pro-modal-Tesla (9,21), pro-modal-bow (2,19)/(15,19), skeleton cell (9.3,24.1), knight cell
(11.8,24.1)} mirrored to the acting side's frame, plus a coarse 3x4 grid over the own half. Record per
play: tag, tick, side, card, pro tile, every term for the pro tile, the rank of the pro tile among
candidates under (a) the summed graded score, (b) each term alone, using per-card radii AND
role-average radii (`role_average_radii`). Use `--limit` to run a 20-replay smoke first, then all.
Restrict the analysis to the icebow-relevant cards: tesla, x-bow, skeletons, knight, ice-wizard,
tornado, the-log, rocket (crawl keys are hyphenated; `x_bow` returns nothing -- trap from §5cs.27).
Blue side = the icebow side in the crawl; own half HIGH y in team-0 frame (mirror for side 1 exactly
as the driver does).

Outputs: `gate_plays.csv` (one row per scored play), `gate_summary.txt`: per card x term -> fraction of
plays where the pro tile outranks the policy's locked tile; median rank of the pro tile; per-card vs
role-average agreement (fraction of plays where the rank is unchanged). Gate rule (doc §3): a term that
ranks the pros' modal Tesla tile BELOW the corner tile on the median Hog/Giant/PEKKA board is dropped
(list it, do not delete code).

## Part 2 -- the current policy's own placements (for w calibration)
Use `scratchpad/gauntlet/L55/place_probe.py::run(ckpt, seed, envs, steps, greedy_card)` or the L56
`tesla_probe.py` harness as the source of c2r_best matches (ckpt `data/bench/c2r_best_36k_backup.pt`;
verify the path exists, read-only). Wrap the env so each accepted placement is scored with
`board_from_engine(env.engine, 0)` BEFORE the deploy (find where the sim env deploys: grep
`self.engine.deploy` in `src/clashrl/sim/env.py`, and monkeypatch from the probe script -- do not edit
env.py). 3 seeds x 24 matches. Output `policy_scores.csv`, and in the summary: mean and distribution of
`p1_pull_band` (and the summed graded score) per card, the implied `w_geom = min(2.0, 1/mean)`, count
of placements per card per match.

## Part 3 -- linear probe (doc §7.8 flip condition), only if Parts 1-2 are done under 2 h wall
From the same c2r_best rollouts, collect (trunk feature vector, base card of the deepest enemy) pairs
at steps where exactly one enemy troop is on our half; fit a numpy least-squares / one-vs-rest linear
classifier (no sklearn) with an 80/20 split; report accuracy vs the role-level baseline (predict the
most common card within the true role). Write `probe.txt`.

Report every number with its n. Say which parts you did not reach.
