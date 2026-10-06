# Deterministic hand pooling successor (before any training)

The v3 qualification reached the final diagnostic permutation check and failed
torch.equal after reversing eight tokens. Keep check_model_v3.py, the original
pipeline/model_hand_belief.py and its133.786720s failed receipt unchanged. No
qualified checkpoint or optimizer update exists from any of these probes.

Separate model_hand_belief_v2.py uses architecture public_hand_belief_v2 and
hand_belief_version2. Before embeddings/pooling it orders the eight input tokens
lexicographically across their six PUBLIC columns, using stable sorts. This
guarantees the same reduction order for any permutation, including duplicated
card diagnostic inputs. It adds no parameters, tactical rule or private input.
Both matched arms use this same successor. live_hand_v2.py and live_play_hand_v2.py
are the separate opt-in companion; original sources remain untouched.

All MODEL_METRICS.md requirements remain, including EXACT initial heads/loss and
permutation invariance. No approximate tolerance substitutes for the failed check.
check_model_v4.py binds all three prior failed receipts and performs the full
initial qualification for the changed implementation. Lightweight canonical-order
positive, permutation and changed-field controls run first; no model inference or
optimizer in those controls. Learning PLAN/recipe retains all draws, seeds,
parameters, optimizer budget, original-label/loss and acceptance criteria; only
this prelaunch engineering successor is substituted before any prepared binding.
