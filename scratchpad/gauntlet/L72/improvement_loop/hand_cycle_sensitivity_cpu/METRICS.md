# Frozen sensitivity definitions

Original trial seed2026100613,1000 batches128, indices0:1000:125. Regenerate all
draws/mirror flags, retain1024 selected draws with duplicates and original ordering.
Features/labels come from the original training-only source IDs. Mirroring uses
the original qualified augmentation; opponent hand tokens are nonspatial.

Censor every revealed token to(card,0,0,1,0,1); padding stays allzero. Set only
quality full_hand column1 to0, preserving all other quality and base input bytes.
No hidden truth or future response descriptors. Record both feature conditions.

For each model/condition save gate logits, four card logits, eight wait logits,
value logits,2304 forced-expert-card cell logits and global embedding. Pads may
be negative infinity only in card/wait logits, identically in both conditions;
all other numbers finite. Original affordability is unchanged and independently
checked. Source weights exactly unchanged, parameter gradients empty.

Report censored-minus-full: per-head signed mean, mean absolute and maximum
absolute logit differences (finite entries only); argmax changes; affordability-
qualified gate>.35 and chosen-card changes; forced aim cell changes. Report all
rows, PLAY/WAIT, full/partial/full-no-issue/issue/zero-reveal, all eight expert card
groups, and every replay. No correctness threshold or action-frequency objective.
These are correlated sampled TRAIN views and not Rocket population evidence.

Exact IDs/labels/censorship/choices/negative-control logits are required. Floating
scalar reductions independently match at rtol1e-10/atol1e-12, prospectively for
this diagnostic only. Two positive synthetic controls and at least eight distinct
corruptions must be rejected. No old model floor/tolerance changes.


## Registered CPU successor

Original CUDA collection failed exact blind-output equality after2048 views;
original source, failed receipt and both caches remain FAILED and hash-bound.
This successor uses CPU, one thread and deterministic algorithms, preserving the
same1024 original draws/mirrors, both checkpoints, conditions, exact negative
control and all diagnostic definitions. It is a new runtime-qualified probe,
not a claim that the old failure passed or its numerical cause is established.
Convert both operands to float64 BEFORE delta subtraction. Existing float64
reduction tolerances stay unchanged. No extra training or checkpoint selection.
