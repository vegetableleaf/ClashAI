# Completed matched public-hand learning trial

All five stages completed October6 13:35:25EDT. Preparation10.185066s,
training511.197607s, training-independent11.786247s, evaluation360.347511s,
results-independent111.251231s: all exit0/expected token. Outside evidence
review1.763518s passed. Do not repeat completed jobs or continue these weights.

Two fresh ordinary_v5 parents, identical initialized model tensors and added
capacity, matched128000 draws/mirror flags per arm,1000 finite updates each,
104 finite optimizer states each at step1000. No changed expert labels, holding
rule/reward, counter table or future/private model input. Independent verification
reconciles every original label, mask, choice, scalar/per-replay count and all
54723 predictions per arm. Log controls1positive7corruptions per arm; result
controls3positive16corruptions. Parent exposure and correlated replay rows remain.

All columns below use the SAME corrected input and original scoring. R1e here
is not the original live-input R1e. Forced aim is conditional on the expert card;
complete actions require the original gate/card/continuous <=1tile tests.

| Metric | Denominator | Corrected R1e | Ordinary v5 | Matched blind | Hand model |
|---|---:|---:|---:|---:|---:|
| Rocket forced aim |955|290|292|294|293|
| Full Rocket action |955|54|77|82|85|
| Late Rocket action |320|14|22|26|25|
| Barrel correct-lane Log |63|36|40|39|40|
| Barrel wrong-lane Log |63|20|22|22|22|
| Barrel no Log |63|7|1|2|1|
| Barrel full action |63|18|20|19|19|
| Witch action |726|332|339|357|361|
| Night Witch action |373|156|161|176|168|
| Furnace action |1174|538|549|578|570|
| Defense action |8183|3952|4011|4174|4122|
| Late-all action |6422|1949|1984|2104|2066|
| General card agreement |17192|11348|11403|11357|11211|
| All action agreement |54723|30968|31962|33236|32815|

Hand-model Rocket gains against v5: +0.104712/+0.837696/+0.937500 percentage
points for aim/full/late; against matched blind: -0.104712/+0.314136/-0.312500.
ALL original +5/+2/+2pp requirements fail against BOTH. General card falls
192/17192 versus v5 (-1.1168pp),146/17192 versus blind (-.8492pp), exceeding the
original .5pp allowed decline. Night Witch/Furnace/defense/late-all protections
also fail versus blind. Other gains cannot rescue these failures. The blind
arm is an experimental control and cannot substitute as a selected replacement.
**Hand candidate REJECTED for continuation; neither accepted nor deployed.**

| Correct action decomposition | Corrected R1e | Ordinary v5 | Matched blind | Hand model |
|---|---:|---:|---:|---:|
| PLAY (17192 labels) |2611|2602|2401|2410|
| WAIT (37531 labels) |28357|29360|30835|30405|
| Defense PLAY |366|369|357|348|
| Defense WAIT |3586|3642|3817|3774|

Hand minus v5 overall +853 = WAIT+1045/PLAY-192. Defense+111 = WAIT+132/PLAY-21.
Hand minus blind overall -421 = WAIT-430/PLAY+9; defense-52 = WAIT-43/PLAY-9.
WAIT is legitimate, but these aggregates do not establish better physical defense,
profitable holding, harmful passivity or winning strength.

Replay-paired hand-minus-control counts, better/worse/same:

| Group/metric | Versus v5 | Versus blind |
|---|---|---|
| Rocket aim |11/10/315|3/4/329|
| Rocket action |11/4/321|5/2/329|
| Late Rocket action |3/0/168|0/1/170|
| Defense action |94/27/91|17/55/140|
| Available-and-retained slice action |265/44/96|36/187/182|

The available-and-retained descriptive slice has29437 rows/405replays. Action
counts18373/18944/19761/19504; PLAY985/995/932/934; WAIT17388/17949/18829/18570.
Predicted spending of the later response card3019/2740/2363/2501. These are not
optimal-holding scores: selecting an actually later-used response card biases the
sample toward retention/cycling back, and windows overlap. All six statuses,
truncated/complete, response-card, enemy-revealed and hand-quality slices remain
in results_verified.json and ignored bench all_replay_counts/response_spending.
No hypothesis of counter intention or downstream profit was converted into a label.

Training first/last256 mean total loss: blind5.122563554/5.131362235;
hand5.123897621/5.095758447. Component means cell/card/wait/gate/value:
blind first3.006113263/.807489752/.516397567/.415193396/.377369596,
last3.038386869/.794580557/.513998432/.410838246/.373558131;
hand first3.006001724/.809628205/.516998459/.415109472/.376159719,
last3.038451370/.799372330/.515958881/.410706284/.331269569.
These sampled TRAIN losses are not fixed EVAL fit or a causal explanation.

Final checkpoint SHA256:
- blind1d81107b437b06706dfe88cd3fc8752933109e179c170c675a434d02354c8cb1
- handc5aedd869b9a8d132be51767dbb1c3aec41d6585e0ce98b1c3f10e251ff7a34a

The hand reader and model integration remain reusable engineering results. The
Mirror-aware exposed replay audit made4253/4367 exact complete development hand
estimates across10424 queries:97.39% conditional precision,41.89% coverage, not
unconditional accuracy. The old reader4245/4354 had97.50% precision. Additional
Mirror inference gave8right5wrong full estimates, not a precision improvement.
Delayed/missed/merged public sightings still require qualification. No hidden
opponent state is used to repair beliefs. Exact identity of observed memory
objects is distinct from an immediate, complete accepted-play event stream.

Final offline CLI v2 failed missing sibling hero_button import,7.849265s; preserved.
Separate live_play_hand_v3.py fixes only the import path and passes5.675248s,
exit0/LIVE_CHECK_PASS on the exact final hand checkpoint, CPU/tau.35/public audit,
anti-leakOFF and argmax card/aim. See parent LIVE_ENTRYPOINT_CORRECTION.md.
No ADB/taps/live hand-model match or simulator gameplay occurred. Original three
M1 failures remain preserved; the v2 model itself passed qualification before
training. No old failed threshold was relaxed.

One compound report delivered13:38:31EDT, stableID model-public-hand-belief-pair-final,
four HTTP200 parts, IDs1557084646729187471,1557084651334533162,
1557084653511249955,1557084655230914582. Delivery3.080620s and
closeout.257716s exit0/token. reviewed_results binds exact text/delivery/IDs,
evidence and both CLI receipts. Never resend this report. Detailed result archives
and all failed/successful sources/receipts are retained.

Next proposed work: diagnose decision differences between matched arms and qualify
public event timing/identity before a new learning recipe. Evaluate counter
retention with downstream resources, defense and outcomes, including justified
immediate spending; do not force holding or reward its frequency. No new recipe
is registered/launched by this review. All final N2-N7/statistical/physical/
component/gameplay/public/Q4/Q5 remain OPEN. STOP intact; overnight scheduler paused.
