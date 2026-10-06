# Proposed fixed-R1e body-visibility diagnostic

Status: **PROPOSED_UNEXECUTED**. October 6, 2026. This document registers no
execution and changes no policy, reader, live configuration, source gate or
checkpoint. Complete the separately prepared fresh captured-batch replay before
any altered-input inference. Preserve both capture latency failures and their
frozen sources. Live capture remains unqualified under the original timing floors.

## What the existing capture can establish

The 24 cases in decision_capture/support.py::fixed_frames are engineering fixtures
built from pipeline/tests/test_live_mem.py::FRAME. They use the Training Camp deck
Knight, Goblin Hut, Goblins, Arrows, Fireball, Giant, Musketeer and Mini PEKKA. Their
hand indices are [2,1,6,7], with one padding variant. Rocket, Log, Tornado, Tesla
and X-Bow are unavailable. There is one friendly Knight and no enemy troop push.
Six cases contain a synthetic incoming Goblin Barrel; four of those also have
the synthetic named Hero objects. Sixteen cases contain the Hero, eight do not.
The original decision split is 6 PLAY, 6 no-affordable WAIT and 12 affordable WAIT.

IdentityPilot normalizes named characters before BOTH observe() and row(),
including the stored motion frames. Captured body tensors contain the exact
IceWizardHero; the FloatingCube and IceCube are excluded and retained in raw
public metadata. Thus these tensors already use the qualified identity adapter.
The current production card-ID-only alias maps every alive 203000023 object to
IceWizard/form2. It can add false full body tokens and inflate own ability
controller counts. The still older omitted-ID input discarded the shared ID.
These three representations must have separate names and provenance.

The existing 24 cases may be reused in full as an optional representation control.
They cannot supply a tactical verdict on Icebow defense, counter spending,
Rocket cycling, X-Bow selection or a profitable decision to WAIT. Do not spend
another experiment presenting their sensitivity as tactical progress.

## Exact optional representation control

After fresh replay succeeds, a separately registered control could compare the
saved input with **friendly Hero body-token visibility suppressed**. The sole
allowed alteration is mask[0,j]: True -> False for independently identified
friendly IceWizard/form2 body rows. Every byte of tok, unit_form and the other
13 input tensors remains unchanged. No compaction, sorting, new body creation,
padding replacement or scalar/history modification is permitted. All original
conditioning kwargs and the original first/second forward distinction remain.

Identify rows by mask=True, tok class=the bound ice_wizard vocabulary index
(currently 2), tok side_mine=1, unit_form=2 and is_spell=0. For this fixture corpus,
independently join to the sole alive raw object named IceWizardHero with status
ok, matching side, HP fraction and oriented coordinates. The three earlier
fixture frames are identical in position, so their measured extrapolated motion
is zero. Freeze and verify all 24 row memberships before model outputs; require
one eligible row in each of the 16 Hero cases and none in the other eight.

Source justification: model_gen.py::encode_gen passes the body mask and forms to
model_v3.py::encode. That encoder substitutes the padding class, multiplies unit
embeddings by the mask, adds only those masked embeddings to spatial patches,
and masks the unit positions as attention keys. Mask-only suppression therefore
removes that body's contribution while preserving the observed features verbatim.
Zeroing tok/unit_form together with the mask has the same real-number masking
interpretation for finite valid inputs. Floating-point signed zeros and reductions
do not justify assuming byte-exact equivalence between those two constructions.
Choose mask-only and do not introduce a second unneeded alteration arm.

The body-only intervention deliberately preserves own_ability, own and opponent
play history, public elixir estimates, projected objects and the hand. Its scope
is dependence on the spatial body channel. It cannot reconstruct the complete
older reader path, which also affected observer/controller state. Do not label it
as original live pre-repair replay. Do not manufacture a production-alias arm by
cloning the Hero token into Cube slots: cubes have distinct raw positions/HP and
unqualified combat roles, and arbitrary duplication changes the representation.

Required unchanged controls: all eight no-Hero inputs remain byte-identical and
must reproduce every saved head exactly; an explicit copy/no-edit construction
must preserve all 16 input tensors and kwargs. The full new corpus must preserve
the original 24 records, 42 saved forward calls, six no-affordable cases, padding
infinities, the six Barrel feature blocks and both observer orientations. The
independent validator must reject wrong-side/wrong-form/wrong-class targeting,
altered history/scalars/projectiles, wrong conditioning, omitted cases and altered
no-Hero masks. Hash original records and assert unchanged after collection.

## Next meaningful source and case preparation

Prepare a public Icebow case set before tactical inference. The shortest route is
an archival readiness check, followed by bounded passive public collection only
where source coverage is missing. No existing collection is to be rerun.

Available evidence inspected for this proposal:

- reader_character_identity/passive_v2_raw.jsonl already contains 120 named raw
  reader frames, ticks 2968 through 4158, with coherent/active markers, sequence,
  public entities/projectiles/effects, and own visible hand/deck/form fields.
  Its first own deck is Icebow, side1, native IDs
  [26000000,26000023,27000006,28000012,27000008,28000003,26000010,28000011], forms
  [1,2,1,0,0,0,0,0], hand indices [6,5,3,7]. This is a useful existing public
  identity/pressure source. The mid-match start leaves the earlier observer and
  confirmed own-action history unproved; the interval also ends before overtime.
  Source readiness must independently inspect event continuity and available
  own receipts before deciding what exact state it supports. A raw file can
  contain private player fields: the preparer must explicitly select the public
  whitelist and own side only, never forward or serialize the other player block.
