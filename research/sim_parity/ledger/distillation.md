# DISTILLATION — the harness, the privileged-teacher gap, and the go/no-go

Spec: `HANDOFF.md` **section 6-PRIORITY-B** (commit `5aceb09`). Evidence it rests on:
`research/sim_parity/ledger/rollout_search.md`. Owner requirement (2026-08-27, twice): the long run
is **PPO + distillation**, not PPO alone.

⚠ **STATUS 2026-08-27 — read this line first.** The harness is BUILT and SMOKE-TESTED. The
small-corpus validation and the go/no-go verdict are **PENDING** the run recorded in section 4
below. **The full corpus has deliberately NOT been generated**: an 8k PPO run is live on this box
and labelling is CPU-heavy.

---

## 1. What exists on disk

| file | what it is |
|---|---|
| `research/sim_parity/scripts/distill_label.py` | teacher-corpus generator. Subclasses `scratchpad/rollout_search.py`'s `Searcher`; does NOT reimplement search. |
| `research/sim_parity/scripts/distill_student.py` | trains a student on the corpus and reports held-out top-1 agreement against two floors. |
| `scratchpad/rollout_search.py` | the teacher itself. Pre-existing, unmodified. |

Neither script is imported by `icebow/src` or `hogeq/src`. They are measurement tools.

## 2. The teacher, and the settings that must not move

```
H = 12 s     horizon      measured optimum: 16/20/30 within 1 sigma; FULL-remainder 5.14 sigma WORSE
N = 1        every decision   ⚠ THE ONE SETTING THAT MUST NOT MOVE
K = 4        candidate cards  INERT (2/4/8 within 0.3 sigma)
cells = 3    cells per card   kept (ceiling arm), but the cell label is PROVENANCE, not a target
```

⚠ **N MUST BE 1.** At N=5 the targets are contaminated by the unsearched policy decisions that
follow them, and the restraint signal comes out with the **wrong sign** — search appears to play
MORE, when at N=1 it plays LESS. Distilling N=5 targets teaches the opposite lesson.
`distill_label.py` **refuses to start** at any other interval without `--allow-interval`.

**MEASURED, and this is the check that the sign is right** (2-match smoke run, commit `6affdef`):

```
teacher play rate   0.2230
policy play rate    0.2518     <- search plays LESS. Correct sign at N=1.
teacher vs policy disagreement  0.2770
```

**Targets: the GATE and CARD heads only.** Card+gate search is +22.0pp; adding cell search adds
+3.3pp, and placement is separately measured as worth ~nothing (the perfect-aim arm is +0.07
sigma). The corpus records the teacher's cell for provenance; `distill_student.py` ignores it.

## 3. Corpus format

One row per **searched decision**. Every field the student's forward pass consumes is stored
verbatim, so the student is fed the identical tensors with no reconstruction step that could drift:

| key | dtype / shape | what it is |
|---|---|---|
| `obs` | uint8 `[n, 96, 64, 12]` | the DEGRADED observation — exactly `env._last_obs` |
| `hand`, `nxt` | float32 `[n, 10]` | `env.hand_vec`, `env.next_vec` |
| `elx` | float32 `[n, 1]` | `env.elixir_vec` |
| `thr` | float32 `[n, 52]` | `env.threat_vec` — the threat context |
| `teach_gate` | int8 | **teacher's gate decision** (0 wait / 1 play) |
| `teach_card` | int16 | **teacher's card choice** (−1 when waiting) |
| `teach_cell` | int16 | provenance only |
| `pol_gate`, `pol_card`, `pol_cell` | | the frozen policy's own greedy action — the FLOOR |
| `match`, `step`, `t` | | provenance, and the key the held-out split uses |
| `meta` | json | see below |

The playable mask is **rebuilt** from `hand`/`elx`/`card_elixir` rather than stored, so a corpus can
never disagree with the live masking rule.

`meta` records **checkpoint path + sha256, git commit, git dirty flag, interpreter path, torch
version, PYTHONHASHSEED, seed range, and every search setting**. Every one of those has produced a
wrong conclusion on this project at least once.

**Size**: 278 rows compressed to **0.1 MB** (20.5 MB raw). The observation is sparse and
`savez_compressed` handles it; an 18k-match-equivalent corpus is tens of MB, not gigabytes.
**Throughput**: ~760 rows/min single-process on a box already running the 8k trainer.

## 4. The go/no-go measurement — PENDING

**The question.** The teacher forks `SimEngine` and reads exact positions, exact hitpoints, the
opponent's real hand. The student sees the degraded observation. If the targets depend on what the
student cannot see, distillation caps out early.

**Encouraging but not sufficient**: handing the policy perfect perception bought it +0.00 sigma on
winrate, so its limitation is not information ACCESS — but that is a fact about the current
policy's ability to USE clean input, not proof these targets are learnable.

