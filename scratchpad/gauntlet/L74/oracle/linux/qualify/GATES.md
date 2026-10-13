# Gates: ORACLE v4 preparation

OWNS: scratchpad/gauntlet/L74/oracle/linux/qualify/**, scratchpad/gauntlet/L70/reader/oracle_160402012/v4-readonly.json

Scope: offline preparation of a read-only worker kit; no runtime qualification is claimed.

- [x] G1: Observer, binding resolution, identity checks and results reject unsafe or ambiguous inputs
  CHECK: python scratchpad/gauntlet/L74/oracle/linux/qualify/test_qualify.py
  EXPECT: QUALIFY_OFFLINE_TESTS_OK
  EVIDENCE: Verified locally; VERIFICATION.json checks[0]: exit 0, marker matched, output SHA-256 9d0a8cb87e1cfbf50e9c983a1687cdb463a01d3957ce5bee6127e212f0d02790; 13 synthetic tests, no target.

- [x] G2: Public files contain no private addresses and private inputs remain ignored
  CHECK: python scratchpad/gauntlet/L74/oracle/linux/qualify/verify.py
  EXPECT: QUALIFY_PRIVACY_OK
  EVIDENCE: Verified locally; VERIFICATION.json checks[1]: exit 0, marker matched, output SHA-256 0b9cc2a519a2d652c551001e75f33eb8219e50bcb9980074cc74c846896274f3; ignored/untracked binding and supplement checked.

- [x] G3: Deployment plan covers exact image, split identity, isolated build/install and failure stops
  EVIDENCE: Manual review of README deployment order and private build exclusion; original upstream bridge unchanged; preparation only. See VERIFICATION.json manual_review.deployment.

- [x] G4: All lifecycle entries and all unproven presentation sites have bounded evidence requirements
  EVIDENCE: Manual review: README has all required lifecycle IDs and a separate row for each unproven site; verify.py independently checks exact ID coverage. See VERIFICATION.json manual_review.coverage.

- [x] G5: Worker handoff distinguishes local checks from unrun Android build and runtime checks
  EVIDENCE: Manual review: README and VERIFICATION.json distinguish passing offline checks from unrun Linux shell/build and Android runtime work; shell-start error retained, zero patches qualified.
