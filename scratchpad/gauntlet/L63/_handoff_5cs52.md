### §5cs.52 -- L63 (2026-09-05 22:0x-22:3x UTC, NEW GAUNTLET: "go back to square one, research, propose a new pipeline"): **THE OWNER'S "BC OVERFITS" PREMISE IS (c) CONTRADICTED -- THE BC INIT UNDERFITS: 17.62 / 48.85 top-1/top-5 ON ITS OWN TRAINING ROWS vs 15.44 / 46.61 on val (v1), CE 3.26 vs 3.52; on v2 val is ABOVE train (15.00 vs 14.09).** The model cannot fit the data it was trained on, and the +1.8 pt it holds over the board-blind card histogram (13.65, §5cs.34) is the whole of its board-conditioning. Research fan-out launched (5 agents, all writing to `scratchpad/gauntlet/L63/`); the pipeline proposal is next loop, gated on the owner's answers to five questions (below).

Instruments: `scratchpad/gauntlet/L63/bc_overfit_probe.py` and `mask_probe.py` (the read_ckpt.py scorer applied to
`split.json`'s TRAIN rows as well as VAL; raw output `bc_overfit_probe.out`, `mask_probe.out`). (a) unless marked.

**A. Train vs val, `bc_bias_native_s0.pt`, same scorer as every number in §5cs.44-51.**

| set | rows | top-1 | top-5 | CE (legal rows) | policy entropy H | uniform-over-legal H |
| --- | --- | --- | --- | --- | --- | --- |
| v1 sim boards TRAIN | 5,918 | **17.62** | 48.85 | 3.262 | 3.47 | 5.17 |
| v1 sim boards VAL | 1,004 | 15.44 | 46.61 | 3.521 | 3.48 | 5.17 |
| v2 engine boards TRAIN | 8,111 | 14.09 | 41.92 | 3.586 | 3.49 | 5.19 |
| v2 engine boards VAL | 1,333 | **15.00** | 43.51 | 3.620 | 3.46 | 5.17 |

Generalisation gap: 2.2 pt top-1 / 0.26 nats on v1 (binomial SE ~1.1 pt at n 1,004); NEGATIVE on v2. An overfit
model has a large train-val gap and low train CE; this one has train CE 3.26 nats over ~188 legal cells (entropy
3.47 = ~32 effective cells per decision) and misses the pro's cell on 82% of the boards it was fit on. **The
ceiling is not regularisation; it is that the model+data barely condition on the board at all** (consistent with
§5cs.34: trunk embedding cos 0.991 across pro boards, and the board-blind prior at 13.65).

**B. The action mask forbids the pro's cell on 3.0-5.1% of rows** (v1 train 300/5,918 = 5.07%, val 30/1,004 =
2.99%; v2 4.82% / 3.45%). §5cs.34 attributed the val 30 to "own-tower footprint"; the train rate is higher, and
the cause is untested (b). Whatever the new pipeline uses as its legal-placement mask must be validated against
the pro corpus (target: <0.5% of pro placements masked) before anything is trained on it.

**C. What this changes for the proposal.** "Overfitting" would call for regularisation, augmentation, more data
of the same kind. Underfitting-with-a-near-constant-embedding calls for a different STATE REPRESENTATION and
model (entity/token input with coordinates, not a rendered-board CNN with a tanh-capped cell head) and a
different OBJECTIVE for multimodal placements (a 3.5-nat entropy over 188 cells is what a unimodal head does to
a multimodal target). Both are (b) until the new BC is measured on the same rows. Owner's other premise, "the
architecture has something to do with it", is (a) supported by §5cs.34 (rails, constant embedding) and A.

**D. Loop bookkeeping.** Five research agents dispatched, each writing incrementally to
`scratchpad/gauntlet/L63/{lit_game_ai, cr_prior_art, recent_2025_2026, assets_audit, lessons}.md` (STATUS line
marks completion). Nothing is training; box: python 3 (guarded survivors), qemu UP, free RAM 3.9 GB.

**Questions posted to the owner (report L63, `--questions`), and what each answer does:**
1. Live training in the final layer conflicts with the gauntlet guardrail "do not touch the live-play path"; I
   read the new order as superseding it for the final layer ONLY, at implementation time, after proposal approval.
2. "Forget everything": I keep the DATA (crawl, replays, detector, BC datasets, val sets) and the REAL ENGINE
   SANDBOX as assets; I drop the hand-written sim, its reward, the PPO/DQN trainers and the policy architecture.
   Is the engine in or out as a training/proxy environment?
3. Which checkpoint file was loaded for the live-play session behind the "worse than a scripted bot" report
   (`engB_ctrl_*` = the 6.87 degenerate arm, `engB_kl_*` = the init-equivalent)?
4. Box budget per stage, and whether renting cloud compute for the offline stages is on the table.
5. Grading ladder: may the pipeline use proxy checkpoints (pro agreement WITH play rate -> engine winrate vs
   scripted bots at n>=100 -> live), or must every stage be graded live?

**Not established.** Whether a different model family lifts train top-1 above 17.6 on the same rows (the first
thing the new pipeline must show); the cause of the masked-target rows; anything the research agents return.
