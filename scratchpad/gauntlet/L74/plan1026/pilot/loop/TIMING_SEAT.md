# OPP-LEARN-A: P2 timing-head opponent seats in the fast loop

Labels: (a) measured, (b) untested, (c) contradicted.

## STATUS (2026-10-28 ~23:10 EDT; keep current)
- DONE (a) FROZEN timing-head opponents play in the fast loop exactly as production (e1_eval HEAD ed890aa: timing_cfg,
  timing_decide_batch, th_costs Mirror, th_decided game over, th_ability learned presses). Commit d1988ef (+ this doc).
- compare (a), 33308, `/workspace/opl` tree (HEAD pipeline + loop), engine fe364ceb + tables 16.635.3,
  CRFORGE_BARREL_DECOY_SIM=1, ROYALE_HEROIW_PRESS=live, in-process cuda, TF32 off, FASTLOOP_MEMHASH=1:
  source msg lint_pa3 fast_msg_u0001 (pilot + B6 ability head + memory), opponent v0 `opp_m10_s0_sim.pt`
  (/workspace/opp/cbs/opp_ckpt, its own card_vocab: 123 ids vs the learner's 124) on every 2nd job of 32, opp_style off:
  - mix32 (`/workspace/opl/out/mix32.json`): 32/32 matches identical (16 P2 + 16 external opponents in ONE producer, two
    card-id universes), every traj key; P2 opponent decisions 7,424 / 7,424 identical (tick, play, slot, cell and the
    sha of every gen_row key incl. deck_gid / ctx_*); memory tables 32/32, MEM rows 11,493 / 11,493; ability results 32/32
    (presses 63 / 46 per side both paths, learner head 3,898 decisions / 66 presses); lp max gate 1.2e-6, card 7.5e-7,
    cell 2.8e-6, ab_lp 3.6e-7 (bar 1e-5).
  - smoke t2 (4 jobs all P2): 4/4, lp 0. The first smoke (t1) diverged at every th_tick re-decision: the producer did not
    keep SelfPlaySide.apply's `_th_slot` (fixed before d1988ef; t2 / mix32 are after it).
- PENDING (Codex OPP-LEARN-A_1): raw16 (the UNMODIFIED source msg, opp_style on: no-P2 regression of the per-seat
  extrap / universe edits), srv16 (all-P2, `--server eager`), the pod pytest. Results -> .foreman/scratch/a2/opplearn/results_1.md.
- Laptop tests (a): `pipeline/tests/test_loop_timing_seat.py` 3 passed + 1 skipped (game-over test needs royalegym = pod).

## What was built
- CfTrain.java: `setSeat(i, side, timing, extrap, universe)` before setJob. Timing seat = SelfPlaySide.apply's timing branch:
  next tick = ceil(tick / 10) * 10 at reset; ACT int 7 = th_tick (j > 0: decide again at slot + j); a play is landed AT the
  decision tick (no delay of ours; crforge's own 20 ticks still apply); then the next slot. Per-seat extrapolate_ticks set
  before each seat's build (timing 0; every other seat gets its SelfPlaySide.extrap = the old producer value at the pilot cfg).
  TH row int = CfCore.check(side, hand 0) in {MATCH_OVER, KING_DEAD} = th_decided's GAME_OVER. Ability mode 3 (TIMING
  HEAD): no rule, no options, recheck learned; the row carries CfAbil.recheck(side, true) (= _scan(_any_gate), the ready
  list); Python writes back {1, j, button, cid, uid}; queued + fired before the round's applies (production: in the decide).
  Card-id universes: `addUniverse(keys, pub)` / `enableMemoryU` = another gid's detector keys, public-object tables,
  memory tables and per-match builders (TrainMatch, CfIdent, CfPubObj, CfMem.Log); every play / press goes to every
  universe's builders; a seat builds in its own universe. Universe 0 = the old objects (no other gid = old behaviour).
- producer.py: ThEnv (the seat's env for production's decode: check_deploy from TH, _scan = ready list, queue_abilities kept
  for CfTrain); done_plays from CfTrain's accepted tally (the issued play joins once accepted, as Match._land); `_th_slot`
  as apply sets it; p = sigmoid(hazard); timing groups always production's path (sample_decide_batch -> timing) with an
  in-process forward; opp_sim deck_gid / ctx_* from GenPolicy.opp_inputs; `_univ(pol)` builds a universe from obs_id's
  fillers (JavaPub without its __init__ act hook).
- msg_p2.py (put a timing checkpoint on every n-th job of a dumped msg), cmp_p2.sh (compare in a given tree; RAW=1 = msg as is).

## Limits / owed
- Opponent-as-LEARNER (part C) is NOT here: a timing learner seat raises NotImplementedError (records, PPO rows: OPP-LEARN-B).
- Server mode (b, srv16 pending): a timing group never goes to serve.py; in server mode the producer's device is cpu, so the
  P2 opponent forwards on the producer's CPU while production's actor forwards it on its device -> lp noise, possible rare
  draw flips. Exact fix if srv16 shows it: serve the timing model (hazard / tick / ab heads + cells) on the server.
- A P2 opponent must not be styled: e1_eval.timing_cfg refuses `_opp_style` (production raises too) -> the pilot pool
  needs opp_style off for P2 entries (or style_config skipping them): a lead / OPP-LEARN-B decision. msg_p2 turns it off.
- Pool spec for P2 entries (`type` not in LIVE_OPP_TYPES, no `cfg`, run opp_decide_every unset or 10): timing_cfg refuses a
  decide_every other than 10.

## Restart
- Pod tree: `/workspace/opl/cb` (copy of /workspace/loop/cb + `git archive HEAD pipeline loop obsid facade` + these files).
- `cd /workspace/opl && CPUS=140-151 GPU=0 FASTLOOP_MEMHASH=1 bash cb/scratchpad/gauntlet/L74/plan1026/pilot/loop/cmp_p2.sh SRC.pkl out/NAME.json --ckpt CK --jobs 32 --every 2 -- --device cuda --in-flight 8 --matches 8 --threads 4`
  (SRC = /workspace/loop/cb/scratchpad/gauntlet/L68/rl/lint_pa3/fast_msg_u0001.pkl, CK = /workspace/opp/cbs/opp_ckpt/opp_m10_s0_sim.pt);
  summary: `python /workspace/opl/summ.py out/NAME.json 40` (laptop copy .foreman/scratch/a2/opplearn/summ.py).

## Codex dispatches
- OPP-LEARN-A_1 (low; .foreman/scratch/a2/codex/OPP-LEARN-A_1.md): wait for chain1, run raw16 / srv16 / pod pytest, tabulate.
