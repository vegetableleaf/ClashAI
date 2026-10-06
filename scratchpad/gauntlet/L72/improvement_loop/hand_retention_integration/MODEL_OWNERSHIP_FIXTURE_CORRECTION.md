# Live ownership fixture correction

Preserve check_model_v2.py and its114.418207s failed receipt/output. It got past
the repaired coordinates and rejected the next privacy fixture: hand_deck_indices
[99,99,99,99] on the opponent makes BOTH sides appear to have visible hands.
my_side_of correctly refuses that ambiguous reader ownership. This is not evidence
that private opponent values influenced a valid decision.

A separate lightweight check_live_hand_fixture.py now verifies real HandGenPilot
row construction with normal ownership markers; hidden opponent elixir/deck/next
and arbitrary hidden_hand values do not change ANY model input or audit. A separate
negative case explicitly requires dual-visible-hand rejection. Future hand events
are excluded and reset clears hand knowledge. l72-hand-live-fixture passed7.929928s.

check_model_v3.py preserves the model/parity/loss/gradient/roundtrip tests, uses
that valid privacy fixture, and counts the malformed-ownership rejection separately.
Original failed probes remain failed and are bound in the eventual qualification.
No model/source/runtime behavior, labels, numerical tolerance or acceptance floor
was changed. No optimization has run.