- The nine owner tower logs and the hash-bound triage_details.json preserve real
  hand/card costs, accepted actions and public decision snapshots. Among that
  nine-match set only live_play_20261006_140419.jsonl has event=frame records.
  live_play.py's frame schema keeps tick, side, own elixir and entity tuples but
  omits the complete hand/next, named characters, projectile/effect stream and
  full observer state. It also includes opp_elixir_true_EVAL_ONLY, which must be
  excluded explicitly. A frame-bearing log alone cannot establish exact replay.
  The later live_play_20261006_145935.jsonl also has frame records and requires
  the same schema assessment; do not infer completeness from its event name.
- decision_capture's existing fixture source can create exact engineering inputs
  with declared histories. A new engineered Icebow pressure suite is possible if
  archival coverage is inadequate, but its output remains fixture sensitivity;
  engineered opponents/actions must never become claimed historical outcomes or
  expert labels. Keep it separate from real match cases.

For real cases require an uninterrupted causal public prefix from a documented
reset, or an exact saved causal observer state plus the subsequent prefix. Bind
all public entity identities, positions, HP/maxHP, observer side, timestamps and
coherence; own hand/next/deck/forms/elixir; own confirmed deployments and ability
receipts; original decision settings; and prior motion frames needed for the
26-tick extrapolation. PublicObserver also maintains opponent sightings, dedup
state, elixir estimates, object motion/TTI and ability histories. A final tensor
snapshot cannot recover these states. Never invent earlier plays, reset opponent
elixir to a guessed value in mid-match, or backfill unrecorded own confirmations.
Historical reproduction additionally requires the exact original row()/decide()
invocation schedule, including warmup, skipped decision frames, confirmation and
ability updates, reset boundaries, and the order of operations within a tick.
obs_contract.from_engine uses history.setdefault(entity_id, tick) during row()
construction; observing the same raw frames without the same row calls can yield
a different history state. Feature4 body_only_board masks age/deployment from
its tokens, but that does not justify changing the recorded call schedule or
claiming exact observer/history reproduction. live_play.py observes every active
coherent frame, performs an initial warmup decide, processes confirmations, then
applies newest-frame/advanced-tick and pending-action decision guards. Freeze
those details from the actual source and event sequence before replay.

If the archival prefix fails, propose one bounded passive named-public prefix
from match start alongside owner-authorized play, with its own read/latency cap
and no action path. Confirm it does not conflict with the single-reader/client
constraint or disturb the owner worker. Keep all writes outside the policy's
decision path. Offline tensor construction can use the complete saved prefix;
failed synchronous/async capture latency does not authorize live activation.
Any incomplete-history arm must explicitly mark unknowns and disclose its changed
observation assumptions; exact historical-policy reproduction stays unestablished.

Freeze case IDs, grouping and exclusions before looking at R1e outputs. Include
real friendly Hero defenders with pressure; otherwise matched absent-Hero cases;
incoming Barrel with zero enemy bodies; counter available/unavailable cases;
pressure in both lanes; and cases where an additional defense is plausibly needed
despite existing defenders (low HP, wrong lane, air/ground mismatch or multiple
threats). Keep the original incoming projectiles/effects and all friendly bodies.
For candidate waste cases use the existing raw receipts and observations as
review aids. Classifying spending as beneficial or wasteful requires measured
later outcomes or independently justified labels. Body counts are insufficient.
Missing strata remain missing; no substitute cases selected after model outputs.

## Registered comparison and reporting requirements

Use the fixed R1e SHA76fdfaacbd9c2049cc88792278f06e3f73a56eaf9653791e922d9332dd6751cd,
original CPU4 environment/eval settings, tau .35, grid and affordable argmax.
Independently reproduce baseline tensors/heads/decisions exactly before any
altered-input forward. Freeze source/checkpoint hashes, byte allowlist, maximum
calls, case membership, label scope and denominator rules prospectively. No
optimizer, backward pass, new checkpoint, source alteration or deployment follows
automatically from this diagnostic.

Report paired gate-logit and p_play deltas; PLAY->WAIT/WAIT->PLAY/unchanged counts;
no-affordable cases separately; affordable card/form changes and full distributions;
forced original-card/form cell argmax and movement in tiles; and every per-case
result grouped by source match and predefined pressure stratum. Keep the original
conditioning for the aim comparison. If an altered affordable card is chosen,
derive its natural placement through a separately budgeted conditioned forward
for every such case, never by reusing another card's cell logits. Report this
natural-choice result separately from fixed-conditioning sensitivity.

Lower p_play or fewer spells is not a success criterion. Report both directions
and legitimate-pressure controls. No resource savings, tower survival, profitable
holding, Rocket/defensive-X-Bow strategy, win gain or trophy-climbing claim follows
from these input interventions. Those measurements require complete interactive
branches, every card/ability cost, subsequent pressure and counter return, both
lanes and final native outcomes. Existing final acceptance floors remain intact.
