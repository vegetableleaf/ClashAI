# Owner tower-session triage

Read all nine completed live_play_20261006_14*.jsonl logs and matching navigation
logs, pinned by SHA before analysis. Confirm each exact checkpoint and options.
No inference, reconstructed hypothetical policy input, optimization, game actions,
or expert labels. These owner-bot trajectories identify failure cases for research.

Count attempted, confirmed, unconfirmed and unresolved plays; require exact
one-at-a-time chronological receipt joins and decision-tick/card/hand-slot joins.
Charge a confirmed card its decision's public own-hand cost, separately from
ability costs (log ability receipts, with cost unknown here). Keep raw observed
elixir separate from model-projected elixir. Low snapshot elixir alone does not
establish inefficient play. Record decision latency/backlog and forced spending.

For every attempt preserve public bodies, projectiles/effects, aim, gate, current
hand, previous confirmed cards within60ticks, receipt, next public decision's
actual elixir/delay, and the next query at200ticks (up to40tick sampling gap).
Record target card return time and first later own princess HP loss while absent.
Unknown/censored paths remain unknown. A loss while a card is absent is a review
signal; it does not establish that holding that card would prevent the loss.
Every play stays in the output; fixed review subset is Log/Tornado with <=1
visible enemy body and >=2 friendly bodies. This subset is descriptive and will
include sensible plays. No automated waste labels or inference from body count.

Navigation outcomes are joined by time: the first later nav outcome before the
next live match. Preserve missing result and never treat a stopped session as a
recorded loss. No trophy count exists in these logged outcome records; climbing
must later use explicitly captured starting/ending trophies and net changes.

Independent verification must reconcile raw event/receipt/card/cost counts for
all nine matches and require mutation controls. Inspect concrete review cases.
No new model report; original model report already delivered.