**The test.** `distill_student.py`, held-out **top-1 agreement with the teacher**, split **by
match** (never by decision — consecutive decisions are ~0.6 s apart and share nearly the same
board, so a row split leaks the answer). Two arms: `heads` (trunk frozen — is the signal already
linearly available?) and `full` (everything trains — is it learnable at all?).

**Two floors, both mandatory.**
* **base policy** — the frozen policy's own agreement with the teacher on the same rows. The number
  to beat.
* **majority class** — what "always WAIT" scores. The teacher plays on ~22% of decisions, so a gate
  accuracy near 0.78 is the class prior, not a result.

```
                              gate      card|teacher plays    joint
  majority-class WAIT         0.7756    -                     -
  base policy (FLOOR)         0.5892    0.4955                0.5719
  student [heads]             0.6012    0.8754                0.5852
  student [full]              0.6305    0.8665                0.6152
  (held-out 1502 rows / 337 teacher plays, split BY MATCH, 30-match corpus 4732 rows)
```

### VERDICT (2026-08-27): GO for the CARD head, NO for the GATE head.

The gap is not uniform -- it is localised, and the two heads answer oppositely.

* **CARD choice distils.** 0.4955 -> 0.8665/0.8754, **+37-38pp over the base floor**. What the
  teacher plays IS inferable from the student's degraded observation.
* **GATE timing does not.** 0.5892 -> 0.6012 (heads) / 0.6305 (full), **+1.2 / +4.1pp** -- and both
  sit far BELOW the majority-class floor of **0.7756**. "Always WAIT" predicts the teacher's timing
  better than either the base policy or the distilled student.

Mechanistically consistent: the teacher decides WHEN by rolling the future out; the student sees one
frame. Timing is exactly the information a single observation does not carry. Card choice is not.

/!\ **The gate number is confounded and must not be over-read.** Accuracy on a 22/78 imbalanced
binary rewards a predictor that never acts, and "always WAIT" is a policy with winrate 0. The honest
claim is *"card distils strongly; gate shows little gain and the metric cannot settle it"* -- NOT
"the gate is useless". A gate verdict needs a decision-value metric, not top-1 agreement.

/!\ **Distillation targets the head that already works.** The known failures live in the GATE:
`bank_to_six_then_bow` 0%, `never_rocket_their_king` 17%, gate collapsed to always-play. So card
distillation is real but is NOT expected to fix the banking/restraint failures on its own.

### Bug fixed while running this (uncommitted -> now committed)
`distill_student.py` crashed on every run: `forward_batch` passed `elx.squeeze(-1)` into
`playable_mask`, giving `(B,)` where the `(1,10)` cost row needs `(B,1)` to broadcast. Measured
corpus shapes: obs (N,96,64,12) u8, hand (N,10), nxt (N,10), elx (N,1), thr (N,52). The floors
printed before the crash, which is why the harness looked half-working.

**How to read it.** Student joint agreement well above the base floor ⇒ the targets are learnable
from the degraded observation and the corpus is worth generating at scale. Student ≈ base floor,
in BOTH arms ⇒ the teacher's edge lives in information the student cannot see, distillation caps
out early, and that is a clean negative worth more than a hopeful start.

## 5. Traps this work has to keep clearing

* **`PYTHONHASHSEED` is a no-op in `rollout_search.py`** — it uses `os.environ.setdefault` AFTER
  interpreter start. Two runs of the identical N=1 config gave **78.7%** and **80.7%**. Both scripts
  here **refuse to start** unless it is exported in the environment, and both record the value that
  was actually in force.
* **The interpreter changes the answer.** Bare `python` is the ROOT venv (torch 2.13.0+cpu), not the
  deck's 2.11.0+cu128: same seeds, same checkpoint, same tree, **43.0% vs 37.0% — 6.0pp at 2.62
  sigma**. Use `icebow\.venv\Scripts\python.exe`. Recorded in `meta.interpreter`.
* **Baselines drift with the tree.** `rs_base.json` no longer reproduces — commit `d9b20d6` moved the
  same checkpoint on the same seeds from 37.0% to 43.0%. Re-measure the baseline on the tree the
  corpus is generated from; `meta.git_commit` names it.
