# SCALE — offline IL capacity/input measurement

ETA: **12–24 hours on one L40**, an unmeasured planning estimate. The first epoch
logs throughput and remaining epoch-cap time. No pod has been launched by this
change. No capacity/input verdict exists until the full job finishes.

Run from a prepared Linux checkout, offline:

```bash
SCALE_PY=/workspace/venv/bin/python bash scratchpad/gauntlet/L74/scale/run_scale.sh
```

The job writes `/workspace/results/SCALE/SUMMARY.txt`, `DONE`, all four selected
checkpoints, per-epoch JSONL/history, train/test row predictions, metric tables,
paired CIs, source/data hashes, and native alignment audit. `DONE` means ended;
read `Status`. The launcher also writes failure receipts for missing Python,
dependencies, test failures, GPU preflight failures, and catchable termination.
It refuses previously used output and a busy GPU; it does not kill processes.
Power loss/SIGKILL cannot run an EXIT handler.

Prerequisites: existing torch with L40 CUDA support, numpy, pytest, Bash/flock,
one visible idle L40, repository catalog/config files, and at least **25 GiB
free disk** plus approximately 16 GiB available host RAM. No install, download,
SSH, notification, deployment, or live-script step exists. The source NPZ is
465,928,463 bytes compressed; the run spools its large arrays to disk for bounded
memory access. Cache files are retained for diagnosis, never deleted by this job.

Keep these existing assets at their checkout-relative paths:

- `icebow/data/pipeline/gen_dataset_v32_fv5.npz` (3,517,863 rows, 14,661 replay tags).
- All six native corpora named by the NPZ metadata: `corpus_gen_pilot/s0_public_v1`
  through `s3_public_v1`, and `corpus_v6/{hogeq,icebow}_public_v1`, under
  `scratchpad/gauntlet/ext/`.
- The existing pipeline's local card catalog and derived data.

For relocated corpora, pass six `--corpus /absolute/root` arguments in the
original metadata order. Full preparation requires every dataset replay and
fails on a missing recording or unmatched effect; no silent sample reduction.

## Matched recipe

`pipeline/train_gen.py` is the existing generalist trainer; the class is
`pipeline/model_gen.py::GenModel`, built on `model_v3.py::S1Model`. This harness
reuses `train_gen.GenRows`, `train_gen.losses`, the mirror augmentation, and the
model directly. It adds experiment-local early stopping and richer reporting;
it does not modify `pipeline/`.

| Arm | d | layers | Only change from A |
|---|---:|---:|---|
| A | 128 | 4 | Baseline |
| B | 256 | 4 | Width |
| C | 128 | 6 | Depth |
| D | 128 | 4 | Two area-token channels describing one feature: observed age + known mask |

With the actual 124-card vocabulary, parameter counts are A **1,519,656**,
B **4,706,088**, C **1,916,200**, D **1,519,784** (measured on CPU).

All start from scratch at seed 0; d_c=64, heads=4, dropout=.1, batch=256,
AdamW lr=3e-4/wd=.01, OneCycle pct_start=.05, clipping=1, mirror probability=.5,
BF16 training, and original unweighted five-head IL loss. No warm-start, deck
reweighting, label change, or extra source data. All train rows from original
split=0 are used; each epoch drops the same final incomplete batch, like the
original trainer. Identical NumPy RNG streams fix row order and mirror draws.

The original split=1 is partitioned **by replay tag** into selection/test using
SHA256(tag)'s first-byte parity. This protects the final paired test from
checkpoint selection; neither held-out partition enters training. A fixed
seed-0 sample of up to 30,000 selection rows selects the lowest loss checkpoint.
Maximum 20 epochs, minimum 5, patience 3, minimum improvement 1e-4, applied
identically to all arms. Actual stop epochs may differ. Original `train_gen`
has a fixed epoch cap and best-checkpoint selection, but no patience mechanism.
`split_rows.npz` stores the exact common row IDs.

## Richer-field evidence and public boundary

The bounded local audit (`local_audit/field_audit.json`) inspected every sampled
and play frame of one native replay per source corpus. All six had compact
9-field entities: side, x, y, name, HP, max HP, kind, native card ID, entity ID.
No per-unit stun/slow/freeze/rage timers or per-unit hero readiness appeared in
that sampled schema. Do not generalize this bounded scan to every stored frame;
the pod audits the full corpus as it constructs aligned inputs.

