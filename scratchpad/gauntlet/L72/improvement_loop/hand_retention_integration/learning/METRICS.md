# Frozen paired recipe and comparisons

- Eligible parent SHA c0ba1ab910df50fdcbe1fcf4191aedd584c86fe94c5a6d3248359bda059db419.
- Architecture public_hand_belief_v2, feature_version5, hand_belief_version2.
  Pre-optimization successor canonicalizes token order to preserve exact permutation invariance; same parameterization.
  Identical initialized tensors seed2026100613. Two modes differ only true/false
  hand_information_enabled. Base dropout .1 in training, EVAL for predictions.
- Each arm: 1000 updates x128 draws sampled uniformly with replacement from
  exactly213995 original training rows. NumPy seed2026100613: choose128 then
  random()<.5 for the whole-batch mirror, repeated1000. Torch seed reset2026100613
  per arm. Original augmentation and five losses, lattice labels unchanged.
- Fresh AdamW base1e-5 / new hand_token and hand_context parameters1e-3, wd.01,
  clip total gradient norm1, FP32. These same groups apply to BOTH arms. No
  optimization in preparation/probe. Final1000 only, no best-checkpoint selection.
- V1 independently regenerates1000x128 draws/flags, validates finite five-part
  logs, unchanged tensor schemas, fixed buffers, exact stored mode, every saved
  Adam state finite and step1000, original parent and source bindings.
- E1 exactly54723 original development rows per arm. Reuse corrected-input R1e
  and ordinary_v5 cached predictions; no new baseline inference. Gate>.35,
  original affordability, argmax card/cell, continuous distance<=1 tile exactly.
- Candidate must gain >=5pp Rocket forced aim, >=2pp full Rocket and >=2pp late
  Rocket vs BOTH ordinary_v5 and same-budget hand_blind_control_v5. General card
  no worse than-.5pp; Barrel correct no decrease/wrong no increase; Witch,
  Night Witch, Furnace, defense and late-all full action counts nondecreasing.
  All original groups/denominators/replay-paired counts/PLAY-WAIT decomposition.
  All filters required; degraded control cannot rescue failure against v5.
- Additional audit slices: all six sequence statuses, truncated/not truncated,
  opponent already publicly revealed, all eight response cards, full/partial hand
  estimates and issue/no-issue. Full action/forced aim/card/correct PLAY/WAIT and
  predicted spending of the later response card, paired per replay. Descriptive
  only: no new selection floor, future-response reward or causal counter label.
- Raw original and corrected labels, source membership, every row/cache choice,
  original masks and all scalar/per-replay results reconcile. Positive and corrupt
  log/cache controls required; first/last256 total and component loss means.
- Passing development permits consideration of further experiments, not acceptance.
  Same-runtime gameplay, material/statistical/component/physical/public evidence,
  Q4/Q5 and final N2-N7 remain mandatory. R1e corrected-input cache is not original
  live-input R1e. No proof of profitable holding from imitation agreement alone.
