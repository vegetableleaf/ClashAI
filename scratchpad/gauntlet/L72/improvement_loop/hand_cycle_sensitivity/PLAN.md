# Fixed-weight public hand cycle sensitivity

The first paired hand trial and cached decision diagnosis are complete. The hand
model regressed in gate/card decisions even on full/no-issue hand estimates. Its
training contrast blanked both newly derived cycle information and revealed card
identities, so it does not isolate the effect of the added cycle-state fields.

Use the two fixed final checkpoints from that rejected trial, EVAL only. On eight
prospectively fixed original TRAINING batches (0,125,...875,128 draws each), retain
the original mirror flags and compare full hand features with derived cycle fields
censored to unknown. Keep revealed identities, issue/Mirror/event-quality flags and
ALL existing base public inputs, including opp_cycle, unchanged. Thus this probes
the added branch, not all cycle information already present in the base model.

Exactly4096 model-row views:2models x2conditions x1024draws. Save every head logit,
forced-expert-card aim distribution, row IDs, transformed features and reductions.
No backward/optimizer/new checkpoint, development/confirmation/old-validation
prediction, native games or live changes. Rejected weights stay fixed and ineligible
as learning parents. The matched blind model must be exactly insensitive, a negative
control. The censored condition may be out of training distribution; this is a
functional sensitivity measurement, not a replacement policy or improvement claim.

Collect once under the common serial chain lock; independently regenerate the
entire original sampling schedule, source labels/features, censorship, head choices
and every scalar/group/per-replay reduction. Review outside the bound leaf, publish
qualified results. No new-model Discord report. Preserve failures before diagnosis.