* **Corpus and student must share a code tree** (section 4q's confound in a new place).
* **The long run also carries the spell veto** (`ppo_spell_min_value`, shipped at 0.0 = OFF). That is
  a SECOND change. Decide deliberately whether to bundle it with distillation or sequence it, and
  say which in the run's own notes.

## 6. Next concrete step

```powershell
$env:PYTHONHASHSEED='0'
cd C:\Users\benpe\ClashBot
.\icebow\.venv\Scripts\python.exe research\sim_parity\scripts\distill_label.py `
    --matches 30 --out scratchpad\distill_corpus.npz
.\icebow\.venv\Scripts\python.exe research\sim_parity\scripts\distill_student.py `
    --corpus scratchpad\distill_corpus.npz
```
Fill in section 4's table from that output and write the verdict. **Only then** consider the full
corpus, and not while the 8k run is still on the box.

## 6. The coef A/B (2026-08-28): NULL, and the design was wrong

3 arms x 3 seeds, 700 matches each, FROM SCRATCH, corpus = 230 matches / 36,521 rows /
7,704 teacher-play rows (5 parallel shards merged with OFFSET MATCH IDS -- per-shard ids are
0..39 and the student holds out BY MATCH, so unoffset ids would group different matches together
and leak across the split). Scored on 200 fixed opponent seeds per checkpoint, greedy gate.

```
   arm   meanWR%    sd    totW/totN   plays%   sd
   0.0     0.00    0.00     0/600      1.47   1.19
   0.5     0.17    0.29     1/600      2.40   1.76
   2.0     0.00    0.00     0/600      0.07   0.06
```

### The winrate column is a FLOOR, not a measurement

**One win in 1,800 matches, across every arm.** Nothing can be distinguished at zero, so this
experiment does not answer whether card distillation helps. It answers only that a 700-match
from-scratch run lands below the benchmark's resolution.

/!\ **3x SAID SO IN ADVANCE and I designed into it anyway**: *"No arm clears untrained on
crowndiff. At this training scale (350 matches) PPO does not produce a policy the benchmark can
distinguish from a random init."* That section was read the same day this was planned. The fix is
not a bigger sample, it is a different STARTING POINT -- `--init` from a checkpoint that already
wins ~17%, so an effect has somewhere to register. Re-run before drawing any conclusion about
distillation itself.

### The one real signal: a high coef SUPPRESSES PLAYING

```
  coef 2.0 vs control:  plays 0.07% vs 1.47%   delta -1.40pp   sigma -2.03
  coef 0.5 vs control:  plays 2.40% vs 1.47%   delta +0.93pp   sigma +0.76
```

coef 2.0 is at 0.1 / 0.0 / 0.1 across all three seeds -- it has essentially stopped playing.
Directionally consistent, ~2 sigma, and it has a mechanism already documented in this repo: the
card-CE gradient reaches the SHARED TRUNK `z`, and `gate = Linear(z, 2)` reads that same trunk.
This is the representation-drift path `ppo_value_detach` was built for, arriving from a new term.

**Consequence for the long run: do NOT ship a large coef.** Whatever the re-run says, 2.0 costs
play rate on the head that is already the failure, and the gate is exactly what distillation was
measured NOT to be able to teach.

### Read the training-time numbers with suspicion, not as support

Cumulative training wins were 43 / 53 / 54 (control / 0.5 / 2.0), which reads as "distillation
helps" at ~1.0 sigma -- and the eval says every one of those policies wins 0% on fixed seeds. The
ordering also INVERTED mid-run: at 300 episodes coef 2.0 was the worst arm on rolling winrate
(0/0/0) and it finished with the most training wins. In-run rolling numbers on a sampled policy
are not a preview of the eval.

## 7. The corrected coef A/B (warm-started): STILL NULL, and the pooled test is a trap

Same 3 arms x 3 seeds x 700 matches, one change from section 6: `--init policy_BEST_m18000`, so
every arm starts from a policy that scores 17.0% +-5.2 instead of from scratch. Scored on 200 fixed
opponent seeds per checkpoint, greedy gate.

```
   arm   meanWR%     sd   per-seed WR        pooled%   plays%    sd
   0.0      6.00   5.07   [ 1.5,  5.0, 11.5]   6.00      8.63   0.46
   0.5      9.00   6.54   [13.5,  1.5, 12.0]   9.02      8.57   3.69
   2.0      7.17  10.32   [ 2.5,  0.0, 19.0]   7.17      4.97   5.11
```

### VERDICT: NULL. No arm clears the pre-committed 2-sigma bar.

```
  coef 0.5:  seed-level +3.00pp (+0.63 sigma)   <- the honest test
  coef 2.0:  seed-level +1.17pp (+0.18 sigma)
```

/!\ **THE POOLED BINOMIAL SAYS z=+1.98 FOR coef 0.5 AND IT IS WRONG.** Pooling all 600 matches
treats them as independent draws, but they come from THREE policies, and the between-seed spread is
sd 5-10pp -- larger than the effect being tested. Pooling discards that variance and manufactures a
CI ~3x too narrow. The unit of analysis is the SEED, not the match; that is the whole reason this
project's rule is 3 seeds minimum. **Do not quote the z. It is pseudo-replication.**

### The one reproducible finding: a high coef SUPPRESSES PLAYING

```
                      from scratch (section 6)   warm-started (here)
  coef 2.0 plays vs control    -2.03 sigma            -1.24 sigma
```
Same direction in two independent experiments with different starting points. Neither clears 2
sigma alone, but a reproduced direction is worth more than one arm's z. Mechanism is already in the
repo: the card-CE gradient reaches the shared trunk `z`, and `gate = Linear(z, 2)` reads that same
trunk -- the representation-drift path `ppo_value_detach` exists for.

### Do not read "every arm lost ground against its init"

All three arms (6.0 / 9.0 / 7.2%) sit below the 17.0% they started from. That is the WARM-START
CRITIC DIP, whose bottom 4a measured at ~1,700 episodes with most recovery by ~7,600 -- these runs
end at ~3,200. It is exactly why the comparison was pre-committed as arm-vs-arm only. It is NOT
evidence that training degrades the policy, and 4c already produced one false alarm by reading a
mid-dip checkpoint against its init.

### What this means for the long run

**Ship `ppo_distill_coef: 0.0`.** There is no measured winrate benefit at 700 matches, and the only
reproduced effect (coef 2.0 costing play rate) points the wrong way on the head that is already the
failure. Card distillation remains well-supported as a REPRESENTATION result (0.4955 -> 0.8754
agreement) and unsupported as a TRAINING intervention at this budget -- those are different claims
and only the first is measured.

What would actually settle it: a run long enough to clear the critic dip (>= ~7,600 episodes) so
the arms are compared after recovery rather than inside the hole, at 3+ seeds. That is a much more
expensive experiment than this one and should not be run on a hunch.

## 8. THE ANSWER: the term works, and card choice is not the bottleneck

The mechanism check the outcome check should have been preceded by. Same 9 warm-started
checkpoints from section 7, scored for top-1 CARD agreement with the teacher on the 36,521-row
corpus (7,704 teacher-play rows).

```
   arm   card|teacher-plays     sd        per-seed
   0.0        0.7975         0.0436   [0.7575, 0.7911, 0.8440]
   0.5        0.9031         0.0009   [0.9025, 0.9041, 0.9026]
   2.0        0.9064         0.0012   [0.9073, 0.9069, 0.9051]

   coef 0.5 vs control  +0.1055  (+4.19 sigma)
   coef 2.0 vs control  +0.1089  (+4.32 sigma)
```

**The distillation term unambiguously works.** +10.6 points of card agreement at 4.2 sigma, and the
variance COLLAPSES: the three distilled seeds land within 0.0016 of each other against the
control's 0.087 spread. The term is doing precisely what it was built to do, and it does it
identically at both coefficients.

### Put that beside the winrate on the SAME checkpoints

```
  card agreement   +0.1055   +4.19 sigma     <- the intervention fires
  winrate          +3.00pp   +0.63 sigma     <- and nothing happens
```

**Card choice is not the bottleneck.** We can now make the policy pick the teacher's card 90% of
the time, and it does not win more. That is the cleanest statement of the result this whole line of
work has produced, and it is only visible because the mechanism and the outcome were measured on
the same artifacts.

### Therefore the search's advantage is in the TIMING, and that is the one thing that will not transfer

The chain now closes:
* search takes the FROZEN policy from 37.0% -> 85.7%;
* its CARD choice is learnable from the student's observation -- 0.4955 -> 0.8754 held out, and
  0.7975 -> 0.9031 inside a live PPO run at 4.2 sigma;
* teaching the card choice moves winrate by nothing;
* so the advantage lives in the GATE -- which measured 0.5892 -> 0.6012, BELOW the always-WAIT
  floor of 0.7756, i.e. not recoverable from a single frame.
A teacher that decides WHEN by rolling the future out cannot hand that over to a student that sees
one frame. The card head was the transferable half, and transferring it is worth ~0.

### DO NOT RUN THE LONGER A/B

It was scoped at 2 arms x 8 seeds x 1,700 matches, ~8 hours unattended, with a minimum detectable
effect of ~6pp. It is now pointless: we know the intervention fires (4.2 sigma) and the outcome
does not follow (0.63 sigma). More seeds would sharpen a null whose mechanism is already explained.
Spend the night on the GATE instead.

/!\ IN-SAMPLE caveat, stated and bounded: the distilled arms trained on this corpus, so 0.90 could
carry memorisation. It does not change the conclusion -- a student trained from scratch on this
corpus scored 0.8754 HELD OUT, so ~0.90 in-sample is the expected value of real learning, not an
artifact. And the conclusion rests on the CONTRAST with winrate, which memorisation cannot explain.
