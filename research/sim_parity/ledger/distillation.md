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
  majority-class WAIT         PENDING   —                     —
  base policy (FLOOR)         PENDING   PENDING               PENDING
  student [heads]             PENDING   PENDING               PENDING
  student [full]              PENDING   PENDING               PENDING
```

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
