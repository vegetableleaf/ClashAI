# Frozen forecast readiness definitions

Exactly213995 original training row IDs/rep/side/tick,1573replays; no train/dev
reallocation. Fixed horizon400ticks, maximum sighting delay100ticks, history16.
These are prospective instrument windows, not measured mechanics/parity limits.

Inputs: last16 opposing accepted-or-unspecified public sightings at tick<query,
ordered by(tick,original stream index), left padded. Columns card_vocab ID,
query-minus-event tick, gap_before flag, identity_unknown flag. No event at query
or later, command oracle, hidden deck/hand/elixir, future target, response descriptor
or replay/row identity is a neural input. Base identity uses card_key; no new Mirror
inference. Copied public identities remain copied identities. Keep completed
opp_hand/opp_hand_quality tokens exactly; IDs are bookkeeping only. Duplicate
public records are retained as uncertainty rather than silently deduplicated.

Targets: accepted nonability command events with card truthy, engine_tick (fallback
tick), opposite side. Select earliest command with query<tick<=query+400. Select
earliest public sighting with query<tick<=query+500. Require singleton timestamps,
known base identity, no target Mirror, no sighting gap/unknown flag, same card and
0<=public_tick-command_tick<=100. The sighting must match exactly one accepted
same-card command in [public_tick-100,public_tick], namely the selected command.
A sighting uniquely attributable to a command at/before query is pending earlier
activity, not the forecast target. No hidden state repairs a mismatch.

Exclusive status precedence:0eligible;1no command/full horizon;2no command/right
censored;3ambiguous next command;4unknown command;5Mirror command;6no sighting/
full delay window;7ambiguous next sighting;8untrusted or unknown sighting;9pending
prior sighting;10wrong first sighting card;11delay out of bounds;12nonunique or
wrong command join;13no command but sighting within400;14sighting window censored.
For no-command rows, status13 precedes1/2 when applicable. Window-complete flag
end_tick>=query+400 is kept for EVERY status. A seen positive can qualify in a
truncated overall window. Only status0 has candidate forecast_class; other rows
have -1. No-event rows are retained diagnostics, not activated negative targets.

Save every command/public index and join count, candidate card/ticks/delay, plus
status and forecast_class. Report all statuses, target card, delay, public quality,
inferred target in/out/unknown, eligible unique commands and every replay. Overlap
means rows are not independent opportunities. Report missing coverage by card;
selective visibility cannot be described as the full tactical distribution.

Exact row/feature/target/integer/per-replay/source equality, no tolerance. At least
15 positive status fixtures,3 causal/private/future invariance controls, and10
independent corrupt-result controls. No model or auxiliary optimization until a
future grouped comparison/control/budget/selection recipe is registered.
