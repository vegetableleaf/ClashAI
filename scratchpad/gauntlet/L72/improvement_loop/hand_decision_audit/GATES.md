# Cached hand decision audit gates

OWNS: scratchpad/gauntlet/L72/improvement_loop/hand_decision_audit/**

- [x] C1: New cached row effects and complete replay summaries are source-bound.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_decision_audit/collect.py
  EXPECT: HAND_DECISIONS_COLLECTED
  EVIDENCE: l72-hand-decisions-collect.json, exit0/matched,3.493583s; collected.json.
- [x] V1: Independent scalar reconstruction matches every row and count and rejects corruptions.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/hand_decision_audit/verify.py
  EXPECT: HAND_DECISIONS_VERIFIED
  EVIDENCE: l72-hand-decisions-verify.json, exit0/matched,18.194326s; verified.json,2positive8corruptions.
- [x] R1: Review binds completed evidence and explains limits and next work.
  EVIDENCE: l72-hand-decisions-reviewed.json, exit0/matched,.631120s; reviewed.json and REVIEW.md.
