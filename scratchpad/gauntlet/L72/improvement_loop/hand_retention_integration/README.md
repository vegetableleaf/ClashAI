# Public opponent hand and learned card retention

This owner-supervised work uses the memory reader's public board observations.
It does not use YOLO or the hidden opponent hand/deck/next-card/elixir fields.
The existing observer recognizes plays from body/spell sightings; that can miss,
merge or delay plays even though each observed object has a direct card identity.

`pipeline/opponent_hand_v2.py` provides causal estimates for revealed identities:
in hand, out of hand, unknown, and lower/upper counts of plays until return. It
normalizes consecutive genuine identical plays to Mirror under standard rules.
It does not interpret two swarm bodies or duplicate frames as two plays. Original
event-grouping limitations remain. Full estimates are always uncertified when
driven by the public board stream, including when no contradiction is detected.

The exposed160-replay regression yielded4253 correct development full estimates
out of4367 (97.39%), covering4367 of10424 queries (41.89%). The older version had
4245/4354 (97.50%). Mirror normalization adds coverage, not perfect precision.
Training was unchanged980/1008. Compare complete denominators in
mirror_replays_verified.json; unknown estimates are not counted as correct hands.

`pipeline/model_hand_belief_v2.py` is the qualified learned integration. Public
belief tokens are canonically ordered, embedded and pooled, then combined with
the existing global board representation through a learned residual. Its final
layer starts at zero so initial predictions/losses equal ordinary_v5 exactly.
Both paired arms have the same capacity; the control blanks only the added hand
information. Existing inputs already contain public history and cycle descriptors;
this explicitly represents deductions rather than granting hidden information.

There is no rule to reserve Log, Tesla or Rocket, no forbidden card action, no
holding-frequency reward, no spell priority and no changed expert label. Original
expert card, placement, PLAY/WAIT and outcome losses teach the choice. Keeping a
card can coexist with playing other cards. An immediately better action remains
available to the policy. Whether this learns profitable retention still needs
measured action/physical/gameplay evidence, not simply higher hold frequency.

Sequence preparation preserves all213995 training/54723 development rows. Separate
future-response windows describe the next opponent play within20seconds followed
by the next own play within5seconds. Future fields are audit-only and never enter
the model. Windows selected for actual later card use are strongly biased toward
retention or cycling back; they do not identify intent or optimal counters.
The verified training windows include446 Log-before-Barrel,884 Tesla-before-Hog,
468 Tesla-before-Balloon,585 Tesla-before-Royal-Hogs,94 Tesla-before-Royal-Giant,
and63 Rocket-before-Collector retained-and-subsequently-used rows. These overlap
within matches and do not establish independent successes or physical effects.

`learning/PLAN.md` and `METRICS.md` govern the fixed paired trial. Read the latest
results/review to determine its status. No qualification check alone promotes a
candidate. All original material/protection/gameplay/statistical/physical/public
acceptance requirements remain, and the overnight scheduler stays paused.

The new model has an explicit opt-in manual companion, `live_play_hand_v2.py`,
which accepts the canonical CLI arguments and requires an explicit `--ckpt`.
It substitutes the pilot only in that newly launched process. Current owner live
workers and canonical live source files are left alone. The companion logs public
hand estimates and quality flags in the decision audit. Use `--check` for offline
loading; starting a real trial remains distinct from accepted deployment.

The earlier v1 model/live companions and three failed qualification probes remain
as preserved evidence. v1 was never trained. Use the v2 integration and qualified
check_model_v4 evidence, not the older prototype. No small-set quarantined weight
is eligible for a learning parent or live policy.