fv5 already includes HP fraction/known, unit form, projectiles with target/TTI,
lingering areas with remaining-time/known, public opponent plays, and own-ability
tokens. Native area exports additionally contain `source_elapsed_ms`,
`source_life_ms`, `source_remaining_ms`, category and tracking identity. These
source timers are marked unvalidated; **D does not feed them to the model**.

D adds **continuous observed area age**, derived from sampled-frame timestamps
and public area identity: `(current_tick - first_continuously_visible_tick) *
0.05 / 30`, clipped to [0,1], plus a known mask. This is time seen, not true
engine age. Disappearance resets the track; missing/duplicate identities or
ambiguous colocated tokens mask the age. IDs/categories are join keys only,
never numeric model inputs. Only frames at or before the dataset row are used.
It reads no players, opponent hand/deck/elixir, ability readiness, or future
events. Tracking IDs encode continuity of a visible object; no hidden state is
derived from their values.

`features.add_richer_inputs(..., richer_inputs=False)` returns the identical
batch object. A/B/C use original six-channel effects and unchanged GenModel.
Only D sets the flag and uses eight-channel effects. The two new projection
columns start at zero; all original initial weights are copied. D has 128 extra
parameters. Its checkpoint carries a dedicated architecture marker so the
normal pipeline loader rejects accidental deployment; use `scale.construct`
with the stored arm configuration for offline reload.

The local audit aligned 1,514 rows / 413 area tokens; 405 known ages, 353 nonzero
ages, 183 bridge-slice rows. This demonstrates usable stored evidence, not an
improvement in imitation.

## Metrics and decision rule

Report both all-deck and exact icebow-deck results. The **primary verdict is
icebow overall**. Groups include overall, 1x/2x/3x, bridge crossing, and each
phase intersected with bridge crossing. Standard ladder phase boundaries are
120 and 240 seconds (ticks 2400/4800 at 20 Hz).

Bridge crossing means the same living enemy non-tower body crosses y=16000 in
native x corridors [2500,6500] or [11500,15500] between adjacent sampled frames
at most 20 ticks apart, with displacement <=2500 native units. A push can be
one or multiple bodies; rows within the following 20 ticks are included.
Presence, a fresh spawn, and a large teleport alone do not count. This is an
explicit sampled-frame event definition; exact sub-frame crossing time and
large-push size are not inferred. It is a reporting mask, never an input.

Card top-1 is pro hand-slot agreement on valid PLAY rows. Cell top-1/top-5 use
the original 2304 half-tile lattice and are teacher-forced on the pro card.
Gate accuracy uses all rows at logit>0. Every group includes denominators;
empty groups are null, not zero. Loss is globally aggregated per head with
the same CE/BCE weights as training (not an average of batch means).

Selected checkpoints are also evaluated without augmentation/dropout on the
same seed-1 sample of up to 30,000 train rows. Gaps are train-minus-test agreement
and test-minus-train loss, with component losses preserved. These diagnose
fitting; a gap alone does not establish an underfitting cause.

Paired bootstrap resamples entire replay clusters, keeping both player sides
and repeated rows together, 4,000 draws at seed 740. Metrics are row-weighted
within each resample. Capacity helps only when B or C has **both card and cell
top-1 lower CI >0** versus A on icebow overall. B/C use 97.5% intervals to account
for trying two capacity arms; D uses 95%. Top-5, gate, phases and bridge slices
are diagnostic, not alternative ways to pass. Otherwise: no evidence. A single
training seed does not estimate seed-to-seed variability or prove live benefit.

CPU and GPU latency use the same median-unit-count icebow test row, batch 1,
FP32, 20 warmups, 200 measured decisions, CPU threads=1 and CUDA synchronization.
The timed path includes encode, gate/card heads and chosen-card cell argmax;
it excludes observation building, transfer, emulator and network overhead.
Report mean/p50/p95 and hardware metadata. RL actor throughput and complete live
loop latency can differ.

## Local verification

```powershell
research/ext/Royale/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L74/scale/test_scale.py -q -p no:tmpdir -p no:cacheprovider
```

Tests use only CPU, including a tiny four-arm optimizer/selection/checkpoint/
evaluation/report round-trip and failure receipts. The real-data audit is
separate and CPU-only. `--allow-cpu-smoke` labels toy runs SMOKE ONLY; it is not
the requested L40 measurement. Changes remain uncommitted.

Local Git Bash cannot start in the managed Windows environment (CreateFileMapping,
Win32 error 5), so Linux launcher execution is pending. The initial pytest run
also encountered pytest's restrictive temporary-directory ACL; tests now use
their own ordinary workspace fixture directories. No permission changes were made.
